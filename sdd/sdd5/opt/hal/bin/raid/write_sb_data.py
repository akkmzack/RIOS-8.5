#!/usr/bin/env python

import os
import sys
import re
from time import sleep
from os import stat
from os.path import exists
from xml.dom.minidom import parse
from rrdm_super import RvbdSuperBlock
from rrdm_util import *

PREV_STATE = {}
SECTOR_SIZE = 512
MIN_HD_SIZE = 10     # This is the minimum disk size that a physical SSD or HD we use

class DiskConfig:
    def __init__(self, config_path=''):
        self.__disks       = {}
        self.__config_path = config_path

        self.__read_config()

    def get_disks(self):
        return self.__disks

    def __read_config(self):
        config_file = self.__config_path

        # write-config just before reading so that we minimize incorrect reads
        run_shell_cmd('/opt/hal/bin/raid/rrdm_tool.py --write-config')

        if config_file == '':
            config_file = "/config/disk_config.xml"

        try:
            stat(config_file)
            name = config_file
        except OSError:
            print 'Unable to find specs.xml'
            return False

        dom = parse(name)
        drives = dom.getElementsByTagName('disk')
        for drive in drives:
            port = int(drive.getAttribute('port'))
            serial = drive.getAttribute('serial')
            self.__disks[port] = serial


def get_current_data_written_to_disk(dname):
    """cat /sys/block/{dname}/stat
    """

    pattern = re.compile(' +')
    arg = "/sys/block/%s/stat" % dname
    if exists(arg):
        sysfs_out = run_shell_cmd("/bin/cat %s" % arg, True).split('\n')
    else:
        raise rrdm_error("No such file or directory")

    try:
        items = pattern.split(sysfs_out[0])
        value = int(items[6])
    except IndexError:
        value = 0

    return value * SECTOR_SIZE

def main():
    while True:
        sleep(1800)
        try:
            dc = DiskConfig('/config/disk_config.xml')
            dc_disks = dc.get_disks()
        except rrdm_error:
            # Couldnt read/write the config file, retry in the next interval
            continue

        hwdl = HwtoolDriveList()

        map = hwdl.get_drive_list()

        size_map = get_disk_list()

        for elem in map:
            dev = elem[1]
            dev_name = elem[2]
            try:
                sysfs_val = get_current_data_written_to_disk(dev_name)
            except ValueError:
                continue
            except rrdm_error:
                #Disk no longer in system
                port = dev[4:]
                try:
                    del PREV_STATE[port]
                except KeyError:
                    continue
                
            # If the disk size is < MIN_HD_SIZE and hwtool says its a disk
            # it has to be a virtual disk. None of our SSD's and HD's are
            # less than MIN_HD_SIZE in size. Skip these disks for wear 
            # level update or else it will mess up the partitions
            if int(size_map[dev]) < MIN_HD_SIZE:
                continue

            try:
                sb_obj = RvbdSuperBlock('/dev/%sp1' % dev)
                sb_val = sb_obj.get_sb_kvp('current_data_stored')
                port_val = sb_obj.get_port()
                if sb_val:
                    sb_val = int(sb_val)
                else:
                    # Set it to zero as its used for addition and needs an int value
                    sb_val = 0

                # The disk_config.xml file has no idea about this disk, skip it and retry
                if not dc_disks.has_key(port_val):
                    continue

                disk_serial = dc_disks[port_val]

                if PREV_STATE.has_key(port_val):
                    # Check to make sure that the previous disk is the same as the current
                    # Check serial to see if the disk is the same
                    if disk_serial == PREV_STATE[port_val][0]:
                        # Check to make sure that the disk was not removed and replaced during the poll interval
                        # if the value stored in PREV_STATE is > than the new value means the disk was removed for sure
                        # There may be a case that the value in PREV_STATE < new value due to a lot of IO after disk inserted
                        # but there is no way for me to figure that out
                        if PREV_STATE[port_val][1] < sysfs_val:
                            prev_val = PREV_STATE[port_val][1]
                            PREV_STATE[port_val] = (disk_serial, sysfs_val)
                            total = sb_val + sysfs_val - prev_val
                            sb_obj.add_sb_kvp(['current_data_stored', total])
                            continue
                
                # If you reach here, it means new disk OR start of script OR
                # same disk removed and reinserted in the poll interval
                PREV_STATE[port_val] = (disk_serial, sysfs_val)
                sb_obj.add_sb_kvp(['current_data_stored', sysfs_val + sb_val])
                
            except TypeError:
                # Riverbed superblock missing
                continue
            except rrdm_error:
                # Could not get the current value in the partition
                # Just retry 
                continue



if __name__ == "__main__":
    main()

