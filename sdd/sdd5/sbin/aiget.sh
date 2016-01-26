#!/bin/sh

#
#  Filename:  $Source$
#  Revision:  $Revision: 101753 $
#  Date:      $Date: 2012-12-27 19:00:04 -0800 (Thu, 27 Dec 2012) $
#  Author:    $Author: vvaidyanathan $
# 
#  (C) Copyright 2002-2005 Tall Maple Systems, Inc.  
#  All rights reserved.
#

# 
# This script gets which image was booted from a disk, and which will boot
# next time the machine is restarted.  See writeimage.sh for more on disk
# layouts.  
#
# This script can only be run on a running system NOT during manufacturing
#
# XXX The script currently only works if you're booted from the disk you
#     want to know the active image of, and the bootmgr partition is mounted
#     on /bootmgr !

PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH

usage()
{
    echo "usage: $0"
    echo ""
    exit 1
}

if [ $# != 0 ]; then
    usage
fi

if [ ! -f /etc/layout_settings.sh ]; then
    echo "Error: No valid layout settings information found."
    exit 1
fi

if [ ! -f /etc/image_layout.sh ]; then
    echo "Error: No valid image layout information found."
    exit 1
fi


# Make sure we listen to anything image_layout.sh may have to say
. /etc/image_layout.sh
. /etc/layout_settings.sh
. /etc/image_layout.sh


# See what root device they started from
BOOTED_ROOT_DEV=`/bin/mount | grep -w '^.* on /boot type .*$' | awk '{print $1}'`
BOOTED_DEV=`echo ${BOOTED_ROOT_DEV} | sed 's/^\(.*[^0-9]*\)[0-9][0-9]*$/\1/'`

if [ ${IL_LAYOUT} = FLASHRRDM -o ${IL_LAYOUT} = VSHSTD -o ${IL_LAYOUT} = VCBSTD \
     -o ${IL_LAYOUT} = VEVASTD -o ${IL_LAYOUT} = VDVASTD -o ${IL_LAYOUT} = SSGSTD \
     -o ${IL_LAYOUT} = FLASHHWRDM -o ${IL_LAYOUT} = VSH55STD ]; then 
    np_dev=`echo "${BOOTED_DEV}" | sed -e 's,/dev/,,'`
    re_dev=`/opt/hal/bin/hwtool.py -q disk=map | grep ${np_dev} | awk '{print $2}'`
    BOOTED_ROOT_DEV=`echo ${BOOTED_ROOT_DEV} | sed -e "s,${np_dev},${re_dev}p,"`
    BOOTED_DEV=`echo ${BOOTED_DEV} | sed -e "s,${np_dev},${re_dev},"`
elif [ ${IL_LAYOUT} = AWSEC2 ]; then
    BOOTED_ROOT_DEV=${IL_LO_AWSEC2_BOOTED_ROOT_DEV}
elif [ ${IL_LAYOUT} = FLASHRRDM_RAID ]; then
    MDX=`basename ${BOOTED_ROOT_DEV}`
    #
    # There can be two kinds of format from /proc/mdstat when a single device fails.
    #    format 1) md12 : active raid1 sdas2[2](F) sdat2[0]
    #    format 2) md12 : active raid1 sdat2[0]
    #
    # Note: md12 : active raid1 sdat2[0] sdas2[2](F) is considered format 2.

    # try to find format 1
    SDAX=`cat /proc/mdstat | grep -B 1 ${MDX} | awk '{print $5}' | grep \(F\) | sed -e 's/[0-9]\[[0-9]\]//g' | tr '\n' ' ' | sed -e 's/ //g'`

    if [ "x${SDAX}" != "x" ]; then
        # format 1 found, use format 1 with 6th token
	SDAX=`cat /proc/mdstat | grep -B 1 ${MDX} | awk '{print $6}' | sed -e 's/[0-9]\[[0-9]\]//g' | tr '\n' ' ' | sed -e 's/ //g'`
    else
        # format 1 cannot be found, use format 2 with 5th token
	SDAX=`cat /proc/mdstat | grep -B 1 ${MDX} | awk '{print $5}' | sed -e 's/[0-9]\[[0-9]\]//g' | tr '\n' ' ' | sed -e 's/ //g'`
    fi

    if [ "x${SDAX}" != "x" ]; then
	# SDAX is either 6th token of format 1 or 5th token of format 2, map to the name flashX
	FLASHX=`/opt/hal/bin/hwtool.py -q disk=map | grep ${SDAX} | awk '{print $2}'`
	BOOTED_DEV=/dev/${FLASHX}
    else
	# We should not be here.
	BOOTED_DEV="unknown"  
    fi
fi

echo "BOOTED_ROOT_DEV=${BOOTED_ROOT_DEV}"

# Find the PART that goes with the root dev
eval 'part_list="${IL_LO_'${IL_LAYOUT}'_PARTS}"'

curr_root_part=
for part in ${part_list}; do
    eval 'part_dev="${IL_LO_'${IL_LAYOUT}'_PART_'${part}'_DEV}"'
    if [ "x${part_dev}" = "x${BOOTED_ROOT_DEV}" ]; then
        curr_root_part=${part}
    fi
done

# See if LOC ROOT_1 or ROOT_2 is on this PART
eval 'root_1_part="${IL_LO_'${IL_LAYOUT}'_LOC_BOOT_1_PART}"'
eval 'root_2_part="${IL_LO_'${IL_LAYOUT}'_LOC_BOOT_2_PART}"'

THIS_BOOT_ID=-1
case "${curr_root_part}" in 
    ${root_1_part})
        THIS_BOOT_ID=1
        ;;
    ${root_2_part})
        THIS_BOOT_ID=2
        ;;
    *)
        ;;
esac


GRUB=/bootmgr/boot/grub/grub.conf
NEXT_BOOT_ID=-1

if [ -f ${GRUB} ]; then
    grub_default=`grep '^default=' ${GRUB} | sed 's/^.*=\([0-9]*\)[ \t]*$/\1/'`
    if [ -z "$grub_default" -o \( "$grub_default" != "0" -a "$grub_default" != "1" \) ]; then
        NEXT_BOOT_ID=-1
    else
        NEXT_BOOT_ID=`expr $grub_default + 1`
    fi

    grub_fallback=`grep '^fallback=' ${GRUB} | sed 's/^.*=\([0-9]*\)[ \t]*$/\1/'`
    if [ -z "$grub_fallback" -o \( "$grub_fallback" != "0" -a "$grub_fallback" != "1" \) ]; then
        FALLBACK_BOOT_ID=-1
    else
        #If this is an AWSEC2 layout then there is no fallback image
        #Set the fallback image to the default image itself
        if [ ${IL_LAYOUT} = AWSEC2 ]; then
            FALLBACK_BOOT_ID=$NEXT_BOOT_ID
        else
            FALLBACK_BOOT_ID=`expr $grub_fallback + 1`
        fi
    fi

fi

#
# FLASHRRDM_RAID layout does not have the line default=x in grub.conf
# The fallback can be the second, third or fourth entry in grub.conf. 
# The code below does the logical mapping for this layout.  
# 
if [ ${IL_LAYOUT} = FLASHRRDM_RAID ]; then
case "${THIS_BOOT_ID}" in 
    1)
        NEXT_BOOT_ID=1
        FALLBACK_BOOT_ID=2
        ;;
    2)
        NEXT_BOOT_ID=2
        FALLBACK_BOOT_ID=1
        ;;
    *)
        ;;
esac
fi

echo "AIG_BOOTED_DEV=${BOOTED_DEV}"
echo "AIG_THIS_BOOT_ID=${THIS_BOOT_ID}"
echo "AIG_NEXT_BOOT_ID=${NEXT_BOOT_ID}"
echo "AIG_FALLBACK_BOOT_ID=${FALLBACK_BOOT_ID}"
