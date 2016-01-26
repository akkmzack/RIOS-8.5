#!/bin/sh

#
#  Filename:  $Source$
#  Revision:  $Revision: 115790 $
#  Date:      $Date: 2012-08-23 18:44:40 -0700 (Thu, 23 Aug 2012) $
#  Author:    $Author: pkunisetty $
# 
#  (C) Copyright 2002-2005 Tall Maple Systems, Inc.  
#  All rights reserved.
#

#
# This script is used to verify a .img file , or to query information about
# the image.  Internally these files are currently zips.  
#

PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH

usage()
{
    echo "usage: $0 <MODEL> [Storage Profile]"
    echo "For use in manufacturing only."
    echo "MODEL:  installed model number."

    exit 1
}

if [ $# -ne 1 -a $# -ne 2 ]; then
	usage
fi

# Make sure a full device name was specified for the image disk

MODEL=$1
STORAGE_PROFILE=$2
# Test all the options that got set for correctness
if [ "x${STORAGE_PROFILE}" = "x" ]; then
    STORAGE_PROFILE_CMD=""
else
    STORAGE_PROFILE_CMD="--profile=${STORAGE_PROFILE}"
fi


if [ ! -f /etc/layout_settings.sh ]; then
    echo "Error: No valid layout settings information found."
    exit 1
fi

if [ ! -f /etc/image_layout.sh ]; then

    if [ -f /mfg/model_data/model_${MODEL}.sh ]; then
	. /mfg/model_data/model_${MODEL}.sh
    else
	echo "Error: Could not find model data file."
	exit 1
    fi

    if [ ! ${MODEL_LAYOUT} ]; then 
	#some stuff just assumes STD
	IL_LAYOUT=STD
    else
	IL_LAYOUT=${MODEL_LAYOUT}
    fi

    case ${IL_LAYOUT} in
	'FLASHRRDM')
	    disks="$MODEL_BOOTDEV"
	    ;;
	'VSHSTD')
	    disks="$MODEL_BOOTDEV"
	    ;;
        'BOBSTD')
	    disks="$MODEL_BOOTDEV $MODEL_BOOTDEV_2 $MODEL_DISKDEV $MODEL_DISKDEV_2"
	    ;;
        'BOBRDM')
	    disks="$MODEL_BOOTDEV $MODEL_BOOTDEV_2 $MODEL_DISKDEV $MODEL_DISKDEV_2"
	    ;;
	'FLASHBV')
	    disks="$MODEL_BOOTDEV $MODEL_DISKDEV"
            ;;
	'SSGSTD')
	    disks="$MODEL_BOOTDEV"
	    ;;
	*)
	    disks="$MODEL_DISKDEV $MODEL_DISKDEV_2 $MODEL_BOOTDEV $MODEL_FLASHDEV"
	    ;;
    esac

    ct=1
    for disk in ${disks}; do
        eval 'IL_LO_'${IL_LAYOUT}'_TARGET_DISK'${ct}'_DEV='${disk}
	ct=`expr $ct + 1`
    done

fi

# Make sure we listen to anything image_layout.sh may have to say
if [ -f /etc/image_layout.sh ]; then
    . /etc/image_layout.sh
fi

. /etc/layout_settings.sh

if [ -f /etc/image_layout.sh ]; then
    . /etc/image_layout.sh
fi

TMP_MNT_IMAGE=/tmp/mnt_image
mkdir -p ${TMP_MNT_IMAGE}

# Build up the list of partitions in IMAGE_[1|2]_PART_LIST . These are
# suitably ordered for mounting because the layout LOCS are suitably ordered
# for mounting.
for inum in 1 2; do
    loc_list=""
    eval 'loc_list="${IL_LO_'${IL_LAYOUT}'_IMAGE_'${inum}'_LOCS}"'

    for loc in ${loc_list}; do
        add_part=""
        eval 'add_part="${IL_LO_'${IL_LAYOUT}'_LOC_'${loc}'_PART}"'

        if [ ! -z "${add_part}" ]; then
            # Only add it on if it is unique
            eval 'curr_list="${IMAGE_'${inum}'_PART_LIST}"'

            present=0
            echo "${curr_list}" | grep -q " ${add_part} " - && present=1
            if [ ${present} -eq 0 ]; then
                eval 'IMAGE_'${inum}'_PART_LIST="${IMAGE_'${inum}'_PART_LIST} ${add_part} "'
            fi
        fi
    done
done

#fixup the target names for software raid.
rrdm_res=`/mfg/rrdm_tool.py -m $MODEL -l ${STORAGE_PROFILE_CMD}`
if [ "x$rrdm_res" != xNOP ]; then
    for pair in ${rrdm_res}; do
        name=`echo $pair | awk 'BEGIN{FS=":"} {print $1}'`
        dev=`echo $pair | awk 'BEGIN{FS=":"} {print $2}'`
        fstype=`echo $pair | awk 'BEGIN{FS=":"} {print $3}'`
	part_id=`echo $pair | awk 'BEGIN{FS=":"} {print $4}'`

	if [ x$name = 'xswap' ]; then 
	    label="SWAP"
	    mount="swap"
	    # For shared partition add them to both PART_LIST's 
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_DEV=/dev/'$dev
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_MOUNT='$mount
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_FSTYPE='$fstype
	    eval 'IMAGE_1_PART_LIST="${IMAGE_1_PART_LIST} '$label'"'
	    eval 'IMAGE_2_PART_LIST="${IMAGE_2_PART_LIST} '$label'"'
	elif [ x$name = 'xsegstore' ]; then 
	    label="DATA"
	    fstype=""
	    mount=""
	    # For shared partition add them to both PART_LIST's 
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_DEV=/dev/'$dev
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_MOUNT='$mount
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_FSTYPE='$fstype
	    eval 'IMAGE_1_PART_LIST="${IMAGE_1_PART_LIST} '$label'"'
	    eval 'IMAGE_2_PART_LIST="${IMAGE_2_PART_LIST} '$label'"'
	elif [ x$name = 'xpfs' ]; then 
	    label="SMB"
	    mount="/proxy"
	    # For shared partition add them to both PART_LIST's 
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_DEV=/dev/'$dev
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_MOUNT='$mount
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_FSTYPE='$fstype
	    eval 'IMAGE_1_PART_LIST="${IMAGE_1_PART_LIST} '$label'"'
	    eval 'IMAGE_2_PART_LIST="${IMAGE_2_PART_LIST} '$label'"'
        elif [ x$name = 'xdata' ]; then
            label="DATA"
            mount="/data"
	    # For shared partition add them to both PART_LIST's 
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_DEV=/dev/'$dev
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_MOUNT='$mount
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_FSTYPE='$fstype
	    eval 'IMAGE_1_PART_LIST="${IMAGE_1_PART_LIST} '$label'"'
	    eval 'IMAGE_2_PART_LIST="${IMAGE_2_PART_LIST} '$label'"'
	elif [ x$name = 'xvar' ]; then 
	    label="VAR"
	    mount="/var"
	    # For shared partition add them to both PART_LIST's 
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_DEV=/dev/'$dev
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_MOUNT='$mount
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_FSTYPE='$fstype
	    eval 'IMAGE_1_PART_LIST="${IMAGE_1_PART_LIST} '$label'"'
	    eval 'IMAGE_2_PART_LIST="${IMAGE_2_PART_LIST} '$label'"'
        elif [ "x$name" = "xscratch" ]; then
            label="SCRATCH"
            mount="/scratch"
	    # For shared partition add them to both PART_LIST's 
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_DEV=/dev/'$dev
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_MOUNT='$mount
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_FSTYPE='$fstype
	    eval 'IMAGE_1_PART_LIST="${IMAGE_1_PART_LIST} '$label'"'
	    eval 'IMAGE_2_PART_LIST="${IMAGE_2_PART_LIST} '$label'"'
	elif [ x$name = 'xshadow' ]; then 
	    label="SHADOW"
	    fstype=""
	    mount=""
	    # For shared partition add them to both PART_LIST's 
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_DEV=/dev/'$dev
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_MOUNT='$mount
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_FSTYPE='$fstype
	    eval 'IMAGE_1_PART_LIST="${IMAGE_1_PART_LIST} '$label'"'
	    eval 'IMAGE_2_PART_LIST="${IMAGE_2_PART_LIST} '$label'"'
        elif [ x$name = 'xvdata' ]; then
            label="VDATA"
            fstype=""
            mount=""
	    # For shared partition add them to both PART_LIST's 
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_DEV=/dev/'$dev
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_MOUNT='$mount
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_FSTYPE='$fstype
	    eval 'IMAGE_1_PART_LIST="${IMAGE_1_PART_LIST} '$label'"'
	    eval 'IMAGE_2_PART_LIST="${IMAGE_2_PART_LIST} '$label'"'
        elif [ x$name = 'xconfig' ]; then
            label="CONFIG"
            mount="/config"
            eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_DEV=/dev/'$dev
            eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_MOUNT='$mount
            eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_FSTYPE='$fstype
            eval 'IMAGE_1_PART_LIST="${IMAGE_1_PART_LIST} '$label'"'
	    eval 'IMAGE_2_PART_LIST="${IMAGE_2_PART_LIST} '$label'"'
            continue
        elif [ x$name = 'xbootmgr' ]; then
            label="BOOTMGR"
            mount="/bootmgr"
            eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_DEV=/dev/'$dev
            eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_MOUNT='$mount
            eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_FSTYPE='$fstype
            eval 'IMAGE_1_PART_LIST="${IMAGE_1_PART_LIST} '$label'"'
	    eval 'IMAGE_2_PART_LIST="${IMAGE_2_PART_LIST} '$label'"'
            continue
        # XXX/munirb: Now since ROOT, BOOT, etc are RAIDed using RRDM
        # they are on the HD, we need to add the partition to the IMG_LIST
        # based on where it belongs. We should not run the check on everything
        elif [ x$name = 'xboot_1' ]; then
	    label="BOOT_1"
	    mount="/boot"
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_DEV=/dev/'$dev
    	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_MOUNT='$mount
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_FSTYPE='$fstype
	    eval 'IMAGE_1_PART_LIST="${IMAGE_1_PART_LIST} '$label'"'
	    continue
        elif [ x$name = 'xroot_1' ]; then
	    label="ROOT_1"
	    mount="/"
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_DEV=/dev/'$dev
    	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_MOUNT='$mount
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_FSTYPE='$fstype
            # XXX/munirb: ROOT_X should be the first partition to be mounted
            # or else the mount points of the partitions before it won't 
            # work correctly. For all models using layout_settings the mount
            # order is hardcoded in there, for xx60 models and onwards the 
            # ROOT/BOOT order is in rrdm_tool so we need to interchange it 
            # here
	    eval 'IMAGE_1_PART_LIST="'$label' ${IMAGE_1_PART_LIST}"'
	    continue
        elif [ x$name = 'xboot_2' ]; then
	    label="BOOT_2"
	    mount="/boot"
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_DEV=/dev/'$dev
    	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_MOUNT='$mount
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_FSTYPE='$fstype
	    eval 'IMAGE_2_PART_LIST="${IMAGE_2_PART_LIST} '$label'"'
	    continue
        elif [ x$name = 'xroot_2' ]; then
	    label="ROOT_2"
	    mount="/"
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_DEV=/dev/'$dev
    	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_MOUNT='$mount
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$label'_FSTYPE='$fstype
            # XXX/munirb: ROOT_X should be the first partition to be mounted
            # or else the mount points of the partitions before it won't 
            # work correctly. For all models using layout_settings the mount
            # order is hardcoded in there, for xx60 models and onwards the 
            # ROOT/BOOT order is in rrdm_tool so we need to interchange it 
            # here
	    eval 'IMAGE_2_PART_LIST="'$label' ${IMAGE_2_PART_LIST}"'
	    continue
        else
            label="${name}"
            fstype=""
            mount=""
	fi
    done
fi

#
# Do everything for both images 1 and 2.  This may / does end up checking
# files on shared partitions twice.  
#
# The plan is to mount all the partitions for a given image, check them against
# the manifest, and then unmount them all.
#
for inum in 1 2; do
    eval 'part_list="${IMAGE_'${inum}'_PART_LIST}"'
    UNMOUNT_LIST=

    #echo "PART LIST = ${part_list}"
    for part in ${part_list}; do
        eval 'part_dev="${IL_LO_'${IL_LAYOUT}'_PART_'${part}'_DEV}"'
        eval 'part_mount="${IL_LO_'${IL_LAYOUT}'_PART_'${part}'_MOUNT}"'
        eval 'part_fstype="${IL_LO_'${IL_LAYOUT}'_PART_'${part}'_FSTYPE}"'

        #echo "${part_dev} == ${part_mount}   ==  ${part_fstype}"

        if [ -z "${part}" -o -z "${part_dev}" \
            -o -z "${part_mount}" -o -z "${part_fstype}" \
            -o "${part_fstype}" = "swap" \
	    -o "${part}" = "SMB" ]; then
            continue
        fi

        mount_point="${TMP_MNT_IMAGE}/${part_mount}"

        mkdir -p ${mount_point}
        unmount ${mount_point} > /dev/null 2>&1
        FAILURE=0
        mount ${part_dev} ${mount_point} || FAILURE=1
        if [ ${FAILURE} -eq 1 ]; then
            echo "*** Could not mount partition ${part_dev} on ${mount_point}"
            exit 1
        fi
        UNMOUNT_LIST="${mount_point} ${UNMOUNT_LIST}"
    done

    FAILURE=0
    case ${IL_LAYOUT} in
        'HDRRDM')
            # Do not check for /bootmgr data as there is no such partition anymore
            cat ${TMP_MNT_IMAGE}/etc/MANIFEST | egrep -v ' \.(/dev/shm|/var/log/messages|/var/log/user_messages|/var/log/lastlog|/var/log/web_access_log|/var/log/web_error_log|/var/lib/logrotate.status|/lib/modules/[^/]*/modules.[^/]*|/etc/opt/tms/output/.*|/etc/fstab|/etc/.firstboot|/proc|/bootmgr/boot.*|/bootmgr/data|/etc/adjtime|/boot/System.map|/boot/vmlinuz|/opt/rbt/lib/modules)$' | /bin/lfi -TNGUM -r ${TMP_MNT_IMAGE} -c - || FAILURE=1
            ;;
        *)
            cat ${TMP_MNT_IMAGE}/etc/MANIFEST | egrep -v ' \.(/dev/shm|/var/log/messages|/var/log/user_messages|/var/log/lastlog|/var/log/web_access_log|/var/log/web_error_log|/var/lib/logrotate.status|/lib/modules/[^/]*/modules.[^/]*|/etc/opt/tms/output/.*|/etc/fstab|/etc/.firstboot|/proc|/bootmgr/boot/grub/grub.conf|/etc/adjtime|/boot/System.map|/boot/vmlinuz|/opt/rbt/lib/modules)$' | /bin/lfi -TNGUM -r ${TMP_MNT_IMAGE} -c - || FAILURE=1
            ;;
    esac

    # Unmount all the partitions
    for ump in ${UNMOUNT_LIST}; do
        umount ${ump} > /dev/null 2>&1
    done

    if [ ${FAILURE} -eq 1 ]; then
        echo "*** Image ${inum} verification failed."
        exit 1
    else
        echo "- Image ${inum} verified successfully."
    fi

done

exit 0
