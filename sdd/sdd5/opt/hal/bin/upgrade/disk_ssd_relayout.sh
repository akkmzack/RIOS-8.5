#!/bin/bash
###############################################################################
# disk_ssd_relayout.sh
#
# Performs disk hardware upgrades for units that are changing from all HDD
# to SSD for segstore layouts.  This would be the case for the CX755L/M to H
# and the 1555L/M to H upgrades
#
# Disk relayouts are advertised to be destructive
#
# Command line :
# <SPECL> The spec to use for the upgrade. 
# --rollback: Revert the changes from a previous upgrade, which applies
# the layout from the original spec.
#
# If a hardware upgrade is killed during the middle of reformatting the disks,
# our end result is unclear. We use a file on /config/upgrade
# called .rollback_needed which means that we need to execute a recovery
# script to roll back the previous upgrade changes. The recovery will reformat
# the appropriate partition(s) or RAID arrays. (destructive).
# 
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


SUPPORTED_MODELS="CX755H CX1555H"
# maybe add these later "1160VH 1260VH"


prep_upgrade()
{
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

}

do_upgrade()
{

    [ $READ_ONLY_ROOT -ne 0 ] && mount / -o remount,rw

    ORIG_SPEC=`${HALD_MODEL} | awk '{print $1}'`
    if [ $? -ne 0 ]; then
        do_log "Failed to determine appliance spec, aborting upgrade." WARN
        exit 1
    fi

    set_upgrade_rollback_file

    do_log "Performing ssd disk relayout for ${TARGET_MODEL} hardware upgrade." NOTICE

    do_disk_remanufacture ${TARGET_MODEL}
    if [ $? -ne 0 ]; then
        do_log "Upgrade to ${TARGET_MODEL} failed."
        # what error message do we put here?
        # Ok, now we're kinda hosed. A rollback probably won't work
        do_rollback
        exit 1
    fi



    # update the model parameters, so we can use the common fs recovery code 
    # which uses the model out of the mfdb for determining the appropriate 
    # action
    do_update_model_params
    if [ $? -ne 0 ]; then
        do_log "Unable to update model params in new mfdb"
        do_rollback
        exit 1
    fi

    recover_filesystems ${TARGET_MODEL}
    if [ $? -ne 0 ]; then
        do_rollback
        exit 1
    fi


    clear_upgrade_rollback_file

    check_fix_fstab ${ORIG_SPEC} ${TARGET_MODEL}
    if [ $? -ne 0 ]; then
        # shouldnt happen but if we can't fix the swap device, the user/support
        # can manually fix it.
        do_log "Unable to fixup swap device in /etc/fstab." WARN
        do_log "Swap device will be unavailable. " WARN
    fi

    # re-layout changes were successful.
    touch ${UPGRADE_STORE_CLEAN_FILE} 
    if [ $? -ne 0 ]; then
        do_log "Unable to set segstore clean file, store will need to be cleaned manually."
    fi

    [ $READ_ONLY_ROOT -ne 0 ] && mount / -o remount,ro
    if [ $? -ne 0 ]; then
        do_log "Remount error."
    fi 

}

#
# update the mfdb in place, we've saved a copy off in case something goes wrong
# we can roll back to it.

#
# Something bad has happened and we need to undo our configuration.
# Just to be sure, if we can't go forward, we'll try to go back
#
# Note that this code _should_ call do_upgrade, since the steps are
# all the same

do_rollback()
{
    [ $READ_ONLY_ROOT -ne 0 ] && mount / -o remount,rw

    # rollback the DB changes first, so we perform recovery steps for
    # the original  model.
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
        # uh-oh: lets see if we can go forward
        check_disk_config ${TARGET_MODEL}
        if [ $? -ne 0 ]; then
            # we can't go back, and we can't go forward: just halt
            do_log "Unable to roll forward to ${TARGET_MODEL} due to missing hardware" WARN
            do_log "Halting appliance." WARN
            /sbin/halt
        fi

        # We can't go back to RB_SPEC, so lets see if we can finish
        # the   upgrade, going forward to TARGET_MODEL
        do_log "Retrying upgrade to ${TARGET_MODEL}" NOTICE
        RB_SPEC=${TARGET_MODEL}

        #since we rolled back the DB, we need to update the
        #model params so we can roll forward

        do_update_model_params
        if [ $? -ne 0 ]; then
            do_log "Unable to update model params in new mfdb"
	    # continue
	    exit 1
        fi

    fi

    do_log "Performing rollback due to critical hardware upgrade error, or interrupted hardware upgrade." WARN
    do_log "Proxy contents will be cleared" WARN
    do_log "Rolling back disk changes to ${RB_SPEC} specification" NOTICE

    # ToDo: we should combine the rest of this function and do_upgrade
    # into common code
    # relayout the disks per the original spec model.
    do_disk_remanufacture ${RB_SPEC}
    if [ $? -ne 0 ]; then
        do_log "Disk layout failed retrying." WARN
        do_disk_remanufacture ${RB_SPEC}
        if [ $? -ne 0 ]; then
            do_log "Rollback failed in disk layout retry, appliance is unrecoverable." WARN
            do_log "Halting appliance." WARN
            /sbin/halt
        fi
    fi

    recover_filesystems ${RB_SPEC}
    if [ $? -ne 0 ]; then
        # we're toast, right?
        do_log "Rollback failed, appliance is unrecoverable." WARN
	do_log "couldn't recover filesystems" WARN
        do_log "Halting appliance." WARN
        /sbin/halt
    fi


    # re-layout changes were successful.
    # we need to tell mgmt to clear the segstore since we did a relayout.
    touch ${UPGRADE_STORE_CLEAN_FILE}
    if [ $? -ne 0 ]; then
        do_log "Unable to set segstore clean file, store will need to be cleaned manually."
    fi

    clear_upgrade_rollback_file
    [ $READ_ONLY_ROOT -ne 0 ] && mount / -o remount,ro
}

do_finish()
{
    # finish the upgrade and clean anything up needed.
    #

    do_log "Hardware Upgrade to ${TARGET_MODEL} successful."
}

check_do_rollback()
{
    if [ ${ROLLBACK_NEEDED} -ne 0 ]; then
        ROLLBACK_NEEDED=1
        do_log "Previous hardware upgrade failed." NOTICE
        do_rollback
        if [ $? -ne 0 ]; then
            do_log "Rolling back from ${TARGET_MODEL} hardware upgrade failed." WARN
            exit 1
        else
            do_log "Rollback from ${TARGET_MODEL} upgrade successful." NOTICE
        fi

        exit 0
    fi
}

###############################################################################
# Main
#s#############################################################################
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

#
# if we need to do rollback, set up the correct condtions, and proceed
#

check_do_rollback





# do things to prepare for the upgrade that do NOT affect the units
# ability to go back to its original configuration.
prep_upgrade
if [ $? -ne 0 ]; then
    do_log "Aborting upgrade for ${TARGET_MODEL} due to failed upgrade prep"
    exit 1
fi


# Actually change structures that may required fall back to the
# original configuration if an error occurs. 

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
