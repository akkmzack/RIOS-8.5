#!/bin/sh

#
#  URL:       $URL$
#  Revision:  $Revision$
#  Date:      $Date$
#  Author:    $Author$
#
#  (C) Copyright 2003-2012 Riverbed Technology, Inc.
#  All rights reserved.
#

usage()
{
    echo "usage: $0 TARGET_DEVICE ALIGNMENT_SIZE"
    echo ""
    echo "Takes a target device and the alignment size in sectors and " \
         "aligns the partitions of the device along that boundary."
    exit 1
}

if [ $# != 2 ]; then
    usage
fi

target_device=$1
align_size=$2

if [ ! -b "$target_device" ]; then
    echo "$target_device is not a valid block device."
    usage
fi

# mapped_target=`realpath ${target_device}`

device_partitions=`sfdisk -l -uS "${target_device}" | grep "${target_device}" \
    | grep -v "Disk"`

IFS=$'\n'

partition_count=0
for partition_line in $device_partitions; do
    # This is kind of hacky. There may be a better way to get the partition num
    partition_count=`expr ${partition_count} + 1`

    partition=`echo -e "${partition_line}" | awk -F ' ' '{print $1}'`

    part_start=`echo -e "${partition_line}" | awk -F ' ' '{print $2}'`
    part_type=`echo -e "${partition_line}" | awk -F ' ' '{print $5}'`

    # if the disk is bootable, theres an extra column
    if [ "${part_start}" = "*" ]; then
        part_start=`echo -e "${partition_line}" | awk -F ' ' '{print $3}'`
        part_type=`echo -e "${partition_line}" | awk -F ' ' '{print $6}'`
    fi

    # skip the extended partition
    if [ "${part_type}" = "f" ]; then
        continue
    fi

    align_remainder=`expr ${part_start} % ${align_size}`
    if [ $align_remainder -eq 0 ]; then
        continue
    fi

    align_start=`expr \( \( ${part_start} / ${align_size} \) \* \
        ${align_size} \) + ${align_size}`

    echo -e "x\n b\n ${partition_count}\n ${align_start}\n y\n w\n" | \
        fdisk "${target_device}"
done
