#!/bin/sh
#
# Modularized script for /var recovery
#
# NOTE - for new 1U units, we'll need config mounted to see if this is a model
# that supports SW RAID. (mddbreq will need the mfdb to get the model info)
#
# Options:
# -f - force fsck on filesystems
# -u - unmount ext3 filesystems when complete.
#


# For hardware upgrades we may leave a file on /config/upgrade
# that we want to restore when we do a var fs recovery after the 
# upgrade
#
VAR_UPGRADE_BACKUP_TGZ=/config/upgrade/var_backup.tgz
RECOVERY_TYPE_SW="RRDM"
RECOVERY_TYPE_3W="3WARE"
LOG_WARN="/usr/bin/logger -p user.WARN -t do_fs_recovery" 
LOG_NOTICE="/usr/bin/logger -p user.NOTICE -t do_fs_recovery" 
LOG_INFO="/usr/bin/logger -p user.INFO -t do_fs_recovery" 

RRDM_TOOL_PY="/opt/hal/bin/raid/rrdm_tool.py"
FORCEIT=0
UNMOUNT_WHEN_DONE=0
while [ "x${1}" != "x" ]; do
    case "x${1}" in
	"x-f")
	    FORCEIT=1
	;;
	"x-u")
	    UNMOUNT_WHEN_DONE=1
	;;
	*)
	    VOL_NAME="${1}"
	;;
    esac
    shift 1
done

# LOG_FLAG = STDOUT => send messages to standard out
# LOG_FLAG = SYSLOG => send messages to syslog
# LOG_FLAG = BOTH => send messages to both stdout and syslog
# defaults to syslog
LOG_FLAG="STDOUT"

#
#
do_log()
{
    LEVEL="$1"
    MSG="$2"

    if [ "x${LEVEL}" = "xINFO" ]; then
	LOG_CMD=${LOG_INFO}
    elif [ "x${LEVEL}" = "xNOTICE" ]; then
        LOG_CMD=${LOG_NOTICE}
    else
	LOG_CMD=${LOG_WARN}
    fi

    case "${LOG_FLAG}" in
	"STDOUT")
	    echo "${LEVEL}:" "${MSG}"
	;;
	"SYSLOG")
	    ${LOG_CMD} "${MSG}"
	;;
	"BOTH")
	    echo "${LEVEL}:" "${MSG}"
	    ${LOG_CMD} "${MSG}"
	;;
    esac
}

#
# if we're fixing var, we obviously can't log to syslog
#
if [ "x${VOL_NAME}" = "xvar" ]; then
    LOG_FLAG="STDOUT"
fi

if [ "x${VOL_NAME}" = "x" ]; then
    do_log WARN "do_fs_recovery.sh must be called with a valid volume name from the spec file."
    exit 1
fi


###############################################################################
#
# VAR Recovery Routines.
#
###############################################################################

###############################################################################
# get_device
#
# Figure out the right /dev/mdX for the var partition on a rrdm_tool
# managed appliance.
#
###############################################################################
get_device()
{
    VOL_NAME="$1"

    if [ ! -f "${RRDM_TOOL_PY}" ]; then
	return 1
    fi

    OUTPUT=`${RRDM_TOOL_PY} -l | grep ${VOL_NAME} | awk 'BEGIN{FS=":"} {print $2}'`
    if [ "x${OUTPUT}" = "x" ]; then
	return 1
    fi

    echo "/dev/${OUTPUT}"
    return 0
}

###############################################################################
# get_reserve_sb
#
# find out if we need to reserve space at the end of our partition
# for an MD superblock
#
###############################################################################
get_reserve_sb()
{
    VOL_NAME="$1"

    if [ ! -f "${RRDM_TOOL_PY}" ]; then
        return 1
    fi

    OUTPUT=`${RRDM_TOOL_PY} -l | grep ${VOL_NAME} | awk 'BEGIN{FS=":"} {print $5}'`
    if [ "x${OUTPUT}" = "x" ]; then
        return 1
    fi

    echo "${OUTPUT}"
    return 0
}



###############################################################################
# get_recovery_type
#
# Determine the RAID type so we know which type of recovery method to use.
# RRDM   - use new platform recovery method
# 3WARE  - use 3ware specific recovery methods.
# NONE   - use the normal method, which is to drop to shell and alert the user.
#
###############################################################################
HWTOOL_PY="/opt/hal/bin/hwtool.py"
get_recovery_type()
{
    ${HWTOOL_PY} -q cli | /bin/grep AMCC > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "${RECOVERY_TYPE_3W}"
        return 0
    fi

    if [ "x${RRDM_SUPPORTED}" = "xTrue" ]; then
	echo "${RECOVERY_TYPE_SW}"
	return 0
    fi

    echo "NONE"
}


###############################################################################
# do_var_repopulate
#
# copy all the files needed to start mgmtd/ssh onto /var
# from the var recovery tarball.
#
# additionally, if there is a VAR_BACKUP_TGZ on /config/upgrade
# we want to unpack it
#
###############################################################################
do_var_repopulate()
{
    cd /
    mount / -o rw,remount > /dev/null 2>&1
    /bin/touch /etc/.firstboot
    mount / -o ro,remount > /dev/null 2>&1
    tar xzf /var.tgz > /dev/null 2>&1
    if [ $? -eq 0 ]; then
	if [ -f ${VAR_UPGRADE_BACKUP_TGZ} ]; then
	    echo "Unpacking backed up var files."
	    # we're not so concerned if this doesnt succeed so long as
	    # the main var recovery was successful, this is an issue of 
	    # completeness, and the system will work this fals.
	    # they may see some of their previous settings not be applied,
	    # but we can't do anything about that now
	    #
	    # I don't print a message since its not easy to articulate what
	    # the customer should do in this case. This backup restored
	    # random mgmt configs that their apps left scattered on /var
	    # and most customers won't see any effect from missing it.
	    tar xvfz ${VAR_UPGRADE_BACKUP_TGZ}
	fi
	echo "Unpacked replacement filesystem." 
	umount LABEL=VAR > /dev/null 2>&1
    else
	echo "Problem rebuilding /var filesystem, contact support." 
	/sbin/halt
    fi

    # Flush out all the dirty pages from memory
    /bin/sync

    MODEL=`/opt/hal/bin/hwtool.py -q motherboard`
    case "x${MODEL}" in
	"x400-00100-01"|"x400-00300-01"|"x400-00099-01"|"x400-00098-01")
	    # new models need special symlinks created for the encrypted store.
	    ln -s /config/rbt/encrypted /var/opt/rbt/encrypted
	    if [ ! -d /var/opt/rbt/decrypted ]; then
                mkdir -m 0700 /var/opt/rbt/decrypted
            fi

            # make the silly ssl link that goes up 1 directory.
            ln -s /var/opt/rbt/decrypted/ssl /var/opt/rbt/ssl

	    # mgmt ssl module will log later if they can't mount.
	;;
	*)
	;;
    esac

}

###############################################################################
# do_3ware_var_check
#
# do the stuff necessary to check that a 3ware RAID is good,
# and that the partition table is valid.
# also, do the apporpriate var checks and rebuild it if necessary.
#
###############################################################################
do_3ware_var_check()
{
    tcli='/usr/sbin/tw_cli'
    parted='/sbin/parted -s'

    change=0
    part=0

    tstat=`$tcli /c0/u0 show status | /bin/awk '{print $4}'`
    $tcli /c0/u0 show status > /dev/null 2>&1

    if [ $? -ne 1 -a "x${tstat}" != "xINOPERABLE" ]; then
        #raid is likely OK.
        echo "Array seems OK.  Continuing."
    else
        #handle DEGRADED & INOPERABLE
        echo "Rebuilding RAID array."

        if [ "x${tstat}" = "xINOPERABLE" \
            -o "x${tstat}" != "xDEGRADED" ]; then
            echo "RAID array is inoperable, deleting" 
            $tcli /c0/u0 del quiet > /dev/null 2>&1
        fi
        change=1
        #going to assume that /sys is still OK.
        $tcli maint deleteunit c0 u0 > /dev/null 2>&1
        #ignore return code, just making sure 
        $tcli /c0 add type=raid10 disk=0-13  > /dev/null 2>&1
        if [ $? -ne 0 ]; then
            echo "Could not create new array, exiting."
            echo "Please contact support."
            /sbin/halt
        fi

        $tcli /c0/u0 set storsave=perform quiet  > /dev/null 2>&1
        #don't care about return code here.
        echo "Rebooting in 10 seconds so that array is recognized"
        /bin/sleep 10
        /sbin/reboot
    fi # end degraded / inoperable 3ware RAID case.

    #check partitioning and repair if broken.
    pcheck=`$parted /dev/sda print | /usr/bin/md5sum`
    if [ "x$pcheck" != "x001e11889bcab7d0b57c6d33c9089cc8  -" ]; then
        echo "Partition table issues, repairing." 
        change=1
        part=1
        $parted /dev/sda mklabel gpt
        if [ $? -ne 0 ]; then
            echo "Partitioning error, contact support." 
            /sbin/halt
        fi
        $parted /dev/sda mkpart 82 0 2046MB
        if [ $? -ne 0 ]; then
            echo "Partitioning error, contact support." 
            /sbin/halt
        fi
        $parted /dev/sda mkpart 83 2046MB 125GB
        if [ $? -ne 0 ]; then
            echo "Partitioning error, contact support." 
            /sbin/halt
        fi
        $parted /dev/sda mkpart da 125GB 3500GB
        if [ $? -ne 0 ]; then
            echo "Partitioning error, contact support." 
            /sbin/halt
        fi
        /bin/sleep 5
    else
        echo "Partition table looks OK.  Continuing." 
    fi

    #check /var mountability, rebuild if hosed.
    #
    /bin/mount LABEL=VAR /mnt > /dev/null 2>&1
    if [ $? -ne 0 -o $part -eq 1 ]; then
        /bin/umount /mnt > /dev/null 2>&1
        echo -n "Waiting for /dev/sda2:"
        while [ ! -b /dev/sda2 ]; do
            sleep 2
            echo -n "."
        done
        echo ""
        echo "Possible /var issues, repairing." 
        vlab=`/sbin/e2label /dev/sda2 2>&1`
        if [ "x$vlab" != "xVAR" ]; then
            /sbin/e2label /dev/sda2 VAR > /dev/null 2>&1
        fi

        /sbin/fsck -y LABEL=VAR > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            /bin/mount LABEL=VAR /mnt > /dev/null 2>&1
            if [ $? -eq 0 ]; then
                /bin/umount /mnt > /dev/null 2>&1
                echo "/var seemingly recoverable." 
            fi
        else
            change=1
            /bin/umount /mnt > /dev/null 2>&1
            /bin/dd if=/dev/zero of=/dev/sda2 bs=1M count=1 > /dev/null 2>&1
            /sbin/mke2fs -qF -O ^resize_inode -L VAR -j /dev/sda2
            if [ $? -ne 0 ]; then
                echo "Could not create /var filesystem" 
                /sbin/halt
            fi
            if [ $part -eq 1 ]; then
                /sbin/mkswap -v1 /dev/sda1
                dd if=/dev/zero of=/dev/sda3 bs=512 count=8192
            fi
        fi
        mount LABEL=VAR > /dev/null 2>&1
        if [ $? -ne 0 ]; then
            echo "Could not mount new /var filesystem" 
            /sbin/halt
        fi

	# if we got here, we have a mounter /var and we need to put the right contents back
	# for mgmt to run.
	#
	do_var_repopulate
    else
        /bin/umount /mnt > /dev/null 2>&1
        echo "/var looks OK.  Continuing."
    fi

    if [ $change -ne 1 ]; then
        echo "Didn't find anything wrong and made no changes."
        echo "Please contact support if there are unresolved issues."
    else
        #rebooting doesn't seem to be necessary here.
        echo "Changes made.  Please allow extra time for your system to boot"
    fi
}

###############################################################################
# do_disk_var_check
#
# for systems that do not boot from flash there is no recovery method.
# only the 3ware units and the new hardware running sw raid have
# var recovery methods to date.
#
###############################################################################
do_disk_var_check()
{
    # we currently don't handle extended recovery cycles for 3ware and non 
    # sw raid systems
    echo "$STRING"
    echo
    echo
    echo $"*** An error occurred during the file system check."
    echo $"*** Dropping you to a shell; the system will reboot"
    echo $"*** when you leave the shell."

    str=$"(Repair filesystem)"
    PS1="$str \# # "; export PS1
    [ "$SELINUX" = "1" ] && disable_selinux
    sulogin -e

    echo $"Unmounting file systems"
    umount -a
    mount -n -o remount,ro /
    echo $"Automatic reboot in progress."
    reboot -f
}

# XXX This assumes a 1K blocksize (which is what mke2fs assumes on the
# cmdline unless you specify -b 4096, at which time you need to divide this
# by 4, if that changes.
# 
RESERVE_BLOCKS=1024 # reserve 1024 x 1024 = 1MB at the end of ext3 partitions.
        
# for new hw single disk units, we want to reserve space at
# the end of the ext3 partitions so we could add a MD SB in the future.
#       
do_calculate_blocks_w_reserve()
{       
    dev=$1
    # if we've been told to reserve some space, we need to calc
    # the number of blocks to tell ext3 to use.
    tmp_syl_dev=`readlink -f ${dev}`
    temp_dev=`echo $tmp_syl_dev | awk '{ print substr( $0, 6 , length($0)) }'`
    dev1=`echo $temp_dev | awk '{ print substr( $0, 1 , 1) }'`
    dev2=`echo $temp_dev | awk '{ print substr( $0, 1 , length($0)-1) }'`
    if [ ${dev1} = "s" ]; then
        total_sectors=`cat /sys/block/${dev2}/${temp_dev}/size`
    else
        total_sectors=`cat /sys/block/${temp_dev}/size`
    fi

    total_blocks=`expr ${total_sectors} / 2`
        
    if [ ${total_blocks} -le ${RESERVE_BLOCKS} ]; then
        echo "*** Block size too small when calculating reserve blocks on $dev"
        cleanup_exit    
    fi  

    expr ${total_blocks} - ${RESERVE_BLOCKS}
}       


###############################################################################
# do_sw_var_check
#
# Var rebuild for sw raided appliances.
# A little different from 3ware since the raid setup and reconstruction occurred
# back in rc.sysinit.
# 
# Here just try to get /var up and running again, through the same sub-process
# as the 3ware unit, except we need to read the raid device name from
# the raid disk tool.
#
###############################################################################
do_sw_var_check()
{
    RDEV=`get_device var`
    if [ $? -ne 0 ]; then
	echo "Internal error, unable to determine var raid device."
	echo "Contact Riverbed Support."
	return 1
    fi
    
    if [ ! -b ${RDEV} ]; then
	echo "Var device $RDEV does not exist."
        do_recover_appliance
        return 0
    fi
    
    # force it - don't mount just rebuild make sure we fsck it first.
    if [ ${FORCEIT} -eq 0 ]; then
    /bin/mount ${RDEV} /mnt > /dev/null 2>&1
    fi

    if [ $? -ne 0 -o ${FORCEIT} -eq 1 ]; then
        /bin/umount /mnt > /dev/null 2>&1
	if [ ${FORCEIT} -eq 1 ]; then
	    echo "Recovering VAR filesystem"
	else
	    echo "VAR problems, starting recovery process for [${rtype}]"
	fi
        vlab=`/sbin/e2label ${RDEV} 2>&1`
        if [ "x$vlab" != "xVAR" ]; then
            /sbin/e2label ${RDEV} VAR > /dev/null 2>&1
        fi

        /sbin/fsck -y LABEL=VAR > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            /bin/mount LABEL=VAR /mnt > /dev/null 2>&1
            if [ $? -eq 0 ]; then
                /bin/umount /mnt > /dev/null 2>&1
                echo "/var seemingly recoverable." 
            fi
        else
            change=1
            part=0
            /bin/umount /mnt > /dev/null 2>&1
            /bin/dd if=/dev/zero of=${RDEV} bs=1M count=1 > /dev/null 2>&1

            reserve_sb=`get_reserve_sb var`
            if [ "x$reserve_sb" = "xtrue" ]; then
                blocks=`do_calculate_blocks_w_reserve ${RDEV}`
            else
                # use the entire partition
                blocks=
            fi

            /sbin/mke2fs -qF -O ^resize_inode -L VAR -j ${RDEV} ${blocks}
            if [ $? -ne 0 ]; then
                 echo "Could not create /var filesystem" 

                # if we couldnt fix /var, then check if we can rebuild the box.
                do_recover_appliance
            fi
            if [ $part -eq 1 ]; then
                /sbin/mkswap -v1 /dev/md2
                dd if=/dev/zero of=/dev/md0 bs=512 count=8192
                # add in clearing sstore notification?
            fi
        fi # attempted to fsck -y and did the right thing after that.

        mount LABEL=VAR > /dev/null 2>&1
        if [ $? -ne 0 ]; then
            echo "Could not mount /var filesystem after reconstruction" 
            do_recover_appliance
        fi

	# if successful restore /var
	echo "Unpacking /var recovery image"
	do_var_repopulate
	
    else
        /bin/umount /mnt > /dev/null 2>&1
	echo "/var is mountable, proceeding."
    fi # tried to mount /var

    # leave var unmounted so the fstab can fsck it.
    umount /var > /dev/null 2>&1
    return 0
}


# get_rvbd_sb_sno
#
# check to see if this disk belongs to one of the new units.
# the serial number for the appliance this disk was mfg'd in is
# in the sb
#
get_rvbd_sb_sno()
{
    DISK=$1
    
    # we really should ask the spec for the rvbd super part,
    # but we don't have an interface for that yet, its assumed to be part 1.
    /opt/tms/bin/rvbd_super -g /dev/disk${DISK}p1 | grep "serial=" | sed 's/serial=//'
}

# 0 means we can remanufacture 
# 1 means don't do it!
# 
is_remanufacture_allowed()
{

    MODEL=`/opt/tms/bin/hald_model | awk '{print $1}'`

    case "x${MODEL}" in
        "x150M"|"x250L"|"x250M"|"x250H"|"x550M"|"x550H"|"x1050L"|"x1050M"|"x1050H"|"xCX255L"|"xCX255M"|"xCX255H"|"xCX555M"|"xCX555H"|"xCX755H"|"xCX755M"|"xCX755L"|"xEX560L"|"xEX560M"|"xEX560H")
            # we do field remanufacturing on these units today
            # for single disk systems or 1050H systems
        ;;
        *)
            # don't do it.
            return 1
        ;;
    esac

    APP_SNO=`/opt/tms/bin/mddbreq -v /config/mfg/mfdb query get - /rbt/mfd/serialnum`
    # we only do disk 0 for now.
    if [ "x${MODEL}" = "xEX560L" -o "x${MODEL}" = "xEX560M" -o "x${MODEL}" = "xEX560H" ]; then
        DISK_SNO=`get_rvbd_sb_sno 1`
    else 
        DISK_SNO=`get_rvbd_sb_sno 0`
    fi

    if [ "x${DISK_SNO}" = "x" ]; then
        # no riverbed sb, blank disk we should be good to remanufacture.
        echo "Blank disk detected, allowing remanufacture"
        return 0
    fi

    if [ "x${DISK_SNO}" = "x${APP_SNO}" ]; then
        # eh, they match so we don't want to remanufacture.  This disk
        # obviously already failed. later we'll add an option to grub or 
        # something that lets the user decide what to do.
        return 1
    fi

    echo "New disk detected, allowing remanufacture"
    return 0
}

# use the raid tool to relayout the disk
#
# later on we'll need to make the jump_to_console use case specific, 
# since for raided units fs recovery will happen in the rbtkmod context
# for things like pfs and segstore.
#
perform_disk_manufacture()
{
    echo "Starting Appliance Remanufacture Process"
    # remount in rw mode.
    mount -o rw,remount /


    CNT=0
    while [ $CNT -lt 10 ]; do
        /opt/hal/bin/raid/rrdm_tool.py -u
        if [ $? -ne 0 ]; then
            CNT=$[ $CNT + 1 ]
            echo "Retrying disk partitioning"
            sleep 20
        else
            break
        fi
    done

    if [ $CNT -ge 10 ]; then
        echo "Remanufacturing failed, halting system."
        /sbin/halt -p
    fi

    /sbin/do_fs_recovery.sh swap
    if [ $? -ne 0 ]; then
        echo "Unable to recreate SWAP, exiting to recovery console."
        /sbin/halt -p
    fi
    /sbin/do_fs_recovery.sh var
    if [ $? -ne 0 ]; then
        echo "Unable to recreate VAR, exiting to recovery console."
        /sbin/halt -p
    fi

    /sbin/do_fs_recovery.sh pfs
    if [ $? -ne 0 ]; then
        echo "Unable to recreate PFS, exiting to recovery console."
        /sbin/halt -p
    fi

    echo "Appliance remanufacturing is complete."
    echo "Rebooting the appliance"
    reboot
}

check_selinux()
{
    # Check SELinux status
    selinuxfs=`awk '/ selinuxfs / { print $2 }' /proc/mounts`
    SELINUX=
    if [ -n "$selinuxfs" ] && [ "`cat /proc/self/attr/current`" != "kernel" ]; then
        if [ -r $selinuxfs/enforce ] ; then
                SELINUX=`cat $selinuxfs/enforce`
        else
                # assume enforcing if you can't read it
                SELINUX=1
        fi
    fi
}

jump_to_repair_console()
{
    echo "$STRING"
    echo
    echo
    echo $"*** An error occurred during the file system check."
    echo $"*** Dropping you to a shell; the system will reboot"
    echo $"*** when you leave the shell."

    str=$"(Repair filesystem)"
    PS1="$str \# # "; export PS1
    [ "$SELINUX" = "1" ] && disable_selinux
    sulogin -e

    echo $"Unmounting file systems"
    umount -a
    mount -n -o remount,ro /
    echo $"Automatic reboot in progress."
    reboot -f


}

disable_selinux() 
{
        echo "*** Warning -- SELinux is active"
        echo "*** Disabling security enforcement for system recovery."
        echo "*** Run 'setenforce 1' to reenable."
        echo "0" > $selinuxfs/enforce
}


# do_recover_appliance
#
# if this is a single disk system or a 1050H, then we can remanufacture 
# if know that this disk was not originally from this SH. Here we're 
# supporting the ability to ship customers a new disk and have the 
# box rebuild itself.
#
# this is a completely destructive remanufacture.
#
do_recover_appliance()
{


    # we really should get these names from the spec
    # but we'll forcibly unmount them so theyre all available in case we want
    # to remanu, also turn off swap
    umount /var >> /dev/null 2>&1
    umount /proxy >> /dev/null 2>&1
    /sbin/swapoff -a >> /dev/null 2>&1

    # check to ensure that this is a single disk model
    # (by motherboard for DTABA) and MODEL for others
    #
    # and check to see if this disk has our SB.  If not, we can use it.
    #
    is_remanufacture_allowed
    if [ $? -eq 0 ]; then
        # do the remanufacture
        perform_disk_manufacture
    else
        # the original behavior here was if we can't fix the box to halt.
        /sbin/halt -p
    fi
}

###############################################################################
#
# Data Recovery Routines.
#
# Only for the new units supported by rrdm_tool.py (TYAN1U/3U/MINNOW)
#
###############################################################################

do_fs_recovery_common()
{
    MOUNT="$1" # /data, /proxy
    PART="$2" # data, pfs
    LABEL="$3" #DATA, SAMBA

    PART_DEV=`get_device ${PART}`
    if [ ! -b ${PART_DEV} ]; then
        do_log WARN "Block device for ${PART} [${PART_DEV}] does not exist."
        do_recover_appliance
        return 0
    fi

    # double check PART mountability
    #
    mount ${PART_DEV} ${MOUNT} > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        umount ${PART_DEV} > /dev/null 2>&1

        do_log INFO "Forcing filesystem recovery on ${PART}"

        # can't mount, device exists .. then do recovery.
        #
        /sbin/fsck -y ${PART_DEV} > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            mount ${PART_DEV} ${MOUNT} > /dev/null 2>&1
            if [ $? -eq 0 ]; then
                do_log INFO "${PART} recovery successful. "
                exit 0
            fi
        fi

        # fsck -y failed, or the mount after fsck -y failed.
        # 
        do_log NOTICE "${PART} filesystem is unrecoverable, rebuilding clean filesystem."
        do_log NOTICE "This may take up to 60 seconds."

        # force an unmount just to be sure.
        umount ${MOUNT} > /dev/null 2>&1

        dd if=/dev/zero of=${PART_DEV} bs=1M count=1 > /dev/null 2>&1
        reserve_sb=`get_reserve_sb data`
        if [ "x$reserve_sb" = "xtrue" ]; then
            blocks=`do_calculate_blocks_w_reserve ${PART_DEV}`
        else
            # use the entire partition
            blocks=
        fi

        /sbin/mke2fs -qF -O ^resize_inode -j ${PART_DEV} ${blocks}
        if [ $? -ne 0 ]; then
            do_log WARN "Unable to rebuild ${PART} filesystem, contact Riverbed Support."
            do_recover_appliance
        fi

        # Special processing for different partitions. For DATA partition we need
        # the /dev/mdX device to have a label, proxy on the other hand doesnt need it
        # Proxy partition needs to be mounted as it isnt a part of fstab
        if [ "x${PART}" = "xdata" ];then 
            # Set the label for the data partition
            vlab=`/sbin/e2label ${PART_DEV} 2>&1`
            if [ "x$vlab" != "x${LABEL}" ]; then
                /sbin/e2label ${PART_DEV} ${LABEL} > /dev/null 2>&1
            fi
        elif [ "x${PART}" = "xpfs" ]; then
            # lastly mount PFS
	    if [ ${UNMOUNT_WHEN_DONE} -ne 1 ]; then
	        mount ${PART_DEV} ${MOUNT} > /dev/null 2>&1
	        if [ $? -ne 0 ]; then
                    do_log WARN "Unable to rebuild ${PART} filesystem, contact Riverbed Support."
                    do_recover_appliance
	        fi
            fi
        fi

        do_log NOTICE "${PART} Filesystem has been successfully re-formatted."
        exit 0
    else
        do_log INFO "${PART} is mountable, no recovery needed."
        if [ ${UNMOUNT_WHEN_DONE} -ne 1 ]; then
            umount ${PART_DEV} ${MOUNT} > /dev/null 2>&1
        fi
        exit 0
    fi

}

###############################################################################
#
# PFS Recovery Routines.
#
# Only for the new units supported by rrdm_tool.py (TYAN1U/3U/MINNOW)
#
###############################################################################

###############################################################################
# do_pfs_fs_recovery
#
# Assuming the PFS Raid array was started, do the appropriate steps to
# get PFS back online.  This should be done after VAR has been recreated so we
# can log the appropriate messages to syslog to track the PFS recovery.
#
# We get in here if the PFS partition was unmountable. Try to fsck and remount,
# if that fails, then wipe the PFS partition and remake it.
#
# If PFS recovery is successful, PFS will be left mounted to the appropriate 
# device
#
###############################################################################
PFS_MOUNT="/proxy"
do_pfs_fs_recovery()
{
    do_fs_recovery_common $PFS_MOUNT "pfs" "SAMBA"
}

###############################################################################
# do_data_fs_recovery
#
# Assuming the Data Raid array was started, do the appropriate steps to
# get Data back online.  This should be done after VAR has been recreated so we
# can log the appropriate messages to syslog to track the Data recovery.
#
# We get in here if the DATA partition was unmountable. Try to fsck and remount,
# if that fails, then wipe the Data partition and remake it.
#
# If Data recovery is successful, Data will be left mounted to the appropriate 
# device
#
###############################################################################
DATA_MOUNT="/data"
do_data_fs_recovery()
{
    do_fs_recovery_common $DATA_MOUNT "data" "DATA"
}


do_swap_recovery()
{
    SWAP_DEV=`get_device swap`
    if [ ! -b ${SWAP_DEV} ]; then
	do_log WARN "Block device for SWAP [${SWAP_DEV}] does not exist."
	exit 1
    fi
    
    do_log INFO "Forcing recovery on SWAP"

    /sbin/mkswap -v1 ${SWAP_DEV}
    if [ $? -ne 0 ]; then
        do_log WARN "mkswap failed on ${SWAP_DEV}" 
        exit 1
    fi

    do_log INFO "SWAP recovery successful"
    return 0
}


###############################################################################
# Main 
###############################################################################
do_log INFO "Running filesystem recovery script for [${VOL_NAME}]"
RRDM_SUPPORTED=`${RRDM_TOOL_PY} --supported`
rtype=`get_recovery_type`
check_selinux

case "x${VOL_NAME}" in
    "xvar")
	case "x${rtype}" in
	    "x${RECOVERY_TYPE_SW}")
		do_sw_var_check
	    ;;
	    "x${RECOVERY_TYPE_3W}")
		do_3ware_var_check
	    ;;
	    *)
		do_disk_var_check
	    ;;
	esac
	;;
    "xpfs")
	# assume that neither sw raid units nor 3ware units have a var recovery check.	
	if [ "x${rtype}" == "x${RECOVERY_TYPE_SW}" ]; then
	    do_pfs_fs_recovery
	fi
    ;;
    "xdata")
	# assume that neither sw raid units nor 3ware units have a var recovery check.	
	if [ "x${rtype}" == "x${RECOVERY_TYPE_SW}" ]; then
	    do_data_fs_recovery
	fi
    ;;
    "xswap")
        do_swap_recovery
    ;;
    # no recovery procedure associated with the segstore.
    #
    "xsegstore")
	exit 0
    ;;
    *)
	do_log WARN "Unknown filesystem specified for recovery."
	exit 1
    ;;
esac
