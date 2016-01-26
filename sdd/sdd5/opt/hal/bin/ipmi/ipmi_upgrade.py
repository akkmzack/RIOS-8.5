#!/usr/bin/env python
#

###############################################################################
#
# ipmi_upgrade.py
#
# Script that reads the ipmi.xml file and gets the versions of the IPMI
# SDR and FW files for this appliance. The appliance associates the 
# files to a motherboard via a regex, so if we ever need to associate
# the same files for different revisions of a motherboard, we can 
# easily do so.
#
# The SDR file is a sensor list, which tells IPMI what sensors to look at
# and how to log events for those sensors to the SEL (system event log).
#
# The FW governs the control of the BMC (Baseboard management controller)
# which handles sensor control, the motherboard watchdog, and onboard
# relay interfaces.
#
#
###############################################################################
from IpmiLib import *
from time import sleep
from os.path import exists
from sys import exit
from getopt import getopt, GetoptError
from xml.dom.minidom import parse
from re import compile as recompile
import sys

from rrdm_logging import *

###############################################################################
#
# get_motherboard
#
# call into hwtool to find out what platform we're running on.
#
###############################################################################
def get_motherboard():
    hwtool_path = '/opt/hal/bin/hwtool.py'
    cmdline     = '%s -q motherboard' % hwtool_path

    if not exists(hwtool_path):
        raise GeneralError ('Unable to find hwtool executable')

    pf = popen (cmdline)
    output  = pf.read()
    rcode = pf.close()

    if rcode == None and output != '':
        return output.strip()
    else:
        raise GeneralError('Unable to determine motherboard %s, skipping IPMI fw checks' %
                           output.strip())

###############################################################################
#
# get_files_from_image
#
# get the paths to the ipmi sdr/fw files associated with this
# image for this motherboard
#
# returns a tuple of (fw, sdr) where these are absolute paths.
#
# (None, None) is returned if there are no images for this platform
# (such as the dell units, where we don't do much with IPMI firmware or SDR
# today)
#
###############################################################################
def get_files_from_image(motherboard):
    base_ipmi_file_loc = '/opt/hal/lib/ipmi'
    ipmi_config_path   = '%s/ipmi.xml' % base_ipmi_file_loc

    if not exists (ipmi_config_path):
        raise GeneralError('IPMI configuration file %s does not exist' % ipmi_config_path)

    dom = parse (ipmi_config_path)
    entries = dom.getElementsByTagName('mobo')
    if not entries:
        raise GeneralError ('Invalid IPMI configuration file %s' % ipmi_config_path)
    
    for entry in entries:
        # look for the mobo tag and find the 
        # entry that matches our motherboard via the regex in the xml 
        # node
        entry_name_pattern = entry.getAttribute('name')
        if entry_name_pattern != '':
            re = recompile(entry_name_pattern)
            if re.match(motherboard):
                try:
                    sdr = entry.getElementsByTagName('sdr')[0].getAttribute('fname')
                    fw = entry.getElementsByTagName('fw')[0].getAttribute('fname')
                except IndexError:
                    raise GeneralError ('Invalid ipmi xml file for motherboard: %s' %
                                        motherboard)
                return ('%s/%s' % (base_ipmi_file_loc, fw), 
                        '%s/%s' % (base_ipmi_file_loc, sdr))
        
    return (None, None)

###############################################################################
# get_upgrade_info
#
# returns a tuple of (version, do_update)
#
# Can raise a GeneralException:
#    - Invalid File Type
#    - IPMI File not found error
#
###############################################################################
def get_upgrade_info(isi, type, file):
    current_fw_file=IpmiFile(file)
    do_upgrade = False

    if type == 'fw':
        version = isi.get_ipmi_fw_version()
    elif type == 'sdr':
        version = isi.get_ipmi_sdr_version()
    else:
        raise GeneralError ('Invalid IPMI file type %s' % type)

    if not exists(file):
        raise GeneralError ('IPMI %s %s file not found' % (type, file))

    result = compare_ipmi_versions (version,
                                    current_fw_file.get_version())
    if result == 'incompatible':
        # we get this if the version of the software in the BMC does not match
        # the configuration file. We'll always apply the version that the image
        # says to run in this case.
        # 
        do_upgrade = True
    elif result in [ 'same', 'older' ]:
        do_upgrade = False
    else:
        do_upgrade = True

    return (version, do_upgrade)


###############################################################################
#
# check_ipmi
#
# Compare the given IPMI file type ('sdr' or 'fw') registered in the image
# against what is currently installed in the appliance.
#
# If the file in the image is newer, update the file, and verify the update
# by reading back the version and comparing with the verion derived from the 
# file.
#
###############################################################################
def check_ipmi (isi, type, file):

    # check if we need to do anything
    #
    (version, do_upgrade) = get_upgrade_info(isi, type, file)

    if do_upgrade:
        print 'Appliance IPMI %s file is out of date, version is [%d:%d]' % (type,
                version[0], version[1])

        print 'IPMI %s upgrade is necessary' % type
        if type == 'fw':
            isi.upgrade_fw_file(file)
        elif type == 'sdr':
            isi.upgrade_sdr_file(file)

        print 'Verifying %s update..' % type
        # give it a sec
        sleep (1)

        # get the version we expect from the file
        current_fw_file=IpmiFile(file)

        isi_new = IpmiSystem()
        if type == 'fw':
            version = isi_new.get_ipmi_fw_version()
        elif type == 'sdr':
            version = isi_new.get_ipmi_sdr_version()

        result = compare_ipmi_versions (version,
                                        current_fw_file.get_version())
        if result != 'same':
            print 'Failed to update %s file' % type
        else:
            print 'New IPMI %s version : [%d:%d]' % (type, version[0], version[1])
    else:
        print 'IPMI %s is up to date [%d:%d]' % (type, version[0], version[1])


###############################################################################
# Main:
#
# Create an IPMI system object and catch any exceptions
#
# note:
# typically called from init_hardware_phase2, since IPMI modules are needed
# phase2 is also run from rbtkmod which gets stdout directed to syslog.
#
###############################################################################
def usage():
    print 'ipmi_upgrade.py [-l] [-u] -a|-c'
    print ' -l : loads necessary IPMI modules'
    print ' -a : returns whether an upgrade is needed'
    print ' -c : compare versions and upgrade if out of date'
    print ' -u : unload modules when done' 
    print ' -a and -c are mutually exclusive'
    exit (0)

def cleanup_exit(code, unload):
    if unload:
        unload_ipmi_modules(True)

    exit (code)
    

# command line arguments

# should we load modules necessary for IPMI updates/versioning
load_modules = False
unload_modules = False

# should we go through the upgrade logic?
do_update = False

# gives the caller an indication of what should happen when they upgrade
# 
get_action   = False

for arg in sys.argv[1:]:
    if arg == "-l":
        load_modules = True
    elif arg == "-a":
        get_action = True
    elif arg == '-c':
        do_update = True
    elif arg == '-u':
        unload_modules = True
    else:
        usage()

# do not allow both an update and an action call
if do_update and get_action:
    usage()

# check if ipmi is supported
#
try:
    if not is_ipmi_supported():
        if get_action:
            print 'notsup'
        else:
            print 'IPMI is not supported, skipping fw/sdr upgrade checks.'

        # no need to cleanup, modules are loaded below.
        exit (0)
except GeneralError, what:
    print 'Hwtool error: unable to determine ipmi support'
    exit (1)


#
# find out what versions we currently support
# if there are no images, we just exit without doing anything
#
(fw_file, sdr_file) = get_files_from_image(get_motherboard())
if fw_file == None or sdr_file == None:
    if get_action:
        print 'noimages'
    else:
        print 'No IPMI images registered for this appliance'
    exit(0)

# if we need to load modules, do it before trying to access any 
# IPMI info
if load_modules:
    load_ipmi_modules()
    # give it a sec or two
    sleep (2)

# read IPMI system config and log appropriate errors if we can't
# get the IPMI versions from the BMC (fw and sdr)
#
try:
    isi = IpmiSystem()
except HalError, what:
    warn(what)
    exit (1)
except GeneralError, what:
    warn(what)
    exit (1)
except IpmiError, what:
    warn(what)
    cleanup_exit (1, unload_modules)

if isi == None:
    print 'Unable to create IPMI system object'
    cleanup_exit(1, unload_modules)

# handle command line actions 
# 
if get_action:
    try:
        (fw_vers, do_fw_upgrade) =  get_upgrade_info(isi, 'fw', fw_file)
        (sdr_vers, do_sdr_upgrade) =  get_upgrade_info(isi, 'sdr', sdr_file)
        if (do_fw_upgrade or do_sdr_upgrade):
            print 'needsupgrade'
        else:
            print 'uptodate'

    except GeneralError:
        print 'error'
        cleanup_exit (1, unload_modules)

elif do_update:
    # now check the FW and SDR files.
    # If we hit an error processing one file, we should still be able to 
    # process the other
    # check the fw first since if it is hosed, you won't be able to update the SDR.
    #

    try:
        check_ipmi(isi, 'fw', fw_file)
    except GeneralError, what:
        print what

    try:
        check_ipmi(isi, 'sdr', sdr_file)
    except GeneralError, what:
        print what


cleanup_exit (0, unload_modules)
