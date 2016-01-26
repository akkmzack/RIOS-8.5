#!/usr/bin/python

#
#  Filename:  $Source$
#  Revision:  $Revision: 5137 $
#  Date:      $Date: 2008-07-28 01:58:56 -0800 (Mon, 28 Jul 2008) $
#  Author:    $Author: munirb $
#
#  (C) Copyright 2003-2008 Riverbed Technology, Inc.
#  All rights reserved.
#

#
# This script is used to write the serial number stored in the eeprom
#

import sys
import read_eeprom_serial
from os import path
import subprocess
from re import compile, search
from string import find
from time import localtime, strftime, sleep

BACKPLANE_ID = 3
t = strftime("%a%d%b%Y%H_%M_%S", localtime())
TMP_OFILE = "/tmp/%s.out" % t

ipmitool = "/mfg/ipmitool"
if not path.exists(ipmitool):
    ipmitool = "/sbin/ipmitool"

EEPROM_WRITE = "%s fru write %s %s" % (ipmitool, BACKPLANE_ID, TMP_OFILE)
EEPROM_STATE = "%s raw 0x06 0x52 0x07 0x32 0x00 0x01 " % ipmitool


def set_eeprom_state(state="RO"):
    # Set the EEPROM to RW and RO as desired
    command = EEPROM_STATE
        
    if "RO" == state:
        command += "0x37"
    else:
        command += "0xFB"
    
    i = 0
    err = False
    while i < 5:
        dummy, output = subprocess.popen(command)
        output = output.read().strip()
        if "" != output:
            print "Can't set EEPROM to %s, retrying" % state
            i += 1
            sleep (5)
            err = True
        else:
            err = False
            break
            
    if err:
        print "Could not change EEPROM state, exiting"
        sys.exit(1)


def write_eeprom_content(mfserial, orig_line, rvbd_sec, replace=False):
    # Write the binary file with RVBD serial back into EEPROM
    global TMP_OFILE

    output_str = ''
    count = 0

    replace_str = "%s%s" % (rvbd_sec, mfserial)
    output_str += replace_str
    count += len(replace_str)

    # Final padding
    for n in range(len(orig_line) - count):
        output_str += chr(255)

    f = open(TMP_OFILE, 'wb')
    f.write(output_str)
    f.close()
    
    i = 0
    err = False
    while i < 5:
        # Time to write it back to the EEPROM image
        dummy, output = subprocess.popen(EEPROM_WRITE)
        output = output.read().strip()
        if None == search(compile("Size to Write[\s]+: [\d]+ bytes$"), output):
            print "Could not write the EEPROM data, retrying"
            i += 1
            sleep (5)
            err = True
        else:
            if None != search(compile("FRU Read failed"), output):
                #retry as likely ipmitool timed out
                print "ipmitool timeout encountered, retrying"
                i += 1
                sleep (5)
                err = True
            else:
                err = False
                break

    if err:
        print "Cannot write back to the EEPROM, exiting"
        sys.exit(1)

    # clear out the files
    command = '/bin/rm -f %s' % TMP_OFILE
    dummy, output = subprocess.popen(command)

def usage():
    print "./write_eeprom_serial --get-serial"
    print "./write_eeprom_serial --set-serial <serial>"

def main():
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        usage()
        sys.exit(1)
    elif '--get-serial' == sys.argv[1]:
        bplane = read_eeprom_serial.backplane()
        if bplane.read_eeprom_content():
            sys.exit(1)

        print bplane.get_serial_eeprom()
        
    elif '--set-serial' == sys.argv[1]:
        if len(sys.argv) < 3:
            usage()
            sys.exit(1)
        serial = sys.argv[2]
        bplane = read_eeprom_serial.backplane()
        if bplane.read_eeprom_content():
            sys.exit(1)

        eeprom_ser = bplane.get_serial_eeprom()
        orig_line = bplane.orig_line
        rvbd_sec = bplane.rvbd_sec
        if "" == eeprom_ser:
            set_eeprom_state("RW")
            write_eeprom_content(serial, orig_line, rvbd_sec, False)
            set_eeprom_state("RO")
        elif serial != eeprom_ser:
            set_eeprom_state("RW")
            write_eeprom_content(serial, orig_line, rvbd_sec, True)
            set_eeprom_state("RO")
        else:
            # EEPROM content is fine, move on
            sys.exit(0)
    else:
        usage()
        sys.exit(0)
        

if __name__ == "__main__":
    main()
