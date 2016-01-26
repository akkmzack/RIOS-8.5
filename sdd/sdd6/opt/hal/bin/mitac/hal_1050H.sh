#!/bin/sh

###############################################################################
# 1050H HAL specific support.
#
#
# The 1050H is a special unit since it is built on the new models,
# but isnt supported by the new tools. It uses the old mechanism of
# blockpoll raid0 and linear pfs raid, none of which are supported by the 
# new tools for managing raid.
#
###############################################################################

PFS_DEV="md1"
SS_DEV="md0"

create_1050H_pfs_raid()
{
    /sbin/mdadm --create /dev/${PFS_DEV} --run \
        --level=linear --raid-devices=2 \
        /dev/disk0p6 /dev/disk1p6 > /dev/null 2>&1

    return $?
}

###############################################################################
# hal_1050H_raid_prep
#
# fo the special raid creation for the 1050H PFS
#
###############################################################################
hal_1050H_raid_prep()
{
    rm -f /dev/${PFS_DEV}
    mknod /dev/${PFS_DEV} b 9 1

    create_1050H_pfs_raid

    /sbin/mke2fs -b 4096 -R stride=8 -q -O ^resize_inode \
        -L SMB -j /dev/${PFS_DEV} > /dev/null 2>&1

    /sbin/mdadm --stop /dev/${PFS_DEV} > /dev/null 2>&1

    rm -f /dev/${SS_DEV}
    mknod /dev/${SS_DEV} b 9 0

    /sbin/mdadm --create /dev/${SS_DEV} --run \
        --level=raid0 --raid-devices=2 \
        /dev/disk0p5 /dev/disk1p5 > /dev/null 2>&1

    /sbin/mdadm --stop /dev/${SS_DEV} > /dev/null 2>&1

    touch /var/opt/rbt/.samba_ready
}

###############################################################################
# hal_1050H_raid_start
#
# Run the PFS array.
#
###############################################################################
hal_1050H_raid_start()
{
    rm -f /dev/${PFS_DEV}
    mknod /dev/${PFS_DEV} b 9 1
    /sbin/mdadm --assemble /dev/${PFS_DEV} /dev/disk0p6 /dev/disk1p6 > /dev/null 2>&1
    /bin/mount /dev/${PFS_DEV} -o defaults,acl,noauto,user_xattr /proxy > /dev/null 2>&1
}

###############################################################################
# 1050H disk 1 (second disk) Recovery Support
#
###############################################################################


###############################################################################
# check_for_ptable
#
# Determine whether a given disk (/dev/disk1 etc) has a partition table
# we have 3 retries built in
#
# Return strings are:
#   MISSING - invalid device string or device does not exist
#   OK      - has a partition table
#   NONE    - No partition table found
# 
###############################################################################
check_for_ptable()
{
    local CNT=0
    local DISK="$1"

    if [ "x${DISK}" = "x" -o ! -b ${DISK} ]; then
        echo "MISSING"
        return
    fi
    
    while [ ${CNT} -lt 3 ]; do
        sfdisk -V ${DISK} > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            echo "OK"
            return
        fi
        CNT=$[ ${CNT} + 1 ]
        sleep 1
    done

    echo "NONE"
}

###############################################################################
# do_partition_disk
#
# Given a disk number X (diskX), apply the partition table based on the config
# file to that disk using rrdm_tool.py --add /disk/pX
#
# Returns 1 on failure
#         0 on sucess
###############################################################################
do_partition_disk()
{
    local CNT=0
    local DISK=$1

    if [ "x${DISK}" = "x" ]; then
        if [ ! -b /dev/disk${DISK} ]; then
            echo "do_partition_disk: Disk device does not exist [/dev/disk${DISK}]"
        else
            echo "do_partition_disk: Invalid disk parameter [${DISK}]"
            return 1
        fi
    fi

    echo "Repartitioning Disk${DISK}"
    FAILED_REPART=1
    while [ ${CNT} -lt 3 ]; do
        ${RRDM_TOOL} --add /disk/p${DISK}
        if [ $? -eq 0 ]; then
            FAILED_REPART=0
            break
        fi
        CNT=$[ ${CNT} + 1 ]
    done 

    if [ ${FAILED_REPART} -ne 0 ]; then
       return 1 
    fi

    return 0
}


###############################################################################
# check_disk_licensed
#
# Make sure that the disk is reported as licensed
#
# Returns 0 for licensed
#         1 for unlicensed
###############################################################################
check_disk_licensed()
{
    DISK="$1"
    LICENSED=`${HWTOOL_PY} -q disk-license | grep "${DISK} " | awk '{print $2}' | tr "[:upper:]" "[:lower:]"`
    if [ "x${LICENSED}" = "xlicensed" ]; then
        return 0
    else 
        return 1
    fi
}

###############################################################################
# perform_1050H_disk1_recovery
#
# 1050H disk one recovery proceeds as follows:
# 1. check disk is licensed
# 2. repartition the drive
# 3. set/clear files on /var to tell hal/sport to clear proxy and clear the
#    datastore on startup
#
# Returns 1 on Error
#         0 on success
###############################################################################
perform_1050H_disk1_recovery()
{
    echo "Detected blank disk in slot 1"
    echo "Initiating disk recovery"

    check_disk_licensed "disk1"
    if [ $? -ne 0 ]; then
        echo "Disk 1 is not a riverbed supported drive"
        echo "Aborting disk recovery"
        return 1
    fi

    # first repartition the disk
    do_partition_disk 1
    if [ $? -ne 0 ]; then
        echo "ERROR: Unable to partition drive 1, aborting recovery"
        return 1
    fi

    echo "Disk Partitioning complete, triggering segstore and proxy reformat"

    # second once we've repartitioned the disk, set the segstore clean 
    # and PFS recovery flags to initiate a wipe of these volumes later 
    # in boot
    touch ${VAR_SPORT_CLEAN_FILE}
    if [ $? -ne 0 ]; then
        echo "ERROR: Unable to signal segstore clear, restart clean manually"
    fi

    # clear the PFS flag to have the later hal calls 
    # reformat the PFS array
    rm -f /var/opt/rbt/.samba_ready
    
    return 0
}

###############################################################################
# hal_1050H_disk_check
#
# Disk1 recovery for the 1050H is predicated on the second disk (disk1) not having
# a partition table (thus we assume it to be a blank new disk). 1050H recovery
# is only initiated on disk1 when the disk is blank. We require this, as we want
# to be super safe about disk recovery on disk 1, since we don't have any 
# other indications that a disk might be bad (such as fsck)  On the single disk
# units we ensure that a required filesystem is indeed corrupt and unusable 
# before proceeding to recovery. On the 1050H we don't have those indicators,
# so we require a blank disk to perform the recovery.
#
#
###############################################################################
hal_1050H_disk_check()
{
    second_disk=/dev/disk1

    PSTATUS=`check_for_ptable ${second_disk}`
    case "x${PSTATUS}" in
        "xMISSING")
            echo "1050H second disk is missing.  Skipping recovery checks"
            return
        ;;

        "xOK")
            # second disk is partitioned, so we skip the recovery
        ;;
        "xNONE")
            # not able to find a partition table on the disk
            perform_1050H_disk1_recovery
            if [ $? -ne 0 ]; then
                echo "Error during 1050H disk 1 recovery"
                echo "Unable to complete 1050H disk 1 recovery process"
            fi
        ;;
    esac
}
