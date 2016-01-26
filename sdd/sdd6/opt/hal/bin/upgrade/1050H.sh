#!/bin/bash
###############################################################################
# 1050H.sh
# Performs upgrade to 1050H series appliance (assumes proper checks have 
# already been done to ensure this model can be upgraded (flex lic), and 
# that this is already a 1050 series appliance.
#
# Based off of the previous 2020 upgrade script
#
# Command line :
# <SPEC>: Perform the ugprade to the indicated spec. This script only supports the
#         1050H upgrade as it is the only one that currently attempts to preserve 
#	  data.
# --rollback: Revert the changes from a previous 1050H upgrade.
#
# If a hardware upgrade is killed during the middle of reformatting the disks,
# our end result is unclear. We use a file on /config/upgrade
# Called .rollback_needed which means that we need to execute a recovery
# script to roll back the previous upgrade changes. The recovery will reformat
# the appropriate partition (destructive).
# 
# The .upgrade_action  file will contain the full path to a shell script
# which can be executed to perform the rollback (This one!).
#
###############################################################################

###############################################################################
# GLOBALS
###############################################################################
PROGRAM="hwupgrade"

LOG_WARN="/usr/bin/logger -p user.WARN -t ${PROGRAM}"
LOG_NOTICE="/usr/bin/logger -t ${PROGRAM} -p user.NOTICE"

# pull in necessary tool and upgrade variable definitions.
#
UPGRADE_COMMON=/opt/hal/bin/upgrade_common.sh
if [ ! -f ${UPGRADE_COMMON} ]; then
    ${LOG_WARN} "Unable to locate ${UPGRADE_COMMON}. Hardware Upgrade processing unavailable"
    exit 1
fi

. ${UPGRADE_COMMON}


SUPPORTED_MODELS="1050H"

###############################################################################
# cleanup_ext3_resize
#
# puts the journal flag back on the PFS device, also it will stop the raid
# array if it had previously been started. This is here to un-do steps taken to 
# get the PFS dev ready for resize.
#
###############################################################################
cleanup_ext3_resize()
{
    /sbin/tune2fs -O has_journal ${PFS_DEV}
    if [ $? -ne 0 ]; then
        do_log "Failed to re-enable journaling on ${PFS_DEV}"
	return 1
    fi
	
    if [ "x$1" = "xstop" ]; then
    	mdadm --stop ${PFS_DEV}
    fi

    return 0
}

###############################################################################
# resize_ext3_fs
#
# Do the setup needed to resize an ext3 fs (we assume its unmounted already).
# This takes a few minutes because of the e2fsck and the resize2fs.
#
# 1. remove the journal bit
# 2. fsck -y -f to ensure consistency (resize2fs fails if you don't do this).
# 3. run resize2fs (this takes a few minutes)
#
#
###############################################################################
resize_ext3_fs()
{
	/sbin/tune2fs -O ^has_journal ${PFS_DEV}
	if [ $? -ne 0 ]; then
		do_log "Failed to remove journal from FS."
		return 1
	fi

	${E2FSCK} -y -f ${PFS_DEV}
	if [ $? -ne 0 -a $? -ne 1 ]; then
		# return codes have meaning
		# everything other than 0,1 indicate a problem
		# which needs attention
		do_log "e2fsck ${PFS_DEV} failed"

		cleanup_ext3_resize stop

		return 1
	fi

	${RESIZE2FS} ${PFS_DEV}
	if [ $? -ne 0 ]; then
		# if we fail to resize the filesystem, the end results are probably 
		# unexpected.
		do_log "Failed to resize2fs ${PFS_DEV}"
		
		cleanup_ext3_resize stop

		# we need to fix the original partition.
		do_rollback
		return 1
	fi

	# put the journal back on.
	# no sense in going back now if it fails since we've already resized.
	# don't stop the array.
	cleanup_ext3_resize

	return 0
}


prep_upgrade()
{
    local COUNT=0

    if [ ! -f ${MODEL_FILE} ]; then
	do_log "Required model file ${MODEL_FILE} not found"
	exit 1
    fi

    # make sure we have enough disks to go to the requested spec
    #
    check_disk_config ${TARGET_MODEL}
    if [ $? -ne 0 ]; then        
        exit 1
    fi

    # save a copy of the mfdb that we can modify.
    #
    save_working_db
    if [ $? -ne 0 ]; then
	do_log "Unable to save mfg DB"
	exit 1
    fi


    # make sure the devices we want are there
    while [ ! -b /dev/disk1 -a ${COUNT} -lt 5 ]; do
        sleep 2
        COUNT=$[ ${COUNT} + 1 ]
    done

    if [ $COUNT -eq 5 ]; then
        do_log "Device /dev/disk1 not found"
        exit 1
    fi

    [ $READ_ONLY_ROOT -ne 0 ] && mount / -o remount,rw
    
    # call out to rrdm_tool to make this disk like
    # a 1050H disk 2.
    ${RRDM_TOOL} -m 1050H -p /disk/p1
    if [ $? -ne 0 ]; then
	do_log "Unable to partition second drive"
	exit 1
    fi

    COUNT=0
    while [ ! -b /dev/disk1p6 -a ${COUNT} -lt 5 ]; do
        sleep 2
        COUNT=$[ ${COUNT} + 1 ]
    done

    if [ $COUNT -eq 5 ]; then
        do_log "Device naming not complete"
        exit 1
    fi

    [ $READ_ONLY_ROOT -ne 0 ] && mount / -o remount,ro

}

do_upgrade()
{


    # we left space at the end of the PFS partition for the MD superblock, so this 
    # operation does not affect the existing /proxy data at all. If we fail the upgrade 
    # process before starting the resize, we don't need to do anything special 
    # to undo the pfs raid changes as we'll mount the single device directly on	
    # startup.
    #
    create_1050H_pfs_raid
    if [ $? -ne 0 ]; then
	do_log "Unable to create software raid for PFS"
	exit 1
    fi

    # PFS_DEV comes from the hal_1050H script.
    PFS_DEV=/dev/${PFS_DEV}

    set_upgrade_rollback_file

    resize_ext3_fs
    if [ $? -ne 0 ]; then
	do_log "Update to ${TARGET_MODEL} failed."
	exit 1
    fi

    # update the model parameters
    #
    do_update_model_params
    if [ $? -ne 0 ]; then
        do_log "Unable to update model params in new mfdb"
        exit 1
    fi

    clear_upgrade_rollback_file

    ${RRDM_TOOL} -m 1050H --write-config > /dev/null
    if [ $? -ne 0 ]; then
        # the config is used for mostly reporting purposes, 
        # but there isnt any reason we should not be able to update it.
        do_log "Unable to update disk configuration XML" WARN
    fi

    # clear the segstore.  The segstore can handle a corrupt FS, so we can do this outside
    # of the rollback window.
    #
    dd if=/dev/zero of=${MODEL_MDRAIDDEV1} bs=1024k count=10 > /dev/null 2>&1
    dd if=/dev/zero of=${MODEL_MDRAIDDEV2} bs=1024k count=10 > /dev/null 2>&1

    # re-layout changes were successful.
    touch ${UPGRADE_STORE_CLEAN_FILE} 
    if [ $? -ne 0 ]; then
	do_log "Unable to set segstore clean file, store will need to be cleaned manually."
    fi
}

# Something bad has happened and we need to undo our configuration.
# For the 1050H we only need to put the PFS partition back the way it was.
#
do_rollback()
{
    do_log "Performing ${TARGET_MODEL} rollback due to critical hardware upgrade error."
    do_log "Proxy contents may be cleared"

    # rollback the DB changes first, so we perform recovery steps for the original
    # model.
    rollback_db_changes
    if [ $? -ne 0 ]; then
	do_log "Unable to rollback configuration DB. System state may be inconsistent." WARN
    fi

    # find the spec name we're going back to
    RB_SPEC=`${HALD_MODEL} | awk '{print $1}'`

    # make sure we have enough disks to rollback to our original spec
    check_disk_config ${RB_SPEC} 
    if [ $? -ne 0 ]; then
        do_log "Unable to rollback to ${RB_SPEC} due to missing hardware" WARN
        do_log "Halting appliance." WARN
        /sbin/halt
    fi

    # as we hit the critical section, we have no idea what state PFS is in,
    # so we have to toss it.
    dd if=/dev/zero of=/dev/disk0p6 bs=1024 count=1000 > /dev/null 2>&1

    # rolling back pfs changes -- throwing out pfs and restoring from scratch.
    ${DO_FS_RECOVERY} pfs
    if [ $? -ne 0 ]; then
	do_log "FS Recovery for Proxy failed." WARN
    fi

    clear_upgrade_rollback_file
}

do_finish()
{
    # Stop the array we just created
    # so we can use the 1050H common proxy start/setup code from the HAL.
    #
    mdadm --stop ${PFS_DEV} >> /dev/null

    do_log "Hardware Upgrade to ${TARGET_MODEL} successful."
}

check_do_rollback()
{
    if [ ${ROLLBACK_NEEDED} -ne 0 ]; then
        ROLLBACK_NEEDED=1
        do_log "Previous hardware upgrade interrupted." NOTICE
        do_log "Rolling back changes for hardware upgrade" NOTICE
        do_rollback
        if [ $? -ne 0 ]; then
            do_log "Rolling back changes for ${TARGET_MODEL} hardware upgrade failed." WARN
            exit 1
        else
            do_log "Rollback from ${TARGET_MODEL} upgrade successful." NOTICE
        fi

        exit 0
    fi
}

###############################################################################
# Main
##############################################################################

# the HAL for the 1050H units has routines for setting up and starting the PFS raid.
# we'll use those instead of writing our own here.
#
source /opt/hal/bin/mitac/hal_1050H.sh
touch / 2>/dev/null
READ_ONLY_ROOT=$?


# process the command line. this sets up the TARGET_MODEL and ROLLBACK_NEEDED if 
# requested on the cmdline
#
handle_arguments $@

# do pre-setup tasks, do this before upgrade or rollback, as it verifies 
# necessary tools for either operation.
#
do_check_preconditions
if [ $? -ne 0 ]; then
    do_log "Aborting upgrade for ${TARGET_MODEL} due to failed precondition checks"
    exit 1
fi

# if we need to do rollback, do it and exit.
#
check_do_rollback

# do things to prepare for the upgrade that do NOT affect the units ability to go back to
# its original configuration.
prep_upgrade
if [ $? -ne 0 ]; then
    do_log "Aborting upgrade for ${TARGET_MODEL} due to failed upgrade prep"
    exit 1
fi

# Actually change structures that may required fall back to the original configuration
# if an error occurs.
do_upgrade
if [ $? -ne 0 ]; then
    do_log "Upgrade to ${TARGET_MODEL} failed."
    exit 1
fi

# Update the database, start any required arrays, etc.
# the system should be usable as the new model after this call.
#
do_finish
if [ $? -ne 0 ]; then
    do_log "Final steps for ${TARGET_MODEL} upgrade failed."
    exit 1
fi
