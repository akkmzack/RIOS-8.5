import sunrpc
import socket
import os

# Nfs credentials - these go into the RPC UNIX auth field in request packets.
class NfsCredentials:
    def __init__(self, my_hostname, uid = 0, gid = 0, extra_gids = []):
        self.my_hostname_ = my_hostname
        self.uid_ = uid
        self.gid_ = gid
        self.extra_gids_ = extra_gids

# a mounted volume; a connection and a root fhandle
class MountedVolume:
    def __init__(self, s, root_fh):
        self.s_ = s
        self.root_fh_ = root_fh
        self.current_fh_ = root_fh
        return
    def get_socket(self):
        return self.s_
    def get_fh(self):
        return self.current_fh_
    def set_fh(self, to):
        oldfh = self.current_fh_ 
        self.current_fh_ = to
        return oldfh
    def get_root_fh(self):
        return self.root_fh_

# MountableVolume contains all of the information needed to mount
# a NFS volume.  The mount() method returns a MountedVolume.
class MountableVolume:
    def __init__(self, nfs_host, nfs_volume, mount_port = 4046,
                 nfs_port = 2049, mount_base = 600, nfs_base = 600):
        self.nfs_host_ = nfs_host
        self.mount_port_ = mount_port
        self.nfs_volume_ = nfs_volume
        self.nfs_port_ = nfs_port
        self.mount_base_ = mount_base
        self.nfs_base_ = nfs_base
    #
    # mount this nfs volume by getting the root fhandle and connecting to 
    # 1the nfs port
    def mount(self, cred = None):
        # If no credential is supplied create a generic one
        if (cred == None):
            cred = NfsCredentials(socket.gethostname(), uid=0, gid=0, extra_gids=[])
        # connect to the mountd port and get the root fhandle
        s = self.get_connection(self.nfs_host_, self.mount_port_, self.mount_base_)
        if (s == None):
            print "ERROR mount: get_connection(%s, %d) failed" % \
                  (self.nfs_host_, self.mount_port_)
            return None
        try:
            root_fh = self.get_root_fh(s, cred)
        finally:
            s.close()
        if (root_fh == None):
            return None
        # now connect to the nfs port
        s = self.get_connection(self.nfs_host_, self.nfs_port_, self.nfs_base_)
        if (s == None):
            print "mount: failed to connect to the nfs port (%d) on %s" % \
                  (self.nfs_port_, self.nfs_host_)
            return None
        return MountedVolume(s, root_fh)
    #
    # get the root fhandle for this mount from the server's mountd
    def get_root_fh(self, s, cred):
        # print "get_root_fh(%s, %s, %d, %d)" % \
        #       (self.nfs_volume_, cred.my_hostname_, cred.uid_, cred.gid_)
	packet = sunrpc.mountrequest(cred.my_hostname_, self.nfs_volume_, \
                                     cred.uid_, cred.gid_)
	s.send(packet)
	# Read the reply and hand it to the parser to get the fhandle
	reply = sunrpc.read_rpc(s.fileno())
	if (reply == None):
            return None
	elif (reply[0] == 0):
            print "get_root_fh failed:", reply[1]
            return None
	fhandle = sunrpc.extract_mount_fhandle(reply[1])
	return fhandle
    #
    # make a connection to (host, port) with local port equal to (or near) base
    def get_connection(self, host, port, base, span=100, timeout=30):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        for i in range(0, span):
            try:
                s.bind( ("0.0.0.0", base + i) )
                s.connect( (host, port) )
                return s
            except socket.timeout:
                print "get_connection: connect to port %d timed out" % port
                return None
            except:
                pass
        s.close()
        print "get_connection: failed to make a connection to (%s, %d)" % (host, port)
        return None

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
    print "WARNING no mountd found on %s" % target
    return None
           
def get_mounts(target, showmount="/usr/sbin/showmount", option="-e"):
    res = run_program("%s %s %s" % (showmount, option, target))
    if (res == '' or res == None):
        print "ERROR run showmount failed"
        return None
    # exported file systems are on lines which aren't empty and start with a /
    items = [item for item in res.split("\n") if item != '' and item[0] == '/']
    return [item.split(" ")[0] for item in items]

# run a program and read the output in 4k blocks
def run_program(program):
    res = os.popen(program)
    result = ""
    while (1):
        next = res.read(4096)
        if (next == ''):
            return result
        result = result + next

# some hints about which volume to mount if the user doesn't specify
volume_hints = {'mint':'/vol/prime/main' }

def get_mount(name, volume = None, nfs_port = 2049,
              mount_base = 600, nfs_base = 600):
    mountport = get_mountport(name)
    if (mountport == None):
        print "ERROR couldn't find the port for mountd on %s" % name
        return
    if (volume != None):
        print "trying to mount %s" % volume
        return MountableVolume(name, volume, mountport, nfs_port, 
                               mount_base=mount_base, nfs_base=nfs_base)
    elif volume_hints.has_key(name):
        volume = volume_hints[name]
        print "trying to mount %s" % volume
        mv = MountableVolume(name, volume, mountport, nfs_port,
                             mount_base=mount_base, nfs_base=nfs_base)
        if (mv != None):
            return mv
    else:
        mounts = get_mounts(name)
        nfs = None
        for fs in mounts:
            print "trying to mount %s" % fs
            try:
                return MountableVolume(name, fs, mountport, nfs_port,
                                       mount_base = mount_base,
                                       nfs_base = nfs_base)
            except Exception, e:
                print e
                pass
        print "ERROR could not mount any file system on %s" % name
        return None
