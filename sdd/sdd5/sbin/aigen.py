#!/usr/bin/python

#import sys, getopt, re, os
import getopt
from sys import exit, argv
from os import  popen, WEXITSTATUS
from aigen_common import *

motherboard = execute_hwtool_query('motherboard')
if motherboard == 'BOB-MOBO':
    from aigen_bob import *
else:
    from aigen_sh import *


def usage():
    print """usage: %s -i [-l NEXT_BOOT_ID]
usage: %s -m -d BOOT_DISK [-L LAYOUT] [-l NEXT_BOOT_ID]
    
NEXT_BOOT_ID: 1 or 2
LAYOUT: STD
BOOT_DISK:  /dev/sda or /dev/hda
    
Writes a grub.conf
With -m (for manufacture), temporarily mounts partitions as needed""" % (argv[0], argv[0])
    exit(1)

def main():
    manufacturing = 0
    boot_disk = ""
    next_boot = -1 
    has_default_disk = False
    layout = ""

    try:
        opts, args = getopt.getopt(argv[1:], "mid:l:L:")
    except getopt.GetoptError:
        usage()
        exit(2)

    for o, a in opts:
        if o == "-m":
            manufacturing = 1
        if o == "-i":
            has_default_disk = True
        if o == "-d":
            boot_disk = a
        if o == "-l":
            next_boot = int(a)
        if o == "-L":
            layout = a 

    if manufacturing and boot_disk == "":
        print "Please specify a default disk."
        usage()

    if manufacturing:
        generate_mfg_grub(boot_disk, next_boot)
    else:
        check_password()
        generate_grub(next_boot)

    if (has_default_disk==True) and (next_boot!=-1):
        call = popen("/opt/hal/bin/hal check_update_bios %d" % next_boot)
        output = call.read()
        code = call.close()
        if code:
            if WEXITSTATUS(code) == 1:
               print '%s' %(output)
               popen("/opt/hal/bin/hal downgrade_bios")
        
    exit(0)

if __name__ == "__main__":
            main()

