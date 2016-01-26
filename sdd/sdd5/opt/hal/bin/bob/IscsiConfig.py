#!/usr/bin/python

# This program generates a configuration file that can be used
# by the iscsi_target server to export luns.  By default, the
# generated file has the iscsi target listening for requests
# only on the Host Private Network since it is only the ESXi host
# connects to the target.
#
# The config file looks like:
#
# <va>
#    <iscsi>
#        <session ignore_persistent_reservation="true" />
#    </iscsi>
#    
#     <edge host="localhost">
#       <iscsi_edge>
#         <edge_target dc="localhost">
#                 <edge_network_portal ip="169.254.131.1" port="3260" />
#         </edge_target>
#         <initiator_group name="all" dc="none" />
#       </iscsi_edge>
#     </edge>
# 
#     <vlun
#         alias="ISCSI Alias"
#         id="BEEF12341"
#         bunid="1"
#         lbacnt="47206656"
#         type="file"
#         file_name="/dev/md5">
#         <mapped_igroup name="all" />
# 	  <member_lun />
#     </vlun>
# </va>

import os
import sys
import string

from optparse import OptionParser

ISCSI_TARGET_CONFIG_FILE = '/var/etc/opt/tms/output/iscsi_config.xml' 
TAB_STRING = r'    '

# Default command server port for Iscsi Target
COMMAND_PORT = "7981"

# IscsiConfig
#
# This the object used to create the xml configuration file
# for the iscsi_target server.
#
class IscsiConfig:
    def __init__(self, path, output=None, debug=False):
        """
        Set up the config object, specifying the output stream.
        """
        if debug and path is not None and os.path.exists(path):
            print >> sys.stderr, 'DEBUG: %s already exists' % path

        if output == None and path == None:
            raise OSError(errno.ENOSYS, 'No output or path given')
            return None

        if path is not None:
            self._path = path
            self._fp = open(path, 'r+')
            self._output = self._fp 
        else:
            self._path = None
            self._fp = None
	    self._output = output

        # indentation level
        self.__tab = 0

        # starting vlun id
        self._vlun_next_id = 1

        # Begin the section.
        self.open_va()
	return

    # Adjust the tab indentation level
    def _settab(self, level):
        self.__tab = level
        return self.__tab

    # Dump to output stream
    def _out(self, s):
        lvl = self.__tab
        while lvl > 0:
            self._output.write(TAB_STRING)
            lvl = lvl - 1
        self._output.write(s)

    # <va>
    #     <iscsi> <session> </iscsi>
    #     <edge> <iscsi_edge> <initiator_group> </edge>
    #     <vlun> <mapped_igroup> <member_lun> </edge>
    # </va>
    #

    # <va>
    #
    def open_va(self):
        self._settab(0)
	self._out('<va>\n')
        self._settab(1)
        self._out('<command port=\"%s\"/>\n' % COMMAND_PORT)
        return

    #     <iscsi> <session> </iscsi>
    #
    def write_iscsi(self):
        self._settab(1)
        self._out('<iscsi>\n')
        self._settab(2)
        self._out('<session ignore_persistent_reservation="true" />\n')
        self._settab(1)
        self._out('</iscsi>\n')
        return


    #     <edge> <iscsi_edge> <initiator_group> </edge>
    #
    def write_edge(self, host, addr, port, mac_addr):
        params = {'host' : host,
                  'addr' : addr,
                  'port' : port,
		  'mac_addr' : mac_addr
                 }
        self._settab(1)
        self._out('<edge host="%(host)s">\n' % params)

        self._settab(2)
        self._out('<iscsi_edge>\n')

        self._settab(3)
        self._out('<edge_target dc="%(host)s" iscsi_name="iqn.2003-10.com.riverbed:%(mac_addr)s">\n' % params)
        self._settab(4)
        self._out('<edge_network_portal  ip="%(addr)s"  port="%(port)s" />\n' % params)
        self._settab(3)
        self._out('</edge_target>\n' % params)

        # All initiators are allowed to connect.
        self._out('<initiator_group name="all"  dc="none" />\n')

        self._settab(2)
        self._out('</iscsi_edge>\n')

        self._settab(1)
        self._out('</edge>\n')
        return

    #     <vlun> <mapped_igroup> <member_lun> </edge>
    #
    def write_vlun(self, devname, blkcount, mac_addr):
        """
        Write an entry into the file.
        devname  := Name of the file or device used to serve the LUN.
                    The file must exist and should (lbacnt * 512).
        blkcount := Number of blocks in the LUN (size is lbacnt * 512)
        """

        # From edge/iscsi_target_standalone.cfg.xml
        #
        # For each VLUN added to the target,
        # 'id' should be unique
        # 'lbasz' is the block size of the LUN
        # 'lbacnt' is the number of blocks (each of lbasz bytes)
        #  on the LUN
        # 'file_name' is the name of the file or device to use as LUN

        # blockstore-lunid aka bunid used at eva, unused at dva

        # XXX Can the target name be specified?
        # target="iqn.2003-10.com.riverbed:default-target"

        # Generate the unique lun identity 
        # The lun id is a number.
        alias = 'RSP Storage %d (%s)' % (self._vlun_next_id, devname)
        id    = '000%d' % (self._vlun_next_id)
        self._vlun_next_id = self._vlun_next_id + 1

        params = {'alias'   : alias,
                  'id'      : id,
                  'bunid'   : '1',
                  'lbacnt'  : str(blkcount),
		  'mac_addr'  : mac_addr,
                  'type'    : 'file',
                  'fname'   : devname }

        self._settab(1)
        self._out('<vlun\n')
        self._settab(2)

        fmt = 'alias="%(alias)s" '  + \
              'id="%(id)s" '        + \
              'bunid="%(bunid)s" '  + \
	      'target="iqn.2003-10.com.riverbed:%(mac_addr)s" ' + \
              'lbacnt="%(lbacnt)s" '+ \
              'type="%(type)s" '    + \
              'file_name="%(fname)s">\n'

        self._out(fmt % params)
        self._out('<mapped_igroup name="all" />\n')
        self._out('<member_lun />\n')
        self._settab(1)
        self._out('</vlun>\n')
        return

    def close(self):
        """
        Clean up the config object.
        """
        self._settab(0)
        self._out('</va>\n')

        # Close file object if it was created here.
        if self._fp:
            self._fp.close()
        return


# =============
# Main Function
# =============
def main(argv=None):

    if argv is None:
        argv = sys.argv

    cli_parser = OptionParser()

    cli_parser.add_option("--host", dest="host", action="store",
                          help="Edge host",
                          type="string", default='localhost')

    cli_parser.add_option("--addr", dest="addr", action="store",
                          help="IP address to listen for requests",
                          type="string", default='169.254.131.1')

    cli_parser.add_option("--port", dest="port", action="store",
                          help="Port used to listen for requests",
                          type="string", default='3261')

    cli_parser.add_option("--mac", dest="mac_addr",
                          action="store",
                          help="MAC address of primary interface", type="string",
                          default='')

    cli_parser.add_option("-d", "--debug", dest="debug",
                          action="store_true",
                          help="Print debug messages",
                          default=False)

    (options, args) = cli_parser.parse_args(argv[1:])

    if options.debug:
        print >> sys.stderr, 'argv=%s' % (argv)
        print >> sys.stderr, 'args=%s' % (args)
        print >> sys.stderr, 'options=%s' % (options)

    xl = IscsiConfig(None, sys.stdout, options.debug)
    xl.write_iscsi()
    xl.write_edge(options.host, options.addr, options.port, options.mac_addr)

    # For each lun specified:
    # The lun entries are speciifed in the form: "device,size"
    #
    for entry in args:
        fields = entry.split(',')
        if len(fields) < 2:
            continue
        # XXX Should we check for the existence of the device file?
        if fields[0][0:5] == '/dev/':
            file = fields[0]
        else:
            file = '/dev/' + fields[0]
        size = fields[1]

        xl.write_vlun(file, size, options.mac_addr)

    xl.close()


# ============
# Main line
# ============
if __name__  == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception, (msg):
        print >> sys.stderr,  "Error: %s" % (msg)
        exit(1)
