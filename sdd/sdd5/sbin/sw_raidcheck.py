#!/usr/bin/python

import os
from time import sleep
from rrdm_util import *
from rrdm_logging import *
import re
from sys import exit, argv

prog_name="sw_raidcheck"
enable_syslog()
init_logging (prog_name)

###############################################################################
# Util Paths
#
###############################################################################
hwtool_py="/opt/hal/bin/hwtool.py"
rrdm_tool_py="/opt/hal/bin/raid/rrdm_tool.py"

disk_regex=re.compile ("^disk")

model = get_model()
if model == '':
    rlog_warning ('Unable to determine appliance model, exiting')
    exit (1)

def get_drive_license_map():
    """Return a map of diskX=Licensed/Unlicensed/Error
    """
    try:
        licensed_drive = run_shell_cmd (hwtool_py + ' -q disk-license |grep disk', True)
    except rrdm_error, what :
        print what
        exit (1)

    licensed_map = {}
    for line in licensed_drive.strip().split('\n'):
        parts = line.split(' ')
        if len(parts) < 2:
            continue
        licensed_map[parts[0]] = parts[1]

    return licensed_map

# Function returns True or False.
# Needs to be invoked on every iteration of sw_raidcheck.py
def md_state_changed ():
    MD_PATH = '/sys/block/'
    ret_val = False
    try: 
	# Loop through /sys/block/
	for filename in os.listdir(MD_PATH):
	    # Look for devices named mdX where X is 0,1,2...
            if filename.startswith("md") == True:
                try:
                    md_id = int(filename[2:].strip())
                except ValueError:
                    rlog_warning ('Could not find md device id')
                    continue
            else:
                continue
            dev_str = '/sys/block/md%d/md/failed_disks' % (md_id)
            fail_disk = -1 
	    try:
	        # Get the value of each failed disk count  
		fail_disk = int(get_sysfs_param(dev_str))
	    except (OSError, IOError, ValueError):
                rlog_warning ('unable to find sysfs entry for device [%s]' % dev_str)
                continue

            # Use the correct file 
            path = '/var/tmp/failcount%d' % (md_id)

            # If file does not exist - e.g. on the first cycle,
            # create with the new value and exit
            if os.path.isfile(path) == False:
		try:
		    # Create the file with the new value
		    fd = open(path, 'w')
		    fd.write(str(fail_disk))
		    fd.close()
		except (OSError, IOError):
		    rlog_warning ('unable to write file [%s]' % path)
                    continue
            else: # Read the file's contents 
		try:
		    # Read the contents of the file
		    fd = open(path, 'r')
		    try:
		        old_fail_disk = int(fd.read())
                    except (ValueError):
		        fd.close()
                        # Delete the file for now.
                        # It will be ire-created on the next try 
                        os.unlink(path) 
                        return False 
                        
		    fd.close()
                    # Compare the contents of the new one and flag if different
                    if old_fail_disk != fail_disk:
                        if ret_val == False:
                            ret_val = True 
                    # Write the new value in the file again
		    fd = open(path, 'w')
		    fd.write(str(fail_disk))
		    fd.close()
		except (OSError, IOError):
		    rlog_warning ('unable to update file [%s]' % path)
                    continue

    except rrdm_error:
        rlog_warning ('Error getting failed_disk change')

    return ret_val 

def get_drive_list():
    global disk_regex
    list = []

    try:
	drive_list = run_shell_cmd (hwtool_py + ' -q disk=map |grep disk', True)
    except rrdm_error, what :
	print what
	exit (1)

    licensed_map = get_drive_license_map()

    # the -i output has the phsyical port and the bus number where we would 
    # look for info in sysfs
    dev_lines = drive_list.split('\n')
    rlog_info ('Scanning disk list')

    for line in dev_lines:
	port_bus = line.split(' ')
	try:
	    if port_bus != '':
		bus = port_bus[0]
		port = port_bus[1]
                if licensed_map.has_key(port):
                    licensed = licensed_map[port]
                else:
                    licensed = 'Error'
	    
		# only match disk entries, possibly expand this to know what type of
		# disk it is, so we can differentiate between flash/disk/ssd, which 
		# may have different uses in the system (right now we're only 
		# concerned with disks for raid management)
		#
		if disk_regex.match(port):
		    rlog_info('adding  port[%s] bus[%s] to disk list' % (port, bus))
		    list.append ((port, bus))
		
	except IndexError:
	    # if we get a malformed entry, ignore it.
	    # should probably log a message.
	    continue

    return list


def send_sighup_to_hald(pid):
    rlog_notice ('Sending SIGHUP to HALD [%d]' % pid)
    try:
        run_shell_cmd("/bin/kill -s sighup %s" % pid, False)
    except rrdm_error:
        rlog_warning("Could not send SIGHUP to rbt_hald, disk state may be inconsistent")


def get_pidof_rbt_hald():
    try:
        pid = int(run_shell_cmd("/sbin/pidof /opt/tms/bin/rbt_hald", True))
    except rrdm_error:
        rlog_notice("Could not get pidof rbt_hald, maybe process not running")
        pid = -1
    except ValueError:
        rlog_notice("Could not get pidof rbt_hald, process not running")
        pid = -1

    return pid

def send_sighup():
    pid = get_pidof_rbt_hald()
    if pid != -1:
	send_sighup_to_hald(pid)

def add_raid_disk(drive, drive_list={}):
    port        = drive[0]
    bus         = drive[1]
    drive_num   = port[4:]

    rlog_notice ('drive insertion notification for device [%s]' % port)
    rlog_notice ('Starting RAID auto rebuild on [%s]' % port)

    # Check to make sure that the diskX is usable via findbranding
    # Retry 3 times with 5 second interval
    retry = 0
    while retry < 3:
        try:
            # We dont care about the output, cause branding will be checked
            # via rrdm_tool when adding, checking there is important to stop
            # manual adding. This is a precaution to not error out later.
            out = run_shell_cmd('%s -q disk-license | grep "disk%s "' % (hwtool_py, drive_num), True)
            if out.strip() != '':
                break
        except rrdm_error, what:
            pass

        rlog_debug ('Try %d to add disk fail, %s' % (retry + 1, what))
        sleep (5)
        retry += 1
            
    if retry == 3:
        rlog_warning ('Unable to get disk information, skipping disk%s add' % drive_num)
        #Since we cant do anything with this disk, just return
        return
    
    (disk, license) = out.split(' ')
    if license == 'Unlicensed':
        rlog_notice('Disk isn\'t supported, please add a Riverbed supported disk')
        err = 1
    else:

	# Check if any partitions are present
	if not os.path.exists('/dev/disk%sp2' % drive_num):
            retry = 0
            while retry < 5:
	        retry += 1
                if os.path.exists('/dev/%s' % port) == False:
                    rlog_notice('Sleeping for the %d time in retry loop' % retry)
                    sleep(2)

        raid_add_cmd = '%s --add /disk/p%s' % (rrdm_tool_py, drive_num)
        try:
            err = run_shell_cmd(raid_add_cmd)
        except rrdm_error, what:
            rlog_notice ('Failed to add disk with shell error %s' % what)
            #Set err, so that it doesnt exit due to "referenced before assignment"
            err = 1

    if err != 0:
        rlog_warning ('Unable to synchrnonize raid arrays on disk %s' % port)

    # when we have added a new disk, update the on disk config.
    #
    raid_cfg_upd_cmd = '%s --write-config' % (rrdm_tool_py)
    try:
        err = run_shell_cmd(raid_cfg_upd_cmd)
    except rrdm_error, what:
        rlog_notice ('Failed to update raid/disk configuration %s' % what)


def remove_raid_disk(port, drive_num):
    rlog_notice ('drive removal notification for device [%s]' % port)
    rlog_notice ('Synchronizing raid arrays on [%s]' % port)

    # tell raid tool to fail all raid arrays on this device.

    raid_fail_cmd = '%s -f /disk/p%s' % (rrdm_tool_py, drive_num)
    try:
        err = run_shell_cmd(raid_fail_cmd)
    except rrdm_error, what:
        rlog_notice ('Failed to fail disk with shell error %s' % what)
        err = 1

    if err != 0:
        rlog_warning ('Unable to synchrnonize raid arrays on disk %s' % port)

## Given a drive list, go through each entry by its 
# physical port and update the bus to match the current
# read bus from the system
#
# This is mainly needed on 3UABA where the disk slot
# to bus mapping is not deterministic, and will
# be unavailable if a drive slot is empty, or the lsi driver
# has re-used a bus number across slots.
#
# @param drive_list drive_list structure which is an
#        array of hwtool disk map entries.
#
def update_drive_scsi_bus(drive_list):
    hwt_drive_map = HwtoolDriveList()
    result = []

    for drive in drive_list:
        port = drive[0]
        bus  = drive[1]
	drive_num = port[4:]

        new_bus = hwt_drive_map.find_bus_by_port(drive_num)
        if new_bus != None:
            result.append( (port, new_bus) )
            if new_bus != bus:
                rlog_info('Bus for %s changed from [%s] to [%s]' % (port, bus, new_bus))
        else:
            # we should get a result for any drive, but if we don't
            # use the original value.
            result.append(drive)

    return result

def sw_raidcheck_main():

    drive_list = []
    event_type = str(argv[1])
    kernel_name = str(argv[2]) # this is referred to as bus below
    rlog_debug('Event type %s' % event_type)
    rlog_debug('Kernel name %s' % kernel_name)

    try:
        sw_raid_supported = run_shell_cmd (rrdm_tool_py + ' --uses-sw-raid', True)
    except rrdm_error, what :
        print what

    drive_list=get_drive_list()
    try:
        # rescan the drive list in case we have had a scsi bus to
        # port mapping change.
        drive_list = update_drive_scsi_bus (drive_list)

        # Do further processing based on the event type
        if event_type == "add":
            # extract disk number; kernel_name is bus_num [0:0:X:0] in this case
            bus_flag = 0
            for drive in drive_list:
                port = drive[0]
                bus = drive[1]
                drive_num = port[4:] 
                if bus == kernel_name:
                    # retry logic to loop if /dev/port is not been created by udev yet
                    if os.path.exists('/dev/%s' % port) == False:
                        retry = 0
                        while retry < 5:
                            retry += 1
                            if os.path.exists('/dev/%s' % port) == False:
                                sleep(2)
                    bus_flag = 1
                    add_raid_disk(drive, drive_list)
                    send_sighup()
            if bus_flag == 0:
                rlog_warning ('Unknown Bus ID %s while disk add' % kernel_name)
        elif event_type == "remove":
            # kernel_name is disk name [diskX] in this case
            port = kernel_name
            drive_num = port[4:]
            remove_raid_disk(port, drive_num)
            send_sighup()
        else:
            rlog_warning ('Unknown event. Bailing...')
            exit(1)

        # Check if the MD state changed
        # Set the flag to true so that we send a SIGHUP to rbt_hald
        if md_state_changed() == True:
            # If a disk is failed via CLI "raid swraid fail ..."
            # the md status changes and we hit this code path
            # need to change the LKCD dump link as the disk is failing
            # We will come here when a disk is added as well,
            # but the link wont change then
            send_sighup()

        # Update LED consistency
        led_update_cmd = '%s --update-led-state' % rrdm_tool_py
        try:
            err = run_shell_cmd(led_update_cmd)
        except rrdm_error, what:
            rlog_notice ('Failed to add disk with shell error %s' % what)

    # catch a bunch of exceptions that we'd be most concerned with and 
    # log an error so we'll catch them.
    # but don't let them kill sw_raidcheck.
    #
    except rrdm_error, what:
        rlog_notice ('rrdm_tool failed with error %s' % what)
    except IOError, (errno, strerror):
        rlog_warning ('IOError error (%s:%s)' % (errno, strerror))
    except OSError, (errno, strerror):
        rlog_warning ('OSError error (%s:%s)' % (errno, strerror))
    except IndexError:
        rlog_warning ('Unhandled IndexError')

supported = run_shell_cmd ('%s --uses-sw-raid' % rrdm_tool_py, True)
if supported == "True":
    sw_raidcheck_main()
else:
    rlog_notice ('Software Raidcheck not supported on model %s' % model)
    

