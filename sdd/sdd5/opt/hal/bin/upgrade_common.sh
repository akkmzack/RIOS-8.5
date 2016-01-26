#!/bin/sh
###############################################################################
# upgrade_common.sh
#
# Common upgrade utilities for hardware upgrades.
#
# Provides standard routines for :
# 1. checking that all required utilites are present.
# 2. mfdb database updates and rollbacks.
# 3. common hwupgrade log interfaces.
# 4. API's for product hal scripts to call in init hw phase0/phase1.
# 
# Uses hal_common_inc definitions.
#
###############################################################################

# grab common HAL definitions.
HAL_COMMON=/opt/hal/bin/hal_common.sh
. ${HAL_COMMON}

UPGRADE_ACTION_DIR=/config/upgrade
UPGRADE_ACTION_FILE=${UPGRADE_ACTION_DIR}/.upgrade_action
UPGRADE_ROLLBACK_FILE=${UPGRADE_ACTION_DIR}/.rollback_needed
UPGRADE_STORE_CLEAN_FILE=${UPGRADE_ACTION_DIR}/.store_clean
VAR_SPORT_CLEAN_FILE=/var/opt/rbt/.clean

BACKUP_DB_DIR=/config/upgrade
BACKUP_DB_FILE=${BACKUP_DB_DIR}/mfdb-hwupgrade

# by default we don't need to do any rollback operations.
ROLLBACK_NEEDED=0

# for upgrade precondition checks, we need a list of the utilities we'll need
# so we don't inadvertantly start an upgrade and find out that we're missing something 
# we need to finish the upgrade. a list of utilities that are required on the system.
#
REQUIRED_EXEC="${RESIZE2FS} ${SFDISK} ${E2FSCK} ${TUNE2FS} ${DO_FS_RECOVERY} ${FLEXPY}"

################################################################################
# supports_hw_upgrades 
#
# Today only SH appliances with xx 50 1U/3U hardware support hw upgrade checks.
#
################################################################################
supports_hw_upgrades()
{
    MOBO=`get_motherboard`
    PLAT=`get_platform`
    case "x${MOBO:0:9}" in
	"x400-00100"|"x400-00300"|"xVM"|"xHyperV"|"x400-00098"|"x425-00140")
	    if [ "x${PLAT}" = "xSH" ]; then
		echo "true"
	    else
		echo "false"
	    fi
	;;
	*)
	    echo "false"
	;;
    esac
    
}

# General logger for upgrades, if the calling script has the PROGRAM variable set
# it uses this as the prefix for all messages.
#
# as upgrades are done from hal phase0 (initlog), we don't use logging calls here.
#
do_log()
{
    MSG=$1
    LEVEL=$2

    if [ "x${LEVEL}" != "x" ]; then
	L_MSG="${LEVEL}:"
    else
	L_MSG=
    fi

    if [ "x${PROGRAM}" != "x" ]; then
        echo "${PROGRAM}:${L_MSG}$1"
    else
	echo $1
    fi
}

# make the upgrade directory on /config if it doesnt exist.
#
check_make_upgrade_dir()
{
    if [ ! -d ${UPGRADE_ACTION_DIR} ]; then
        mkdir -p ${UPGRADE_ACTION_DIR} >> /dev/null
        if [ $? -ne 0 ]; then
            return 1
        fi
    fi

    return 0
}

###############################################################################
# Common Upgrade Utilities
#
# Rollback - We use a file on /config/upgrade to ensure that if a user 
#            shuts down a unit, or the unit crashes during a hardware upgrade,
#	     that we can determine this and bring the box back to a runnable state.
#
# Save working DB - Save off / restore a copy of the working mfdb.
#
###############################################################################

###############################################################################
# set_upgrade_rollback_file
#
# Once we enter a critical section in the upgrade process, we set a file on 
# the filesystem to indicate that we entered the point in the upgrade where if
# we crash, we'll want to perform filesystem recovery on the next boot.
#
###############################################################################
set_upgrade_rollback_file()
{
    ERROR=0

    check_make_upgrade_dir
    ERROR=$?

    if [ ${ERROR} -eq 0 ]; then
        /bin/touch ${UPGRADE_ROLLBACK_FILE}
        if [ $? -ne 0 ]; then
            ERROR=1
        fi
    fi

    if [ ${ERROR} -eq 1 ]; then
        do_log "Unable to set rollback needed file for ${TARGET_MODEL} hardware upgrade." WARN
        do_log "Upgrade will not be protected from unexpected shutdown during upgrade." WARN
        return 1
    fi
}

###############################################################################
# clear_uprade_rollback_file
#
# Remove the state left on the filesystem indicating that we were in a critical
# upgrade section. No rollback will be performed if the unit crashes after this 
# section.
#
###############################################################################
clear_upgrade_rollback_file()
{
    if [ -f ${UPGRADE_ROLLBACK_FILE} ]; then
        rm -f ${UPGRADE_ROLLBACK_FILE} >> /dev/null
	if [ $? -ne 0 ]; then
	    do_log "Failed to delete upgrade rollback file ${UPGRADE_ROLLBACK_FILE}" WARN
	fi
    fi
}


###############################################################################
# save_working_db
#
# copy the working db off so we have a backup
#
###############################################################################
save_working_db()
{
    rm -f ${BACKUP_DB_FILE}

    cp -f ${DB_PATH} ${BACKUP_DB_FILE}
    if [ $? -ne 0 ]; then
        # unable to make a copy of the config db.
        return 1
    fi
}


###############################################################################
# rollback_db_changes
#
# Abandon the changes to the db by copying the saved original db over
# the working db.  We don't need to backup the mfdb.bak per conversations with
# the mgmt team, as they don't use the file.
#
###############################################################################
rollback_db_changes()
{
    if [ -f ${BACKUP_DB_FILE} ]; then
        cp -f ${BACKUP_DB_FILE} ${DB_PATH}
        if [ $? -ne 0 ]; then
            return 1
        fi
    fi
}

###############################################################################
# HAL Interfaces
#
# The upgrade code grafts into the HAL scripts in init hardware phase0, before
# any filesystems are up.
#
# Mgmt uses a file on /var to signal a segstore clean action, which means we need
# to split the upgrade code into two parts, one that runs before filesystems are up.
# and one that runs after /var is mounted so we can touch the file to signal a
# segstore restart.
#
###############################################################################

###############################################################################
#
# check_hardware_upgrades_phase0
#
# run from initlog in hal phase0 by rc.sysinit. No filesystems are up at this
# time, so /var, /proxy are unavailable.
#
###############################################################################
check_hardware_upgrades_phase0()
{
    if [ -f ${UPGRADE_ACTION_FILE} ]; then
        CMD=`cat ${UPGRADE_ACTION_FILE}`
        if [ "x${CMD}" = "x" ]; then
            if [ -f ${UPGRADE_ROLLBACK_FILE} ]; then
                do_log "Upgrade action file is empty, but rollback needed is set." WARN
                return
            else
                do_log "Upgrade file is empty, skipping" WARN
                return
            fi
        fi

        # allow for command line options in the script though, we 
        # won't normally use them
        SCRIPT=`echo "$CMD" | awk '{print $1}'`
        if [ ! -x ${SCRIPT} ]; then
            do_log "Upgrade script ${SCRIPT} does not exist" WARN
            return
        fi

        if [ -f ${UPGRADE_ROLLBACK_FILE} ]; then
            CMD_ARG="--rollback"
            do_log "Previous upgrade was interrupted, data may have been lost." WARN
        else
            CMD_ARG=""
            # we want a user visible console message.
            do_log "Performing hardware upgrade, do not shutdown the appliance" NOTICE
        fi

        # run the shell command
        ${CMD} ${CMD_ARG}

        # clear the action file whether we failed or succeeded.
        # the customer can always retry the action if it fails.
        rm -f ${UPGRADE_ACTION_FILE}

        # clear upgrade rollback, as it exists to allow rollback
        # when the unit crashes or shut down during the upgrade.
        rm -f ${UPGRADE_ROLLBACK_FILE}

        # Touch a file in /lib/modules tmpfs as thats the only rw partition
        # This file will indicate to the shadow code that a hardware upgrade
        # was done and config on flash is the latest and should not be
        # overwritten
        /bin/touch /lib/modules/.config_fresh_on_flash
    fi
}

###############################################################################
# check_hardware_upgrades_phase1
#
# after all the filesystems are up and mounted, and we've done a hardware
# upgrade, we need to set the store clean flag on /var/opt/rbt/.clean to 
# force mgmt to auto-start the segstore clean.
#
# We can't do it from phase0 since /var isnt mounted yet, or from the upgrades
# section since those are typically destructive of fs data.
#
###############################################################################
check_hardware_upgrades_phase1()
{
    if [ -f ${UPGRADE_STORE_CLEAN_FILE} ]; then
        touch ${VAR_SPORT_CLEAN_FILE}
        if [ $? -ne 0 ]; then
	    # use logging here because phase1 is not run from initlog.
            do_log "Unable to mark segstore for auto clean. use restart clean." WARN
        fi

        rm -f ${UPGRADE_STORE_CLEAN_FILE}
    fi
}

###############################################################################
# do_check_preconditions
#
# The calling script needs to set SUPPORTED_MODELS to the list of models 
# supported by that script, and TARGET_MODEL to the model we'll upgrade to.
#
# Check everything we'll need to proceed with an upgrade.
# 1. check that the requested model is supported by this script.
# 2. check all required binaries and configuration files.
# 3. Make sure that we still have the right hardware for the upgrade.
#
###############################################################################
do_check_preconditions()
{

    check_supported_models ${SUPPORTED_MODELS}
    if [ $? -ne 0 ]; then
        do_log "Internal error, script does not support ${TARGET_MODEL} upgrade."
        return 1
    fi

    if [ ! -f ${DB_PATH} ]; then
        do_log "MFG DB not found ${DB_PATH}"
        return 1
    fi

    for executable in ${REQUIRED_EXEC}; do
        if [ ! -x ${executable} ]; then
            do_log "Required utility $executable not found or not executable."
            return 1
        fi
    done

    check_make_upgrade_dir
    if [ $? -ne 0 ]; then
        return 1
    fi
}

###############################################################################
# do_update_mfdb
#
# Given a key, type and value, insert it into the mfdb
# This will accept blank keys, but some mfdb types (like bool) will fail
# with a blank entry (invalid type).
#
###############################################################################
do_update_mfdb()
{
    NODE="$1"
    TYPE="$2"
    VALUE="$3"

    # we can set an empty value in the mfdb
    #
    if [ "x${NODE}" = "x" -o "x${TYPE}" = "x" ]; then
	return 1
    fi

    $MDDBREQ -c ${DB_PATH} set modify - "${NODE}" "${TYPE}" "${VALUE}"
    if [ $? -ne 0 ]; then
	return 1
    fi

    return 0
}


###############################################################################
# check_supported_models
#
# Given a list of supported models, check to see if our target model is 
# in the list.
#
# returns 0 if true, 1 otherwise
#
###############################################################################
check_supported_models()
{
    while [ "x${1}" != "x" ]; do
        if [ "x${TARGET_MODEL}" = "x${1}" ]; then
            return 0
        fi
        shift 1
    done

    return 1
}

###############################################################################
#
# handle_arguments
#
# common argument handler for all hardware upgrade scripts. returns values 
# globally TARGET_MODEL, ROLLBACK_NEEDED, and MODEL_FILE.
#
# each hwupgrade takes a target model and optionally the --rollback
# argument on the command line, in the case we want to roll back
# from a previously failed upgrade.
#
###############################################################################
handle_arguments()
{
    while [ "x$1" != "x" ]; do
        case "x${1}" in
            "x--rollback")
                # set rollback needed
                ROLLBACK_NEEDED=1
            ;;
            *)
                TARGET_MODEL="$1"
            ;;
        esac
        shift 1
    done

    if [ "x${TARGET_MODEL}" = "x" ]; then
        do_log "No target model specified." WARN
        exit 1
    fi

    # we need to have the model files present if we're doing to do an
    # upgrade to another model
    #
    MODEL_FILE="${MODEL_PATH}/model_${TARGET_MODEL}.sh"
}

##############################################################################
# do_update_model_params
#
# Calling script must set MODEL_FILE and TARGET_MODEL
#
# update the mfdb in place, we've saved a copy off in case something goes wrong
# we can roll back to it. 
#
# We need to set empty string values in the mfdb to 
# keep consistency with mfdb's for units that were manufactured and not upgraded.
#
# for example, a 1050H has dualstore set and a mdraiddev1/2, but when upgrading
# to a 1050RH, we won't have any dualstore or any mdraiddev's, so the mdraiddev
# fields would be empty in the mfdb.
#
# This is product specific code.
#
###############################################################################
do_update_model_params()
{
    # Do configuration changes
    # READ the params from the model file.

    # no need to change image_layout.sh since all new xx50's share the same
    # layout.
    source ${MODEL_FILE}

    do_update_mfdb /rbt/mfd/model string "${MODEL_CLASS}"
    if [ $? -ne 0 ]; then return 1; fi

    do_update_mfdb /rbt/mfd/flex/model string "${TARGET_MODEL}"
    if [ $? -ne 0 ]; then return 1; fi

    if [ "x${MODEL_DISKSIZE}" = "x" ]; then
        MODEL_DISKSIZE=0
        MODEL_DISKDEV=
    fi

    STORE_SIZE=$[ ${MODEL_DISKSIZE} / 1024 / 1024 ]
    do_update_mfdb /rbt/mfd/store/size uint32 "${STORE_SIZE}"
    if [ $? -ne 0 ]; then return 1; fi

    # weird case in the mfdb.. a new entity was introduced for next gen models 
    # xx50's, where there might not be a MODEL_DUALSTORE param, but there will
    # be a MODEL_DUALSTORE_NG param, though as far as i can tell they mean 
    # the same thing.
    # set dualstore if dualstore or dualstore_ng is true..
    #
    if [ "x${MODEL_DUALSTORE}" = "x" -o "x${MODEL_DUALSTORE}" = "xfalse" ]; then
        if [ "x${MODEL_DUALSTORE_NG}" = "xtrue" ]; then
            MODEL_DUALSTORE=true
        else
            MODEL_DUALSTORE=false
        fi
    fi

    do_update_mfdb /rbt/mfd/store/dual bool "${MODEL_DUALSTORE}"
    if [ $? -ne 0 ]; then return 1; fi
    do_update_mfdb /rbt/mfd/store/dev string "${MODEL_STOREDEV}"
    if [ $? -ne 0 ]; then return 1; fi

    do_update_mfdb /rbt/mfd/store/mdraid1 string "${MODEL_MDRAIDDEV1}"
    if [ $? -ne 0 ]; then return 1; fi
    do_update_mfdb /rbt/mfd/store/mdraid2 string "${MODEL_MDRAIDDEV2}"
    if [ $? -ne 0 ]; then return 1; fi

    do_update_mfdb /rbt/mfd/smb/dev string "${MODEL_SMBDEV}"
    if [ $? -ne 0 ]; then return 1; fi

    # update media: catch case where we pull out an hdd, and put in an ssd
    if [ "x${MODEL_FTS_MEDIA}" != "x" ]; then
	do_update_mfdb /rbt/mfd/fts/media string ${MODEL_FTS_MEDIA}
	if [ $? -ne 0 ]; then return 1; fi
    fi


    # strange case with the MODEL_SMBSIZE model parameter.  It isnt used anywhere.
    # Instead we calculate the SMB size depending on the layout/partition size and 
    # insert that into the mfdb
    # code is copied from rbtmanufacture.sh
    #
    if [ "x${MODEL_SMBDEV}" != "x" ]; then
        if [ "x$MODEL_DUALSTORE" = "xtrue" ]; then
            SMB_DISK1=`$SFDISK -s $MODEL_MDRAIDSMBDEV1`
            SMB_DISK2=`$SFDISK -s $MODEL_MDRAIDSMBDEV2`

            SMB_DISKSIZE=`expr "(" $SMB_DISK1 "+" $SMB_DISK2 ")" "*" 1024`
        else
            SMB_DISK1=`$SFDISK -s $MODEL_SMBDEV`
            SMB_DISKSIZE=`expr $SMB_DISK1 "*" 1024`
        fi
        MODEL_SMBSIZE_MB=`expr $SMB_DISKSIZE "/" 1024 "/" 1024`
    fi

    if [ "x${MODEL_SMBSIZE_MB}" = "x" ]; then
        MODEL_SMBSIZE_MB=0
    fi

    do_update_mfdb /rbt/mfd/smb/size uint32 "${MODEL_SMBSIZE_MB}"
    if [ $? -ne 0 ]; then return 1; fi
    do_update_mfdb /rbt/mfd/smb/mdraid1 string "${MODEL_MDRAIDSMBDEV1}"
    if [ $? -ne 0 ]; then return 1; fi
    do_update_mfdb /rbt/mfd/smb/mdraid2 string "${MODEL_MDRAIDSMBDEV2}"
    if [ $? -ne 0 ]; then return 1; fi
}

###############################################################################
# recover_filesystems
#
# loops over all volumes indicated by rrdm_tool and uses the appropriate
# FS recovery method for each.
#
###############################################################################
recover_filesystems()
{
    local TARGET_MODEL=$1
    echo "Reinitializing filesystems for ${TARGET_MODEL}"

    VOL_LIST=`${RRDM_TOOL} -l -m ${TARGET_MODEL} | awk 'BEGIN{FS=":"}{print $1}'`
    for vol in ${VOL_LIST}; do
        SUCCESS=0
        RETRY=0
        while [ ${SUCCESS} -ne 1 -a ${RETRY} -lt 2 ]; do
            do_log "Initializing ${vol}, attempt ${RETRY}"
            VOL_DEV=`${RRDM_TOOL} -l -m ${TARGET_MODEL} | grep "${vol}:" | awk 'BEGIN{FS=":"}{print $2}'`

            # clear the first bit of each volume, as fs recovery for ext3 filesystems
            # requires a fs to be unmountable and fsck without error.
            dd if=/dev/zero of=/dev/${VOL_DEV} bs=1024 count=1000 > /dev/null 2>&1

            # force the fs recovery.
            ${DO_FS_RECOVERY} ${vol} -f -u
            if [ $? -eq 0 ]; then
                SUCCESS=1
            fi

            RETRY=$[ ${RETRY} + 1 ]
        done

        if [ ${SUCCESS} -ne 1 ]; then
            # can't proceed for some reason, go back.
            #
            do_log "Filesystem recovery for ${vol} failed." WARN
            # stop any raid arrays.
            ${RRDM_TOOL} -q /raid
            if [ $? -ne 0 ]; then
                do_log "Unable to stop raid arrays." WARN
            fi

            return 1
        fi
    done

    ${RRDM_TOOL} -q /raid
    if [ $? -ne 0 ]; then
        do_log "Unable to stop raid arrays." WARN
    fi

    return 0
}

###############################################################################
# do_disk_remanufacture
#
# Wrapper around calling rrdm_tool to remanufacture the hotswappable disks
# to a new configuration.
#
###############################################################################
do_disk_remanufacture()
{
    local TARGET_MODEL=$1
    ${RRDM_TOOL} -u -m ${TARGET_MODEL} > /dev/null
    if [ $? -eq 0 ]; then
        ${RRDM_TOOL} -m ${TARGET_MODEL} --write-config > /dev/null
        if [ $? -ne 0 ]; then
            # the config is used for mostly reporting purposes, 
            # but there isnt any reason we should not be able to update it.
            do_log "Unable to update disk configuration XML" WARN
        fi 
    else 
	do_log "$RRDM_TOOL failed" WARN
    fi
}

###############################################################################
# check_disk_config
#
# Given a target model, return 0 if the disk system is correct for that model
# or 1 if the disk config does not meet the minimum specifications
# for the target model.
#
###############################################################################
check_disk_config()
{
    local TARGET_MODEL=$1

    DISK_OK=`${RRDM_TOOL} --validate -m ${TARGET_MODEL}`
    case "x${DISK_OK}" in
        "xTrue")
                # these actions mean that we have the right hardware to 
                # run this model
                do_log "Hardware is correct for ${TARGET_MODEL}."
            ;;
        *)
            do_log "Required hardware not present for ${TARGET_MODEL}."
            return 1
        ;;
    esac
}

###############################################################################
# get_rrdm_volume_device
#
# given a model spec and a volume, ask rrdm tool for the volume map 
# and extract the device name for the indicated spec/volume.
#
###############################################################################
get_rrdm_volume_device()
{
    SPEC="$1"
    VOLUME="$2"
    
    if [ "x${SPEC}" = "x" -o "x${VOLUME}" = "x" ]; then
        return 1
    fi

    DEVICE=`${RRDM_TOOL} -m ${SPEC} -l | grep "${VOLUME}" | awk 'BEGIN{FS=":"}{print $2}'`
    if [ $? -ne 0 ]; then
        return 1
    fi

    echo "${DEVICE}"
}

###############################################################################
# check_fix_fstab
#
# after a hardware upgrade we may need to fixup the fstab.  Since the fstab is
# created by writeimage, it won't get regenerated during a hw upgrade.
#
# in the case of an upgrade where the swap device changes (1050L/M to LCR/MCR/HR)
# we need to manually go into the fstab and replace the old swap device with the
# new for the new spec.
#
# NOTE - requires rw root partition
#
###############################################################################
check_fix_fstab()
{
    local CUR_SPEC="$1"
    local TARGET_SPEC="$2"

    /bin/touch /  > /dev/null 2>&1
    READ_ONLY_ROOT=$?

    [ $READ_ONLY_ROOT -ne 0 ] && mount / -o remount,rw

    CS_SWAP=`get_rrdm_volume_device ${CUR_SPEC} swap`
    if [ $? -ne 0 ]; then
        return 1
    fi
    TS_SWAP=`get_rrdm_volume_device ${TARGET_SPEC} swap`
    if [ $? -ne 0 ]; then
        return 1
    fi

    if [ "x${CS_SWAP}" != "x${TS_SWAP}" ]; then
        # do the fstab update.
        /bin/sed -i "s/${CS_SWAP}/${TS_SWAP}/g" /etc/fstab
        if [ $? -ne 0 ]; then
            return 1
        fi
    fi

    [ $READ_ONLY_ROOT -ne 0 ] && mount / -o remount,ro
    
    return 0
}

