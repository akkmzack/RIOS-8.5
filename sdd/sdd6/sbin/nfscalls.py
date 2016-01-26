import time
import sys

from nfsmount import *

# RPC message type definitions        
CALL   = 0
RETURN = 1

# nfs procedure numbers
GETATTR     = 1
SETATTR     = 2
LOOKUP      = 3
ACCESS      = 4
READLINK    = 5
READ        = 6
WRITE       = 7
CREATE      = 8
MKDIR       = 9
SYMLINK     = 10
MKNOD       = 11
REMOVE      = 12
RMDIR       = 13
RENAME      = 14
LINK        = 15
READDIR     = 16
READDIRPLUS = 17
FSSTAT      = 18
FSINFO      = 19
PATHCONF    = 20
COMMIT      = 21

# nfs error codes
NFSV3ERR_OK          = 0
NFSV3ERR_PERM        = 1
NFSV3ERR_NOENT       = 2
NFSV3ERR_IO          = 5
NFSV3ERR_NXIO        = 6
NFSV3ERR_ACCES       = 13
NFSV3ERR_EXIST       = 17
NFSV3ERR_XDEV        = 18
NFSV3ERR_NODEV       = 19
NFSV3ERR_NOTDIR      = 20
NFSV3ERR_ISDIR       = 21
NFSV3ERR_INVAL       = 22
NFSV3ERR_FBIG        = 27
NFSV3ERR_NOSPC       = 28
NFSV3ERR_ROFS        = 30
NFSV3ERR_MLINK       = 31
NFSV3ERR_NAMETOOLONG = 63
NFSV3ERR_NOTEMPTY    = 66
NFSV3ERR_DQUOT       = 69
NFSV3ERR_STALE       = 70
NFSV3ERR_REMOTE      = 71
NFSV3ERR_BADHANDLE   = 10001
NFSV3ERR_NOT_SYNC    = 10002
NFSV3ERR_BAD_COOKIE  = 10003
NFSV3ERR_NOTSUPP     = 10004
NFSV3ERR_TOOSMALL    = 10005
NFSV3ERR_SERVERFAULT = 10006
NFSV3ERR_BADTYPE     = 10007
NFSV3ERR_JUKEBOX     = 10008

nfs_opname = {
    GETATTR:"GETATTR(1)",
    SETATTR:"SETATTR(2)",
    LOOKUP:"LOOKUP(3)",
    ACCESS:"ACCESS(4)",
    READLINK:"READLINK(5)",
    READ:"READ(6)",
    WRITE:"WRITE(7)",
    CREATE:"CREATE(8)",
    MKDIR:"MKDIR(9)",
    SYMLINK:"SYMLINK(10)",
    MKNOD:"MKNOD(11)",
    REMOVE:"REMOVE(12)",
    RMDIR:"RMDIR(13)",
    RENAME:"RENAME(14)",
    LINK:"LINK(15)",
    READDIR:"READDIR(16)",
    READDIRPLUS:"READDIRPLUS(17)",
    FSSTAT:"FSSTAT(18)",
    FSINFO:"FSINFO(19)",
    PATHCONF:"PATHCONF(20)",
    COMMIT:"COMMIT(21)", }

nfs_errorcode = { 
    NFSV3ERR_OK: "NFSV3ERR_OK(0)", 
    NFSV3ERR_PERM: "NFSV3ERR_PERM(1)", 
    NFSV3ERR_NOENT: "NFSV3ERR_NOENT(2)", 
    NFSV3ERR_IO: "NFSV3ERR_IO(5)", 
    NFSV3ERR_NXIO: "NFSV3ERR_NXIO(6)", 
    NFSV3ERR_ACCES: "NFSV3ERR_ACCES(13)", 
    NFSV3ERR_EXIST: "NFSV3ERR_EXIST(17)", 
    NFSV3ERR_XDEV: "NFSV3ERR_XDEV(18)", 
    NFSV3ERR_NODEV: "NFSV3ERR_NODEV(19)", 
    NFSV3ERR_NOTDIR: "NFSV3ERR_NOTDIR(20)", 
    NFSV3ERR_ISDIR: "NFSV3ERR_ISDIR(21)", 
    NFSV3ERR_INVAL: "NFSV3ERR_INVAL(22)", 
    NFSV3ERR_FBIG: "NFSV3ERR_FBIG(27)", 
    NFSV3ERR_NOSPC: "NFSV3ERR_NOSPC(28)", 
    NFSV3ERR_ROFS: "NFSV3ERR_ROFS(30)", 
    NFSV3ERR_MLINK: "NFSV3ERR_MLINK(31)", 
    NFSV3ERR_NAMETOOLONG: "NFSV3ERR_NAMETOOLONG(63)", 
    NFSV3ERR_NOTEMPTY: "NFSV3ERR_NOTEMPTY(66)", 
    NFSV3ERR_DQUOT: "NFSV3ERR_DQUOT(69)", 
    NFSV3ERR_STALE: "NFSV3ERR_STALE(70)", 
    NFSV3ERR_REMOTE: "NFSV3ERR_REMOTE(71)", 
    NFSV3ERR_BADHANDLE: "NFSV3ERR_BADHANDLE(10001)",
    NFSV3ERR_NOT_SYNC: "NFSV3ERR_NOT_SYNC(10002)",
    NFSV3ERR_BAD_COOKIE: "NFSV3ERR_BAD_COOKIE(10003)",
    NFSV3ERR_NOTSUPP: "NFSV3ERR_NOTSUPP(10004)",
    NFSV3ERR_TOOSMALL: "NFSV3ERR_TOOSMALL(10005)",
    NFSV3ERR_SERVERFAULT: "NFSV3ERR_SERVERFAULT(10006)",
    NFSV3ERR_BADTYPE: "NFSV3ERR_BADTYPE(10007)",
    NFSV3ERR_JUKEBOX: "NFSV3ERR_JUKEBOX(10008)", }

# the type fields in the fattr
NF3REG  = 1
NF3DIR  = 2
NF3BLK  = 3
NF3CHR  = 4
NF3LNK  = 5
NF3SOCK = 6
NF3FIFO = 7

# access modes
ACCESS3_READ    = 0x0001
ACCESS3_LOOKUP  = 0x0002
ACCESS3_MODIFY  = 0x0004
ACCESS3_EXTEND  = 0x0008
ACCESS3_DELETE  = 0x0010
ACCESS3_EXECUTE = 0x0020
# convienence
ACCESS3_ALL = ACCESS3_READ|ACCESS3_LOOKUP|ACCESS3_MODIFY| \
              ACCESS3_EXTEND|ACCESS3_DELETE|ACCESS3_EXECUTE
# write modes
UNSTABLE = 0
DATA_SYNC = 1
FILE_SYNC = 2

# create modes
UNCHECKED = 0
GUARDED   = 1
EXCLUSIVE = 2

#
# Mount a volume and create an encoder to talk to the server
# See nfsmount.py for the definition of get_mount and the list
# of name -> nfsserver bindings.
def mount(name, cred=NfsCredentials("dakota.nbttech.com"), volume=None,
          mount_base=600, nfs_base=600):
    mv = get_mount(name, volume=volume, mount_base=mount_base,
                   nfs_base=nfs_base).mount()
    if (mv == None):
        return None
    return NfsEncoder(mv, cred)

def nfssession(name, volume = None, uid=1096, gid=100, mount_base=600, nfs_base=600):
    mounted = mount(name, volume=volume, mount_base=mount_base, nfs_base=nfs_base)
    if (mounted == None):
        return None
    nfs = NfsSession(mounted)
    nfs.user(uid=uid, gid=gid)
    return nfs

#
# Encode and decode NFS protocol.
#
# This class keeps a 'current working fhandle' which is used as the first fhandle
# argument to all of the calls.  Hence you can say send(GETATTR) without supplying
# any arguments.
class NfsEncoder:
    def __init__(self, mounted_volume, cred):
        self.mount_ = mounted_volume
        self.cred_ = cred
        self.dirs_ = [] # dir stack
        return
    def close(self):
        self.mount_.get_socket().close()
    def get_packet(self):
        reply = sunrpc.read_rpc(self.mount_.get_socket().fileno())
        if (reply[0] == 0):
            print "Get packet fails: %s" % (reply[1])
            return None
        return reply[1]
    def send_packet(self, packet):
        return self.mount_.get_socket().send(packet)
    def	get_credentials(self):
        return self.cred_
    def	set_credentials(self, to):
        oldcred = self.cred_
        self.cred_ = to
        return oldcred
    # forwarding (convienence) methods
    def get_fh(self):
        return self.mount_.get_fh()
    def set_fh(self, to):
        return self.mount_.set_fh(to)
    def root_fh(self):
        return self.mount_.get_root_fh()
    # Some useful navigation methods, for interactive testing
    def move(self, path):
        for name in filter(lambda i: i != '', path.split("/")):
            res = self.call(LOOKUP, name)
            if res == None:
                print "move: no reply to lookup"
                return
            if (res[0] == 0):
                print "move: couldn't read the reply packet"
                return
            elif (res[1]["status"] != 0):
                print "move: couldn't lookup %s (nfserr=%s)" % \
                      (name, nfs_errorcode[res[1]["status"]])
                return
            self.set_fh(res[1]["fh"])
    def pushd(self, name):
        self.dirs_.append(self.get_fh())
        return self.move(name)
    def popd(self):
        oldfh = self.get_fh()
        self.set_fh(self.dirs_.pop())
        return oldfh
    def go_root(self):
        oldfh = self.get_fh()
        self.set_fh(self.root_fh())
        return oldfh
    def ls(self):
        for item in dirwalk(nfs, op=READDIR):
            print item
    # Send a write packet.  This requires a special implementation to make
    # count default to the length of the data.
    def write_send(self, towrite, offset = 0, stable = UNSTABLE, count = -1):
        if (count < 0):
            count = len(towrite)
        return self.generic_send_function(sunrpc.generate_write, \
                                          count, offset, stable, towrite)
    # Call the passed send function with the passed arguments and unpack the
    # reply packet
    def generic_send_function(self, gen_function, *args, **kwargs):
        packet = gen_function(self.cred_.my_hostname_, self.cred_.uid_, \
                              self.cred_.gid_, self.get_fh(), *args, **kwargs)
        if (packet[0] == 0):
            print "generic_send: packet creation failed:", packet[1]
            return None
        self.send_packet(packet[1])
        return packet[1]
    # Make and return a send method that wraps this function
    def create_send_function(function):
        return lambda self, *args: self.generic_send_function(function, *args)
    #
    # Table of nfs send and reply methods
    nfs_functions_ = { 
        GETATTR:(create_send_function(sunrpc.generate_getattr), 
                 sunrpc.parse_getattr_reply), 
        SETATTR:(lambda self, attrs, guard = None: 
                     self.generic_send_function(sunrpc.generate_setattr, 
                                                attrs, guard), 
                 sunrpc.parse_setattr_reply), 
        LOOKUP:(create_send_function(sunrpc.generate_lookup), 
                sunrpc.parse_lookup_reply), 
        ACCESS:(lambda self, how = ACCESS3_ALL:
                    self.generic_send_function(sunrpc.generate_access, how),
                sunrpc.parse_access_reply), 
        READLINK:(create_send_function(sunrpc.generate_readlink), 
                  sunrpc.parse_readlink_reply), 
        READ:(lambda self, count = 1024, offset = 0: 
                  self.generic_send_function(sunrpc.generate_read, 
                                             offset, count), 
              sunrpc.parse_read_reply), 
        WRITE:(write_send, sunrpc.parse_write_reply), 
        CREATE:(lambda self, name, mode = {"mode":0777}, how = GUARDED:
                self.generic_send_function(sunrpc.generate_create,
                                           name, how, mode),
                sunrpc.parse_create_reply), 
        MKDIR:(lambda self, name, attrs = None:
                   self.generic_send_function(sunrpc.generate_mkdir, name, attrs), 
               sunrpc.parse_mkdir_reply), 
        REMOVE:(create_send_function(sunrpc.generate_remove), 
                sunrpc.parse_remove_reply), 
        RMDIR:(create_send_function(sunrpc.generate_rmdir), 
               sunrpc.parse_rmdir_reply), 
        RENAME:(create_send_function(sunrpc.generate_rename), 
                sunrpc.parse_rename_reply), 
        LINK:(create_send_function(sunrpc.generate_link), 
              sunrpc.parse_link_reply), 
        READDIR:(lambda self, cookie = 0, count = 32 * 1024, cookieverf = "":
                     self.generic_send_function(sunrpc.generate_readdir, 
                                                cookie, count, cookieverf), 
                 sunrpc.parse_readdir_reply), 
        READDIRPLUS:(lambda self, cookie = 0, dircount = 256, 
                             maxcount = 32 * 1024, cookieverf = "": 
                         self.generic_send_function(sunrpc.generate_readdirplus, 
                                                    cookie, cookieverf, 
                                                    dircount, maxcount), 
                     sunrpc.parse_readdirplus_reply), 
        COMMIT:(lambda self, offset = 0, count = 0: 
                    self.generic_send_function(sunrpc.generate_commit, 
                                               offset, count), 
                sunrpc.parse_commit_reply), 
        SYMLINK:(lambda self, name, target, args = {"mode":0777} : 
                     self.generic_send_function(sunrpc.generate_symlink, 
                                                name, target, args), 
                 sunrpc.parse_symlink_reply),
	FSSTAT:(create_send_function(sunrpc.generate_fsstat), 
		sunrpc.parse_fsstat_reply),
	FSINFO:(create_send_function(sunrpc.generate_fsinfo), 
		sunrpc.parse_fsinfo_reply),
	PATHCONF:(create_send_function(sunrpc.generate_pathconf), 
		  sunrpc.parse_pathconf_reply),
        }
    # Methods to send and receive NFS packets
    def send(self, fn, *args, **kwarfs):
        return self.nfs_functions_[fn][0](self, *args, **kwarfs)
    def recv(self, fn):
        packet = self.get_packet()
        if (packet == None):
            print "recv failed in get_packet()"
            return None
        return self.parse_reply(fn, packet)
    def parse_reply(self, fn, data):
        return self.nfs_functions_[fn][1](data)
    # send a packet, wait for and return the reply.  this assumes that the
    # first packet read is the reply; will not work if there are multiple
    # outstanding packets.
    def call(self, fn, *args):
        if (self.send(fn, *args) == False):
            print "send failed"
            return None
        return self.recv(fn)

# Keep track of packet xids and automatically parse replies
class NfsSession:
    def __init__(self, enc):
        self.encoder_ = enc
        self.xid_list_ = {}
        self.pending_packets_ = []
        self.print_call_info_ = False
        return
    # terminate the connection now
    def close(self):
        self.encoder_.close()
    # send a packet, register it's xid and return the xid
    def send(self, proc, *args, **kwargs):
        packet = self.encoder_.send(proc, *args, **kwargs)
        rpc = sunrpc.parse_rpc(packet)
        if (rpc[0] == 0):
            print "failed to parse packet:", rpc
            return None
        xid = rpc[2][1]
        if (xid in self.xid_list_):
            print "xid already registered for proc %d" % (self.xid_list_[xid])
        self.xid_list_[xid] = (proc, time.time())
        # print "call registered: xid=0x%x" % (xid)    
        return xid
    # get the next packet from the server, parse it and return the following:
    # (xid, nfs_procedure, delay, result)
    # result is a list of (0, error) or (1, parsed-reply)
    def recv(self):
        packet = self.encoder_.get_packet()
        if (packet == None):
            print "recv: get_packet failed"
            return None
        # Get the rpc header from the reply packet to get the xid
        rpc = sunrpc.parse_rpc(packet)
        if (rpc[0] == 0):
            print "recv: parse rpc failed: packet is", packet
            return None
        if (rpc[2][0] != RETURN):
            print "recv: rpc packet type is not RETURN: it is", rpc[2][0]
            return None
        xid = rpc[2][1]
        # Get the procedure number associated with this xid
        info = self.xid_list_.pop(xid, None);
        if (info == None):
            print "recv: xid 0x%x is not known" % (xid)
            return self.recv()
        (proc, begin) = info
        # Parse the reply nfs info using the procedure number
        result = self.encoder_.parse_reply(proc, packet)
        delay = time.time() - begin
        if (self.print_call_info_):
            print "proc=%d delay=%gms" % (proc, delay)
        return (xid, proc, delay, result)
    # send a packet and return the reply; return values are the same as recv
    def call(self, proc, *args, **kwargs):
        callxid = self.send(proc, *args, **kwargs)
        if (callxid == None):
            print "call: send failed."
            return None
        while 1:
            reply = self.recv()
            if (reply == None):
                print "call: recv returns nothing"
                return None
            (xid, proc, delay, res) = reply
            if (xid == callxid):
                return (xid, proc, delay, res)
            self.pending_packets_.append( (xid, proc, delay, res) )
    # like call except it only returns the parsed reply packet
    def unpack(self, proc, *args, **kwargs):
        reply = self.call(proc, *args, **kwargs)
        if (reply == None):
            return None
        (xid, proc, delay, result) = reply
        if (result[0] == 0):
            return None
        return result[1]
    # Just report the amount of time a call took
    def time(self, op, *args, **kwargs):
        (x, p, d, r) = self.call(op, *args, **kwargs)
        if (r[0] != 0 and r[1]["status"] == NFSV3ERR_OK):
            return d
        elif (r[0] != 0):
            print "ERROR couldn't read the reply packet delay=%d" % (d)
            return None
        else:
            print "ERROR call failed (error=%s delay=%d)" % \
                  (nfs_errorcode[r[1]["status"]], d)
            return None
    # like unpack but pretty prints the reply to the terminal
    def pp(self, op, *args, **kwargs):
        (x, p, d, r) = self.call(op, *args, **kwargs)
        print "(delay=%dms)" % (d * 1000)
        if (r[0] == 0):
            print "call failed"
        else:
            self.pprint(r[1])
    def pprint(self, item, indent=0, label=""):
        # field names which are printed specially and format strings
        # or procedures used to print them 
        filetype = { NF3REG: "NF3REG", NF3DIR: "NF3DIR", NF3BLK: "NF3BLK",
                     NF3CHR: "NF3CHR", NF3LNK: "NF3LNK", NF3SOCK: "NF3SOCK",
                     NF3FIFO: "NF3FIFO", }
        def time_format( (sec, usec) ):
            return "\"%s\" (%d, %d)" % \
                   (time.asctime(time.localtime(sec)), sec, usec)
        def cookie_format(cookie):
            return "".join(["%d:" % ord(i) for i in cookie])[0:-1]
        def namehandle_format(nh):
            if (nh[0] == 0):
                return "<no handle returned>"
            else:
                return fh_format(nh[1])
        special_format = { "mode":"0%o", "fileid":"0x%x", "fsid":"0x%x",
                           "name":"\"%s\"", "cookie":"0x%x", "access":"0x%x",
                           "status":lambda x: nfs_errorcode[x],
                           "type":lambda x: filetype[x], "atime":time_format,
                           "ctime":time_format, "mtime":time_format,
                           "verf":cookie_format, "cookieverf":cookie_format ,
                           "fh":fh_format, "name_handle":namehandle_format}
        def every(fn, list):
            if (list == () or list == [] or list == None):
                return True
            return fn(list[0]) and every(fn, list[1:])
        def is_structure(item):
            return type(item) in [dict, list, tuple]
        if (item == None):
            print "%s%s" % (" " * indent, "None")
        elif (label in special_format):
            if callable(special_format[label]):
                print "%s%-12s%s" % (" " * indent, label, special_format[label](item))
            else:
                print "%s%-12s%s" % (" " * indent, label, special_format[label] % item)
                
        elif (type(item) == dict):
            for field in item.keys():
                if (type(item[field]) == dict):
                    print "%s%s" % (" " * indent, field)
                    self.pprint(item[field], indent=indent + 4)
                else:
                    self.pprint(item[field], label=field, indent=indent)
        elif (type(item) == list or type(item) == tuple):
            if (every(lambda x: not is_structure(x), item)):
                print "%s%-12s%s" % (" " * indent, label, item)
            else:
                print "%s%s" % (" " * indent, label)
                for i in range(0, len(item)):
                    self.pprint(item[i], indent=indent + 4)
        else:
            print "%s%-12s%s" % (" " * indent, label, item)
        return None
    # write a file to the terminal; by default the current fhandle,
    # but this takes an optional file name as an argument
    def cat(self, file = None):
        def cat_file():
            for block in readiter(self):
                sys.stdout.write(block)
        if (file != None):
            self.pushd(file)
            try:
                cat_file()
            finally:
                self.popd()
        else:
            cat_file()
    def ls(self):
        files = [item["name"] for item in readdir_complete(self)]
        files.sort()
        for item in files:
            print item
    def lsl(self):
        def type_string(type):
            types = ['?', 'R', 'D', 'B', 'C', 'L', 'S', 'F']
            return types[type]
        def legible_size(value):
            if (value > 1024 * 1024 * 1024):
                return "%3.3gG" % (value / (1024.0 * 1024 * 1024))
            elif (value > 1024 * 1024):
                return "%3.3gM" % (value / (1024.0 * 1024))
            elif (value > 1024):
                return "%3.3gK" % (value / (1024.0))
            else:
                return value
	for (name, attr, fh) in [(x["name"], x["name_attr"][1], x['name_handle'][1]) \
			     for x in readdirplus_complete(self)]:
	    if attr['type'] == NF3REG:
                print "%s %8o  %s -- size=%d (%s)" % (type_string(attr['type']), attr['mode'], name, attr['size'], legible_size(attr['size']))
            elif attr['type'] == NF3LNK:
                oldfh = self.set_fh(fh)
                try:
                    res = self.unpack(READLINK)
                    link = res['link']
                    print "%s %8o  %s --> %s" % (type_string(attr['type']), attr['mode'], name, link)
                finally:
                    self.set_fh(oldfh)
            else:
                print "%s %8o  %s" % (type_string(attr['type']), attr['mode'], name)
    def truncate(self):
        return self.unpack(SETATTR, {'size':0})
    def user(self, uid=1096, gid=100, host='dakota.nbttech.com'):
        return self.set_credentials(NfsCredentials(host, uid, gid))
    # return a number that is less than the rtt
    def min_rtt(self):
        # use FSINFO b/c 1: it doesn't get optimized 2: the service time seems
        # most consistent
        self.call(FSINFO)
        time.sleep(.1)
        return min([self.time(FSINFO) for i in range(0, 5)]) * .9
    # Forward these method calls to encoder_
    def move(self, to):
        return self.encoder_.move(to)
    def pushd(self, to):
        return self.encoder_.pushd(to)
    def popd(self):
        return self.encoder_.popd()
    def	set_credentials(self, to):
        return self.encoder_.set_credentials(to)
    def	get_credentials(self):
        return self.encoder_.get_credentials()
    def	get_fh(self):
        return self.encoder_.get_fh()
    def	set_fh(self, to):
        return self.encoder_.set_fh(to)
    def root(self):
        return self.set_fh(self.encoder_.root_fh())
    def apply(self, file, *args, **kwargs):
        self.pushd(file)
        try:
            return self.pp(*args, **kwargs)
        finally:
            self.popd()
    def apply_fh(self, fh, *args, **kwargs):
        oldfh = self.set_fh(fh)
        try:
            return self.call(*args, **kwargs)
        finally:
            self.set_fh(oldfh)
    # direct access to nfs calls
    def getattr(self, *args, **kwargs): self.pp(GETATTR, *args, **kwargs)
    def setattr(self, *args, **kwargs): self.pp(SETATTR, *args, **kwargs)
    def lookup(self, *args, **kwargs): self.pp(LOOKUP, *args, **kwargs)
    def access(self, *args, **kwargs): self.pp(ACCESS, *args, **kwargs)
    def readlink(self, *args, **kwargs): self.pp(READLINK, *args, **kwargs)
    def read(self, *args, **kwargs): self.pp(READ, *args, **kwargs)
    def write(self, *args, **kwargs): self.pp(WRITE, *args, **kwargs)
    def create(self, *args, **kwargs): self.pp(CREATE, *args, **kwargs)
    def mkdir(self, *args, **kwargs): self.pp(MKDIR, *args, **kwargs)
    def symlink(self, *args, **kwargs): self.pp(SYMLINK, *args, **kwargs)
    def mknod(self, *args, **kwargs): self.pp(MKNOD, *args, **kwargs)
    def remove(self, *args, **kwargs): self.pp(REMOVE, *args, **kwargs)
    def rmdir(self, *args, **kwargs): self.pp(RMDIR, *args, **kwargs)
    def rename(self, *args, **kwargs): self.pp(RENAME, *args, **kwargs)
    def link(self, *args, **kwargs): self.pp(LINK, *args, **kwargs)
    def readdir(self, *args, **kwargs): self.pp(READDIR, *args, **kwargs)
    def readdirplus(self, *args, **kwargs): self.pp(READDIRPLUS, *args, **kwargs)
    def fsstat(self, *args, **kwargs): self.pp(FSSTAT, *args, **kwargs)
    def fsinfo(self, *args, **kwargs): self.pp(FSINFO, *args, **kwargs)
    def pathconf(self, *args, **kwargs): self.pp(PATHCONF, *args, **kwargs)
    def commit(self, *args, **kwargs): self.pp(COMMIT, *args, **kwargs)

#
# Utility functions

# This function iterates over the contents of a directory - it reads more
# data only as needed (eg. it doesn't read the directory when it is first
# accessed).  op is one of READDIR or READDIRPLUS.
def dirwalk(nfs, op = READDIRPLUS, **kwargs):
    lastcookie = 0
    cookieverf = '\0' * 8
    while 1:
        (xid, proc, delay, res) = nfs.call(op, cookie=lastcookie, \
                                           cookieverf=cookieverf, **kwargs)
        if (res[0] != 1):
            print "dirwalk: get reply packet fails", res[1]
            return
        nfsreply = res[1]
        if (nfsreply["status"] != NFSV3ERR_OK):
            print "dirwalk: readdir operation %d failed: nfs error is %s" % \
                  (op, nfs_errorcode[nfsreply["status"]])
            return
        cookieverf = nfsreply["cookieverf"]
        for item in nfsreply["entries"]:
            yield item
            lastcookie = item["cookie"]
        if (nfsreply["eof"]):
            return

def readdir_complete(nfs, count = 32 * 1024):
    return tuple(dirwalk(nfs, op=READDIR, count=count))

def readdirplus_complete(nfs, maxcount = 32 * 1024):
    return tuple(dirwalk(nfs, op=READDIRPLUS, maxcount=maxcount))

# Iterator which reads the file in count size units and returns the file
# contents in blocksize size blocks.
def readiter(nfs, count = 32768, blocksize=1024):
    offset = 0
    while 1:
        (xid, proc, delay, res) = nfs.call(READ, offset=offset, count=count)
        if (res[0] != 1):
            print "readiter: couldn't parse the read reply packet"
            return
        reply = res[1]
        if (reply["status"] != 0):
            print "readiter: read fails, nfs error is", \
                  nfs_errorcode[reply["status"]]
            return
        for i in range(0, len(reply["data"]), blocksize):
            yield reply["data"][i:i + blocksize]
        reply["data"] = None
        if (reply["eof"] != 0):
            return
        offset += reply["length"]

# iterate over the entire contents of a file system, going into
# subdirectories
def fsiter(nfs, path = "."):
    res = readdirplus_complete(nfs)
    subdirs = []
    for item in res:
        if item['name_handle'][0] == 0 or item['name_attr'][0] == 0:
            raise Exception("%s in %s has no attributes or handle" % \
                            (item['name'], path))
            pass
        elif not item['name'] in ('.', '..'):
            if item['name_attr'][1]['type'] == NF3DIR:
                subdirs.append( (item['name'], item['name_handle'][1]) )
                pass
            pass
        yield (path, item)
        pass
    orig_fh = nfs.get_fh()
    for (name, fh) in subdirs:
        nfs.set_fh(fh)
        for item in fsiter(nfs, path + "/" + name):
            yield item
            pass
        pass
    nfs.set_fh(orig_fh)

# Convert a string representation of a fhandle (as found in the log file) to
# a fhandle.
# Use; get a fhandle out of a log message and past it into something like this
# nfs.set_fh(make_fh('0:80:0:0:0:0:0:2:0:a:0:0:0:0:4f:5b:23:1c:d0:3c:0:a:0:0:0:0:4f:5b:23:1c:d0:3c:'))
def make_fh(str):
    return reduce(lambda x, y: x + y, \
                  [chr(int(x, 16)) for x in str.split(":") if x != ''])

# return an ethereal compatible hash for this fhandle
def fhandle_hash(fh):
    hash = 0L
    items = [((ord(fh[i]) << 24) + (ord(fh[i + 1]) << 16)  + \
              (ord(fh[i + 2]) << 8) + ord(fh[i + 3])) \
             for i in range(0, len(fh), 4)]
    for i in items:
        hash ^= i
        hash += i
    if hash < 0:
        hash *= -1
    return hash

def fh_format(fh):
    fhstring = "".join(["%x:" % ord(i) for i in fh])[0:-1]
    return "0x%x (%s)" % (fhandle_hash(fh), fhstring)

# make this available outside the context of a nfs session
def pprint(item, indent=0, label=""):
    # field names which are printed specially and format strings
    # or procedures used to print them 
    filetype = { NF3REG: "NF3REG", NF3DIR: "NF3DIR", NF3BLK: "NF3BLK",
                 NF3CHR: "NF3CHR", NF3LNK: "NF3LNK", NF3SOCK: "NF3SOCK",
                 NF3FIFO: "NF3FIFO", }
    def time_format( (sec, usec) ):
        return "\"%s\" (%d, %d)" % \
               (time.asctime(time.localtime(sec)), sec, usec)
    def cookie_format(cookie):
        return "".join(["%d:" % ord(i) for i in cookie])[0:-1]
    def namehandle_format(nh):
        if (nh[0] == 0):
            return "<no handle returned>"
        else:
            return fh_format(nh[1])
    special_format = { "mode":"0%o", "fileid":"0x%x", "fsid":"0x%x",
                       "name":"\"%s\"", "cookie":"0x%x", "access":"0x%x",
                       "status":lambda x: nfs_errorcode[x],
                       "type":lambda x: filetype[x], "atime":time_format,
                       "ctime":time_format, "mtime":time_format,
                       "verf":cookie_format, "cookieverf":cookie_format ,
                       "fh":fh_format, "name_handle":namehandle_format}
    def every(fn, list):
        if (list == () or list == [] or list == None):
            return True
        return fn(list[0]) and every(fn, list[1:])
    def is_structure(item):
        return type(item) in [dict, list, tuple]
    if (item == None):
        print "%s%s" % (" " * indent, "None")
    elif (label in special_format):
        if callable(special_format[label]):
            print "%s%-12s%s" % (" " * indent, label, special_format[label](item))
        else:
            print "%s%-12s%s" % (" " * indent, label, special_format[label] % item)
    elif (type(item) == dict):
        for field in item.keys():
            if (type(item[field]) == dict):
                print "%s%s" % (" " * indent, field)
                pprint(item[field], indent=indent + 4)
            else:
                pprint(item[field], label=field, indent=indent)
    elif (type(item) == list or type(item) == tuple):
        if (every(lambda x: not is_structure(x), item)):
            print "%s%-12s%s" % (" " * indent, label, item)
        else:
            print "%s%s" % (" " * indent, label)
            for i in range(0, len(item)):
                pprint(item[i], indent=indent + 4)
    else:
        print "%s%-12s%s" % (" " * indent, label, item)
        return None
                            
# Probe the nfs server and return whether the connection is working or not
def check_nfs_connection(nfs, procedure = FSINFO, timeout = 1):
    import threading
    event = threading.Event()
    result = [False]
    def probe_server(nfs):
        try:
            try:
                (x, p, d, res) = nfs.call(procedure)
                if res[0] == 0:
                    print "probe_server: failed to get RPC reply"
                    result[0] = False
                else:
                    result[0] = True
            except Exception:
                result[0] = False
                return
        finally:
            event.set()
    import thread
    thread.start_new_thread(probe_server, (nfs, ))
    event.wait(timeout)
    return result[0]
