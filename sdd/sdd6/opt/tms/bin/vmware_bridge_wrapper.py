#!/usr/bin/python
import os
import sys
import errno
import Logging
import signal
import re

VmwareDb = {}
VmDbFile = "/etc/vmware/locations"

# Interfaces that we want bridged 
BridgedInterfaces = ['aux', 'primary']

# build_vmware_db
#
# VMware stores install locations in a flat text file
# on disk. Parse this to get bin and lib locations.

def build_vmware_db():
    global VmwareDb

    if (os.path.exists(VmDbFile)):
        db = open(VmDbFile, 'r')

        for line in db:
            list = line.split()
            if list[0] == "answer":
                VmwareDb[list[1]]=list[2]
    else:
        Logging.log(Logging.LOG_ERR, "Unable to open VMware's location file.")    
        fatal_error("Unable to open %s - is VMware installed?." % VmDbFile)

def fatal_error(str):
    Logging.log(Logging.LOG_ERR, str)
    print str
    sys.exit(1)

# handle_down_signal
#
# Very simple handler which terminates all bridging processes
# and then exits the script.

def handle_down_signal(signum, frame):
    os.system("killall -TERM -q vmnet-bridge")
    sys.exit(0)

def set_up_signal_handlers():
    signal.signal(signal.SIGTERM, handle_down_signal)
    signal.signal(signal.SIGQUIT, handle_down_signal)
    signal.signal(signal.SIGINT, handle_down_signal)

# launch_process
#
# Start a given process at a desired nice level. Don't wait for it to 
# return.

def launch_process(command_list, nice_val):
    os.nice(nice_val)
    normal_return_flag = False

    return os.spawnvp(os.P_NOWAIT, command_list[0], command_list)

def shutdown_process(pid):
    # Send SIGTERM to this VMware process
    os.kill(pid, signal.SIGTERM)

def enable_vmware_bridging():
    # For each interface find the vmnet to which it is bridged,
    # and call the bridging software.

    for i in BridgedInterfaces:
        for k,v in VmwareDb.iteritems():
            if ( v == i ):
                # Make sure that it is of VNET_x_INTERFACE form.
                s = k.split('_')
                if ((s[0] == 'VNET') & (s[2] == 'INTERFACE')):
                    command_list = [VmwareDb['BINDIR'] + "/vmnet-bridge",
                                    "-d", "/var/run/vmnet-bridge-" + s[1] + ".pid", 
                                    "-n", s[1],
                                    "-i", i]
                    Logging.log(Logging.LOG_INFO, "Bridging %s and %s" % (k, i))
                    pid = launch_process(command_list, 10)
                    os.waitpid(pid, 0)

def main(argv = sys.argv):
    Logging.log_init('rsp2_bridge_wrapper', 'rsp2_bridge_wrapper', 0,
                     Logging.component_id(Logging.LCI_RSP), Logging.LOG_DEBUG,
                     Logging.LOG_LOCAL0, Logging.LCT_SYSLOG)

    build_vmware_db()
    set_up_signal_handlers()

    enable_vmware_bridging()

    # Spin waiting for signals.
    while (True):
        signal.pause()

if __name__ == "__main__":
    main()

