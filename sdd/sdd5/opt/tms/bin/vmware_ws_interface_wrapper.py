#!/usr/bin/env python
import os, time
import sys
import getopt
import subprocess
import errno
import Logging
import signal
import re
import Vsp
import Mgmt

# Interfaces that we want bridged 
bridgeInterfaces = ['aux', 'primary']
hostOnlyInterfaces = ["hpn", "hpn3"]

# XXX/we need to kill this and upgrade the pm nodes since we now know
# how to name interfaces something other than vmnetX
interfaceMappingVmnet = {
    'hpn' : 'vmlocal',
    'primary' : 'vmpri',
    'aux' : 'vmaux',
    'hpn3'  :   'vmnet3'
}

interfaceToDeviceMapping = {
    'hpn' : '/dev/vmnet0',
    'primary' : '/dev/vmnet1',
    'aux' : '/dev/vmnet2',
    'hpn3' : '/dev/vmnet3'
}

printToStd = False
vmwareBasePath = "/opt/vmware/vmware_vil/"
graniteHpnIp = "169.254.200.1"
hpnNetmask = "255.255.255.0"

shutdown_marker = "/var/opt/tms/.esxi_shutting_down"

vmnetReadyEvent = "/rbt/vsp/event/vmnet/ready"
vmnetDeleteEvent = "/rbt/vsp/event/vmnet/deleted"

def fatalError(str):
    Logging.log(Logging.LOG_ERR, str)
    if printToStd:
        print str
    sys.exit(1)

#------------------------------------------------------------------------------

def testEsxiShutdownInProgress():
    # The interfaces will wait for ESXi to go down fully if a shutdown is in
    # progress. Otherwise we should just let the interface go down immediately.

    if os.path.exists(shutdown_marker):
        return True
    else:
        return False

#------------------------------------------------------------------------------

def waitForVmwareVmx():
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

class VmwareWsInterface(object):
    def __init__(self, interfaceName):
        self.interfaceName = interfaceName
        self.vmnetReal = interfaceMappingVmnet[self.interfaceName]
        self.watchdogSleepSec = 1
        self.sig_quit_count = 0

    def launchProcess(self, commandList):
        return subprocess.Popen(commandList).pid

    def launchProcessAndWait(self, commandList,
                             logLevel = Logging.LOG_ERR):
        processAndWait = subprocess.Popen(commandList,
                 stdout=subprocess.PIPE,
                 stderr=subprocess.PIPE)
        output, errmsg = processAndWait.communicate()
        if processAndWait.returncode != 0:
            Logging.log(logLevel,
                        "Launch process '%s' with error(%s):%s" % (
                         ' '.join(commandList),
                         processAndWait.returncode,
                         errmsg))
        return (processAndWait.returncode, output, errmsg)

    def shutdownProcess(self, pid, sig = signal.SIGTERM):
    # Send SIGTERM to this VMware process
        Logging.log(Logging.LOG_DEBUG,
                    "Shutdown process id %s with signal %s" % (pid, sig))
        if not pid is None:
            os.kill(pid, sig)

    def pid_is_running(self, pid):
    # There are three cases when call os.kill(pid, 0):
    # 1. If the process exists and belongs to you, the call succeeds
    # 2. If the process exists but belong to another user,
    #    it throws an OSError with the errno attribute set to errno.EPERM.
    # 3. If the process does not exist, it throws an OSError 
    #    with the errno attribute set to errno.ESRCH.
        try:
            os.kill(pid, 0)
        except OSError as err:
            if err.errno == errno.ESRCH:
                return False
        return True

    def getLivePids(self, keywords):
        cmd = "ps -e -o pid= -o args= --no-heading"
        for keyword in keywords:
            cmd = "%s | grep '%s'" % (cmd, keyword)
        cmd = "%s | grep -v grep" % cmd
        process = subprocess.Popen(
               cmd, bufsize=-1, shell=True, stdout=subprocess.PIPE)
        output = process.stdout.read()
        process.stdout.close()
        process.wait()
        pids = []
        # Output of this command will be "PID arguments"
        for line in output.split("\n"):
            segs = re.findall("^\s*(\d+)\s+(.*)", line)
            if segs:
                pid = int(segs[0][0])
                wildargs = segs[0][1]
                pids.append(pid)
        return pids

    def isMgmtdRunning(self):
        pids = self.getLivePids("/opt/tms/bin/mgmtd")
        cmd = "pidof /opt/tms/bin/mgmtd | wc -w"
        process = subprocess.Popen(
               cmd, bufsize=-1, shell=True, stdout=subprocess.PIPE)
        output = process.stdout.read()
        process.stdout.close()
        process.wait()
        return int(output)

class VmwareNetifupInterface(VmwareWsInterface):
    def __init__(self, interfaceName, ipaddr = None, netmask = None,
                 mtu = None):
        super(VmwareNetifupInterface, self).__init__(interfaceName)
        self.vmnetDev = interfaceToDeviceMapping[self.interfaceName]
        self.vmnetNetIfUpCmd = vmwareBasePath + "bin/vmnet-netifup"
        self.ipaddr = ipaddr
        self.netmask = netmask
        self.netifupProcess = None
        self.sleepIntervalBeforeBringup = 0.05
        self.sleepMaxBeforeBringup = 100
        self.pid = None
        self.mtu = mtu

    def getLiveNetifupPids(self):
        return self.getLivePids(["%s " % self.vmnetDev,
                                 self.vmnetNetIfUpCmd])

    def shutdownNetifupProcesses(self, sig = signal.SIGTERM):
        pids = self.getLiveNetifupPids()

        for pid in pids:
            self.shutdownProcess(pid, sig)

    def cleanWildNetifups(self):
        self.shutdownNetifupProcesses()

    def isNetifupRunning(self):
        pids = self.getLiveNetifupPids()
        return (len(pids) > 0)

    def bringDownInterface(self):
        if self.isNetifupRunning():
            commandList = ["/sbin/ifconfig", self.vmnetReal, "down"]
            self.launchProcessAndWait(commandList)

    def sendVmnetReadyEvent(self):
        if self.isMgmtdRunning():
            Logging.log(Logging.LOG_INFO, "Mgmtd is running!")
            self.sendVmnetEvent(vmnetReadyEvent)
        else:
            Logging.log(Logging.LOG_INFO, "Mgmtd is not running!")

    def sendVmnetDeleteEvent(self):
        if self.isMgmtdRunning():
            Logging.log(Logging.LOG_INFO, "Mgmtd is running!")
            self.sendVmnetEvent(vmnetDeleteEvent)
        else:
            Logging.log(Logging.LOG_INFO, "Mgmtd is not running!")

    def sendVmnetEvent(self, eventName):
        binding = ("interface", "string", self.vmnetReal)
        Mgmt.open()
        Mgmt.event(eventName, binding)
        Mgmt.close()
        Logging.log(Logging.LOG_INFO, "Event %s on interface %s sent" % (
                      eventName, self.vmnetReal))

    def isInterfaceRunningAndExist(self):
        commandList = ["/sbin/ifconfig", self.vmnetReal]
        if self.isNetifupRunning():
            (retcode, output, errmsg) = self.launchProcessAndWait(
                        commandList, logLevel = Logging.LOG_DEBUG)
            if retcode == 0:
                return True
            else:
                return False
        else:
            return False

    def enableRPS(self):
        # Enable RPS
        Logging.log(Logging.LOG_INFO, "Enabling RPS")
        commandList = ["/bin/cat", "/cgroup/cpuset/esx/cpuset.cpus"]
        (retcode, output, errmsg) = self.launchProcessAndWait(
                        commandList, logLevel = Logging.LOG_INFO)
        cpus = output.split("-")
        no_of_cpus = int(cpus[1]) - int(cpus[0]) + 1
        mask = ''
        for bit in range(no_of_cpus):
            mask = mask + '1'
        hex_mask = hex(int(mask, 2)).replace('0x', '')
        rps_file = '/sys/class/net/' + self.vmnetReal + '/queues/rx-0/rps_cpus'

        cmd = "/bin/echo %s > %s" % (hex_mask, rps_file)
        process = subprocess.Popen(
               cmd, bufsize=-1, shell=True, stdout=subprocess.PIPE, 
               stderr=subprocess.PIPE)
        output, errmsg = process.communicate()
        if process.returncode != 0:
            Logging.log(Logging.LOG_ERR,
                        "Launch process '%s' with error(%s):%s" % (
                        ' '.join(cmd),
                        process.returncode,
                        errmsg))

    def bringUpInterface(self, up = False):
        commandList = ["/sbin/ifconfig", self.vmnetReal]

        if not self.ipaddr is None:
            commandList.append(self.ipaddr)
            if not self.netmask is None:
                commandList.append("netmask")
                commandList.append(self.netmask)
        if up:
            commandList.append("up")

        if self.mtu != None and self.mtu != "0":
            commandList.append("mtu")
            commandList.append(self.mtu)
        for retry in range(self.sleepMaxBeforeBringup):
            if self.isInterfaceRunningAndExist():
                self.enableRPS()
                break
            else:
                time.sleep(self.sleepIntervalBeforeBringup)

        return self.launchProcessAndWait(commandList)


    def start(self, bringUpInterface = False):
        self.cleanWildNetifups()
        commandList = [self.vmnetNetIfUpCmd,
                       self.vmnetDev,
                       self.vmnetReal]
        Logging.log(Logging.LOG_INFO, "Interface %s is added" % (
                       self.vmnetReal))
        self.pid = self.launchProcess(commandList)

        self.bringUpInterface(up=bringUpInterface)

class VmwareDhcpdInterface(VmwareWsInterface):
    def __init__(self, interfaceName):
        super(VmwareDhcpdInterface, self).__init__(interfaceName)
        self.vmnetDhcpdCmd = vmwareBasePath + "bin/vmnet-dhcpd"
        self.vmnetVarDhcpdConfBasePath = "/var/etc/vmware/%s/" % (
             self.vmnetReal)
        self.dhcpdConf = self.vmnetVarDhcpdConfBasePath + "dhcpd/dhcpd.conf"
        self.dhcpdLease = self.vmnetVarDhcpdConfBasePath + "dhcpd/dhcpd.leases"
        self.dhcpdLeaseTemp = self.vmnetVarDhcpdConfBasePath + "dhcpd/dhcpd.leases~"
        self.dhcpdPidFileName = "/var/run/vmnet-dhcpd-%s.pid" % (
                        self.vmnetReal)
        self.dhcpdProcess = None

    def getLiveDhcpdPids(self):
        return self.getLivePids([self.dhcpdPidFileName,
                                 self.vmnetDhcpdCmd])

    def shutdownDhcpdProcesses(self, sig = signal.SIGTERM):
        pids = self.getLiveDhcpdPids()

        for pid in pids:
            self.shutdownProcess(pid, sig)

    def cleanWildDhcpds(self):
        self.shutdownDhcpdProcesses()

        if os.path.isfile(self.dhcpdPidFileName):
            os.remove(self.dhcpdPidFileName)
        if os.path.isfile(self.dhcpdLeaseTemp):
            os.remove(self.dhcpdLeaseTemp)

    def isDhcpdRunning(self):
        pids = self.getLiveDhcpdPids()
        return (len(pids) > 0)


    def start(self):
        self.cleanWildDhcpds()

        # XXX/jshilkaitis: WARNING -- lame shitty hack that will break if
        # VMware fixes vmnet-dhcpd.  Today, vmnet-dhcpd assumes that the
        # last character of the interface passed to it is the last
        # character of the interface's associated device.  Thus, for
        # vmlocal, vmnet-dhcpd tries to attach to /dev/vmnetl (that's a
        # lowercase L).  It turns out we can hack around this by
        # appending a 0 to the interface name.  vmlocal0 causes
        # vmnet-dhcpd to attach to /dev/vmnet0, ESXi's vmk0 properly gets
        # a DHCP address from dhcpd and everything is happy.  This is
        # total crap and is brittle since VMware fixing dhcpd will
        # almost certainly break us, but it works and, IMO, is better than
        # slapping a random 0 after vmlocal that the user can see.
        # I apologize to future generations for my expediency.
        #
        # P.S. I think my hack-guilt can be measured by the length
        # of the XXX comment preceding the hack.
        XXXlameHackSuffixForVMLocalInterface = "0"
        commandList = [self.vmnetDhcpdCmd,
                        "-d",
                        "-cf", self.dhcpdConf,
                        "-lf", self.dhcpdLease,
                        "-pf", self.dhcpdPidFileName,
                        "%s%s" % (self.vmnetReal,
                                  XXXlameHackSuffixForVMLocalInterface)]

        Logging.log(Logging.LOG_INFO, "Starting dhcpd on %s" % (
                    self.interfaceName))
        self.pid = self.launchProcess(commandList)

class VmwareLinuxBridgeInterface(object):
    def __init__(self, bridgeName, ipaddr = None, netmask = None):
        self.bridgeName = bridgeName
        self.netifup = VmwareNetifupInterface(bridgeName, ipaddr, netmask,
                             self.getBridgeInterfaceMTU(bridgeName))
        self.sig_quit_count = 0
        self.sleepWatchdogInterval = 1
        self.pid_kill_sleep = 0.1
        self.wait_pid_kill_count = 20
        self.bridgeCheckInterval = 0.1
        self.bridgeCheckCount = 10

    def handleTermSignal(self, signum, frame):
        # kill related processes, if no process left
        # exit with 0, otherwise return this function
        # and the script will continue

        if testEsxiShutdownInProgress():
            waitForVmwareVmx()

        self.shutdownBridgedInterface()

        if not self.netifup.isNetifupRunning():
            sys.exit(0)

    def handleQuitSignal(self, signum, frame):
        # handle SIGQUIT signal, if second SIGQUIT
        # received, change the signal to SIGKILL,
        # if no process running, exit with 0
        self.sig_quit_count = self.sig_quit_count + 1
        quit_signal = signal.SIGQUIT
        if self.sig_quit_count >= 2:
            quit_signal = signal.SIGKILL

        self.shutdownBridgedInterface(sig = quit_signal)

        if not self.netifup.isNetifupRunning():
            sys.exit(0)

    def registerSignalHandler(self):
        signal.signal(signal.SIGTERM, self.handleTermSignal)
        signal.signal(signal.SIGQUIT, self.handleQuitSignal)

    def shutdownBridgedInterface(self, sig = signal.SIGTERM):
        if self.netifup.isNetifupRunning():
            self.netifup.bringDownInterface()
            self.deleteInterfaceFromLinuxBridge()
            self.netifup.shutdownNetifupProcesses(sig)
            for checking_count in range(self.wait_pid_kill_count):
                if self.netifup.isNetifupRunning():
                    time.sleep(self.pid_kill_sleep)
                else:
                    break
    def getBridgeInterfaceMTU(self, bridgeName):
        bn_node = "/rbt/vsp/state/interface/%s/bridged/interface/mtu" % bridgeName
        Mgmt.open()
        infMTU = Mgmt.get_value(bn_node)
        Mgmt.close()
        return infMTU

    def deleteInterfaceFromLinuxBridge(self):
        commandList = ["/usr/sbin/brctl", "delif",
                       self.bridgeName, self.netifup.vmnetReal]

        return self.netifup.launchProcessAndWait(commandList)

    def isLinuxBridged(self):
        commandList = ["/usr/sbin/brctl", "show"]
        (retcode, output, errmsg) = self.netifup.launchProcessAndWait(commandList)
        if re.search("%s\s*$" % self.netifup.vmnetReal, output, re.M):
            return True
        return False 

    def bridgeLinuxInterface(self):
        commandList = ["/usr/sbin/brctl", "addif",
                       self.bridgeName, self.netifup.vmnetReal]

        for retry in range(self.bridgeCheckCount):
            time.sleep(self.bridgeCheckInterval)
            if self.isLinuxBridged():
                break
            else:
                self.netifup.launchProcessAndWait(commandList, logLevel = Logging.LOG_INFO)

        if self.isLinuxBridged():
            Logging.log(Logging.LOG_INFO, "Interface %s is bridged with %s" % (
                        self.netifup.vmnetReal, self.bridgeName))
        else:
            Logging.log(Logging.LOG_ERR, "Interface %s can not be bridged with %s" % (
                        self.netifup.vmnetReal, self.bridgeName))

    def watchdog(self):
        while (True):
            if self.netifup.isNetifupRunning() == False or self.isLinuxBridged() == False :
                sys.exit(2)
            else:
                time.sleep(self.sleepWatchdogInterval)

    def startService(self):
        self.registerSignalHandler()
        self.netifup.start()
        self.bridgeLinuxInterface()
        self.netifup.sendVmnetReadyEvent()

        # start watchdog after all processes are started or some failed
        self.watchdog()

class VmwareHpnInterface(object):
    def __init__(self, interfaceName, ipaddr = None, netmask = None):
        self.interfaceName = interfaceName
        self.netifup = VmwareNetifupInterface(interfaceName, ipaddr, netmask)
        self.sig_quit_count = 0
        self.sleepWatchdogInterval = 1

    def handleTermSignal(self, signum, frame):
        # kill related processes, if no process left
        # exit with 0, otherwise return this function
        # and the script will continue

        if testEsxiShutdownInProgress():
            waitForVmwareVmx()

        self.netifup.shutdownNetifupProcesses()
        self.netifup.sendVmnetDeleteEvent()

    def handleQuitSignal(self, signum, frame):
        # handle SIGQUIT signal, if second SIGQUIT
        # received, change the signal to SIGKILL,
        # if no process running, exit with 0
        self.sig_quit_count = self.sig_quit_count + 1
        quit_signal = signal.SIGQUIT
        if self.sig_quit_count >= 2:
            quit_signal = signal.SIGKILL

        self.netifup.shutdownNetifupProcesses(sig = quit_signal)
        self.netifup.sendVmnetDeleteEvent()

    def registerSignalHandler(self):
        signal.signal(signal.SIGTERM, self.handleTermSignal)
        signal.signal(signal.SIGQUIT, self.handleQuitSignal)

    def watchdog(self):
        while (True):
            if (self.netifup.isNetifupRunning() == False ):
                self.netifup.shutdownNetifupProcesses()
                self.netifup.sendVmnetDeleteEvent()
                sys.exit(2)
            else:
                time.sleep(self.sleepWatchdogInterval)

    def startService(self):
        self.registerSignalHandler()
        # Start Netifup after DHCPD is started or fail
        self.netifup.start(bringUpInterface = True)
        self.netifup.sendVmnetReadyEvent()

        # start watchdog after all processes are started or some failed
        self.watchdog()

class VmwareHpnWithDhcpdInterface(object):
    def __init__(self, interfaceName, ipaddr = None, netmask = None):
        self.interfaceName = interfaceName
        self.dhcpd = VmwareDhcpdInterface(interfaceName)
        self.netifup = VmwareNetifupInterface(interfaceName, ipaddr, netmask)
        self.sig_quit_count = 0
        self.sleepWatchdogInterval = 1

    def handleTermSignal(self, signum, frame):
        # kill related processes, if no process left
        # exit with 0, otherwise return this function
        # and the script will continue

        if testEsxiShutdownInProgress():
            waitForVmwareVmx()

        self.netifup.shutdownNetifupProcesses()
        self.dhcpd.shutdownDhcpdProcesses()

        if ((not self.dhcpd.isDhcpdRunning()) and
            (not self.netifup.isNetifupRunning())):
            self.netifup.sendVmnetDeleteEvent()
            sys.exit(0)

    def handleQuitSignal(self, signum, frame):
        # handle SIGQUIT signal, if second SIGQUIT
        # received, change the signal to SIGKILL,
        # if no process running, exit with 0
        self.sig_quit_count = self.sig_quit_count + 1
        quit_signal = signal.SIGQUIT
        if self.sig_quit_count >= 2:
            quit_signal = signal.SIGKILL

        self.dhcpd.shutdownDhcpdProcesses(sig = quit_signal)
        self.netifup.shutdownNetifupProcesses(sig = quit_signal)

        if ((not self.dhcpd.isDhcpdRunning()) and
            (not self.netifup.isNetifupRunning())):
            self.netifup.sendVmnetDeleteEvent()
            sys.exit(0)

    def registerSignalHandler(self):
        signal.signal(signal.SIGTERM, self.handleTermSignal)
        signal.signal(signal.SIGQUIT, self.handleQuitSignal)

    def watchdog(self):
        while (True):
            if (self.dhcpd.isDhcpdRunning() == False) or \
               (self.netifup.isNetifupRunning() == False ):
                self.netifup.shutdownNetifupProcesses()
                self.dhcpd.shutdownDhcpdProcesses()
                self.netifup.sendVmnetDeleteEvent()
                sys.exit(2)
            else:
                time.sleep(self.sleepWatchdogInterval)

    def startService(self):
        self.registerSignalHandler()
        # Start DHCPD first
        self.dhcpd.start()
        # Start Netifup after DHCPD is started or fail
        self.netifup.start()
        self.netifup.sendVmnetReadyEvent()
        
        # start watchdog after all processes are started or some failed
        self.watchdog()


def usage():
    print 'Usage: '+sys.argv[0]+' [option]'
    print 'options:'
    print '        -h/--help'
    print '        -p/--print: print fatal message to stdout'
    print '        -i/--interface ifname: interface to bridge'

def main(argv = sys.argv):
    Logging.log_init('vmware_ws_interface_wrapper', 'vmware_ws_interface_wrapper', 0,
                     Logging.component_id(Logging.LCI_VSP), Logging.LOG_DEBUG,
                     Logging.LOG_LOCAL0, Logging.LCT_SYSLOG)

    interfaceName = ""

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hpi:", ["help", "print","interface="])
    except getopt.GetoptError, err:
        # print help information and exit:
        print str(err) # will print something like "option -a not recognized"
        usage()
        sys.exit(2)

    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-p", "--print"):
            printToStd = True
        elif o in ("-i", "--interface"):
            interfaceName = a
        else:
            assert False, "unhandled option"

    if interfaceName in bridgeInterfaces:
        linuxbridge = VmwareLinuxBridgeInterface(interfaceName)
        linuxbridge.startService()
    elif interfaceName in hostOnlyInterfaces:
        if interfaceName == 'hpn':
            hpn = VmwareHpnWithDhcpdInterface(interfaceName)

        elif interfaceName == 'hpn3':
            hpn = VmwareHpnInterface(interfaceName, 
                        graniteHpnIp, hpnNetmask)

        hpn.startService()
    else:
        fatalError("Interface name %s is invalid" % interfaceName)

if __name__ == "__main__":
    main()

