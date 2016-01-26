#!/usr/bin/python

#
#  Filename:  $Source$
#  Revision:  $Revision: 94137 $
#  Date:      $Date: 2011-12-05 15:10:41 -0800 (Mon, 05 Dec 2011) $
#  Author:    $Author: timlee $
#
#  (C) Copyright 2003-2008 Riverbed Technology, Inc.
#  All rights reserved.
#

#
# This script is used to read the serial number stored in the eeprom
#

import sys
from os import path, unlink
from re import compile, search
from string import find
from time import strftime, localtime, sleep
import subprocess


class backplane(object):
    def __init__(self):
        self.backplane_id = 3
        t = strftime("%a%d%b%Y%H_%M_%S", localtime())

        self.ifile = "/tmp/%s.in" % t
        self.ipmitool = None
        ipmitool_paths = ( '/mfg/ipmitool', '/sbin/ipmitool', '/usr/bin/ipmitool')
        for p in ipmitool_paths:
            if path.exists(p):
                self.ipmitool = p
                break
        if self.ipmitool is None:
            raise Exception('cannot find ipmitool in %s' % str(ipmitool_paths))

        self.rvbd_sec = '[RVBD section] Riverbed Serial : '
        self.orig_line = ''
        # This is used while writing, it isnt a useless var
        self.mitac_len = 0

    def set_backplane_id(self, id):
        self.backplane_id = id

    def read_eeprom_content(self):
        # Read the EEPROM backplane
        cmd = (self.ipmitool, 'fru', 'read', str(self.backplane_id), self.ifile)
        output = subprocess.Popen(cmd, stdout=subprocess.PIPE).communicate()[0].strip()

        #Make sure there was no error
        i = 0
        err = False
        while i < 5:
            if None == search(compile("Fru Size[\s]+: [\d]+ bytes[\s]+Done"), output):
                print "Could not read the EEPROM data"
                try:
                    unlink(self.ifile)
                except:
                    pass
                i += 1
                err = True
                print "Could not read EEPROM data, retrying"
                sleep(5)
            else:
                if None != search(compile("FRU Read failed"), output):
                    #retry as likely ipmitool timed out
                    print "Probably ipmitool timeout, retrying"
                    i += 1
                    err = True
                    sleep(5)
                else:
                    err = False
                    break

        if err:
            print "Could not read EEPROM contents, exiting"
            return 1

        f = open(self.ifile, 'rb')
        self.orig_line = f.readline()
        file_len = len(self.orig_line)
        # Naming mitac section, though it may be inclusive of RVBD section as well
        count = 0
        # Need to find the length of the mitac section as
        # Note that its likely that the riverbed string is already
        # present in the EEPROM. What this does is to read the ascii chars
        # in the range 32-128, After the mitac and RVBD section, the file is full of junk chars
        for char in self.orig_line:
            decchar = ord(char)
            if decchar > 31 and decchar < 128:
                self.mitac_len = count

            count += 1

        f.close()

        # clear out the file
        unlink(self.ifile)
        return 0


    def get_serial_eeprom(self):
        # Get the serial number from the EEPROM
        start = find(self.orig_line, self.rvbd_sec)
        serial = ""
        if start > -1:
            start += len(self.rvbd_sec)
            while start < len(self.orig_line) and ord(self.orig_line[start]) > 31 and ord(self.orig_line[start]) < 128:
               serial += self.orig_line[start]
               start += 1

        return serial.strip()    

def usage(prog_name):
    print "./read_eeprom_serial"

def main():
    if len(sys.argv) > 1:
        usage(sys.argv[0])
        sys.exit(1)
        
    bplane = backplane()
    if bplane.read_eeprom_content():
        sys.exit(1)

    print bplane.get_serial_eeprom()
        
if __name__ == "__main__":
    main()
