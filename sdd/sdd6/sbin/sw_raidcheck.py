#!/usr/bin/python

import os
from time import sleep
from rrdm_util import *
from rrdm_logging import *
import re

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

# we poll every 5 seconds for changes in disk state.
#
poll_interval=5

##############################################################################
# We'll only poll status on the disks to update the led status
# every 10s since we acutally ahve to talk to all the drives a
# few times to get the status of the raids, etc, and it seems silly
# to do that much IO just to control the LED's
#
##############################################################################
disk_status_poll_interval=2

model = get_model()
if model == '':
    rlog_warning ('Unable to determine appliance model, exiting')
    exit (1)
    
# read the uid for a specific scsi device.
# we need the bus slot to port mapping in order to do it.
#
def get_scsidev_param(bus_num, sysfs_param):
    sysfs_val=''
    dev_str = '/sys/bus/scsi/devices/%s/%s' % (bus_num, sysfs_param)
    try:
	sysfs_val = get_sysfs_param (dev_str)
    except (OSError, IOError):
	raise rrdm_error ('unable to find sysfs entry for device [%s]' % dev_str)

    return sysfs_val


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
		    try:
                        # Check if the disk is available
		        uid = get_scsidev_param(bus, 'dev_uniq_id')
                        if licensed != 'Licensed':
                            # If disk present but unbranded set the unique id to -1
                            # this will trigger a hot plug event if disk replaced
                            uid="-1"
		    except rrdm_error, error_msg:
			# can't read the device info for some reason, just log and continue
			# uid is negative so we'll take any change as an insertion
			#
			uid="-1"

		    rlog_info('adding [%s] [%s] [%s] to disk list' % (port, bus, uid))
		    list.append ((port, bus, uid))
		
	except IndexError:
	    # if we get a malformed entry, ignore it.
	    # should probably log a message.
	    continue

    return list


def get_mgmt_disk_mapping():
    disk_map = {}
    licensed_map = get_drive_license_map()
    licensed = 'Unlicensed'

    # Figure out which disks are used in RAID
    # these are currently in the mgmt zone
    online_disks = {}
    retmessage = run_shell_cmd(rrdm_tool_py + ' -s /mgmt', True)
    for line in retmessage.split('\n'):
        (dname, status) = re.compile('\s+').split(line)
        online_disks['disk%s' % dname] = status
            

    retmessage = run_shell_cmd(hwtool_py + ' -q disk=map | grep disk', True)
    for line in retmessage.split('\n'):
        try:
            disk_line = re.compile('\s+').split(line)
            try:
                slot     = disk_line[0]
                dname    = disk_line[1]
                devname  = disk_line[2]
                devstate = disk_line[3]

                if licensed_map.has_key(dname):
                    licensed = licensed_map[dname]
                else:
                    # ignore the disk if it isnt in the licensed map.
                    continue

            except IndexError:
                rlog_warning ('disk map returned invalid disk info [%s]' % disk_line.strip())
                # skip this line and move on
                continue

        except TypeError:
            rlog_warning ('hwtool query -q disk-license returned nothing')
            return disk_map

        # don't try to talk to missing drives or drives that are failed
        # but not missing. Only expose a drive in the disk map for sw_raidcheck
        # if its 
        if 'missing' != devname and 'online' == devstate and licensed == 'Licensed':
            # Only disks that are used by RAID should be considered
            if online_disks.has_key(dname):
                if online_disks[dname] == 'online':
                    disk_map[dname] = devname

    return disk_map

def get_swap_partition():
    swap_partid = ''
    raid_part_cmd = '%s --get-partition /swap' % rrdm_tool_py
    try:
        swap_partid = run_shell_cmd(raid_part_cmd, True).strip()
    except rrdm_error:
        rlog_warning ('Failed to get the RAID partition ID, %s' % what)

    return swap_partid


def change_root_partition_state(state="ro"):
    run_shell_cmd("mount / -o remount," + state)

# is_read_only_root
# quick method to determine if / is mounted rw or ro
#
def is_read_only_root():
    try:
        open('/tempfile', 'w').close()
    except IOError:
        return True

    os.remove ('/tempfile')
    return False

def repair_dump_link(disk_map, swap_partid):
    i = 0
    link_changed = False
    # 3 retries with a second interval. 
    while i < 3:
        i += 1
        ro_root = is_read_only_root()

        try:
            if disk_map.values()[0]:
                try:
                    if ro_root:
                        change_root_partition_state("rw")

                    target = '\/dev\/%s%s' % (disk_map.values()[0], swap_partid)
                    run_shell_cmd('cat /etc/sysconfig/dump | sed \'s/DUMPDEV=.*/DUMPDEV=%s/g\' > /var/tmp/dump.conf' % target)
                    run_shell_cmd('mv /var/tmp/dump.conf /etc/sysconfig/dump')
                    run_shell_cmd('/sbin/lkcd config')
                    link_changed = True
                except rrdm_error:
                    if i < 3:
                        rlog_notice('Could not change LKCD link, will retry in a second')
                try:
                    run_shell_cmd('/sbin/lkcd save')
                except rrdm_error:
                    rlog_info('No kernel dump, thats fine')

                try:
                    if ro_root:
                        change_root_partition_state("ro")
                except rrdm_error:
                    rlog_warning('Cannot change root partition to ro')
            else:
                rlog_warning ('All RAID disks down')
        except IndexError:
            rlog_warning ('Disk map says no valid disks')

        if link_changed:
            break

        # Sleep for a second and retry
        sleep(1)

    if not link_changed:
        rlog_warning('Could not change LKCD link')

def check_vmdump_link():
    # Find the diskX to drive mapping
    disk_map = get_mgmt_disk_mapping()

    # Find the swap partition number on the RAID drive
    swap_partid = get_swap_partition()

    target = ''
    partition = ''

    try:
        dumptargetdev = run_shell_cmd('grep "DUMPDEV=" /etc/sysconfig/dump | awk -F"=" \'{print $2}\' |sed \'s/"//g\'', True)
        for char in dumptargetdev:
            if char.isdigit():
                partition += char
            else:
                target += char

        target = target.replace('/dev/', '')

    except (OSError, IndexError):
        rlog_notice ('vmdump link not pointing to any valid device, repairing link')
        # Repair link of possible
        repair_dump_link(disk_map, swap_partid)
        return

    # Case where the link is pointing to invalid partition
    # Eg: /dev/sda3 instead of /dev/sda2

    if partition != swap_partid:
        rlog_notice ('vmdump link not pointing to a valid swap partition, repairing link')
        # Repair link of possible
        repair_dump_link(disk_map, swap_partid)
        return

    change_link = True

    # Find all the online drives
    try:
        retmessage = run_shell_cmd(rrdm_tool_py + ' -s /mgmt', True)
        for line in retmessage.split('\n'):
            (dname, status) = re.compile('\s+').split(line)
            if 'online' == status:
                if disk_map.has_key('disk%s' % dname):
                    if disk_map['disk%s' % dname] == target:
                        # Disk healthy, break check and leave link as it is
                        change_link = False
                        break

    except (TypeError, rrdm_error):
        rlog_notice ('rrdm_tool query -s /disk returned nothing')

    if change_link:
        # Need to change the dump link as the drive its
        # currently pointing is dead
        # Change link only if any disk still online
        repair_dump_link(disk_map, swap_partid)

def send_sighup_to_hald(pid):
    try:
        run_shell_cmd("/bin/kill -s sighup %s" % pid, False)
    except rrdm_error:
        rlog_warning("Could not send SIGHUP to rbt_hald, disk state may be inconsistent")


def get_pidof_rbt_hald():
    try:
        pid = int(run_shell_cmd("/sbin/pidof /opt/tms/bin/rbt_hald", True))
    except rrdm_error:
        rlog_notice("Could not get pifof rbt_hald, maybe process not running")
        pid = -1
    except ValueError:
        rlog_notice("Could not get pifof rbt_hald, process not running")
        pid = -1

    return pid


def add_raid_disk(drive, new_uid, drive_list={}, missing_drive_list={}):
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

    drive_list.remove (drive)

    if missing_drive_list.has_key(port):
        del missing_drive_list[port]

    drive_list.append((port, bus, new_uid))


def remove_raid_disk(port, drive_num, missing_drive_list={}):
    rlog_notice ('drive removal notification for device [%s]' % port)
    missing_drive_list[port] = port

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
	uid  = drive[2]
	drive_num = port[4:]

        new_bus = hwt_drive_map.find_bus_by_port(drive_num)
        if new_bus != None:
            result.append( (port, new_bus, uid) )
            if new_bus != bus:
                rlog_info('Bus for %s changed from [%s] to [%s]' % (port, bus, new_bus))
        else:
            # we should get a result for any drive, but if we don't
            # use the original value.
            result.append(drive)

    return result
            
def sw_raidcheck_main():
    global poll_interval
    global disk_status_poll_interval

    # Flag to indicate that the SIGHUP needs to be sent to rbt_hald
    send_sighup=False

    drive_list = []
    missing_drive_list = {}

    # Find the swap partition number on the RAID drive
    swap_partid = get_swap_partition()

    try:
        sw_raid_supported = run_shell_cmd (rrdm_tool_py + ' --uses-sw-raid', True)
    except rrdm_error, what :
        print what

    # Change link for 2050 and above
    if "True" == sw_raid_supported:
        # Set the initial link to the /dev/sdaX instead of /dev/mdX        
        check_vmdump_link()

    # read the initial drive list from disk using hwtool
    drive_list=get_drive_list()

    rescan_drive_list	= False
    poll_count		= 0
    while True:
	try:
	    sleep (poll_interval)
            # Check to see if rbt_hald is up, if sighup wasnt sent before
            if send_sighup:
                # Update rbt_hald cache
                pid = get_pidof_rbt_hald()
                if pid != -1:
                    send_sighup_to_hald(pid)
                    send_sighup = False
	
	    # if we had an error in the drive list for some reason,
	    # rescan it.
	    if rescan_drive_list:
		rlog_info ('Rescanning drive list')
		drive_list = get_drive_list()

            poll_count += 1
            # only poll disk status to update LED's every status poll cycle
            # to reduce chattiness to the disks.
            if poll_count % disk_status_poll_interval == 0:
		poll_count = 0
                try:
                    err = run_shell_cmd('/opt/hal/bin/raid/rrdm_tool.py --check-raid-consistency')
                except rrdm_error:
                    err = 1

                if err > 0:
                        rlog_info ('Raid sw daemon failed to update led state')

            # rescan the drive list in case we have had a scsi bus to
            # port mapping change.
            drive_list = update_drive_scsi_bus (drive_list)

	    for drive in drive_list: 
		try:
		    port	= drive[0]
		    bus		= drive[1]
		    uid		= drive[2]
		    drive_num	= port[4:]

		    try:
			new_uid = get_scsidev_param (bus, 'dev_uniq_id')
		    except rrdm_error, error_msg:
			# unable to read uid, log error and proceed to the next drive
			# assume the drive has been removed
 
                        if uid == "-1":
                            # dev is missing, skip it.
                            continue

			if not missing_drive_list.has_key (port):
                            remove_raid_disk(port, drive_num, missing_drive_list)

                            # this is where the vmdump link directory needs to be changed
                            # if it was pointing to a drive that just crapped out
                            # pick the next online drive and redirect vmdump to it
                            check_vmdump_link()

                            # Set the flag to true so that we send a SIGHUP to rbt_hald
                            send_sighup = True

			continue

		    if uid != new_uid:
			# the scsi device has changed, someone has removed and re-inserted the disk.
			# log message and invoke the rrdm_tool to re-add the drive.
                        add_raid_disk(drive, new_uid, drive_list, missing_drive_list)

                        # Set the flag to true so that we send a SIGHUP to rbt_hald
                        send_sighup = True
	    
		except IndexError:
		    rescan_drive_list = True
		    rlog_warning ('Index exception while processing drive list, re-reading drive list.')

		    # log a message indicating a bad entry, and we'll re-read the hwtool map
		    # the next time we come around
		    continue

            # Check if the MD state changed
            # Set the flag to true so that we send a SIGHUP to rbt_hald
            if md_state_changed() == True:
                # If a disk is failed via CLI "raid swraid fail ..."
                # the md status changes and we hit this code path
                # need to change the LKCD dump link as the disk is failing
                # We will come here when a disk is added as well,
                # but the link wont change then
                check_vmdump_link()
                send_sighup = True

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

supported = run_shell_cmd ('%s --supported' % rrdm_tool_py, True)
if supported == "True":
    sw_raidcheck_main()
    rlog_notice ('starting Software RaidCheck for model %s' % model)
else:
    rlog_notice ('Software Raidcheck not supported on model %s' % model)
    

