import HTTPUtils
import Nodes

import gzip
import os
import RVBDUtils
from wsm import mgmt as globalMgmt

## Open a gzipped log file for reading uncompressed data.
#
# This is used on the log download page for returning gzipped files as
# plain text.
#
# @private
def __gunzippedOpenFile(pathName):
    f = gzip.open(pathName, 'rb')
    f.readline()    # let IOError percolate if f not gzipped.
    f.close()
    return gzip.open(pathName, 'rb')


## Return the default name of the file to create on the user's machine.
#
# For gzipped files being returned as plain text, we want to strip off
# the .gz and replace it with .txt instead.
#
# @private
def __gunzippedMakeFilename(pathName):
    fn = os.path.basename(pathName)
    fnparts = fn.split('.')
    if len(fnparts) > 2:
        fn = '.'.join(fnparts[:-1])
    return fn + ".txt"


## Define the types of files that can be downloaded.
#
# Each entry in this dictionary contains the following keys:
#
# - <tt>dir</tt>:  The directory that the files should be in.  This is
#   an absolute path.
# - <tt>rbaNode</tt>:  The node to use for the RBA check.
# - <tt>mode</tt>:  'ascii' or 'binary'.
# - <tt>openFileFn</tt>:  (Optional.)  A function that returns a file
#   object containing the data to be returned.  This is run after the
#   input and RBA checks.
# - <tt>makeFilenameFn</tt>:  (Optional.)  A function that determines
#   the default filename to create on the user's system.
# - <tt>allowSubdirs</tt>:  (Optional.)  Whether or not to allow access to
#   subdirectories of <tt>dir</tt> by allowing forward slashes in the filename
#   in the URL.  '..' is not allowed anywhere in the filename.  Default is
#   False (this behavior must be explicitly requested).
# - <tt>postDownloadFn</tt>:  (Optional.)  Function to invoke after the file
#   download completes.  The function will be passed one parameter: the fields
#   dictionary.
_TARGETS = {
    'plainlog': {
        'dir': '/var/log',
        'rbaNode': '/logging/syslog/action/file/\/var\/log\/messages',
        'mode': 'ascii',
    },
    'gzippedlog': {
        'dir': '/var/log',
        'rbaNode': '/logging/syslog/action/file/\/var\/log\/messages',
        'mode': 'binary',
    },
    'gunzippedlog': {
        'dir': '/var/log',
        'rbaNode': '/logging/syslog/action/file/\/var\/log\/messages',
        'mode': 'binary',
        'openFileFn': __gunzippedOpenFile,
        'makeFilenameFn': __gunzippedMakeFilename,
    },
    'sysdump': {
        'dir': '/var/opt/tms/sysdumps',
        'rbaNode': '/debug/generate/dump',
        'mode': 'binary',
    },
    'snapshot': {
        'dir': '/var/opt/tms/snapshots',
        'rbaNode': '/rbm_fake/debug/download/snapshot',
        'mode': 'binary',
    },
    'tcpdump': {
        'dir': '/var/opt/tms/tcpdumps',
        'rbaNode': '/rbm_fake/debug/generate/tcpdump',
        'mode': 'binary',
    }
}

if RVBDUtils.isCMC():
    _TARGETS['apptcpdump'] = {
        'dir': '/var/opt/tms/tcpdumps/appliance',
        'rbaNode': '/rbm_fake/debug/generate/tcpdump',
        'mode': 'binary',
    }

if RVBDUtils.isRspSupported():
    import rsp
    _TARGETS['rspbackup'] = {
        'dir': rsp.rsp_backupdir,
        'rbaNode': '/rbt/rsp2/action/backup/create',
        'mode': 'binary'
    }

if RVBDUtils.isGW():
    _TARGETS['SHMsysdump'] = {
        'dir': '/data/endpoint/sysdumps',
        'rbaNode': '',
        'mode': 'binary',
    }

    _TARGETS['SHMtcpdump'] = {
        'dir': '/data/endpoint/tcpdumps',
        'rbaNode': '',
        'mode': 'binary',
    }

    _TARGETS['SHMmemdump'] = {
        'dir': '/data/endpoint/memdumps',
        'rbaNode': '',
        'mode': 'binary',
    }

if RVBDUtils.isEXVSP():
    import vsp

    _TARGETS['vspv1Archive'] = {
        'dir': '/proxy/__RBT_VSERVER_SHELL__/rsp2/archive/',
        'rbaNode': '/rbt/vsp/migrate/action/slot/archive/upload',
        'mode': 'binary',
        'allowSubdirs': True,
        'postDownloadFn': vsp.vspv1MigrationFileDownload
    }

    _TARGETS['vspv1Package'] = {
        'dir': '/proxy/__RBT_VSERVER_SHELL__/rsp2/packages/',
        'rbaNode': '/rbt/vsp/migrate/action/package/upload',
        'mode': 'binary',
        'postDownloadFn': vsp.vspv1MigrationFileDownload
    }

    _TARGETS['vspv1Backup'] = {
        'dir': '/proxy/__RBT_VSERVER_SHELL__/rsp2/backup/',
        'rbaNode': '/rbt/vsp/migrate/action/backup/upload',
        'mode': 'binary',
        'postDownloadFn': vsp.vspv1MigrationFileDownload
    }

## Transfer a file to the client/browser.
#
# This handles the basic case where we have a file on the disk that we
# want to send to the user.  Input sanitization and RBA checks are
# performed by this class.  The file is returned through the following
# URL:
#
# <tt>/mgmt/download?f=[filename]&type=[filetype]</tt>
#
# <tt>filename</tt> is a base name (possibly with directory components) and
# <tt>filetype</tt> is one of the keys in the <tt>_TARGETS</tt> dict
# defined in this file.
class download(HTTPUtils.OctetStream):


    ## Get the dict that describes the type of file being downloaded.
    #
    # @private
    #
    # @return
    #   One of the dicts in _TARGETS.
    def __getTarget(self):
        return _TARGETS[self.fields['type']]


    def _mapFileKeyToPathname(self, fileKey):

        # Ensure the filename is legal.  Normally this is done by verifying that
        # the filename's basename is the same as itself, except in the case
        # where traversing into a subdirectory is permitted.
        errorMsg = '"%s" not allowed' % fileKey
        if self.__getTarget().get('allowSubdirs', False):
            assert fileKey.find('..') < 0, errorMsg
        else:
            assert os.path.basename(fileKey) == fileKey, errorMsg

        return '%s/%s' % (self.__getTarget()['dir'], fileKey)


    def _openPathname(self, pathName):

        # check permissions
        mgmt = self.session().value('mgmt')
        assert 'monitor' != mgmt.remoteUser.lower(), \
            'Download prohibited for the monitor user.'
        assert Nodes.permission(
            mgmt, self.__getTarget()['rbaNode']) != 'deny', \
            ('Download prohibited for user %s.' % mgmt.remoteUser)

        if 'openFileFn' in self.__getTarget():
            return self.__getTarget()['openFileFn'](pathName)
        else:
            return file(pathName, "r")


    def _mapPathNameToFileName(self, pathName):
        if 'makeFilenameFn' in self.__getTarget():
            return self.__getTarget()['makeFilenameFn'](pathName)
        elif self.__getTarget()['mode'] == 'binary':
            return os.path.basename(pathName)
        else:
            return os.path.basename(pathName) + '.txt'


    def _fluffBuf(self, buf):
        ua = self.request().environ().get('HTTP_USER_AGENT', '')
        if self.__getTarget()['mode'] == 'ascii' and '; Windows' in ua:
            return buf.replace('\n', '\r\n')
        else:
            return buf


    # Override the function in HTTPUtils.OctetStream to add support for
    # postDownloadFn.
    def _sendOctet(self, response, fileObj):
        super(download, self)._sendOctet(response, fileObj)

        postDownloadFn = self.__getTarget().get('postDownloadFn', None)
        if postDownloadFn:
            postDownloadFn(self.fields)
