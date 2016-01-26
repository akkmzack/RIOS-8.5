#!/usr/bin/env python

###############################################################################
#
# RRDM TOOL (Riverbed RAID Disk Management Tool)
#
###############################################################################
from os import stat, system
from sys import exit, argv
from getopt import getopt, GetoptError
from os import stat
from os.path import exists, ismount
from optparse import OptionParser

# RRDM Class Library
from rrdm_util import enable_syslog, rrdm_error, get_model, rlog_debug, display_debug
from rrdm_util import rlog_debug, rlog_notice, rlog_warning, rlog_info
from rrdm_util import DiskInfoMap, DiskInfo, DiskMedia, SSDDiskWearInfo, model_to_ssdinfo_map 
from rrdm_system import System, Spec, SystemConfig, validate_spec
from rrdm_raid import RaidArray, RaidPartition, RaidDevices
from rrdm_disk import DiskArray, HardDisk, Partition, PartitionTable, spare_serial_num
from rrdm_logging import *
from rrdm_config import *
from rrdm_super import RvbdSuperBlock 
from rrdm_ftraid import FtDiskPartition

enable_syslog ()
init_logging ("sw_raid")

# determines whether output should be xml or std readable output
output_xml=False
# Global
spec_file=None

################################################################################
# XML Processing
# 
# Uses specs.xml to determine disk membership and geometry
# - Uses a state machine parser since we don't include a DOM XML 
#   parser in our appliances
#
# - Builds a Hard Disk Structure and Hard Drive Array Structure
#   based on the disk # and partition information in the config
#
# - The config is used as an indicator of what should be there,
#   Disk information is populated from the system as well so
#   we can tell if a drive is mis-partitioned, invalid size, etc.
#
################################################################################


###############################################################################
# read_spec_configuration
#
# Read the specs.xml file and populate associative arrays for the system
# which can be used to fill in the partition table, raid array information
#
###############################################################################
def read_spec_configuration(model, spec_file = None):
    image_spec_file="/opt/hal/lib/specs/specs.xml"
    mfg_spec_file="/mfg/specs.xml"

    if not spec_file:
        try:
	    stat(image_spec_file)
            name = image_spec_file
        except OSError:
	    try:
	        stat(mfg_spec_file)
                name = mfg_spec_file
	    except OSError:
	        print 'Unable to find specs.xml'
	        exit (1)
    else:
        if not exists(spec_file):
            print 'Unable to find  spec file %s' % spec_file
            exit (1)

        name = spec_file

    
    specmap = read_specmap(name)
    if specmap == None:
        print 'Unable to parse spec file %s' % name
        exit (1)

    spec = specmap.get_spec_by_name(model)
    if spec == None:
        raise rrdm_error("Model definition [%s] not found in spec file [%s]" % \
                         (model,
                          name))

    return spec

####################################################################################
# End XML Utils
####################################################################################


##############################################################################
# RRDM Path Utilities
#
# Paths look like /segstore
#		  /segstore/p[0-X]
#		  /pfs/p[]
#		  /drive
#
##############################################################################

class TargetError(Exception):
    pass

##############################################################################
#
# Targets
#
# Given a path, this creates a class that is typed:
# Types are "raid-drive" "raid" "raid-array" "drive" or "drive-array"
# "ftraid-array" or "ftraid-drive"
#
# The type field is used to indicate which fields should be used,
# for root urls like /segstore, the target is filled in
# for specific device urls that sub_target is filled in with pX
#
# The disk member is filled in with the X of pX
#
##############################################################################
class Target:
    def __init__(self, path, spec, model):
        path = path.strip('/')
        pc = path.count('/')
	if len(path) == 0 or pc > 2 or pc < 0:
	    raise TargetError('Invalid path: %s' % path)

        comp = path.split("/")

        self.sub_target = ''
        self.vol_target = None

	self.target = comp[0]
	if (len(comp) == 2):
	    self.sub_target = comp[1]
        elif (len(comp) == 3):
	    self.sub_target = comp[1]
            self.vol_target = comp[2]

        is_raid    = False
        is_ftraid  = False

	# handle the special path of /raid to mean do all raid arrays.
	if self.target == 'raid':
	    is_raid = True 
	    self.type = 'raid'
	else:
            if spec.get_zone_spec_by_name(self.target) != None:
                self.type = 'zone'
            else:
                if spec.has_lvm_by_name(self.target):
                    # ok we're an LVM classify the LVM and update the right 
                    # bits
                    lvm = spec.get_lvm_by_name(self.target)
                    if lvm.is_raid():
                        is_raid = True
                    elif lvm.is_ftraid():
                        is_ftraid = True
                    ## What do we do about direct nodes.  We never had
                    # status for them before
                    
	        for a in spec.get_raid_arrays():
		    if a.get_name() == self.target:
		        is_raid = True

                for a in spec.get_ftraid_arrays():
                    if a.get_name() == self.target:
                        is_ftraid = True

	        if is_raid:
		    if (self.sub_target != ''):
		        self.type = 'raid-drive'
		    else:
		        self.type='raid-array'
                elif is_ftraid:
		    if (self.sub_target != ''):
		        self.type = 'ftraid-drive'
		    else:
		        self.type='ftraid-array'
                    
	        elif self.target == 'disk':
		    if self.sub_target == '':
		        self.type='disk-array'
		    else:
		        self.type = 'disk'
	        else:
		    raise TargetError('Path %s isn\'t a disk or ' \
                                      'raid device on model %s' % (path, model))

	if self.type in ["raid-drive", "disk", 'ftraid-drive']:
	    if (self.sub_target[0] != 'p'):
		raise TargetError('Invalid device target %s' % self.sub_target)
	    try:
		self.disk = int(self.sub_target.strip('p'))
	    except ValueError:
		raise TargetError('Invalid sub target device ' %
                                  'specified %s' % self.sub_target)

            # we now want to be able to reference a particular volume
            # on a disk for a given function, for example
            # -s /disk/p5/segstore would correspond to show me the
            # status of the segstore on disk 5
            if self.vol_target != None and self.type != "disk":
                raise TargetError('Volume paths are supported only' \
                                  ' for disk queries')

	rlog_debug ('Device Target type is : ' + self.target)
	rlog_debug ('Device Target sub type is : ' + self.sub_target)
        if (self.vol_target != None):
	    rlog_debug ('Device Target vol type is : ' + self.vol_target)

    disk=-1
    # cmd type is drive, raid array, or raid drive
    type=''
    # target is a raid array or disk array
    target=''
    # sub target is everything if empty or a disk/raid disk
    sub_target=''

####################################################################################
# Main RRDM Tool Stuff
####################################################################################

####################################################################################
# list_volumes
#
# display a list of the volumes that RiOS is concerned with.  Is used to feed
# manufacturing and maintenance of the drives.
#
####################################################################################
def list_volumes(system):
    ret = ''
    for arr in system.raid_arrays.get_array_list(): 
        # on the raided partitions we already have a SB so we don't need
        # to reserve space.
        if arr.bitmap != None:
            bitmap=arr.bitmap
        else:
            bitmap='none'
        ret += '%s:%s:%s:%s:false:true:%s\n' % (arr.name, arr.dev_name, arr.fstype, arr.type, bitmap)

    for arr in system.volumes: 
        if arr.fstype == "ext3" or arr.fstype == "ext4" :
            reserve_sb_space='true'
        else:
            reserve_sb_space='false'
        bitmap='none'
        ret += '%s:%s:%s:%s:%s:false:%s\n' % (arr.name, arr.dev_name, arr.fstype, arr.type, reserve_sb_space, bitmap)

    print ret

## find_system_volcfg_by_name
# @param system System class object
# @param name name of the associated VolumeConfig object
#
# loops through the list of populated system objects
# and returns the one associated with name
# 
def find_system_volcfg_by_name(system,
                               name):
    for arr in system.raid_arrays.get_array_list():
        if arr.name == name:
            return arr

    for volume in system.volumes:
        if volume.name == name:
            return volume

    return None

###############################################################################
# list_all_disks
#
# Dump disk related information (including partition table) to stdout in XML
# This query facilitates hal_raid_mod converting disk and partition info
# to GCL.
###############################################################################
def list_all_disks(system):
    system.list_all_drive_raid_status()


def update_system_metadata(system, 
                           mfdb_path='/config/mfg/mfdb'):
    # in manufacturing /config is not mounted until later on in the process
    # so we'll need to have an out of band call for updating the mfdb
    # but through run-time reconfiguration, we'll update the mfdb if
    # it exists at the default run-time expected location
    return system.update_system_metadata(mfdb_path)

def cmd_update_metadata(option, spec, model):
    rlog_notice ('Running device metadata update for model:%s' % (
                 model))

    # punt if we don't have a spec.. this model isnt supported with this tool
    if spec == None or not spec.uses_layouts():
        print 'NOP'
        exit (0)

    if option.profile in [ None, '' ]:
        profile = None
    else:
        profile = option.profile
        rlog_notice('Storage Profile is forced to %s' % profile)

    system = System (spec,
                     model,
                     profile = profile)
    if option.mfdb_path != None:
        update_system_metadata(system, option.mfdb_path)
    else:
        # use the default path to the mfdb if none is specified
        update_system_metadata(system)

## mfg_format_volume
# @param system System object
# @param volume name
# Given a volume (Raid or Partition object) run its format method
# if there is one defined
def mfg_format_volume(system, 
                      volume_name,
                      verbose = False):
    # sanity check our system/spec 
    if system.spec.has_storage_cfg() and \
        system.spec.has_lvm_by_name(volume_name):
        lvm = system.spec.get_lvm_by_name(volume_name)
        if lvm.has_format_method():
            system.format_volume(volume_name, verbose)
        else:
            rlog_notice('No format method defined for volume %s' % volume_name)


###############################################################################
# do_mfg_setup
# @param dry boolean indicating whether or not to actually do any actions or 
#            just print out information (dry run)
# @param reconfigure boolean indicating whether or not this is a remanufacture
#        or a profile reconfiguration
# 
# Partitions the drives and does any necessary RAID setup for a given 
# system/model. For reconfiguration, we assume this is a storage profile
# change and we will not recreate any raid arrays that correspond to
# persistant volumes in the storage config, we will simply re-assemble these.
# Also for reconfiguration we will not clear any ext3 labels, as we want
# these labels to maintain across the reconfig for filesystems like VAR etc.
#
# Returns output of list_volumes to allow the mfg scripts 
# to use the partitions and devices created.
#
###############################################################################
def do_mfg_setup(system, 
                 dry,
                 reconfigure): 
    if reconfigure:
        clear_labels = False
    else:
        clear_labels = True

    try:
        #make sure we have the right number of drives
        # and they're the right size etc.
        system.validate()
    
        #partition them and clear any labels on them
        system.setup_drives(dry = dry,
                            clear_labels = clear_labels)

        # do raid setup, if we are enabling a new profile, 
        # we only reassemble persistant arrays, we don't
        # recreate them
        for arr in system.raid_arrays.get_array_list():
            if not reconfigure:
                arr.create_raid_array(dry)
                mfg_format_volume(system, arr.name, True)
            else:
                if system.is_persist_lvm(arr.name):
                    arr.start_raid_array(dry)
                else:
                    # this is the case of changing a profile and creating a 
                    # new array since this array is classified as one that
                    # will change across a profile switch
                    # 
                    arr.create_raid_array(dry)
                    
                    # this will check to see if we have a format method
                    # and if so run it for this volume
                    mfg_format_volume(system, arr.name, True)

        if system.spec.has_storage_cfg():
            for volume in system.volumes:
                if not reconfigure:
                    mfg_format_volume(system, volume.name, True)
                elif not system.is_persist_lvm(volume.name):
                    mfg_format_volume(system, volume.name, True)
    
    except Exception, what:
        print what
        exit(1)
    
    # update metadata with the default mfdb path
    update_system_metadata(system)

    #return a list of name:devname pairs to the command line
    list_volumes(system)
    exit(0)

###############################################################################
# has_command_set
# global
#
# Used to determine if a user specifies multiple commands on the command line.
# We only support one command at a time.
#
###############################################################################
has_command_set=False

###############################################################################
#
# get_cmd_target
#
# get a target class, and the device the request refers to.
#
###############################################################################
def get_cmd_target(system, option, spec):
    try:
	target = Target (option, spec, system.get_model())
    except TargetError, what:
	raise rrdm_error (what)

    if target.type == 'raid':
	device_target = system.raid_arrays
    if target.type in [ 'raid-array', 'raid-drive' ]:
	for dev in system.raid_arrays.get_array_list():
	    if dev.name == target.target:
		if target.type == 'raid-drive':
		    device_target = dev.find_dev_by_logical_devnum (target.disk)
                    # XXX
                    device_target.get_detail_status()
		else: 
		    device_target = dev
    elif target.type in [ 'ftraid-array', 'ftraid-drive' ]:
        for dev in system.get_ftraid_arrays():
            if dev.get_name() == target.target:
                if target.type == 'ftraid-drive': 
                    device_target = dev.find_dev_by_logical_port(target.disk)
                else:
                    device_target = dev

    elif target.type in [ 'disk', 'disk-array' ]:
        if target.type == "disk-array":
            device_target = system.disk_array
        elif target.type == "disk":
            if target.vol_target != None:
                # we want to find if the volume lives on this disk
                hd = system.disk_array.find_drive_by_id(target.disk)

                if hd == None:
                    raise rrdm_error ('%s is not a valid disk %s' % \
                                      (target.vol_target, target.disk))

                device_target = system.find_sys_dev_by_hd_volname(hd, 
                                    target.vol_target)
                if device_target == None:
                    raise rrdm_error ('%s is not a volume on disk %s' % \
                                      (target.vol_target, target.disk))

                if isinstance(device_target, RaidPartition):
                    target.type = 'raid-drive'
                elif isinstance(device_target, FtDiskPartition):
                    target.type = 'ftraid-drive'
                else:
                    raise rrdm_error('Only RAID or FTS devices are supported')
            else:
                device_target=system.disk_array.find_drive_by_id(target.disk)
    elif target.type in [ 'zone' ]:
            device_target = system.get_zone_by_name(target.target)

    if not device_target:
	raise rrdm_error ('Could not determine device target for %s' % option)

    return (target, device_target)
    
###############################################################################
# check_spec
#
# small helper to make sure that we have a valid spec in routines where we need
# to use the spec.
#
###############################################################################
def check_spec (spec, model):
    if spec == None:
	raise rrdm_error ('Required specification' \
                          ' for model %s not found.' % model)

    if not spec.uses_layouts():
        raise rrdm_error ('Specification %s is not supported ' \
                          'by rrdm_tool' % model)
    

###############################################################################
#
# Command Line Helpers
#
###############################################################################
def is_raid_command(target):
    return target.type in [ "raid", "raid-drive", "raid-array" ]

###############################################################################
# is_cmd_supported
#
# Checks the command arguments against the appliance type and indicates
# whether this command is allowed on this appliance.
#
###############################################################################
def is_cmd_supported(target, system):
    if is_raid_command (target):
	if not system.supports_sw_raid():
	    raise rrdm_error('Raid commands are not supported on model %s' % system.get_model())

###############################################################################
#
# Command Line Handlers
#
# Command line options are registered through the 
# optparse.add_option() and cmd_handlers{} dictionary.  new commands
# must be added to both.
#
# The cmd_handlers dictionary takes the option string created by optparse
# as the key, which is a concatenation of the short/long options by "/"
# e.g "-s"."--status" has a key of "-s/--status"
#
###############################################################################

###############################################################################
# cmd_get_status
#
# displays simple status usable by mgmt for determining system status
# basically drive number or raid number and status
#
###############################################################################
def cmd_get_status(option, spec, model):
    rlog_debug ('Running get status for [%s] [model:%s]' % (
		 option.target,
		 model))


    # make sure we were able to get a spec
    check_spec(spec, model)

    system = System (spec, model)
    (target, device_target) = get_cmd_target(system, option.target, spec)
    is_cmd_supported(target, system)

    device_target.get_status (option.xml_output)

###############################################################################
# cmd_get_detail_status
#
# displays more detailed status suitable for CLI output.
#
###############################################################################
def cmd_get_detail_status (option, spec, model):
    rlog_debug ('Running get detail status for [%s] [model:%s]' % (
                 option.target,
                 model))

    # make sure we were able to get a spec
    check_spec(spec, model)

    system = System (spec, model)
    (target, device_target) = get_cmd_target(system, option.target, spec)
    is_cmd_supported(target, system)
    
    print device_target
    device_target.get_detail_status (option.xml_output)

###############################################################################
# cmd_get_partition
#
# displays the partition number for various partions on the raid drives  
# this routine should be used with care, it will tell you the partition 
# number, but the partition number belongs to a particular zone, which
# the caller is expected to know.
#
###############################################################################
def cmd_get_partition(option, spec, model):
    rlog_debug ('Running get swap partition for [%s] [model:%s]' % (
                 option.target,
                 model))

    # Make a check here to see if this model has RAID or not
    partitions = spec.get_raid_arrays()
    sprof = get_storage_profile()
    if sprof != None:
        spec.set_spec_profile_view(sprof)

    target = option.target.lstrip('/')

    if 0 == len(partitions):
        vol_list = spec.get_volumes()
    else:
        vol_list = spec.get_raid_arrays()

    for vol in vol_list:
        if target == vol.get_name():
            print vol.get_part_id()

###############################################################################
# cmd_has_volume
#
# Indicates whether the current spec/profile has a given volume.
# volume is passed in via the option.target parameter.
# 
# Method is only supported for models that have associated storage profiles.
#   
# returns true if the current specification/profile has the volume by name,
#         false otherwise (or if the appliance does not support storage
#                          profiles)
#   
###############################################################################
def cmd_has_volume(option, spec, model):
    has_volume = False

    check_spec(spec, model)

    if option.profile in [ None, '' ]:
        # use the profile from the mfdb
        profile_name = get_storage_profile()
    else:
        profile_name = option.profile

    # set the spec view for the correct profile
    spec.set_spec_profile_view(profile_name)
    target = option.target.lstrip('/')

    if spec.has_storage_cfg():
        has_volume = spec.has_lvm_by_name(target)
    else:
        has_volume = False

    print '%s' % str(has_volume).lower()

###############################################################################
# cmd_get_raid_info
#
# displays user visible raid status and configuration information.
#
###############################################################################
def cmd_get_raid_info (option, spec, model):
    rlog_debug ('Running get raid info for [%s] [model:%s]' % (
                 option.target,
                 model))

    # make sure we were able to get a spec
    check_spec(spec, model)

    system = System (spec, model)

    print 'System Serial\t\t\t=> %s' % system.get_appliance_serial()
    print 'System Model\t\t\t=> %s' % system.get_model()
    print 'Number of Arrays\t\t=> %d' % system.raid_arrays.get_num_arrays()
    print 'Max Rebuild Rate\t\t=> %s MB/s' % system.get_rebuild_rate()
    for array in system.raid_arrays.get_array_list():
	print 'Array Name\t\t\t=> %s' % array.name
	print '\tArray Status\t\t=> %s' % array.status
	print '\tRaid Type\t\t=> %s' % array.level
	print '\tStripe Size\t\t=> %s' % array.chunk

def cmd_get_physical(option, spec, model):
    # make sure we were able to get a spec
    check_spec(spec, model)

    system = System (spec, model)
    for drive in system.disk_array.get_drive_list():
        drive.display_drive_info()

    # Now add spare disks
    cmd_show_spare_disks(option, spec, model)

###############################################################################
# cmd_get_raid_configuration
#
# Display user visible RAID configuration, such as stripes, mirrors
# types, etc.
#
###############################################################################
def cmd_get_raid_configuration(option, spec, model):

    if option.profile in [ None, '' ]:
        # use the profile from the mfdb
        profile_name = get_storage_profile()
    else:
        profile_name = option.profile
        rlog_notice('Storage Profile is forced to %s' % profile)

    # make sure we were able to get a spec
    check_spec(spec, model)

    scdm = spec.get_spec_cfg_disk_map()
    try:
        # Some of the disks are ordered 0, 2, 1, 3 from a RAID logical volume perspective
        # example is a CX1555L and a CX1555M model.
        # In that case we get the order from the specs.xml file and 
        # use that order to display the configuration
        mgmt_order = scdm.get_disk_config(profile_name).get_zone_map()['mgmt'].get_disk_index_list()
    except:
        # If there is an exception means the ordering is not defined and
        # we will go with the default 'ascending' ordering. So set the 
        # order to None as the routine will take care of it
        mgmt_order = None

    try:
        fts_order = scdm.get_disk_config(profile_name).get_zone_map()['fts'].get_disk_index_list()
    except:
        fts_order = None

    system = System (spec, model)
    # this should be elsewhere, but putting it in here for the moment.
    #
    for array in system.raid_arrays.get_array_list():
        if array.get_zone() == 'mgmt':
            array.display_configuration(mgmt_order)
        elif array.get_zone() == 'fts':
            array.display_configuration(fts_order)
        else:
            print 'Invalid zone %s' % array.get_zone()

###############################################################################
# cmd_get_all_disks
#
# Displays all disk statii and their partition information in XML form
# to stdout.
#
###############################################################################
def cmd_get_all_disks(option, spec, model):

    if spec == None or not spec.uses_layouts():
        print 'NOP'
        exit (0)

    system = System (spec, model)
    list_all_disks (system)

## cmd_format_lvm
# @param option OptParse option object
# @param spec Spec object
# @param model System model string
def cmd_format_lvm(option,
                   spec,
                   model):
    if spec == None or not spec.uses_layouts():
        print 'NOP'
        exit (0)

    if option.profile in [ None, '' ]:
        profile = None

        rlog_notice('Storage Profile is forced to %s' % profile)

    system = System (spec,
                     model,
                     profile = profile)
    
    if not spec.has_storage_cfg():
        print 'Model %s has no associated storage config' % model
        exit(0)

    vol_name = option.volume_name
    if vol_name == '' or vol_name == None:
        raise AssertionError('Invalid volume name %s' % vol_name)
    
    system.format_volume(vol_name, True)

## cmd_list_by_media
# @param option OptParse option object
# @param spec Spec object
# @param model System model string
#
# Returns a list of drive numbers/status based on media type
# Refer to DiskMedia class for valid media types
#
def cmd_list_by_media(option, 
                   spec, 
                   model):
    if spec == None or not spec.uses_layouts():
        print 'NOP'
        exit (0)

    if option.profile in [ None, '' ]:
        profile = None
    else:
        profile = option.profile
        rlog_notice('Storage Profile is forced to %s' % profile)

    system = System (spec, 
                     model,
                     profile = profile)

    darray = system.disk_array.get_drive_list()
    media = option.media

    if media not in DiskMedia.supported_media_types:
        raise AssertionError('Invalid media type request %s' % media)

    disk_list = filter(lambda y: y.get_media() == media, darray)
    for disk in disk_list:
        print '%s %s' % (disk.portnum, disk.status)
        

###############################################################################
# cmd_list_mount_points
#
# Displays information about mount points managed by rrdm_tool
#
###############################################################################
def cmd_list_mount_points(option, spec, model):

    if spec == None or not spec.uses_layouts():
        print 'NOP'
        exit (0)

    if option.profile in [ None, '' ]:
        # use the profile from the mfdb
        profile_name = get_storage_profile()
    else:        
        profile_name = option.profile
        rlog_notice('Storage Profile is forced to %s' % profile)

    if not spec.has_storage_cfg():
        print 'NOP'
        exit (0)

    scfg = spec.get_storage_cfg()
    lvm_list = scfg.get_logical_volumes(profile_name)
    for lvm in lvm_list:
        if lvm.get_mount() not in [ '', None ]:
            print '%s:%s:%s:%s' % (lvm.get_name(), 
                                   lvm.get_fstype(), 
                                   lvm.get_mount(),
                                   lvm.get_mount_opts())

###############################################################################
# cmd_mount
#
# For a spec with particular LVM's that have filesystems on them managed by
# rrdm, mount each filesystem of the appropriate type.
#
###############################################################################
def cmd_mount(option, spec, model):

    if spec == None or not spec.uses_layouts():
        print 'NOP'
        exit (0)

    if option.profile in [ None, '' ]:
        # use the profile from the mfdb
        profile_name = get_storage_profile()
    else:
        profile_name = option.profile
        rlog_notice('Storage Profile is forced to %s' % profile)

    if not spec.has_storage_cfg():
        print 'NOP'
        exit (0)

    sysobj = System (spec, 
                     model,
                     profile = profile_name)

    scfg = spec.get_storage_cfg()
    lvm_list = scfg.get_logical_volumes(profile_name)
    for lvm in lvm_list:
        do_mount = True
        devname  = None
        if lvm.get_mount() not in [ '', None ]:
            vcfg = find_system_volcfg_by_name(sysobj, lvm.get_name())
            if vcfg == None:
                errmsg = 'LVM %s has no associated system volume' % \
                            (lvm.get_name(),
                             lvm.get_mount())
                print errmsg
                rlog_warning(errmsg)
                do_mount = False
            else:
                devname = vcfg.dev_name
                
            if do_mount and not exists(lvm.get_mount()):
                errmsg = 'LVM %s mount point %s does not exist' % \
                            (lvm.get_name(),
                             lvm.get_mount())
                print errmsg
                rlog_warning(errmsg)
                do_mount = False
                
            if do_mount and ismount(lvm.get_mount()):
                errmsg = 'LVM %s mount target %s is already mounted' % \
                          (lvm.get_name(), 
                           lvm.get_mount())
                print errmsg
                rlog_warning(errmsg)
                do_mount = False

            if do_mount and devname != None:
                mopt = lvm.get_mount_opts()
                if mopt in [ '', None ]:
                    cmd = '/bin/mount /dev/%s %s' % (devname,
                                                     lvm.get_mount())
                else:
                    cmd = '/bin/mount %s /dev/%s %s' % (mopt,
                                                        devname,
                                                        lvm.get_mount())
            
                err = system(cmd)
                if err:
                    errmsg = 'failed to mount device on %s on %s [%s]' % \
                              (devname, 
                               lvm.get_mount(),
                               mopt)
                    print errmsg
                    rlog_warning(errmsg)
                else:
                    print 'Device %s mounted on %s [%s]' % (devname,
                                                            lvm.get_mount(),
                                                            mopt)

###############################################################################
# cmd_list_logical_volumes
#
# Displays information about logical volumes and services provided to RiOS.
#
###############################################################################
def cmd_list_logical_volumes(option, spec, model):

    if spec == None or not spec.uses_layouts():
        print 'NOP'
        exit (0)

    if option.profile in [ None, '' ]:
        profile = None
    else:
        profile = option.profile
        rlog_notice('Storage Profile is forced to %s' % profile)


    system = System (spec, 
                     model,
                     profile = profile)
    print system.get_logical_volumes()

###############################################################################
# cmd_list_profiles
#
# this option displays information in xml about the current profile and
# the available profiles.  All information is driven by the config 
# files and not the current system state.
# 
###############################################################################
def cmd_list_profiles(option, spec, model):
    if spec == None or not spec.uses_layouts() or not \
        spec.has_storage_cfg():
        # dump xml to indicate we don't support profiles on this model
        print '<profiles supported=\"False\">'
        print '</profiles>'

        exit (0)
    
    scfg = spec.get_storage_cfg()
    current_profile = get_storage_profile()

    profiles = scfg.get_storage_profiles()

    final_profile_list = []

    if spec.get_supported_profiles():
        for profile in profiles:
            if profile.get_name() not in spec.get_supported_profiles():
                continue
            final_profile_list.append(profile)
    else:
        final_profile_list = profiles

    num_profiles = len(final_profile_list)
    print '<profiles supported=\"%s\" count=\"%d\" current=\"%s\">' % \
        (str(True), num_profiles, current_profile)

    for profile in final_profile_list:
        spec.set_spec_profile_view(profile.get_name())
        lvm_list = scfg.get_logical_volumes(profile.get_name())
        num_lvm  = len(lvm_list) 
        (spec_available, msg) = validate_spec(spec)
            
        print '<profile name=\"%s\" count=\"%d\" description=\"%s\" featurekey=\"%s\" upgradeable=\"%s\">' % ( \
                profile.get_name(),
                num_lvm,
                profile.get_description(),
                profile.get_featurekey(),
                spec_available)
        for lvm in lvm_list:
            print '<logical_volume name=\"%s\" description=\"%s\"' \
                  ' size_mb=\"%s\" usable_size_mb=\"%s\"/>' % (lvm.get_name(),
                                         '',
                                         lvm.get_size_mb(),
                                         lvm.get_usable_size_mb())
            
        print '</profile>'
    print '</profiles>'

###############################################################################
# cmd_get_list
#
# displays the volume list used for setup, manufacturing and VAR recovery in colon seperated 
# form
#
###############################################################################
def cmd_get_list(option, spec, model):

    if spec == None or not spec.uses_layouts():
	print 'NOP'
	exit (0)

    if option.profile in [ None, '' ]:
        profile = None
    else:
        profile = option.profile
        rlog_notice('Storage Profile is forced to %s' % profile)

    system = System (spec, 
                     model,
                     profile = profile)
    list_volumes (system)

###############################################################################
# cmd_get_led_status
#                
# Displays LED status information on systems that support it 
#                
###############################################################################
def cmd_get_led_status(option, spec, model):  
                 
    system = System (spec, model)
    system.get_led_status()


###############################################################################
# cmd_update_led_state
#                
# This command applies the current disk state to the System LED's
# It is used to take the LED's out of ON when a drive is no longer failed,
# but also will ensure that the drive LEd
#                
###############################################################################
def cmd_update_led_state(option, spec, model):

    system = System (spec, model)
    system.update_led_state()

###############################################################################
# cmd_uses_sw_raid
#
# Indicates whether this appliance uses sw raid.
#
###############################################################################
def cmd_uses_sw_raid(option, spec, model):
    check_spec (spec, model)
    profile = get_storage_profile()

    print spec.uses_raid(profile)
    return 0
    
###############################################################################
# cmd_supported
#
# is rrdm_tool supported on this appliance.
#
###############################################################################
def cmd_supported(option, spec, model):
    # if we have found a spec, rrdm_tool is supported for managing the disks
    # if we also have a spec with that supports disk layouts.
    # 
    print (spec != None and spec.uses_layouts())
    
###############################################################################
# cmd_create
#
# creates a raid device on the system.  this routine will reset the state of the
# raid arrays, and data will be lost on the devices.
#
###############################################################################
def cmd_create(option, spec, model):
    # if we're running create operationally, log it since its destructive.
    #
    rlog_notice ('Running array create for [%s] [model:%s]' % (
                 option.target,
                 model))

    # make sure we were able to get a spec
    check_spec(spec, model)

    system = System (spec, model)
    (target, device_target) = get_cmd_target(system, option.target, spec)
    is_cmd_supported(target, system)

    if target.type in [ "raid-array", "raid" ]:
	device_target.create_raid_array()
    else:
	raise rrdm_error ('%s is not a raid device' % option.target)

###############################################################################
# cmd_run
#
# starts a given raid device on the system.  This is the normal
# command used to get things started and does not harm any data on the devices.  
# 
# This will fail if the raid is not startable, i.e has multiple missing /failed
# drives.
#
###############################################################################
def cmd_run(option, spec, model):
    rlog_debug ('Running array assemble for [%s] [model:%s]' % (
                 option.target,
                 model))
    
    check_spec(spec, model)
    system = System (spec, model)
    (target, device_target) = get_cmd_target(system, option.target, spec)
    is_cmd_supported(target, system)

    if target.type in [ "raid-array", "raid" ]:
	device_target.start_raid_array()
    else:
	raise rrdm_error ('%s is not a raid device' % option.target)

###############################################################################
# cmd_stop
#
# stops a given raid device on the system.  This command will fail if users are
# still accessing the device. (i.e. its still mounted or some such )
#
###############################################################################
def cmd_stop(option, spec, model):
    rlog_debug ('Running array stop for [%s] [model:%s]' % (
                 option.target,
                 model))
    
    check_spec(spec, model)
    system = System (spec, model)
    (target, device_target) = get_cmd_target(system, option.target, spec)
    if target.type in [ "raid-array", "raid" ]:
	device_target.stop_raid_array()
    else:
	raise rrdm_error ('%s is not a raid device' % option.target)

###############################################################################
# cmd_partition
#
# Only available for disk devices, this command will apply the current partition
# table to the indicated disk.
#
###############################################################################
def cmd_partition(option, spec, model):
    check_spec(spec, model)
    if option.profile in [ None, '' ]:
        profile = None
    else:
        profile = option.profile
        rlog_notice('Storage Profile is forced to %s' % profile)

    system = System (spec, 
                     model,
                     profile = profile)
    (target, device_target) = get_cmd_target(system, option.target, spec)
    if target.type == 'disk':
	    device_target.partition_drive()
    else:
	raise rrdm_error ('%s is not a disk device.' % option.target)

###############################################################################
# cmd_fail
#
# Accepts either a disk or a raid device, for the raid device, it will
# remove the device from its parent raid array.
#
# For a disk device, it will fail all raid arrays living on that device.
#
###############################################################################
def cmd_fail(option, spec, model):
    
    # log failure commands to syslog
    #
    rlog_notice ('Running device fail for [%s] [model:%s]' % (
                  option.target,
                  model))
    
    check_spec(spec, model)
    system = System (spec, model)
    (target, device_target) = get_cmd_target(system, option.target, spec)
    is_cmd_supported(target, system)

    if target.type in [ "raid-drive", "ftraid-drive" ]:
	device_target.fail()
    elif target.type in [ "disk" ]:
	system.fail_disk (device_target)
    else:
	raise rrdm_error ('%s is not a raid device or disk device' % option.target)

###############################################################################
# cmd_add
#
# Given a physical disk or raid device add it back into the system.
#
###############################################################################
def cmd_add(option, spec, model):
    rlog_notice ('Running device add for [%s] [model:%s]' % (
                  option.target,
                  model))
        
    force_add = option.force

    check_spec(spec, model)
    system = System (spec, model)

    disk_members = spec.get_disk_members()

    # Check if the disk is a spare - print something & return 0
    if option.target.startswith('/disk'):
        split_target = option.target.lstrip('/').split('/')
        
        if len(split_target) < 1:
            rlog_notice ('Error processing %s' % (option.target))
            print 'Error processing %s' % (option.target)
	    exit (1)
        elif len(split_target) >= 2:
            disk_str = split_target[1].replace('p','')

        if disk_str.isdigit() == True:
    	    disk_num = int (disk_str, 10) 
        else:
            rlog_notice ('Error processing %s' % (option.target))
            print 'Error processing %s' % (option.target)
	    exit (1)

        if disk_num not in disk_members:
            rlog_notice ('Spare disk on %s' % (option.target))
            print 'Spare disk on %s' % (option.target)
            exit (0)
		
    (target, device_target) = get_cmd_target(system, option.target, spec)
    is_cmd_supported(target, system)

    hd = system.disk_array.find_drive_by_id(int (target.sub_target[1:], 10))
    if hd == None:
	raise rrdm_error ('Invalid drive specified %s' % (target.sub_target))

    if hd.is_missing():
        raise rrdm_error('Disk %d is missing' % hd.portnum)

    if not hd.get_license():
        raise rrdm_error ('Not a Riverbed branded disk, failing device')

    if hd.get_media() == 'ssd':
        rlog_notice ('Media is %s' % hd.get_media())
        readlink = 'readlink /dev/disk%s' % disk_num
        try:
            output = run_shell_cmd(readlink, True)
        except rrdm_error, what:
            rlog_notice ('Failed to get symbolic link %s' % what)

        rlog_notice ('Setting sysfs params for this ssd: %s' % output)
        cmd = 'echo 1 > /sys/block/%s/queue/unplug_threshold' % output
        try:
            err = run_shell_cmd(cmd)
        except rrdm_error, what:
            rlog_notice ('Failed to set sysfs params %s' % what)

    # we allow users to specify a raid target on the cmdline so we
    # can add to a specific array.
    #
    if option.raid_target != None:
	(rtarget, rdev) = get_cmd_target( system, option.raid_target, spec)
	if rdev == None:
	    raise rrdm_error ('Invalid raid device specified %s' % option.raid_target)

	rlog_debug ('Adding hot drive back to target %s' % option.raid_target)
	rdev.hot_add_drive (device_target)
    elif target.type == "ftraid-drive":
        (target, device_target) = get_cmd_target(system, option.target, spec)
        is_cmd_supported(target, system)
        device_target.add()

         
    else:
	if target.type in [ "disk" ]:
	    system.hot_add_drive (device_target, force_add)
	else:
	    raise rrdm_error ('%s is not a disk device' % option.target)


###############################################################################
# cmd_setup
#
# Do all necessary operations (partitioning, raid creation, etc) to
# restructure this unit to match the hardware layout of the given
# system model/spec.
#
# This command is destructive and will wipe out system data.
#
# Command is used in manufacturing and indicates not being supported
# with NOP as output
#
###############################################################################
def cmd_setup(option, spec, model):
    rlog_notice ('Running device mfg for model:%s' % (
                 model))

    # punt if we don't have a spec.. this model isnt supported with this tool
    if spec == None or not spec.uses_layouts():
	print 'NOP'
	exit (0)
    
    if option.profile in [ None, '' ]:
        profile = None
    else:
        profile = option.profile
        rlog_notice('Storage Profile is forced to %s' % profile)
    
    system = System (spec, 
                     model,
                     profile = profile)
    do_mfg_setup (system, option.dry_run, False)

## cmd_change_profile
# @param option OptParse option object
# @param spec appliance spec
# @param model system model number
#
# Run a storage profile reconfiguration for a given profile
# of the given system model.  The profile command line must be 
# specified
def cmd_change_profile(option, spec, model):
    rlog_notice ('Running profile reconfiguration for model %s profile' \
                  ' %s' % (model, option.profile))

    # punt if we don't have a spec.. this model isnt supported with this tool
    if spec == None or not spec.uses_layouts():
        print 'NOP'
        exit (0)

    if option.profile in [ None, '' ]:
        raise AssertionError('Change profile command requires a profile' \
                             ' command line argument')
    profile = option.profile

    system = System (spec,
                     model,
                     profile = profile)
    do_mfg_setup (system, option.dry_run, True)


################################################################################ 
# cmd_disk_count
#       
# Count of the number of disks needed for a particular spec
#           
# This return the count in the spec, does not worry 
# about how many drives are in the system
#       
###############################################################################
def cmd_disk_count(option, spec, model):
    rlog_debug ('Running disk count query for model:%s' % (model))
        
    # punt if we don't have a spec.. this model isnt supported with this tool
    if spec == None:
        # return an empty set if this tool isnt supported.
        exit (0)

    system = System (spec, model)
    try:
        print system.disk_array.get_expected_drives()
    except rrdm_error, what:
        rlog_warning("Could not find the number of disks for current spec")
        exit (1)


################################################################################ 
# cmd_spare_disks
#       
# We want to know a list of all the disks in the system that we are currently 
# not using as part of any array or part of the system.
#           
# All drives that are unused are considered spares today.
#       
###############################################################################
def cmd_spare_disks(option, spec, model):
    rlog_debug ('Running spare disk query for model:%s' % (model))
        
    # punt if we don't have a spec.. this model isnt supported with this tool
    if spec == None:
        # return an empty set if this tool isnt supported.
        exit (0)

    system = System (spec, model)
    try:
        list = system.get_spare_disks()
        for disk in list:
            print '%d %s' % (disk[0], disk[1])

    except rrdm_error, what:
        print False
        exit (0)

###############################################################################
# rrdm_spare_add_ssd_param
#
# Find the SSD parsm from the Dictionary and add to the RVBD super 
# 
# returns nothing
#
###############################################################################
def rrdm_spare_add_ssd_param(drive_number, sb):

    ## Key used for the erase block size in the SB
    #
    erase_block_key="erase_block_size"

    ## Key used for the max write lifetime in the SB
    #
    max_write_lifetime_key="max_write_lifetime_gb"
    
    found_bus = hwtool_disk_map.find_bus_by_port(drive_number)	
    if found_bus != 'unknown':
        model = get_scsi_sysfs_param(found_bus, 'model')
        if not model_to_ssdinfo_map.has_key(model):
            block_size = 1048576 # default 1MB if model not found
            max_write_lifetime = 640000 # default if model not found 
        else:
            block_size = model_to_ssdinfo_map[model].get_erase_block_size()
            max_write_lifetime = model_to_ssdinfo_map[model].get_max_write_lifetime()

        sb.add_sb_kvp((erase_block_key, '%d' % block_size))
        sb.add_sb_kvp((max_write_lifetime_key, '%d' % max_write_lifetime))
        # re-read the SB and verify the contents written.
        sb2 = RvbdSuperBlock('/dev/disk%sp1' % drive_number)
        eb = sb2.get_sb_kvp(erase_block_key)
        wlt = sb2.get_sb_kvp(max_write_lifetime_key)
        if eb == None or wlt == None:
	    print '/dev/disk%sp1 failed to add SSD info keys to SB' % drive_number 
            exit(1)
        elif int(eb) != block_size:
	    print '/dev/disk%sp1 : incorrect block size read back from SB %s' % (drive_number, eb)
            exit(1)
        elif int(wlt) != max_write_lifetime:
	    print '/dev/disk%sp1 : incorrect max write lifetime read from SB %s' % (drive_number, eb)
            exit(1)
        else:
	    print '/dev/disk%sp1: %s : eb_size [%d bytes] : max_wlt [%d GB] ' % (drive_number, 
                  model, block_size, max_write_lifetime)
    return

###############################################################################
# rrdm_spare_partition_str
#
# Generate the partition string using the DiskLayout passed in.
# 
# returns the partition string; None on failure
#
###############################################################################
def rrdm_spare_partition_str(dl):
    if dl == None:
        print 'Unable to find DiskLayout'
        exit (1)

    part_str = []
    first_part = True
    total_size = 0
    part_tbl_type = dl.get_part_tbl_type()

    for part in dl.get_part_list():

    	size = part.get_cfg_size()
    	type = part.get_ptype()

        if (part_tbl_type == "mbr"):
            if (type != '0f'):
	        if first_part:
	            part_str.append(',%d,%s,*' % (size, type))
    	            first_part = False
                else:
	            part_str.append(',%d,%s,' % (size, type))
            else:
	        part_str.append(',,%s,' % type)
        else:
            prev_total_size = total_size
            total_size += size
            part_str.append('%s %d %d' % (type, prev_total_size, total_size))

    return ''.join (["%s\n" % (str) for str in part_str])
	

###############################################################################
# rrdm_spare_partition_drive
#
# CAREFUL .. this command will repartition your drive
# create a temp file in /tmp and use that for the master partition record
#
# returns nothing 
#
###############################################################################
def rrdm_spare_partition_drive(drive_number, partition_str, dl, dry = True):
    try:
        name="/tmp/spare_part"
	tfile = open(name, "w+b")
	part_str = partition_str
	tfile.write(part_str)
	tfile.close()

	rlog_debug ("Partition Table :")
	rlog_debug (part_str)
	rlog_debug ("End Partition Table")
    except IOError:
	raise rrdm_error ('Unable to open temp partition table file')

    # Add Licensing constraints
    licensed = hwtool_dlm.is_licensed('%s' % drive_number)
    if licensed == False:
        rlog_notice ('disk%s is not licensed - Bailing' % drive_number)
        print 'disk%s is not licensed ' % (drive_number)
        exit(1)
                
    dname = 'disk%s' % (drive_number)
    part_tbl_type = dl.get_part_tbl_type()

    if part_tbl_type == "mbr":
        cmd_line = 'sfdisk -q -uM /dev/%s 2>&1 < %s > /dev/null' % (dname, name)
    else:
        cmd_line = '/sbin/parted -s /dev/%s mklabel gpt > /dev/null 2>&1' % (dname)

    if dry:
	print cmd_line
    else:
	err = run_shell_cmd(cmd_line)
	if err:
	    raise rrdm_error ('Failed to partition device /dev/%s' % dname)

    if part_tbl_type == "gpt":
        f = open(name, 'r')
        for line in f:
            cmd_line = '/sbin/parted /dev/%s mkpart %s' % (dname, line)
            if dry:
                print cmd_line
            else:
                err = run_shell_cmd(cmd_line)
                if err:
                    raise rrdm_error ('Failed to partition device /dev/%s' % dname)


############################################################################
# rrdm_spare_clear_labels
#
# During manufacturing it is necessary to clear the labels on disks, because 
# repartitioning isnt guaranteed to do that and if a disk being inserted
# is from an old machine, we may inadvertently get a duplicate label
# which can cause the system to not boot.
#
############################################################################
def rrdm_spare_clear_labels(dl, drive_number):
    e2_cmd  = '/sbin/e2label'
    for part in dl.get_part_list():
	dev = '/dev/disk%s' % (drive_number)
	cmd = '%s %s \"\"' % (e2_cmd, dev)

	if not exists (dev):
	    rlog_info ('device %s does not exist' % dev)
	else:
	    try:
		run_shell_cmd (cmd)
	    except rrdm_error, what:
		# right now just trying on each partition to ensure that
		# if it had ext3 data on it and a label, then
		# we should clear it.
		pass

###############################################################################
# rrdm_spare_get_layout
#
# Read the spare disk layout from the spec file and sake in DiskLayout object.
# 
# returns the DiskLayout object; None on failure
#
###############################################################################
def rrdm_spare_get_layout(spec_file):

    from xml.dom.minidom import parse
    # Get the disk_layout from the spec file for the spares
    image_spec_file="/opt/hal/lib/specs/specs.xml"
    mfg_spec_file="/mfg/specs.xml"

    # Lookup the partition table layout from 
    # spare-partition layout in spec file
    if not spec_file:
        try:
            stat(image_spec_file)
            name = image_spec_file
        except OSError: 
            try:
                stat(mfg_spec_file)
                name = mfg_spec_file
            except OSError:
                print 'Unable to find specs.xml'
                exit (1)
    else:
        if not exists(spec_file):
            print 'Unable to find  spec file %s' % spec_file
            exit (1)

        name = spec_file

    rlog_debug('Using spec file :' + name)
    xml = parse(name)

    # The zone_layout tag contains the relevent info
    layout_list = xml.getElementsByTagName('zone_layout')
    for layout in layout_list:
        dl = DiskLayout(layout)
        if dl.get_name() == 'spare_all':
            return dl

    return None

###############################################################################
# rrdm_spare_get_number
#
# Read spec file to determine the number of unused disks in the system.
# 
# returns a list of spares i.e. their port numbers 
#
###############################################################################
def rrdm_spares_get_num(spec, model, system = None):
    # Look for all online disks apart from the ones already defined in 
    # the spec - for e.g. execpt mgmt and fts disk zones. 
    spare_list = []
    if system == None:
        system = System (spec, model)
    try:
        list = system.get_spare_disks()
	# the prints are just for debug
        for disk in list:
            if disk[1] == 'spare':
                spare_list.append(disk[0])	

    except rrdm_error, what:
        exit (0)
        
    return spare_list

###############################################################################
# rrdm_spare_get_serial 
#
# Use the disk port to get serial number 
# 
# returns serial number
#
###############################################################################
def rrdm_spare_get_serial(system, mfg_mode = False):
    if mfg_mode == True:
        serial = spare_serial_num
        return serial
    else:
        # Get Serial number of the box 
        serial = system.get_appliance_serial()

    return serial

###############################################################################
# rrdm_spare_add_rvbd_super
#
# Look for the "rvbd" partition in the disk layout.
# Use a device for each such partition e.g. /dev/disk2p1 or /dev/disk3p2
# to instantiate a RvbdSuperBlock object for each.
# Add Information  to it e.g. serial number etc. - Maybe from a Dict file
# Use class methods to update rvbd super the partition
# 
# returns nothing
#
###############################################################################
def rrdm_spares_add_rvbd_super( dl, drive_number, system, mfg_mode = False):
    rlog_debug ('Adding super blocks to spare disks')
    if dl == None:
        print 'Unable to find DiskLayout'
        exit (1)

    try:	
        for part in dl.get_part_list():
            if part.get_name() == 'rvbd': 
	       device_name = "/dev/disk%sp%s" % (drive_number, part.get_part_id())
               rvbd_super = RvbdSuperBlock (device_name)
	       serial = rrdm_spare_get_serial (system, mfg_mode) 
	       ver = ('version', '1')
	       rvbd_super.update_from_kvp(ver)
	       # Update the superblock information
	       rvbd_super.update_superblock (serial, drive_number, 0)
	       # Add params like "erase block size"
	       rrdm_spare_add_ssd_param(drive_number, rvbd_super)

    except rrdm_error, what:
        rlog_warning ('Error adding RVBD super-block to spare')
        print 'Error adding RVBD super-block to spare'
        exit (1)


###############################################################################
# cmd_fmt_spares
#
# Partition all spare disks with the RVBD super block
#
# return nothin
#
###############################################################################
def cmd_fmt_spares(option, spec, model, mfg_mode = True):
    global spec_file
    rlog_debug ('Formatting spare disks')
    # punt if we don't have a spec.. this model isnt supported with this tool
    if spec == None:
        # return an empty set if this tool isnt supported.
        exit (0)

    system = System (spec, model)

    # Find if any spare disks exist in the system.
    spare_list = rrdm_spares_get_num (spec, model, system) 
    # Check if spare disk list is empty
    if len(spare_list) == 0:
    	rlog_debug ('No spare disks found')
    	print 'No spare disks found'
        exit (0)	

    # Get Spare disk Layout
    dl = rrdm_spare_get_layout(spec_file)
    # If layout is not found - exit	
    if dl == None:
    	rlog_warning ('Spare disk layout not found')
    	print 'Spare disk layout not found'
	# Its not returning a failure because we do not want
	# code to fail on other products.
        exit (0)

    # Generate the partition layout 
    partition_str = rrdm_spare_partition_str(dl)
    if partition_str == None or len(partition_str) == 0:
    	rlog_warning ('Spare disk layout bad string')
	exit (1)
 
    try:	
	# Partition and Add RVBD super to each disk
	for drive in spare_list:
	    # Partition each spare disk with this disk layout
	    rrdm_spare_partition_drive (drive, partition_str, dl, False)
	    # Clear labels 
	    rrdm_spare_clear_labels (dl, drive)
	    # Add rvbd-super to each disk
	    rrdm_spares_add_rvbd_super (dl, drive, system, mfg_mode)

    except rrdm_error, what:
        rlog_warning ('Error Partitioning / adding RVBD super-block to spare')
        print 'Error Partitioning / adding RVBD super-block to spare'
        exit (1)

###############################################################################
# cmd_setup_spare
#
# Partition and add rvbd_super to the given spare disk
#
# return nothin
#
###############################################################################
def cmd_setup_spare(option, spec, model, mfg_mode = True):
    global spec_file
    rlog_debug ('Setting-up spare disk')
    # Cmd line options
    drive_num = option.drive

    # Check if drive number is invalid
    if drive_num == None or drive_num.isdigit() == False:
    	rlog_warning ('Drive number is missing')
    	print 'Drive number is missing'
	exit (1)

    # Create the drive
    drive = int(drive_num)
    
    # Get Spare disk Layout
    dl = rrdm_spare_get_layout(spec_file)
    # If layout is not found - exit	
    if dl == None:
    	rlog_warning ('Spare disk layout not found')
    	print 'Spare disk layout not found'
        exit (1)

    # Generate the partition layout 
    partition_str = rrdm_spare_partition_str(dl)
    if partition_str == None or len(partition_str) == 0:
    	rlog_warning ('Spare disk layout bad string')
        exit (1)

    # Partition and Add RVBD super to the disk
    try: 
	# Partition disk with this disk layout
	rrdm_spare_partition_drive (drive, partition_str, dl, False)
	# Clear labels 
	rrdm_spare_clear_labels (dl, drive)
	# Add rvbd-super to each disk
	rrdm_spares_add_rvbd_super (dl, drive, None, mfg_mode)

    except rrdm_error, what:
        rlog_warning ('Error Partitioning / adding RVBD super-block to spare')
        print 'Error Partitioning / adding RVBD super-block to spare'
        exit (1)

################################################################################ 
# cmd_show_spare_disks
#       
# Display the information of all spares disks present. 
#           
# All drives that are unused are considered spares today.
#       
###############################################################################
def cmd_show_spare_disks(option, spec, model):
    rlog_debug ('Running spare disk info query for model:%s' % (model))
        
    # make sure we were able to get a spec
    check_spec(spec, model)

    # Find if any spare disks exist in the system.
    spare_list = rrdm_spares_get_num (spec, model) 
    # Check if spare disk list is empty
    if len(spare_list) == 0:
    	rlog_debug ('No spare disks found')
        exit (0)	

    # Get the information for each spare disk 
    for port in spare_list:
        drive = HardDisk()
	try: 
	    drive.fill_system_spare_info(port)
            drive.display_drive_info()
        except rrdm_error, what:
            print 'Error getting spare disk information from system'
            rlog_warning ('Error getting spare disk information from system')
	    exit (1)
        	 

###############################################################################
# cmd_validate
#
# Verify that this unit has the required hardware for the given spec/model.
#
# returns True if Hardware is approriate, False otherwise.
#
###############################################################################
def cmd_validate(option, spec, model):
    rlog_debug ('Running hardware validate for model:%s' % (model))

    # punt if we don't have a spec.. this model isnt supported with this tool
    if spec == None:
        print 'NOP'
        exit (0)

    if option.profile in [ None, '' ]:
        profile = None
    else:
        profile = option.profile
        rlog_notice('Storage Profile is forced to %s' % profile)

    system = System (spec, 
                     model, 
                     profile = profile)
    try:
        if spec.uses_layouts():
	    system.validate()
    except rrdm_error, what:
        rlog_notice(str(what))
	print False
	exit (0)

    print True

	

###############################################################################
# cmd_check_consistency
#
# Check the system RAID for consistency
# This involves making sure that all the raid arrays match are on the drives
# they are supposed to be on.  If this is ever not true, we might have 
# a configuration where a 2 disk failure (which are not on the same mirror for one
# array but are on the same mirror for another array) might reduce our robustness:w
#
# really only for RAID-10, but still good if we offer other raids as well, 
# we should always be in a good known state.
#
###############################################################################
def cmd_check_consistency(option, spec, model):
    in_sync = True

    system = System (spec, model)

    # sync the led's to the physical disk state.
    system.update_led_state()

    for array in system.raid_arrays.get_array_list():
	# make an attempt to clear out any drives that md was too busy 
	# to remove, when we failed them
	try:
            array.purge_faulty_drives()
	except rrdm_error:
	    pass

	try:
	    if not array.check_consistency():
		print 'Array %s is out of sync' % array.get_devname()
		in_sync = False
	except rrdm_error, what:
            # this should be info level, but at the moment, we'll still talk to failed drives
            # and spam the logs so lowering this debug level.
	    rlog_debug ('Unexpected exception in consistency check, continuing, [%s]' % what)

    if in_sync:
	print 'System Raid Array configuration is correct'

###############################################################################
# cmd_apply_disk_settings
#
# Command to apply any disk specific sysfs params. To be called in the init scripts
#
###############################################################################
   
def cmd_apply_disk_settings(option, spec, model):
    rlog_notice ('Applying disk settings for [%s] [model:%s]' % (
                  option.target,
                  model))

    check_spec(spec, model)
    system = System (spec, model)

    for hd in system.disk_array.get_drive_list():
	if hd.is_missing():
    	    rlog_notice('Disk %d is missing' % hd.get_portnum())
	    continue
	if hd.get_media() == 'ssd':
	    rlog_info ('Media is %s' % hd.get_media())
            readlink = 'readlink /dev/disk%s' % hd.get_portnum()
            try:
                output = run_shell_cmd(readlink, True)
            except rrdm_error, what:
                rlog_notice ('Failed to get symbolic link %s' % what)
    
            rlog_info ('Setting sysfs params for this ssd: %s' % output)
            cmd = 'echo 1 > /sys/block/%s/queue/unplug_threshold' % output
            try:
                err = run_shell_cmd(cmd)
            except rrdm_error, what:
                rlog_notice ('Failed to set sysfs params %s' % what)
 
	
###############################################################################
# cmd_config
#
# Commands to get/set the disk config, optionally a command line arg
# can be passed to tell the tool not to use the default path and instead
# to use the path specified by --system-config. 
#
###############################################################################
def cmd_config(option, spec, model):
    system = System (spec, model)
    
    # check the command line for the path to the config
    #
    try:
	if option.system_config != None:
	    sysConfig = SystemConfig(option.system_config)
	else:
	    sysConfig = SystemConfig()
    except AttributeError:
	sysConfig = SystemConfig()
    
    command = '%s' % option.command
    if command == '--read-config':
	sysConfig.display_disk_config ()
    elif command == '--write-config':
	sysConfig.write_config (system)
    

###############################################################################
# cmd_rebuild_rate
#
# Allows getting/setting of the system rebuild rate, which is a per array
# maximum bandwidth allowed to rebuild operations (in MB/s).
#
# Also accepts the following for the set command:
#   fast_rebuild: rebuild rate is very high
#   slow_rebuild: rebuild rate is very low
#   normal:       rebuild rate and IO are evenly matched
#
###############################################################################

def cmd_rebuild_rate(option, spec, model):
    rate_table = { "fast_rebuild": "40000",
		   "slow_rebuild": "10000",
		   "normal": "25000" }

    rlog_debug ('Running rebuild rate for model:%s' % (
                model))

    raid_rebuild_max_proc = '/proc/sys/dev/raid/speed_limit_max'
    if not exists (raid_rebuild_max_proc):
	raise rrdm_error ('Raid rebuild speed proc entry does not exist')

    command = '%s' % option.command
    if command == "--get-rebuild-rate":
	try:
	    file = open (raid_rebuild_max_proc, 'r')
	    try:
		rate=file.read()
	    
	    finally:
		file.close()
	except (IOError, OSError):
	    raise rrdm_error ('Unable to read rebuild rate from proc')
	
	print '%s' % rate
	
    elif command == "--set-rebuild-rate":
	try:
	    rate = '%s' % option.target
	except AttributeError:
	    raise rrdm_error ('Set rebuild rate requires a rate parameter')

	try:
	    rate=rate_table[rate]
	except KeyError:
	    try:
		if int(rate,10) < 0:
		    raise rrdm_error ('Rebuild rate must be > 0')
	    except ValueError:
		raise rrdm_error('Rebuild rate must be a positive integer')

        try:
            file = open (raid_rebuild_max_proc, 'w')
            try:
                file.write(rate)
            finally:
                file.close()
        except IOError:
            raise rrdm_error ('Unable to read rebuild rate from proc')


def cmd_generate_spec_cache(option, spec, model):
    pass
    
###############################################################################
# List of command handlers indexed by optparse option string.
#
# When adding new command line options that result in an action,
# add a new handler here.
#
# optparse appends each argument together with a /.  So a command
# with a short option -s and a long option -- status gets '-s/--status'
# as the key
#
###############################################################################
cmd_handlers = { '-s/--status'		: cmd_get_status,
		 '-d/--detail-status'	: cmd_get_detail_status,
		 '--get-partition'	: cmd_get_partition,
		 '--raid-info'		: cmd_get_raid_info,
		 '--get-physical'	: cmd_get_physical,
		 '--get-raid-configuration' : cmd_get_raid_configuration,
		 '--get-rebuild-rate'   : cmd_rebuild_rate,
		 '--set-rebuild-rate'   : cmd_rebuild_rate,
		 # config test routines
		 '--write-config' : cmd_config,
		 '--read-config' : cmd_config,
		 '--check-raid-consistency' : cmd_check_consistency,
		 '--apply-disk-settings'    : cmd_apply_disk_settings,
		 '-l/--list'		: cmd_get_list,
		 '--all-disk-list'      : cmd_get_all_disks,
                 '--logical-volumes'    : cmd_list_logical_volumes,
                 '--list-profiles'      : cmd_list_profiles,
                 '--list-mount-points'  : cmd_list_mount_points,
                 '--mount-filesystems'  : cmd_mount,
                 '--format-volume'      : cmd_format_lvm,
                 '--update-metadata'    : cmd_update_metadata,
		 '--get-led-status'	: cmd_get_led_status,
		 '--update-led-state'	: cmd_update_led_state,
		 '--uses-sw-raid'	: cmd_uses_sw_raid,
		 '--supported'		: cmd_supported,
                 '--has-volume'         : cmd_has_volume,
		 '-c/--create'		: cmd_create,
		 '-r/--run'		: cmd_run,
		 '-q/--stop'		: cmd_stop,
		 '-p/--partition'	: cmd_partition,
		 '-f/--fail'		: cmd_fail,
		 '-u/--setup'		: cmd_setup,
                 '--change-profile'     : cmd_change_profile,
		 '--validate'		: cmd_validate,
		 '--spares'		: cmd_spare_disks,
		 '--show-spares'	: cmd_show_spare_disks,
		 '--disk-count'		: cmd_disk_count,
		 '-a/--add'	        : cmd_add,
		 '--format-spares'	: cmd_fmt_spares,
		 '--setup-spare'	: cmd_setup_spare,
                 '--list-by-media'      : cmd_list_by_media,
                 '--generate-spec-cache': cmd_generate_spec_cache}

###############################################################################
# Cmd Line Callbacks
#
# We support two types of callbacks at the moment, a boolean flag, which sets
# a bool in the option structure, or a command, which has one required
# argument.
#
# When adding a command you would choose the callback action and specify the 
# type of callback needed in the optparse.add_option() call.
#
###############################################################################
def rrdm_bool_cmd_callback(option, opt_str, value, parser, *args, **kwargs):
    global has_command_set
    if has_command_set:
	print 'Only one command allowed on the command line at a time.'
	exit(1)
    else:
	has_command_set=True
	setattr(parser.values, 'command', option)

def rrdm_cmd_callback(option, opt_str, value, parser, *args, **kwargs):
    global has_command_set
    if has_command_set:
	print 'Only one command allowed on the command line at a time.'
	exit(1)
    else:
	has_command_set=True
	setattr(parser.values, 'command', option)
	setattr(parser.values, option.dest, value)


###############################################################################
#
# Call back function for generate_spec_cache cmd line option
#
###############################################################################
def rrdm_generate_spec_cache(option, opt_str, value, parser):
    image_spec_file="/opt/hal/lib/specs/specs.xml"
    mfg_spec_file="/mfg/specs.xml"
    spec_file = None
    if not spec_file:
        try:
	    stat(image_spec_file)
            name = image_spec_file
        except OSError:
	    try:
	        stat(mfg_spec_file)
                name = mfg_spec_file
	    except OSError:
	        print 'Unable to find specs.xml'
	        exit (1)
    else:
        if not exists(spec_file):
            print 'Unable to find  spec file %s' % spec_file
            exit (1)

        name = spec_file

    generate_spec_cache( name );
    setattr(parser.values, 'command', option)
    setattr(parser.values, option.dest, value)
    


###############################################################################
#
###############################################################################
def setup_parser():
    global cmd_handlers, spec_file
    parser = OptionParser()

    # command line option flags
    #
    parser.add_option ("-m", "--model", dest="model",
		       help="use MODEL specification", metavar="MODEL") 
    parser.add_option ("--mfdb-path", dest="mfdb_path",
		       help="use mfdb path for manufacturing DB") 
    parser.add_option ("--profile", dest="profile",
                       help="use storage PROFILE", metavar="PROFILE")
    parser.add_option ("-n", "--dry-run", action="store_true", dest="dry_run", default=False,
			help="performs an operation without making any changes")
    parser.add_option ("-v", "--verbose", action="store_true", dest="verbose", default=False,
			help="display debugging info to the screen")
    parser.add_option ("--force", action="store_true", dest="force", default=False,
			help="Aways perform action regardless of system statte (e.x. adding an invalid drive")
    parser.add_option ("-x", "--xml", action="store_true", dest="xml_output", default=False,
			help="display status command output in XML")
    parser.add_option ("--raid-target", dest="raid_target", type="string", nargs=1,
			help="When used with the add device command, add the device into the specified RAID_TARGET",
		        metavar="RAID_TARGET")
    parser.add_option ("--system-config", dest="system_config",
		       help="Use TARGET as the system disk configuration file", metavar="TARGET") 
    parser.add_option ("--spec-file", dest="spec_file",
		       help="Use TARGET as the spec file", metavar="TARGET") 

    # commands, these can  be one at a time on the cmdline
    # commands without arguments, note the use of the rrdm_bool_cmd_callback
    #
    parser.add_option ("--get-led-status",  action="callback", callback=rrdm_bool_cmd_callback,
			dest="ledstat", default=False, help="Display Disk LED status information")
    parser.add_option ("--get-rebuild-rate",  action="callback", callback=rrdm_bool_cmd_callback,
			dest="get_rebuild", default=False, help="Get the rebuild rate for the system in MB/s")
    # XXX config write
    parser.add_option ("--write-config",  action="callback", callback=rrdm_bool_cmd_callback,
			dest="write_config", default=False, help="Get the rebuild rate for the system in MB/s")
    parser.add_option ("--read-config",  action="callback", callback=rrdm_bool_cmd_callback,
			dest="read_config", default=False, help="Get the rebuild rate for the system in MB/s")
    parser.add_option ("--update-led-state",  action="callback", callback=rrdm_bool_cmd_callback,
			dest="ledstat", default=False, help="Apply the current disk configuration state to the Disk LED's")
    parser.add_option ("-l", "--list",  action="callback", callback=rrdm_bool_cmd_callback,
			dest="list", default=False, help="list riverbed volume information")
    parser.add_option ("--all-disk-list",  action="callback", callback=rrdm_bool_cmd_callback,
			dest="alldisklist", default=False, help="list riverbed disk information in XML with partition information")
    parser.add_option ("--logical-volumes",  action="callback", callback=rrdm_bool_cmd_callback,
			dest="lvm", default=False, help="List XML information about logical volumes/services")
    parser.add_option ("--list-profiles",  action="callback", callback=rrdm_bool_cmd_callback,
			dest="listprof", default=False, help="List XML info about available storage profiles")
    parser.add_option ("--list-mount-points",  action="callback", callback=rrdm_bool_cmd_callback,
			dest="listmount", default=False, help="List information about mounted filesystems profiled by the model")
    parser.add_option ("--mount-filesystems",  action="callback", callback=rrdm_bool_cmd_callback,
			dest="mountfs", default=False, help="Mount rrdm managed filesystems associated with this model")
    parser.add_option ("--update-metadata",  action="callback", callback=rrdm_bool_cmd_callback,
			dest="updatemetadata", default=False, help="Sync spec/profile metadata to the mfdb")
    parser.add_option ("--uses-sw-raid",  action="callback", callback=rrdm_bool_cmd_callback,
			dest="uses_sw_raid", default=False, help="Does this appliance use sw raid")
    parser.add_option ("--supported",  action="callback", callback=rrdm_bool_cmd_callback,
			dest="supported", default=False, help="Is this tool supported on this appliance")
    parser.add_option ("--has-volume", action="callback", callback=rrdm_cmd_callback,
                        dest="target", type="string", nargs=1,
                        help="Returns true if the appliance has the volume TARGET", metavar="TARGET")
    parser.add_option ("--validate", action="callback", callback=rrdm_bool_cmd_callback,
			dest="validate", default=False, help="Verify the hardware for this spec")
    parser.add_option ("--spares", action="callback", callback=rrdm_bool_cmd_callback,
			dest="validate", default=False, help="Display a list of unused disks in the system")
    parser.add_option ("--show-spares", action="callback", callback=rrdm_bool_cmd_callback,
			dest="validate", default=False, help="Display the information of unused disks in the system")
    parser.add_option ("--format-spares", action="callback", callback=rrdm_bool_cmd_callback,
			dest="validate", default=False, help="Format all spare disks in the system")
    parser.add_option ("--disk-count", action="callback", callback=rrdm_bool_cmd_callback,
			dest="info", default=False, help="Display the number of disks in a spec")
    parser.add_option ("-u", "--setup", action="callback", callback=rrdm_bool_cmd_callback,
			dest="setup", default=False, help="Do the manufacturing setup for this appliance")
    parser.add_option ("--change-profile", action="callback", callback=rrdm_bool_cmd_callback,
			dest="change_profile", default=False,  help="Perform a storage profile reconfiguration for the system")
    parser.add_option ("--raid-info", action="callback", callback=rrdm_bool_cmd_callback,
			dest="info", default=False, help="Display user visible raid information from the system")
    parser.add_option ("--get-physical", action="callback", callback=rrdm_bool_cmd_callback,
			dest="info", default=False, help="Display user visible disk system info")
    parser.add_option ("--get-raid-configuration", action="callback", callback=rrdm_bool_cmd_callback,
			dest="info", default=False, help="Display user visible disk system info")
    parser.add_option ("--check-raid-consistency", action="callback", callback=rrdm_bool_cmd_callback,
			dest="consist", default=False, help="Verifies that the software raid configuraiton on this unit is correct.")
    parser.add_option ("--apply-disk-settings", action="callback", callback=rrdm_bool_cmd_callback,
                        dest="settings", default=False, help="Apply any sysfs disk settings")

    # commands with arguments
    # note the use of the rrdm_cmd_callback, which takes 1 argument
    #
    parser.add_option ("--set-rebuild-rate", action="callback", callback=rrdm_cmd_callback, 
			dest="target", type="string", nargs=1,
			help="Set the rebuild rate limit in MB/s for the system, or optionally the preset values fast_rebuild, slow_rebuild, or normal", metavar="TARGET")
    parser.add_option ("-s", "--status", action="callback", callback=rrdm_cmd_callback, 
			dest="target", type="string", nargs=1,
			help="get status of system TARGET", metavar="TARGET")
    parser.add_option ("-d", "--detail-status", action="callback", callback=rrdm_cmd_callback,
		        dest="target", type="string", nargs=1,
			help="get detailed status of system TARGET", metavar="TARGET")
    parser.add_option ("--get-partition", action="callback", callback=rrdm_cmd_callback,
			dest="target", type="string", nargs=1,
                        help="Return the swap partition", metavar="TARGET")
    parser.add_option ("-c", "--create", action="callback", callback=rrdm_cmd_callback,
		        dest="target", type="string", nargs=1,
			help="create raid array TARGET", metavar="TARGET")
    parser.add_option ("-r", "--run", action="callback", callback=rrdm_cmd_callback,
		        dest="target", type="string", nargs=1,
			help="start raid array TARGET", metavar="TARGET")
    parser.add_option ("-q", "--stop", action="callback", callback=rrdm_cmd_callback,
		        dest="target", type="string", nargs=1,
			help="stop raid array TARGET", metavar="TARGET")
    parser.add_option ("-p", "--partition", action="callback", callback=rrdm_cmd_callback,
		        dest="target", type="string", nargs=1,
			help="partition disk TARGET", metavar="TARGET")
    parser.add_option ("-f", "--fail", action="callback", callback=rrdm_cmd_callback,
		        dest="target", type="string", nargs=1,
			help="fail raid TARGET", metavar="TARGET")
    parser.add_option ("-a", "--add", action="callback", callback=rrdm_cmd_callback,
		        dest="target", type="string", nargs=1,
			help="add DEVICE back into the system raid arrays (use raid-target to limit to a particular array)")
    parser.add_option ("--setup-spare", action="callback", callback=rrdm_cmd_callback,
		        dest="drive", type="string", nargs=1,
			help="Format and add rvbd_super to the given disk - make it a spare")
    parser.add_option ("--list-by-media", action="callback", callback=rrdm_cmd_callback, 
                        dest="media", type="string", nargs=1,
			help="display a list of drives in the system by MEDIA type",
		        metavar="MEDIA")
    parser.add_option ("--format-volume", action="callback", callback=rrdm_cmd_callback, 
                        dest="volume_name", type="string", nargs=1,
			help="Run the format-method assigned with VOLUME",
		        metavar="VOLUME")

    # special commands to generate the binary cache file for spec file
    parser.add_option ("--generate-spec-cache", action="callback", callback=rrdm_generate_spec_cache, 
			help="Generate the binary xml cache file for spec file to improve the parsing speed",
			dest = "gen_spec_cache")

    (options, args) = parser.parse_args()

    if options.verbose:
	display_debug(True)

    # the cmdline model overrides the system model
    #
    # check if the model was passed on the cmdline, if not fetch it from
    # the mfdb
    #
    if not options.model:
        model = get_model()
        if not model:
            print "Could not determine model, exiting"
            exit(1)
    else:
	model = options.model

    spec_file = options.spec_file

    #
    # do system setup
    #
    # figure out what hw we need by parsing the configuration file.
    spec = None
    try:
        spec = read_spec_configuration(model, spec_file)
    except rrdm_error:
	# this is ok on old platforms.
	rlog_debug ('Specification not found for model %s' % model)

    # spec error handling got pushed into the cmd handlers since
    # for setup and list commands we use the string internally and don't
    # really want an end user visible string, for the rest, a reasonable 
    # error message is appropriate.

    # looks like python is doing something with the string type for the option, 
    # so convert it to a normal internal string before use.
    #
    cmd='%s' % options.command
    try:
	cmd_handlers[cmd](options, spec, model)
    except KeyError:
	print 'No command handler registered for cmd %s' % cmd
	exit (1)
    except rrdm_error, error_msg:
	rlog_notice ('rrdm tool failed with error [%s]' % error_msg)
	print error_msg
	exit (1)

def main():

    setup_parser ()

if __name__ == '__main__':
    try:
        main()
    except rrdm_error, what:
	rlog_notice ('rrdm tool failed with error [%s]' % what)
        print what
        exit(1)
    exit(0)
