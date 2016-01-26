#!/bin/bash
###############################################################################
# VSH.sh
# Performs upgrade to a Virtual appliance (assumes proper checks have 
# already been done to ensure this model can be upgraded (flex lic), and 
# that this is already a Virtual class series appliance.
#
# Based off of the previous 2020 upgrade script
#
# Command line :
# <SPEC>: Perform the ugprade to the indicated Virtual spec. 
#
# --rollback: Revert the changes from a previous VSH upgrade.
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


SUPPORTED_MODELS="V550M V550H V1050L V1050M V1050H V2050L V2050M V2050H VCX555M VCX555H VCX755L VCX755M VCX755H VCX1555L VCX1555M VCX1555H"

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


}

do_upgrade()
{

    set_upgrade_rollback_file

    [ $READ_ONLY_ROOT -ne 0 ] && mount / -o remount,rw

    # Clear the segstore=true flag from the rvbd superblock
    # Needed in the case we expand the disk as opposed to 
    # destroying & re-creating it
    dd if=/dev/zero of=/dev/disk1p1 > /dev/null 2>&1

    # call out to rrdm_tool to partition the second drive 
    # and update rvbd_super.
    ${RRDM_TOOL} -u -m ${TARGET_MODEL}
    if [ $? -ne 0 ]; then
	do_log "Unable to partition second drive"
	exit 1
    fi

    [ $READ_ONLY_ROOT -ne 0 ] && mount / -o remount,ro

    # update the model parameters
    #
    do_update_model_params
    if [ $? -ne 0 ]; then
        do_log "Unable to update model params in new mfdb"
        exit 1
    fi

    # Reread the partition table     
    for i in {1..5}; do
        sfdisk -R "${MODEL_DISKDEV}"
        sleep 1
    done

    clear_upgrade_rollback_file

    # clear the segstore.  The segstore can handle a corrupt FS, so we can do this outside
    # of the rollback window.
    #
    dd if=/dev/zero of=${MODEL_STOREDEV} bs=1024k count=10 > /dev/null 2>&1

    # re-layout changes were successful.
    touch ${UPGRADE_STORE_CLEAN_FILE} 
    if [ $? -ne 0 ]; then
	do_log "Unable to set segstore clean file, store will need to be cleaned manually."
    fi
}

# Something bad has happened and we need to undo our configuration.
#
do_rollback()
{
    do_log "Performing ${TARGET_MODEL} rollback due to critical hardware upgrade error."

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

    [ $READ_ONLY_ROOT -ne 0 ] && mount / -o remount,rw
    
    # call out to rrdm_tool to partition the second drive 
    # and update rvbd_super.
    ${RRDM_TOOL} -u -m ${RB_SPEC}
    if [ $? -ne 0 ]; then
	do_log "Unable to partition second drive"
	exit 1
    fi

    [ $READ_ONLY_ROOT -ne 0 ] && mount / -o remount,ro

    clear_upgrade_rollback_file
}

do_finish()
{
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
