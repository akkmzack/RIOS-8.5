#!/usr/bin/env python
#
# Read LSI Controller/Expander FW and compute md5sums.
#
# (C) Copyright 2010 - 2012 Riverbed Technology, Inc.
# All rights reserved.
#

import os
import sys
import time
import traceback

from struct import *
from subprocess import *
from optparse import OptionParser

#
# Classes and globals
#

# create new class to overload "print" statements to go to screen and logfile
class tee_log:
    def __init__(self, stdout, filename):
        self.stdout = stdout
        self.logfile = open(filename, 'w')
    
    def write(self, text):
        self.stdout.write(text)
        self.logfile.write(text)
    
    def close(self):
        self.stdout.close()
        self.logfile.close()
    
    def flush(self):
        self.stdout.flush()
        self.logfile.flush()


#
# Defines/Constants
#
SHELL = "/bin/bash"
LSPCI = "/sbin/lspci"
SETPCI = "/sbin/setpci"

DEBUG_LEVEL_NONE = 0
DEBUG_LEVEL_ERROR = 1
DEBUG_LEVEL_WARNING = 2
DEBUG_LEVEL_INFO = 3
DEBUG_LEVEL_VERBOSE = 4

LSIUTIL_MIN_MAJOR_VERSION = 1
LSIUTIL_MIN_MINOR_VERSION = 65

LSI_COMMAND_EXIT = 0
LSI_COMMAND_IDENTIFY = 1
LSI_COMMAND_DOWNLOAD_FW = 2
LSI_COMMAND_UPLOAD_FW = 3
LSI_COMMAND_DOWNLOAD_BIOS = 4
LSI_COMMAND_UPLOAD_BIOS = 5
LSI_COMMAND_SCAN = 8
LSI_COMMAND_DISPLAY = 16
LSI_COMMAND_DIAGS = 20
LSI_COMMAND_DISPLAY = 47
LSI_COMMAND_RESET = 99

LSI_DIAG_COMMAND_DOWNLOAD = 20
LSI_DIAG_COMMAND_UPLOAD = 24

LSI_EXPANDER_FW_BUFFER_ID = 0
LSI_EXPANDER_MFG_BUFFER_ID = 131

TMP_FILE_NAME = "lsi_fw_tmp.read"

MD5SUM_DICT = dict([
    # MPT BIOS Versions
    ("3777c3cf1e1d6e0879d0efa5f8ef0fbb", ("BIOS", "6.28.00.00 2009.02.03")),
    ("36d1bbc179376d2f1778330f16aa8f16", ("BIOS", "7.17.00.00 2011.02.18")),
    ("b6606bcb6d3ffe77883487b96071bf23", ("BIOS", "7.21.00.00 2011.08.11")),
    ("89d4dd2b3da2e42a42ee509ec10ce1f8", ("BIOS", "7.25.00.00 2012.02.17")),
	    #  -- Yellowtail MPTBIOS
    ("4b44e9eb4fb3bdf4d73bb6b7d7f66b9d", ("BIOS", "7.25.00.00 2012.02.17")),
    
    # Controller FW Versions
    ("fabfa2cd9c310cc456e19dfcd0c7ce54", ("Controller", "SAS1 Phase17")),
    ("8ad68a65893fc6c35e9c8c56c1e56de4", ("Controller", "SAS2 Phase9-exp")),
    ("246624574bb95bee8a824575a387572b", ("Controller", "SAS2 Phase13")),
    ("81fc01b8586c281cbcef7897d4db9364", ("Controller", "SAS2 Phase9")),
 
    # Expander FW Versions
    ("5c6d0fd989d7a7c0a48c199f8404f83c", ("Expander", "SAS2 Phase5")),
    ("fa4cfc003aaf4a1c68bcc1edc7e2ea95", ("Expander", "SAS2 Phase10.1")),
    ("f58dd79c2053fc9fce8e34dc887cb0c9", ("Expander", "SAS2 Phase11.1")),
    ("eb8cd2c48eafdedb81ccdde282e88520", ("Expander", "SAS2 Phase12")),
	    #  -- Yellowtail 2x36 Expander firmware
    ("4c128fabb5aa79eee90d1766678d1622", ("Expander", "SAS2 Phase13")),
    
    # Expander Config Files
    ("24f4a97a176a57691572562a86b30f4a", ("Config", "mfg1014.bin")),
    ("a11ca0b7e41df7f282a0bc35085badc7", ("Config", "mfg0604.bin")),
    ("8155f19d127660070fd1252900d75cfe", ("Config", "mfg0611.bin")),
    ("5e1790bc5b3e583bdda4cfa2756cc6ce", ("Config", "mfg_BP12_0719.bin")),
	    #  -- Yellowtail 2x36 Expander config (x4)
    ("d6698c371d3e7fd5b4154e2f8888b114", ("Config", "mfg_exp_u27_07302012.bin")),
    ("b1710997c768af7bec33e607a6bb0ce6", ("Config", "mfg_exp_u27_07302012.bin")),
    ("b997bef3d5af3cad99af96593d355e1e", ("Config", "mfg_exp_u27_07302012.bin")),
    ("76f9951073b5e67dfb431e936aef1425", ("Config", "mfg_exp_u27_07302012.bin"))
    ])

#
# Lookup an md5sum value.
#
def md5sum_lookup(md5sum_key):
    try:
        md5sum_list = MD5SUM_DICT[str(md5sum_key)]
        md5sum_type = md5sum_list[0]
        md5sum_val = md5sum_list[1]
    except KeyError, e:
        md5sum_type = "Unknown"
        md5sum_val = "Unknown"
    
    return (md5sum_type, md5sum_val)


#
# Delete a file (like rm -f)
#
def rm_file(fname):
    try:
        os.remove(fname)
    except OSError, e:
        pass
    
#
# Read the controller firmware for the specified LSI controller and store in
# into the specified filename.
#
def controller_fw_read(port, fname):
    cmd = "%s -p %d -f %s %d" \
          % (options.lsiutil, port, fname, LSI_COMMAND_UPLOAD_FW)
    pipe1 = Popen([cmd], stdout=PIPE, shell=True, executable="%s" \
                  % (SHELL))
    pipe1_out = pipe1.communicate()[0]
    if (options.debug >= DEBUG_LEVEL_VERBOSE):
        print "%s" % (pipe1_out)


#
# Read the BIOS for the specified LSI controller and store in into the
# specified filename.
#
def controller_bios_read(port, fname):
    cmd = "%s -p %d -f %s %d" \
          % (options.lsiutil, port, fname, LSI_COMMAND_UPLOAD_BIOS)
    pipe1 = Popen([cmd], stdout=PIPE, shell=True, executable="%s" \
                  % (SHELL))
    pipe1_out = pipe1.communicate()[0]
    if (options.debug >= DEBUG_LEVEL_VERBOSE):
        print "%s" % (pipe1_out)


#
# Query the Version string in the controller BIOS and FW.
# Return touple with (active-FW-str, FW-image-str, BIOS-str).
#
def controller_sw_version_get(port):
    cmd = "%s -p %d -a 0,0 %d" % (options.lsiutil, port, LSI_COMMAND_IDENTIFY)
    pipe1 = Popen([cmd], stdout=PIPE, shell=True, executable="%s" % (SHELL))
    pipe1_out = pipe1.communicate()[0]
    if (options.debug >= DEBUG_LEVEL_VERBOSE):
        print "%s" % (pipe1_out)
    
    pipe_lines = pipe1_out.splitlines()
    active_version_raw = "Not found"
    active_version = ""
    firmware_version = "Not found"
    bios_version = "Not found"
    bios_version_date = "Not found"
    for line_index in range(len(pipe_lines)):
        line = pipe_lines[line_index]
        line_split = line.split()
        if (len(line_split) < 1):
            # ignore blank lines
            continue
        
        if (line_split[0] == "Current"):
            # Found the starting line for version info
            if (options.debug >= DEBUG_LEVEL_VERBOSE):
                print "Current: '%s'." % (line_split)
            active_version_raw = line_split[5]
            active_version = line_split[6]
            active_version_str = "%s %s" % (active_version_raw, active_version)
            continue
            
        if (line_split[0] == "Firmware"):
            # Found FW version
            if (options.debug >= DEBUG_LEVEL_VERBOSE):
                print "FW: '%s'." % (line_split)
            firmware_version_str = line_split[4]
            continue
            
        if (line_split[0] == "x86"):
            # Found BIOS version
            if (options.debug >= DEBUG_LEVEL_VERBOSE):
                print "BIOS: '%s'." % (line)
            bios_version = line_split[5]
            bios_version_date = line_split[6]
            bios_version_str = "%s %s" % (bios_version, bios_version_date)
            continue

    return (active_version_str, firmware_version_str, bios_version_str)


#
# Read the expander firmware for the specified LSI controller/expander
# pair and store in into the specified filename.
#
def expander_fw_read(port, expander_id, fname, buffer_id):
    cmd = "%s -p %d -f %s -a %d,%d,%d,,%d%d%d %d" \
          % (options.lsiutil, port, fname, LSI_DIAG_COMMAND_UPLOAD,
             expander_id, buffer_id, LSI_COMMAND_EXIT,
             LSI_COMMAND_EXIT, LSI_COMMAND_EXIT, LSI_COMMAND_DIAGS)
    pipe1 = Popen([cmd], stdout=PIPE, shell=True, executable="%s" \
                  % (SHELL))
    pipe1_out = pipe1.communicate()[0]
    if (options.debug >= DEBUG_LEVEL_VERBOSE):
        print "%s" % (pipe1_out)

def display_controller_ver( controllerc ):
    (active_ver_str, fw_ver_str,bios_ver_str) = controller_sw_version_get(controllerc + 1)
    print "Controller #%d Versions :" % (controllerc + 1)
    print "   BIOS image      = %s." % (bios_ver_str)
    print "   Active firmware = %s." % (active_ver_str)
    print "   Firmware image  = %s." % (fw_ver_str)


def display_controller_BIOS_md5( controllerc ):
    # Compute Controller BIOS md5sum
    rm_file(TMP_FILE_NAME)
    controller_bios_read(controllerc + 1, TMP_FILE_NAME)
    cmd = "%s %s" % (options.md5sum, TMP_FILE_NAME)
    pipe1 = Popen([cmd], stdout=PIPE, shell=True, executable="%s" \
                  % (SHELL))
    pipe1_out = pipe1.communicate()[0]
    if (options.debug >= DEBUG_LEVEL_VERBOSE):
        print "%s" % (pipe1_out)
    md5sum_val = pipe1_out.split(" ")[0]
    (md5sum_type, md5sum_match) = md5sum_lookup(md5sum_val)
    print "   BIOS md5sum     = %s (%s)." % (md5sum_val, md5sum_match)
    rm_file(TMP_FILE_NAME)

def display_controller_FW_md5( controllerc ):
    # Compute Controller FW md5sum
    controller_fw_read(controllerc + 1, TMP_FILE_NAME)
    cmd = "md5sum %s" % (TMP_FILE_NAME)
    pipe1 = Popen([cmd], stdout=PIPE, shell=True, executable="%s" \
                  % (SHELL))
    pipe1_out = pipe1.communicate()[0]
    if (options.debug >= DEBUG_LEVEL_VERBOSE):
        print "%s" % (pipe1_out)
    md5sum_val = pipe1_out.split(" ")[0]
    (md5sum_type, md5sum_match) = md5sum_lookup(md5sum_val)
    print "   FW md5sum       = %s (%s)." % (md5sum_val,
                                            md5sum_match)
    rm_file(TMP_FILE_NAME)


def found_expanders():
    #
    # now figure out how many expanders there are for this controller
    # and grab info from each expander.
    #
    cmd = "%s -p %d -a %d,,0,0,0 %d" \
          % (options.lsiutil, controllerc + 1, LSI_DIAG_COMMAND_UPLOAD,
             LSI_COMMAND_DIAGS)
    pipe1 = Popen([cmd], stdout=PIPE, shell=True,
                  executable="%s" % (SHELL))
    pipe1_out = pipe1.communicate()[0]
    if (options.debug >= DEBUG_LEVEL_VERBOSE):
        print "%s" % (pipe1_out)
    pipe1_out = pipe1_out.splitlines()
    expander_list = []
    found = False
    for loopc in range(len(pipe1_out)):
        curr_line = pipe1_out[loopc]
        
        # skip blank lines
        if (curr_line == ""):
            continue
        
        # look for line starting with B___T as marker to start processing
        if (found):
            product = curr_line[32:38]
            version = curr_line[49:]
            device_id = curr_line.split(".")[0]
            if (product == "Bobcat"):
                expander_list.append((int(device_id, 10), version))
        else:
            if (curr_line[5:10] == "B___T"):
                found = True
    return expander_list

def display_expander_FW_md5( controllerc, expander_id ):
    # Compute Expander FW md5sum
    expander_fw_read(controllerc + 1, expander_id, TMP_FILE_NAME,
                     LSI_EXPANDER_FW_BUFFER_ID)
    cmd = "md5sum %s" % (TMP_FILE_NAME)
    pipe1 = Popen([cmd], stdout=PIPE, shell=True, executable="%s" \
                  % (SHELL))
    pipe1_out = pipe1.communicate()[0]
    if (options.debug >= DEBUG_LEVEL_VERBOSE):
        print "%s" % (pipe1_out)
    md5sum_val = pipe1_out.split(" ")[0]
    (md5sum_type, md5sum_match) = md5sum_lookup(md5sum_val)
    print "      FW md5sum    = %s (%s)." % (md5sum_val,
                                            md5sum_match)
    rm_file(TMP_FILE_NAME)


def display_expander_Config_md5( controllerc, expander_id ):
    # Compute Expander Config File md5sum
    expander_fw_read(controllerc + 1, expander_id, TMP_FILE_NAME,
                     LSI_EXPANDER_MFG_BUFFER_ID)
    cmd = "md5sum %s" % (TMP_FILE_NAME)
    pipe1 = Popen([cmd], stdout=PIPE, shell=True, executable="%s" \
                  % (SHELL))
    pipe1_out = pipe1.communicate()[0]
    if (options.debug >= DEBUG_LEVEL_VERBOSE):
        print "%s" % (pipe1_out)
    md5sum_val = pipe1_out.split(" ")[0]
    (md5sum_type, md5sum_match) = md5sum_lookup(md5sum_val)
    print "     *MFG md5sum   = %s (%s)." % (md5sum_val,
                                            md5sum_match)
    print "     *Riverbed refers to these as \"config\" or \"bin\" files"

    rm_file(TMP_FILE_NAME)
    
def requested_xpndr( user_option, controllerc, expanderc ):
	# This assumes each controller has one, or two, expanders
	# Future products, that might have relationships greater
	# that 1:2 should modify the function to accomodate that. 
    if(user_option == 1 and controllerc == 0 and expanderc == 0):
        return True
    if(user_option == 2 and controllerc == 0 and expanderc == 1):
        return True
    if(user_option == 3 and controllerc == 1 and expanderc == 0):
        return True
    if(user_option == 4 and controllerc == 1 and expanderc == 1):
        return True
    return False

def requested_ctrl( user_option, controllerc ):
    if(user_option == 1 and controllerc == 0):
        return True
    if(user_option == 2 and controllerc == 1):
        return True
    return False

def print_xpndr_banner( version, controllerc, expanderc ):
    print "   Expander #%d (Controller #%d) :" % ((expanderc + 1), (controllerc + 1))
    print "      FW Version   = %s (Phase%d.%s)." \
      % (version, int(version[0:2], 16), int(version[2:], 10))

#
# Main program starts here
#

# Set up command line args
parser = OptionParser(version="%prog Version 0.6")

# command line parser options
parser.add_option("-d", "--debug", action="store", type="int",
                  dest="debug", default="0",
                  help="Set debug level, 0 is none")
parser.add_option("-i", "--identify", action="store", type="string",
                  dest="identify", default="",
                  help="Identify this specific MD5SUM value only")
parser.add_option("-l", "--logfile", action="store", type="string",
                  dest="logfile", default="",
                  help="Log stdout to this file (like Unix tee command)")
parser.add_option("-m", "--md5sum", action="store", type="string",
                  dest="md5sum", default="md5sum",
                  help="path to md5sum, default is 'md5sum'.")
parser.add_option("-u", "--lsiutil", action="store", type="string",
                  dest="lsiutil", default="./lsiutil",
                  help="path to lsiutil, default is ./lsiutil.")
parser.add_option("-c", "--controller_bios_md5", action="store", type="int",
                  dest="ctrl_bios", default=0,
                  help="only show the controller BIOS md5")
parser.add_option("-f", "--controller_FW_md5", action="store", type="int", 
                  dest="ctrl_fw", default=0,
                  help="only show the controller FW md5")
parser.add_option("-x", "--expander_FW_md5", action="store", type="int", 
                  dest="xpndr_fw", default=0,
                  help="only show the expander FW md5")
parser.add_option("-y", "--expander_config_md5", action="store", type="int", 
                  dest="xpndr_config", default=0,
                  help="only show the expander config md5")

                  
(options, args) = parser.parse_args()

# Check status of parsing
if len(args) != 0:
    sys.exit("Unknown arguments '%s'. Exiting." % (args))

# log stdout like tee
if (options.logfile != ""):
    tee = tee_log(sys.stdout, options.logfile)
    sys.stdout = tee

try:
    #
    # Sanity checking
    #
    if (not os.path.exists(options.lsiutil)):
        sys.exit("%s not found. Use the '-u' option to specify a different "\
                 "path." % (options.lsiutil))
    
    #
    # make sure we are using version 1.65 or above and number of controllers
    #
    cmd = "%s %d" % (options.lsiutil, LSI_COMMAND_EXIT)
    pipe1 = Popen([cmd], stdout=PIPE, shell=True, executable="%s" % (SHELL))
    pipe1_out = pipe1.communicate()[0]
    if (options.debug >= DEBUG_LEVEL_VERBOSE):
        print "%s" % (pipe1_out)
    pipe1_out = pipe1_out.splitlines()
    loopc = 0
    while (pipe1_out[loopc] == ""):
        # skip blank lines
        loopc += 1
    
    # the first non blank line has the version string
    line = pipe1_out[loopc].split(",")
    if (len(line) < 4):
        sys.exit("\nUnsupported version of LSIUtile used. Must use version " \
                 "%d.%d or above.\n" % (LSIUTIL_MIN_MAJOR_VERSION,
                                        LSIUTIL_MIN_MINOR_VERSION))
    version_string = line[1].strip()
    version_string = version_string.split(" ")[1]
    lsiutil_major_version = int(version_string.split(".")[0].strip(), 10)
    lsiutil_minor_version = int(version_string.split(".")[1].strip(), 10)
    if ((lsiutil_major_version < LSIUTIL_MIN_MAJOR_VERSION)
        or ((lsiutil_major_version == LSIUTIL_MIN_MAJOR_VERSION)
            and (lsiutil_minor_version < LSIUTIL_MIN_MINOR_VERSION))):
        print "LSIUtil version %d.%d is too old. Minimum required version " \
              "is %d.%d." % (lsiutil_major_version, lsiutil_minor_version,
                             LSIUTIL_MIN_MAJOR_VERSION,
                             LSIUTIL_MIN_MINOR_VERSION)
        sys.exit(1)
    
    # The next non blank line has the number of controllers founs
    loopc += 1
    while (pipe1_out[loopc] == ""):
        # skip blank lines
        loopc += 1
    line = pipe1_out[loopc].split(" ")
    if ((line[1] == "MPT") and ((line[2] == "Port") or (line[2] == "Ports"))
        and (line[3] == "found")):
        num_lsi_ports = int(line[0], 10)
    else:
        sys.exit("Could not determine the number is LSI controllers.")
    
    # Display LSIUtil Version
    print "LSIUtil version    = %d.%d" % (lsiutil_major_version,
                                           lsiutil_minor_version)
    
    if (options.identify != ""):
        (md5sum_type, md5sum_match) = md5sum_lookup(options.identify)
        print ""
        print "MD5SUM '%s' = %s, %s." \
              % (options.identify, md5sum_type, md5sum_match)
        print ""
        sys.exit(0)
    
    # Record the version of FW/BIOS on each LSI controller
    print ""
    for controllerc in range(num_lsi_ports):
        if ( (not options.xpndr_fw) and (not options.xpndr_config )):
            if (options.ctrl_bios and requested_ctrl(options.ctrl_bios, controllerc)):
                display_controller_BIOS_md5( controllerc )
                sys.exit(0)
            elif(options.ctrl_fw and requested_ctrl(options.ctrl_fw, controllerc)):
                display_controller_FW_md5( controllerc )
                sys.exit(0)
                
        if not (options.ctrl_bios) and not (options.ctrl_fw) \
            and not (options.xpndr_fw) and not (options.xpndr_config):
            display_controller_ver( controllerc )
            display_controller_BIOS_md5( controllerc )
            display_controller_FW_md5( controllerc )
        
        expander_list = found_expanders()
        
        # get data from each expander
        for expanderc in range(len(expander_list)):
            (expander_id, version) = expander_list[expanderc]
            if (options.xpndr_fw and requested_xpndr(options.xpndr_fw, controllerc, expanderc)):
                print_xpndr_banner( version, controllerc, expanderc )
                display_expander_FW_md5( controllerc, expander_id )
                sys.exit(0)
            elif (options.xpndr_config and requested_xpndr(options.xpndr_config, controllerc, expanderc)):
                print_xpndr_banner( version, controllerc, expanderc )
                display_expander_Config_md5( controllerc, expander_id )
                sys.exit(0)
                
            if not (options.ctrl_bios) and not (options.ctrl_fw) \
                and not (options.xpndr_fw) and not (options.xpndr_config):
                print_xpndr_banner( version, controllerc, expanderc )
                display_expander_FW_md5( controllerc, expander_id )
                display_expander_Config_md5( controllerc, expander_id )
        
        print ""
    
except Exception, e:
    print ""
    print str(e)
    print ""
    cont = raw_input("Display stack trace for debugging (y/n)? ")
    if (cont == 'y' or cont == 'Y'):
        print ""
        traceback.print_exc()
    print ""

sys.exit(0)
