#!/usr/bin/env python
#
#  Filename:  $Source$
#  Revision:  $Revision: 51619 $
#  Date:      $Date: 2009-05-14 00:51:19 -0700 (Thu, 14 May 2009) $
#  Author:    $Author: jshilkaitis $
# 
#  (C) Copyright 2003-2008 Riverbed Technology, Inc.  
#  All rights reserved.


###############################################################################
# fw_util.py
#
# Utility to update drive firmware to the version of fw indicated by the
# configuration file /opt/hal/lib/disk/fw_cfg.xml.
#
# Wraps fw_util (executable). Care must be taken to ensure that no other 
# operations to the disk may occur while the firmware update is happening
# since non MICROCODE_DOWNLOAD commands cause the update to fail.
#
# This utility is meant to be run from early in startup, or in situation
# when the user has taken care to stop all raid arrays and quiesce all IO
# to drives that will be updated.
#
# fw_util.py will always attempt two internal retries for updating the firmware.
# We also stop the retries after two calls to fw_util.py have failed, using state
# kept on the /config/disk.
#
###############################################################################
from os.path import exists
from os import popen, remove
from rrdm_util import get_hwtool_motherboard, run_shell_cmd, rrdm_error
import sys
from DiskLib import *

def usage():
    print 'Usage : %s [-v] [-f|-c] [-h] <device name>' % sys.argv[0]
    print '        -f : force update'
    print '        -c : print whether a firmware update would be needed'
    print '        -v : verbose output'
    print '        -h : print this help'
    sys.exit(1)

# Display verbose debugging output to stdout
#
verbose=False

# Display whether or not we need a firmware update for the devic
check_update_needed=False

# Device name specified on the command line
device_name=''

# shall we force the firmware update specified in the configuration file 
# regardless of whether or not the disk firmware is out of date
#
force = False

# output_prefix
# for normal output messages (non-verbose) 
# prepend this string so we can easily identify the messages in the logs.
#
output_prefix = 'diskfw'

# prepend all normal output with a tag that identifies this app.
#
def do_print(str):
    print '%s: %s' % (output_prefix, str)

# Parse the command line args
#
for arg in sys.argv[1:]:
    if arg == "-v":
        verbose = True
    if arg == "-f":
        force = True
    if arg == "-c":
        check_update_needed = True
    if arg == "-h":
        usage()
    else:
        device_name = arg

if device_name == '':
    do_print ('Usage: %s <dev name>' % sys.argv[0])
    sys.exit(1)

if not exists(device_name):
    do_print ('Device %s does not exist' % device_name)
    sys.exit(1)

# Read the disk firmware configuration for all disks with firmawre
# updates supported by this revision of the sw.
#
try:
    disk_fw_cfg = DriveConfigMap(verbose = verbose)
except DiskConfigException, what:
    do_print ('Failed to read config file with error [%s]' % what)
    sys.exit(1)

try:
    d = Drive(device_name, disk_fw_cfg, verbose)
except SmartInfoException, what:
    do_print ('Failed to fetch disk information %s [%s]' % (device_name, what))
    sys.exit(1)
except DiskConfigException, what:
    print 'Failed to fetch disk information %s [%s]' % (device_name, what)
    sys.exit(1)
    

try:
    disk_fw_context = DiskFwUpdateContext(d)
except OSError:
    do_print ('Unable to set up disk state cache %s'  % device_name)

#force and check update needed are mutually exclusive
if force and check_update_needed:
    usage()

if check_update_needed:
    print d.needs_fw_update()
    sys.exit(0)

if not force and not disk_fw_context.should_update():
    # this disk has failed a few times before, exit.
    do_print ('%s: %s: %s: Firmware Update has exceeded %d retries, skipping update' % (
              device_name, d.get_model(), d.get_serial(),
              disk_fw_context.get_max_retries()))
    sys.exit(1)

# assume if we're not -c we're performing an update.
# if we're not forcing, we need to check any previous failed attempts
#
if d.needs_fw_update() or force:
    try:
        do_print ('%s: %s: %s: Firmware Update Required [%s]' % (
                  device_name, d.get_model(), d.get_serial(),
                  d.get_firmware()))
        d.do_fw_update(force = force)
    except FirmwareUpdateException, what:
        disk_fw_context.mark_failed()
        print what
        sys.exit(1)
    except Exception:
        disk_fw_context.mark_failed()
        do_print ('%s: Firmware update failed' % device_name)
        sys.exit(1)

    if disk_fw_cfg.has_entry(d.get_model()):
        fw = disk_fw_cfg.get_entry(d.get_model()).get_firmware()
    else:
        fw=''

    disk_fw_context.mark_success()

    do_print ('%s: %s: %s: Firmware Update from %s to %s successful' % (
              device_name, d.get_model(), d.get_serial(),
              d.get_firmware(), fw))
