#!/usr/bin/env python

import sys
import os
import subprocess
import time
import signal
import Logging
import shutil
import Mgmt
import Vsp
import RamFs
import shutil

#Should be replaced with actual esxi vmx file
ESXI_VMX_NAME = "esxi.vmx"

#the time interval to check if vmware-vmx is running
vmx_poll_time = 0.5

#wait time for factory reset's scrub.sh to complete before vmx wrapper to go
#down
factory_reset_wait_time=120

#location of vsp tmpDirectory for WS8
vsp_ramfs_path = "/tmp/vsp_ovhd_mem"

#vmrun directory
vmrun_path = "/opt/vmware/vmware_vil/bin/vmrun"

release_path = "/opt/vmware/vmware_vil/lib/vmware/bin/vmware-vmx"
stats_path = "/opt/vmware/vmware_vil/lib/vmware/bin/vmware-vmx-stats"
debug_path = "/opt/vmware/vmware_vil/lib/vmware/bin/vmware-vmx-debug"

option_to_path = {
    'release' : release_path,
    'stats' : stats_path,
    'debug' : debug_path
}

#Perf library path
vmperf_path = "/opt/tms/lib/libvmperf.so"

# IQN cache file path
iqn_cache_path = "/var/opt/tms/iqn_cache"

#keep track of whether we are asked to shutdown
g_shutdown_requested = False

vsp_ovhd_ramfs_min_size_mb = 20

# host shutdown commands
RUNFOR_TIMEOUT = "20"
ENABLE_SSH_COMMAND = ["/opt/tms/bin/run_for", "-t", RUNFOR_TIMEOUT, "--", \
                  "/opt/tms/variants/rvbd_ex/bin/esxi_services_management.pl", \
                  "--service", "TSM-SSH", \
                  "--operation", "start"]

DISABLE_SSH_COMMAND = ["/opt/tms/bin/run_for", "-t", RUNFOR_TIMEOUT, "--", \
                  "/opt/tms/variants/rvbd_ex/bin/esxi_services_management.pl", \
                  "--service", "TSM-SSH", \
                  "--operation", "stop"]

SAVE_STATE_COMMAND = ["/opt/tms/bin/run_for", "-t", RUNFOR_TIMEOUT, "--", \
                      "/opt/tms/variants/rvbd_ex/bin/launch_esxi_ssh.py", \
                      "--", "/sbin/auto-backup.sh", "10"]

SHUTDOWN_COMMAND = ["/opt/tms/bin/run_for", "-t", RUNFOR_TIMEOUT, "--", \
                    "/opt/vmware/vsphere_perl_sdk/bin/vicfg-hostops", \
                    "--operation", "shutdown", "--force"]

SHUTDOWN_MARKER = "/var/opt/tms/.esxi_shutting_down"
CONNECTED_MARKER = "/var/opt/tms/.esxi_connected"

pgrep_path = "/usr/bin/pgrep"
kill_path = "/bin/kill"
ovftool_wrapper_path="/opt/tms/variants/rvbd_ex/bin/ovftool_wrapper.py"

#------------------------------------------------------------------------------
def check_connectivity(env_vars):
    """!
    Run esxcli command to determine connectivity
    """

    is_connected = False

    command = ["/opt/tms/bin/run_for", "-t", RUNFOR_TIMEOUT, "--", \
               "/opt/vmware/vsphere_perl_sdk/bin/esxcli", \
               "system", "version", "get"]

    pobj = subprocess.Popen(command, env=env_vars,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    ret_code = pobj.wait()

    # If run_for timed out, there will not be a stdout to check
    if pobj.stdout:
        message = pobj.stdout.readline()
        if message.find("Product: VMware ESXi") != -1:
            is_connected = True

    return is_connected

#------------------------------------------------------------------------------
def copy_vsp_vix_logs():
    """!
        Copy the vix logs in the vmware-admin directory to
        /var/log/vmware (and make the dir if it does not exist)
    """
    vix_log_dest_dir = '/var/log/vmware'

    if not os.path.isdir(vix_log_dest_dir):
        os.makedirs(vix_log_dest_dir)

    log_dir = '%s/vmware-admin' % vsp_ramfs_path
    file_list = os.listdir(log_dir)
    for file in file_list:
        if file.endswith('.log'):
            try:
                # we'll try to copy the files, but if we can't we'll just 
                # continue and try the rest.
                shutil.copy('%s/%s' % (log_dir, file),  vix_log_dest_dir)
            except Exception as e:
                Logging.log(Logging.LOG_NOTICE, 'COPY FILE : %s' % str(e))

def shutdown_vsp_ramfs():
    """!
        Once vsp is shut down, we want to remove the vsp ramfs.  We don't want
        persistent data living in RAM.

        \return boolean True if we successfully brought down the mount, False
                        otherwise
    """
    vsp_ramfs = RamFs.RamFs(vsp_ramfs_path)
    if vsp_ramfs.is_mounted():

        # save vix logs off before we unmount.
        copy_vsp_vix_logs()

        try:
            vsp_ramfs.unmount_ramfs()
        except RamFs.RamFsCmdException as e:
            Logging.log(Logging.LOG_ERR, e.msg)
            return False

    return True
        

#---------------------------------------------------------------------------
def terminate_term_handler(signum, frame):
    """!
    Signal handler for SIGTERM and SIGINT. Whenever one of the
    signals occur, we will attempt to make the vicfg-hostops call to gracefully
    power down the host. If there is an issue with the password, we will
    immediately power down the host with vmrun stop. If the issue is connection
    related, we will not do anything and will let PM retry again (if possible)
    when the next signal is sent.
    """

    do_forceful = False

    Logging.log(Logging.LOG_DEBUG, "Wrapper: got TERM signal")

    # We used to open and close the session in main(). However, if mgmtd
    # crashes and is restarted by PM, the session we created will not be
    # stale and any queries will fail miserably. To mitigate this issue,
    # we'll open and close the session as tightly as possible
    Mgmt.open()

    env_vars = Vsp.make_vicfg_env_vars()
    Logging.log(Logging.LOG_DEBUG, "Wrapper env: %s" % env_vars)

    Mgmt.close()

    # Send signal to active VM migration task so it can clean up
    stop_migrate_deploy()

    if env_vars == None or not os.path.exists(CONNECTED_MARKER):
        Logging.log(Logging.LOG_NOTICE,
                  "Cannot get password or currently disconnected from ESXi")
        do_forceful = True

    # Do one last check for connectivity just in case the watchdog
    # says we are connected when really we are not due to a change of
    # IP or password on the ESXi side (but our sessionfile is still valid)
    # XXX/rcenteno Enhance with the session file
    if not do_forceful and not check_connectivity(env_vars):
        Logging.log(Logging.LOG_NOTICE, "ESXi connectivity not found")
        do_forceful = True


    if do_forceful:
        Logging.log(Logging.LOG_NOTICE, "Performing forceful power off")
        # We cannot get the ESXi password or cannot connect to ESXi,
        # so we must forcibly power down
        stop_vmware_vmx();

    else:
        global g_shutdown_requested

        # update IQN cache value
        iqn = Vsp.get_iqn(env_vars, RUNFOR_TIMEOUT)

        if iqn:
            try:
                iqn_cache = open(iqn_cache_path, 'w')
                iqn_cache.write(iqn)
                iqn_cache.close()
            except Exception as e:
                Logging.log(Logging.LOG_ERR,
                    "Exception while updating IQN cache file")

        # Create the shutdown marker that the hpn will use to know it should
        # wait for ESXi shutdown first
        open(SHUTDOWN_MARKER, 'w').close()

        # Enable SSH on the host
        pobj = subprocess.Popen(ENABLE_SSH_COMMAND, env=env_vars,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ret_code = pobj.wait()

        if ret_code == 0:
            # Save the state on the host
            pobj = subprocess.Popen(SAVE_STATE_COMMAND, env=env_vars,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            ret_code = pobj.wait()

            if ret_code == 0:
                Logging.log(Logging.LOG_INFO, "Saved state on the host")

            # Disable SSH on the host
            pobj = subprocess.Popen(DISABLE_SSH_COMMAND, env=env_vars,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            ret_code = pobj.wait()

        # Regardless of what happened earlier, send the host operations command
        Logging.log(Logging.LOG_INFO, "ESXi graceful shutdown in progress")
        pobj = subprocess.Popen(SHUTDOWN_COMMAND, env=env_vars,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ret_code = pobj.wait()

        if ret_code == 0:
            g_shutdown_requested = True

        # the command timed out
        elif ret_code == 99:
            Logging.log(Logging.LOG_INFO,
                        "Timed out trying to send graceful shutdown request")

#---------------------------------------------------------------------------
def terminate_quit_handler(signum, frame):
    """!
    Signal handler for SIGQUIT. Whenever one of the
    signals occur, the vmrun stop is called to stop the vm
    """

    stop_vmware_vmx();

#---------------------------------------------------------------------------
def terminate_usr1_handler(signum, frame):
    """!
    Signal handler for SIGUSR1. Used by RiOS factory reset feature to quickly
    bring down vmx wrapper (via vmrun stop). It sleeps for
    'factory_reset_wait_time' seconds so scrub.sh can remove the vmdks used by
    vmx wrapper and other releveant files without PM automatically bringing the
    wrapper back up.
    """
    Logging.log(Logging.LOG_DEBUG, "Wrapper: got USR1 signal")

    stop_vmware_vmx()
    time.sleep(factory_reset_wait_time)
    Logging.log(Logging.LOG_DEBUG, "Wrapper: End USR1 handler")

#---------------------------------------------------------------------------
def monitor_vmware_vmx(proc_id):
    """!
    Monitor vmware-vmx every 0.5 seconds to see
    if it is running
    """
    
    while Vsp.is_process_running(proc_id):
        Logging.log(Logging.LOG_DEBUG, "vmware-vmx is running")   
        time.sleep(vmx_poll_time)
    
    #We are here means the process has exited   
    Logging.log(Logging.LOG_DEBUG, "vmware-vmx is not running") 

    # whenever vmware-vmx stops we want to unmount the ramfs
    # also before unmounting we want to save off the vix logs
    # in the vmware-admin directory
    shutdown_vsp_ramfs()

    # Clean up the "shutting down" file used for ESXi HPN dependency
    if os.path.exists(SHUTDOWN_MARKER):
        os.remove(SHUTDOWN_MARKER)

    if not g_shutdown_requested:
        sys.exit(1)  
   
    
#---------------------------------------------------------------------------
def start_vmware_vmx(path):
    """!
    Start vmware-vmx with given vm
    """
    
    Logging.log(Logging.LOG_INFO, "Starting vm %s" % path)

    vsp_ramfs = RamFs.RamFs(vsp_ramfs_path)
    if vsp_ramfs.is_mounted():
        # we generally should not hit this path, we unmount the ramfs when 
        # we stop vmware-vmx
        Logging.log(Logging.LOG_INFO, 
                    "VSP ramfs is already mounted %s, unmounting" % \
                    vsp_ramfs_path)
        try:
            vsp_ramfs.unmount_ramfs()
        except RamFs.RamFsCmdException as e:
            # we'll proceed with starting vmx even if we can't unmount
            Logging.log(Logging.LOG_ERR, e.msg)

    if not vsp_ramfs.is_mounted():
        try:
            vsp_ramfs.mount_ramfs(vsp_ovhd_ramfs_min_size_mb)
        except (OSError, RamFs.RamFsCmdException) as e:
            Logging.log(Logging.LOG_ERR, str(e))
            Logging.log(Logging.LOG_ERR, 
                        "Unable to create ramfs %s" \
                        " not starting VMX" % vsp_ramfs_path)
            # skip starting VMX, the caller will look for vmx status
            return
            
    
    # Link in performance tweaks library
    env_dict = os.environ.copy()
    Mgmt.open()
    
    if Vsp.is_memlock_enabled():
        if env_dict.has_key("LD_PRELOAD"):
            env_dict["LD_PRELOAD"] = vmperf_path + " " + env_dict["LD_PRELOAD"]
        else:
            env_dict["LD_PRELOAD"] = vmperf_path

    # Check the ESXi debug option to see which binary we need to run
    vmx_option = get_debug_option()
    Mgmt.close()

    binary_path = option_to_path[vmx_option]
    Logging.log(Logging.LOG_DEBUG, "BINARY PATH: %s" % binary_path)

    pobj = subprocess.Popen([binary_path, "-qx", path], env = env_dict)
    pobj.wait()
    
#---------------------------------------------------------------------------   
def stop_vmware_vmx():
    """!
    Stop vmware-vmx.
    """
    global g_shutdown_requested
    #We just use vmrun stop to terminate vm right now but this
    #will change when we handle graceful shutdown

    path = "%s/%s" % (Vsp.get_esxi_dir(), ESXI_VMX_NAME)

    Logging.log(Logging.LOG_INFO, "Stopping vm %s" % path)
    pobj = subprocess.Popen([vmrun_path, "stop", "%s" % path])
    pobj.wait()

    g_shutdown_requested = True;
    
#---------------------------------------------------------------------------   
def cleanup_locks(esxi_root):
    """!
    Removes the lck files
    """

    #XXX:We might need to check if vmware-mount is running
    for dir in os.listdir(esxi_root):
        if dir.endswith(".lck"):
            Logging.log(Logging.LOG_INFO, "Removing stale locks in %s" % dir)
            shutil.rmtree("%s/%s" % (esxi_root, dir))

#---------------------------------------------------------------------------
def get_debug_option():
    """!
    Note: requires an existing Mgmt connection
    Returns either "release", "debug", "stats"
    """

    node_name = "/rbt/vsp/config/esxi/vmx/debug_option"

    ret_option = "release"

    option = Mgmt.get_value(node_name)

    # If somehow the node does not exist, we'll assume the release binary
    if option:
        ret_option = option

    return ret_option

#---------------------------------------------------------------------------
def stop_migrate_deploy():
    """!
    Stop any active migrate deploy tasks if any
    """
    Logging.log(Logging.LOG_INFO, "Stopping active VM migration task")

    #import pdb; pdb.set_trace()

    pobj = subprocess.Popen([pgrep_path, "-f", "%s" % ovftool_wrapper_path],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    pobj.wait()

    if pobj.returncode != 0:
        Logging.log(Logging.LOG_DEBUG,
                    'No active VM migration task found. Not stopping '
                    'VM migration')
        return
    else:
        output = pobj.communicate()[0].strip()

        if output.find("\n") != -1:
            Logging.log(Logging.LOG_INFO,
                        'Unexpectedly found more than one VM migration tasks. '
                        'Not stopping VM migration')
            return
        elif not output.isdigit():
            Logging.log(Logging.LOG_INFO,
                        'Found unexpected pid format for VM migration task. '
                        'Not stopping VM migration')
            return
        else:
            ovftool_pid = int(output)

            pobj = subprocess.Popen([kill_path, "-SIGINT", "%d" % ovftool_pid],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            pobj.wait()

            Logging.log(Logging.LOG_INFO,
                        'Stopped VM migration task exited with code %d.' %
                        pobj.returncode)
            return
    return



#---------------------------------------------------------------------------       
def main():
    """!
    Entry point of the wrapper, intialize logger and signal handler. Starts
    vmware-vmx and starts monitoring it 
    """
    
    Logging.log_init('vmware_vmx_wrapper', 'vmware_vmx_wrapper', 0,
                     Logging.component_id(Logging.LCI_VSP), Logging.LOG_DEBUG,
                     Logging.LOG_LOCAL0, Logging.LCT_SYSLOG)
     
    Logging.log(Logging.LOG_INFO, 
                "vsp_vmware_vmx_wrapper started")
    
    signal.signal(signal.SIGINT, terminate_term_handler)
    signal.signal(signal.SIGTERM, terminate_term_handler)
    signal.signal(signal.SIGQUIT, terminate_quit_handler)
    signal.signal(signal.SIGUSR1, terminate_usr1_handler)
    
    #get the esxi dir
    esxi_dir = Vsp.get_esxi_dir()
    
    vmx_conf_file_path = "%s/%s" %(esxi_dir, ESXI_VMX_NAME)
      
    #Check if the vm configuration exists
    if not os.path.exists(vmx_conf_file_path): 
        Logging.log(Logging.LOG_ERR, 
                    "VM configuration %s doesn't exist" % vmx_conf_file_path)
        sys.exit(1)

    # Check if vmware-vmx is already running. The fuction returns None if no
    # process_id exists or if there's multiple process_ids associated with
    # the vmx_conf. However, it's not possible to launch two running vmware_vmx
    # using the same vmx_conf. The chance this returns None b/c of multiple
    # process ids is almost nonexistant. 
    proc_id = Vsp.get_vmx_proc_id(vmx_conf_file_path)

    #Start vmware-vmx if an instance has not been started
    if proc_id == None:

        # Clean up the "shutting down" file used for ESXi HPN dependency
        if os.path.exists(SHUTDOWN_MARKER):
            os.remove(SHUTDOWN_MARKER)
        cleanup_locks(esxi_dir)
        start_vmware_vmx(vmx_conf_file_path)

    #Get the new process id
    proc_id = Vsp.get_vmx_proc_id(vmx_conf_file_path)

    monitor_vmware_vmx(proc_id)
    

#---------------------------------------------------------------------------            
if __name__ == "__main__":
    main()
    
