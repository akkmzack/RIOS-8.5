#!/usr/bin/env python

import os
import subprocess
import Logging
import signal
import Mgmt
import sys
import time
import Vsp
from common import decrypt_scrypt

#session file
SESSION_FILE = "/tmp/esxi_session"
# esxcli command
RUN_FOR_TIMEOUT = "10"

#amount of time to wait for ESXi to stabilize
#after connection is successful
ESXI_STABILIZATION_TIME = 30

# Mgmt events
DISCONNECTED_EVENT = "/rbt/vsp/event/esxi/disconnected"
READY_EVENT = "/rbt/vsp/event/esxi/ready"

g_shutdown_requested = False

REASONS_DICT = {
    "invalid ESXi password" : "incorrect user name or password",
    "disconnected": "Connection failure",
    "invalid session": "The session is not authenticated",
    "lockdown mode": "Permission to perform this operation was denied",
    None: "Product: VMware ESXi"
    }

g_disconnected_reasons = [
    "invalid ESXi password",
    "disconnected",
    "lockdown mode"
    ]

SHUTDOWN_MARKER = "/var/opt/tms/.esxi_shutting_down"
CONNECTED_MARKER = "/var/opt/tms/.esxi_connected"

# attempt ESXi connection rate
POLL_RATE=10

# global counter to retry for 20 minutes (120 times) before sending a 
# disconnect event after startup
g_disconnect_retry_count = 1
MAX_INITIAL_CONNECT_RETRY_COUNT=(20*60)/POLL_RATE

# global counter to track the event resent
# Bug 111270: If mgmtd is killed due to some reason (oomed / crashed) 
# but vmware-vmx process keeps running; 
# on recovery of mgmt vsp is stuck in initializing. Modify watchdog to send
# periodic events.
#
# Wish python had enum datatypes
class WdtStates:
    INITIAL='1'
    DISCONNECTED='2'
    CONNECTED='3'

    def __init__(self, Type):
        self.value = Type
    def __str__(self):
        if self.value == WdtStates.INITIAL:
            return 'initial'
        if self.value == WdtStates.DISCONNECTED:
            return 'disconnected'
        if self.value == WdtStates.CONNECTED:
            return 'connected'

g_curr_wdt_state = None
g_event_resend_counter = 1
EVENT_RESEND_TIMEOUT = 30


# global variable to keep track if within disconnected state, reason for no 
# connection to ESXi has changed or not.
g_reason = None

# global variable to track mgmtd pid
g_mgmtd_pid = None
MGMTD_SETTLE_TIMEOUT = 0.1
MAX_MGMTD_SETTLE_RETRY = 5 # give it 5*.1 seconds to settle down

#------------------------------------------------------------------------------
def test_esxi_shutdown_in_progress():
    # The watchdog will wait for ESXi to go down fully if a shutdown is in
    # progress. Otherwise we should just let it go down immediately.

    return os.path.exists(SHUTDOWN_MARKER)

#------------------------------------------------------------------------------
def wait_for_vmware_vmx():
    """!
    Monitor vmware-vmx every 5 seconds to see if it is running
    """
    vmx_conf_file_path = "%s/esxi.vmx" % Vsp.get_esxi_dir()

    proc_id = Vsp.get_vmx_proc_id(vmx_conf_file_path)

    while Vsp.is_process_running(proc_id):
        Logging.log(Logging.LOG_DEBUG, "vmware-vmx is still running")
        time.sleep(5)

    #We are here means the process has exited
    Logging.log(Logging.LOG_DEBUG, "vmware-vmx is not running")

#------------------------------------------------------------------------------
def mark_esxi_connected():
    """!
    Add the marker that the wrapper script will use to know if we are
    connected to ESXi. We cannot use the available monitor node since it will
    be set to false even though we may still be connected.
    """

    if not os.path.exists(CONNECTED_MARKER):
        open(CONNECTED_MARKER, 'w').close()

#------------------------------------------------------------------------------
def mark_esxi_disconnected():
    """!
    Remove the marker that the wrapper script will use to know if we are
    connected to ESXi. We cannot use the available topr_monitor node since it will
    be set to false even though we may still be connected.
    """

    if os.path.exists(CONNECTED_MARKER):
        os.remove(CONNECTED_MARKER)

#------------------------------------------------------------------------------
def monitor_esxi():
    """!
    Periodically sees if the esxcli command can communicate with ESXi. If not,
    send mgmtd appropriate events
    """
    global g_curr_wdt_state
    first_connection = False

    command = ["/opt/tms/bin/run_for", "-t", RUN_FOR_TIMEOUT, "-q", "--", \
               "/opt/vmware/vsphere_perl_sdk/bin/esxcli", \
                "--savesessionfile=%s" % SESSION_FILE, \
                "system", "version", "get"]
    command_using_session = ["/opt/tms/bin/run_for", "-t", RUN_FOR_TIMEOUT, "-q", "--", \
               "/opt/vmware/vsphere_perl_sdk/bin/esxcli", \
               "--sessionfile=%s" % SESSION_FILE, \
               "system", "version", "get"]

    version_info="unknown"
    g_curr_wdt_state = WdtStates.INITIAL

    while not g_shutdown_requested:
        curr_reason = None
        #if session file exists try connecting using it
        if os.path.exists(SESSION_FILE):
            Logging.log(Logging.LOG_DEBUG, "Trying to connect using session file")
            (curr_reason, version_info) = run_esxcli_command(command_using_session, True)
            if curr_reason == "invalid session":
                Logging.log(Logging.LOG_DEBUG, 
                    "Invalid Session.Trying to connect without using session file")
                #something went wrong try connecting without using session 
                (curr_reason, version_info) = run_esxcli_command(command, False)
        else:
            Logging.log(Logging.LOG_DEBUG, 
                "Session not created yet. Connecting using username and password")
            (curr_reason, version_info) = run_esxcli_command(command, False)
        
        #If we are able to connect the first time, wait 30 seconds 
        # for esxi to stabilize
        if not first_connection and not curr_reason:
            time.sleep(ESXI_STABILIZATION_TIME)
            first_connection = True
        else:
            event(curr_reason, version_info)
            
        time.sleep(POLL_RATE)

#------------------------------------------------------------------------------
def run_esxcli_command(command, use_session):
    """!
    Run esxcli command to determine connectivity
    """
    version="unknown"
    build="unknown"
    version_info = "unknown"
    curr_reason = None
    env_vars = None

    if use_session == False:
        env_vars = Vsp.make_esxcli_env_vars()
        if env_vars == None:
            curr_reason = "invalid ESXi password"
            return (curr_reason, version_info)

    pobj = subprocess.Popen(command, env=env_vars, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    ret_code = pobj.wait()
        
    if ret_code == 99:
        Logging.log(Logging.LOG_INFO, "Watchdog timed out connecting to ESXi")
        curr_reason = "disconnected"
    
    # run_for will return 99 if timed out. Otherwise, check stdout
    if pobj.stdout:
        error_message = pobj.stdout.readline()
        for (reason, message) in REASONS_DICT.iteritems():
            if error_message.find(message) != -1:
                curr_reason = reason
    # if we can sucessfully get the version
    # extract Version and Build information from stdout:
    # Product: VMware ESXi
    # Version: major-ver.minor-ver.maintenance-ver
    # Build: build#
    if not curr_reason:
        for line in pobj.stdout:
            if line.rstrip().find("Version") != -1:
                version_str = line.rstrip().split()
                version = version_str[1]
            if line.rstrip().find("Build") != -1:
                build_str = line.rstrip().split()
                build = build_str[1].replace('Releasebuild-', '')
        version_info = version + "." + build
    
    return (curr_reason, version_info)

#------------------------------------------------------------------------------
def generate_mgmt_event(event, reason, version_info):
    """!
    Generate Mgmt event.
    """
    binding_to_send = None

    if event == READY_EVENT:
        binding_to_send = ("version_info", "string", version_info) 
    elif event == DISCONNECTED_EVENT:
        binding_to_send = ("reason", "string", reason)
    else:
        Logging.log(Logging.LOG_ERR, "Unknown event")
        # suicide!
        sys.exit()

    Mgmt.event(event, binding_to_send)
          
#------------------------------------------------------------------------------
def set_state(new_state, reason, version_info):
    """!
    Perform required operation and transition current watchdog 
    state to new state
    """
    global g_curr_wdt_state
    global g_event_resend_counter

    if new_state == WdtStates.CONNECTED:
        mark_esxi_connected()
        Logging.log(Logging.LOG_INFO, "ESXi Connection Established")

        generate_mgmt_event(READY_EVENT, reason, version_info)
    elif new_state == WdtStates.DISCONNECTED:
        mark_esxi_disconnected()
        log_reason_fmt = "Cannot connect to ESXi: %s failed"
        if reason == "invalid ESXi password":
            log_reason = log_reason_fmt % "password"
        else:
            log_reason = log_reason_fmt % "connection"
        Logging.log(Logging.LOG_INFO, log_reason)

        generate_mgmt_event(DISCONNECTED_EVENT, reason, version_info)

    msg = "set_state from: '%s', to: '%s'"  \
        % (WdtStates(g_curr_wdt_state), WdtStates(new_state))
    Logging.log(Logging.LOG_INFO, msg)

    g_curr_wdt_state = new_state

    # event send, reset the event resend counter
    g_event_resend_counter = 1

#------------------------------------------------------------------------------
def initial_state_handler(reason, version_info):
    """!
    After startup, wdt waits to get connected to ESXi. If wait timer times out
    it sets the state to disconnected and transitions to disconnected state.
    If wdt gets response in the meantime, it changes state as per esxcli 
    command response.
    """
    global g_disconnect_retry_count
    global g_reason
    
    new_wdt_state = g_curr_wdt_state

    # During startup ESXi connection cannot be established.
    # Loop till initial timer expires before sending disconnected event.
    # If state changes occurs, take necessary actions.
    if reason == "disconnected":
        if g_disconnect_retry_count < MAX_INITIAL_CONNECT_RETRY_COUNT:
            g_disconnect_retry_count += 1
            Logging.log(Logging.LOG_INFO, 
                "No connection to ESXi after startup. Retrying.")
        else:
            Logging.log(Logging.LOG_ERR, 
                "Cannot connect to ESXi: Connection failure after startup")
            new_wdt_state = WdtStates.DISCONNECTED
            g_reason = reason
    elif reason == "invalid ESXi password":
        new_wdt_state = WdtStates.DISCONNECTED
        g_reason = reason
    elif reason == "lockdown mode":
        new_wdt_state = WdtStates.DISCONNECTED
        g_reason = reason
    elif not reason:
        # connection established
        new_wdt_state = WdtStates.CONNECTED

    return new_wdt_state

#------------------------------------------------------------------------------
def disconnected_state_handler(reason, version_info):
    """!
    Handles transition of trigger event when wdt is in disconnected state.
    """
    global g_reason
    global g_event_resend_counter

    new_wdt_state = g_curr_wdt_state

    if not reason:
        # connection established
        new_wdt_state = WdtStates.CONNECTED
        g_reason = None
    elif reason != g_reason:
        # dsconnect reason changed, re-send disconnected event
        generate_mgmt_event(DISCONNECTED_EVENT, reason, version_info)
        g_reason = reason
        g_event_resend_counter = 1

    return new_wdt_state

#------------------------------------------------------------------------------
def connected_state_handler(reason, version_info):
    """!
    Handles transition of trigger event when wdt is in disconnected state.
    """
    global g_reason
    
    new_wdt_state = g_curr_wdt_state

    # are we still connected to ESXi?
    if reason in g_disconnected_reasons:
        new_wdt_state = WdtStates.DISCONNECTED
        g_reason = reason
    
    return new_wdt_state


#------------------------------------------------------------------------------
def check_resend_event(reason, version_info):
    """!
    Handle the case if wdt needs to send periodic event
    """
    global g_event_resend_counter

    # resend event if wdt not in initial state and timer has expired
    if g_curr_wdt_state != WdtStates.INITIAL and \
       (g_event_resend_counter >= EVENT_RESEND_TIMEOUT):
        if reason in g_disconnected_reasons:
            Logging.log(Logging.LOG_INFO, "Resending disconnected event.")
            generate_mgmt_event(DISCONNECTED_EVENT, reason, version_info)
        elif version_info.find("unknown") == -1:
            Logging.log(Logging.LOG_INFO, "Resending ready event.")
            generate_mgmt_event(READY_EVENT, reason, version_info)
        # event resend, reset the counter
        g_event_resend_counter = 1
    else:
        g_event_resend_counter += 1

#------------------------------------------------------------------------------
# map state to their handler routines
STATE_HANDLER_DICT= {
    WdtStates.INITIAL : initial_state_handler,
    WdtStates.DISCONNECTED : disconnected_state_handler,
    WdtStates.CONNECTED : connected_state_handler,
    }

#------------------------------------------------------------------------------
def event(reason, version_info):
    """!
    State machine event loop. The three possible states are:
    1. initial 
    2. disconnected
    3. connected
                                               
    The graphical FSM may look like:           ___ 
                                              |   |(resend_event)
                                           ___|___|________
    ____________     init_connect_timeout  |              |
    |          | ------------------------->| disconnected |
    | initial  |-------------------------->|______________|
    |__________|   (wdt_trigger)            |          |
              |                             |          | (wdt_trigger)   
              |               (wdt_trigger) |          |
              |                            _|__________|__
              |       wdt_connect          |             |
              |--------------------------->| connected   |    
                                           |_____________|
                                                |   |
                                                |___|  (resend_event)
    """
    global g_curr_wdt_state

    mgmtd_pids = []

    old_wdt_state = g_curr_wdt_state
    new_wdt_state = None
    
    mgmtd_pids = Vsp.get_pids('mgmtd')
    if mgmtd_pids == None or g_mgmtd_pid not in mgmtd_pids:
        Logging.log(Logging.LOG_ERR, "Unexpected termination of mgmtd, kill watchdog!")
        sys.exit()

    # 
    # wish python had switch statement, that would make it more pretty.
    #
    # Based on the current state, call appropriate state handler function,
    # this function based on given input check if state needs to be changed,
    # if yes, then would take required action as well (send event).

    if g_curr_wdt_state in STATE_HANDLER_DICT.keys():
        new_wdt_state = \
            STATE_HANDLER_DICT[g_curr_wdt_state](reason, version_info)
    else:
        # unknown state detected, KILL ME !!!!
        error_str = "Unknown state: %s, reset to initial" % g_curr_wdt_state
        Logging.log(Logging.LOG_ERR, error_str)
        sys.exit()
    
    if old_wdt_state != new_wdt_state:
        set_state(new_wdt_state, reason, version_info)
    else:
        # No state change detected. Verify if we need to resend event.
        check_resend_event(reason, version_info)

#------------------------------------------------------------------------------
def terminate_handler(signum, frame):
    """!
    Signal handler for SIGTERM, SIGQUIT, and SIGINT
    """

    if test_esxi_shutdown_in_progress():
        wait_for_vmware_vmx()

    global g_shutdown_requested
    g_shutdown_requested = True
    mark_esxi_disconnected()

#------------------------------------------------------------------------------
def main():
    """!
    Entry point to the watchdog. Initialize logger and starts attempting to
    communicate with ESXi
    """
    global g_mgmtd_pid

    g_mgmtd_pid = None

    mgmtd_pids = []

    Logging.log_init('esxi_watchdog', 'esxi_watchdog', 0,
                     Logging.component_id(Logging.LCI_VSP), Logging.LOG_DEBUG,
                     Logging.LOG_LOCAL0, Logging.LCT_SYSLOG)

    Logging.log(Logging.LOG_INFO, "esxi watchdog started")

    # Bug 117274: It may happen that we get multiple pids for mgmtd process,
    # pidof ran between fork-exec call, retry to allow mgmtd to settle
    for i in range(1, MAX_MGMTD_SETTLE_RETRY):
        mgmtd_pids = Vsp.get_pids('mgmtd')
        if len(mgmtd_pids) > 1:
            # multiple pids detected, give mgmtd sometime to settle
            time.sleep(MGMTD_SETTLE_TIMEOUT)
        else:
            g_mgmtd_pid = mgmtd_pids[0]
            break

    # Bug 112192: monitor mgmtd pid, if mgmtd crashes/exits
    # terminate watchdog as well
    if g_mgmtd_pid == None:
        # mgmtd not up kill watchdog process
        Logging.log(Logging.LOG_ERR, "Mgmtd is not ready, kill watchdog!")
        sys.exit();

    Mgmt.open()
    signal.signal(signal.SIGINT, terminate_handler)
    signal.signal(signal.SIGTERM, terminate_handler)
    signal.signal(signal.SIGQUIT, terminate_handler)

    # Invalidate the session file if it exists on startup
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)

    monitor_esxi()
    Mgmt.close()

#------------------------------------------------------------------------------
if __name__ == "__main__":
    main()

