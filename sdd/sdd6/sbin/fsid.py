#!/usr/bin/python

from nfscalls import *
import sys
import os
import socket

# This script uses rpcinfo and showmount to get information about the
# exported file systems on a host, and then uses the python bindings for
# nfs v3 protocol to get the fsid of each of the exported file systems.
#
# Arguments;
#   the name (or ip address) of the host to probe
# Output;
#   a line for each exported volume containing it's name and fsid as a
#   hex number
# Diagnostics;
#   errors begin with ERROR, diagnostics begin with NOTICE or INFO

def error(str):
    sys.stderr.write("ERROR %s\n" % str)

def warn(str):
    sys.stdout.write("WARNING %s\n" % str)

def note(str):
    sys.stdout.write("NOTICE %s\n" % str)

# run a program and read the output in 4k blocks
def run_program(program):
    res = os.popen(program)
    result = ""
    while (1):
        next = res.read(4096)
        if (next == ''):
            return result
        result = result + next

# attempt to connect to the portmapper and report whether successful
def probe_portmap(target, timeout=30):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, \
                         socket.IPPROTO_TCP)
    if (sock == None):
        error("probe_portmap could not create a TCP socket")
        return False
    try:
        try:
            sock.settimeout(timeout)
            sock.connect((target, 111))
            return True
        except socket.timeout:
            error("timeout trying to connect to portmap on %s" % target)
            return False
        except socket.error, se:
            error("could not connect to portmap on %s: %s" % \
                  (target, se[1]))
            return False
    finally:
        sock.close()

def get_mountport(target, rpcinfo="rpcinfo", option="-p", mount_version=2,
                  mount_program_id = 100005):
    res = run_program("%s %s %s" % (rpcinfo, option, target))
    items = res.split("\n")[1:]
    for item in [x for x in items if x != '']:
        values = [x for x in item.split(" ") if x != '']
        program = int(values[0])
        vers = int(values[1])
        proto = values[2]
        if (program == mount_program_id
            and proto == "tcp"
            and mount_version == 2):
            return int(values[3])
    warn("no mountd found on %s" % target)
    return None
           
def get_mounts(target, showmount="/usr/sbin/showmount", option="-e"):
    res = run_program("%s %s %s" % (showmount, option, target))
    if (res == '' or res == None):
        error("ERROR run showmount failed\n")
        return None
    # exported file systems are on lines which aren't empty and start with a /
    items = [item for item in res.split("\n") if item != '' and item[0] == '/']
    return [item.split(" ")[0] for item in items]

def get_fsid(target, volume, mountport):
    mv = MountableVolume(target, volume, mount_port=mountport)
    if (mv == None):
        error("couldn't mount host %s volume %s "\
              "mount_port %d" % (target, volume, mountport))
        return None
    cred = NfsCredentials(socket.gethostname(), uid=0, gid=0)
    mount = mv.mount(cred)
    if (mount == None):
        error("failed to mount host %s volume %s mount_port %d" % \
              (target, volume, mountport))
        return
    enc = NfsEncoder(mount, cred)
    res = enc.call(GETATTR)
    if (res == None or res[0] == 0):
        error("getattr fails for host %s volume %s mount_port %d" % \
              (target, volume, mountport))
        return None
    return res[1]['obj_attr']['fsid']

def get_exports(target):
    # connect to the host and get information about it's exported volumes
    port = get_mountport(target)
    if (port == None):
        warn("failed to get the mountd port for %s" % (target))
        return
    mounts = get_mounts(target)
    if (mounts == None):
        note("no exported filesystems found on %s" % (target))
        pass
    for mount in mounts:    
        fsid = get_fsid(target, mount, port)
        if fsid != None:
            print "%s 0x%x" % (mount, fsid)

def main():
    if (not (len(sys.argv) in [2, 3])):
        print "Usage: fsid.py target-host [timeout]"
        return
    if (os.getuid() != 0):
        warn("You are not running this test as root.  " \
             "The test will probably fail to connect to the client " \
             "mountd because it cannot bind to a priveleged port.")
    # parse command line arguments
    target = sys.argv[1]
    timeout = 30
    if (len(sys.argv) == 3):
        try:
            timeout = int(sys.argv[2])
        except:
            error("the second argument (%s) should be an integer" % \
                  sys.argv[2])
            return
        if (timeout < 0 or timeout > 3600):
            error("%d is not a valid timeout value" % timeout)
            return
    # see if there is an accessible portmapper on that host
    if (probe_portmap(target, timeout=timeout) == False):
        error("no portmapper found on host %s" % target)
        return
    # gather and print the information
    get_exports(target)

if __name__ == "__main__":
    main()
    
