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
# This script is used to update the serial location
# and set it in the correct location
#

import sys
import read_eeprom_serial
from os import popen, path

EEPROM_FILE = '/var/opt/rbt/.eeprom_set'
WRITE_CMD = '/sbin/write_eeprom_serial.py --set-serial'
(PASS, FAIL) = range(2)


def set_serial(bplane):
    # If not present, check ID 5
    bplane.set_backplane_id(5)
    if bplane.read_eeprom_content():
        print "Unable to read EEPROM content"
        return FAIL
    serial = bplane.get_serial_eeprom()
    if serial == '':
        # Get the serial from mfdb and write it
        call = popen('/opt/tms/bin/mddbreq -v /config/mfg/mfdb query get - /rbt/mfd/serialnum')
        serial = call.read().strip()
        if serial == '' or call.close() != None:
            print "Could not get the serial from MFDB"
            return FAIL

        #If serial not present, time to write it
        call = popen('%s %s' % (WRITE_CMD, serial))
        output = call.read().strip()
        if output != '' or call.close() != None:
            print "Error updating the serial in EEPROM"
            return FAIL
    else:
        #Found the serial in other EEPROM, copy it over
        call = popen('%s %s' % (WRITE_CMD, serial))
        output = call.read().strip()
        if output != '' or call.close() != None:
            print "Error updating the serial in EEPROM"
            return FAIL
        else:
           print "Set serial to %s" % serial

    return PASS


def update_attempt_counter(attempt):
    call = popen('echo %s > %s' % (attempt, EEPROM_FILE))
    output = call.read().strip()
    if call.close() != None:
        print "Could not set the attempt value"
        return FAIL

    return PASS


def check_serial_state (tries):
    # Read EEPROM as we can have unlimited reads
    # It adds a few seconds to boot up, but makes sure serial is there
    bplane = read_eeprom_serial.backplane()
    if bplane.read_eeprom_content() == FAIL:
        print "Unable to read EEPROM content"
        return FAIL

    # Check if EEPROM present in ID 3
    serial = bplane.get_serial_eeprom()
    if serial == '':
        if set_serial(bplane) == FAIL:
            print "Could not write to the EEPROM"
            tries = int(tries) + 1
            update_attempt_counter(tries)
            return FAIL
        else:
            # Serial updated just create the file and set attempts
            print "Set the serial in the EEPROM"
    else:
        # If the file is ever deleted, create the file since serial is present
        print "Serial %s is already set in the system" % serial
 
    tries = "SET"
    if update_attempt_counter(tries) == FAIL:
        return FAIL

    return PASS


def main():
    tries = 0
    if path.exists(EEPROM_FILE):
        #Serial already present
        call = popen('cat %s' % EEPROM_FILE)
        tries = call.read().strip()
        # If 3 attempts already 
        if call.close() != None:
            print "Could not read EEPROM file, exiting"
            sys.exit(1)
        else:
            if tries == "SET":
                # EEPROM is already set in the correct place, exit
                sys.exit(0)
            elif int(tries) > 3:
                print "There maybe something wrong with the EEPROM, not retrying"
                sys.exit(1)
                

    # the file never existed, so serial has to be in the wrong place
    # or something happened and the file got deleted
    # or we still have a few retries left
    if check_serial_state(int(tries)) == FAIL:
        print "Could not set the EEPROM serial in the correct location"
        sys.exit(1)
        

if __name__ == "__main__":
    main()
