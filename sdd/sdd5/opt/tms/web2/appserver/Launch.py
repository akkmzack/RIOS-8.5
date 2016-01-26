#!/usr/bin/python

## Copyright 2007, Riverbed Technology, Inc., All rights reserved.
##
## Launch.py
##
## Launches WebKit.
##
## You can pass several parameters on the command line (more info by
## running this with option --help) or you can modify the default
## values here (more info in WebKit.Launch):

import sys
import os

workDir = '/opt/tms/web2/appserver'
webwareDir = '/opt/tms/web2/webware'
libraryDirs = ['/opt/tms/web2/pythonlib']

sys.path.insert(0, webwareDir)
for dir in libraryDirs:
    sys.path.insert(0, dir)
sys.argv = []

import Logging
Logging.log_init('webasd', 'web', 0,
                 Logging.component_id(Logging.LCI_WEB), Logging.LOG_DEBUG,
                 Logging.LOG_LOCAL0, Logging.LCT_SYSLOG)
Logging.log(Logging.LOG_INFO, 'Logging initialized for webasd')

tempDir = '/var/tmp'

# tempfile package uses this
os.environ['TMPDIR'] = tempDir
# fork/exec'ed CLI uses this
os.environ['USER'] = 'admin'

# clean out any old temporary upload files
for name in os.listdir(tempDir):
    if name.startswith('tmp_upload_'):
        os.unlink('%s/%s' % (tempDir, name))

runProfile = 0
logFile = None
pidFile = None
user = None
group = None

from WebKit import Launch
Launch.workDir = workDir
Launch.webwareDir = webwareDir
Launch.libraryDirs = libraryDirs
Launch.runProfile = runProfile
Launch.logFile = logFile
Launch.pidFile = pidFile
Launch.user = user
Launch.group = group

import RbtUtils

if not RbtUtils.isProduction():
    Logging.log(Logging.LOG_INFO, 'webasd is not production')

try:
    try:
        import wsm
        wsm.wsm().start()
    except Exception:
        Logging.log(Logging.LOG_ERR,
            'Global web connection to mgmtd failed.')
    else:
        # clean up temporary nodes that userconfig may leave behind
        import UserConfig
        from wsm import mgmt as globalMgmt
        UserConfig.cleanUp(globalMgmt)

        Launch.main(['ThreadedAppServer'])
finally:
    Logging.log(Logging.LOG_NOTICE, 'Appserver closing')
