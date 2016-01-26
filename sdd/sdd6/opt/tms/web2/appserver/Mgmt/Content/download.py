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

if RVBDUtils.isRspSupported():
    import rsp
    _TARGETS['rspbackup'] = {
        'dir': rsp.rsp_backupdir,
        'rbaNode': '/rbt/rsp2/action/backup/create',
        'mode': 'binary'
    }

if RVBDUtils.isBOB():
    import rsp3
    _TARGETS['rsp3backup'] = {
        'dir': rsp3.rsp_backupdir,
        'rbaNode': '/rbt/rsp3/action/backup/create',
        'mode': 'binary'
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
# <tt>filename</tt> is a base name (with no directory components) and
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

        # make sure we have a basename so we don't break out of
        # our directory
        assert os.path.basename(fileKey) == fileKey

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
