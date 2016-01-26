#!/bin/sh

###############################################################################
# 560 HAL specific support.
#
#
# The 560 is a special unit since it has two disks but the not all the partitions
# are RAID. The segstore partitions is FTS so nor RAID, but VA and RSP partitions
# are RAID but probably different RAID levels
#
###############################################################################

VA_DEV="md0"
RSP_DEV="md1"

create_560_rsp_raid()
{
    /sbin/mdadm --create /dev/${RSP_DEV} --run \
        --level=raid0 --raid-devices=2 \
        /dev/disk3p7 /dev/disk4p7 > /dev/null 2>&1

    return $?
}

###############################################################################
# hal_560_raid_prep
#
# for the special raid creation for the 560 PFS
#
###############################################################################
hal_560_raid_prep()
{
    rm -f /dev/${RSP_DEV}
    mknod /dev/${RSP_DEV} b 9 1

    create_560_rsp_raid

    /sbin/mke2fs -b 4096 -R stride=8 -q -O ^resize_inode \
        -L SMB -j /dev/${RSP_DEV} > /dev/null 2>&1

    /sbin/mdadm --stop /dev/${RSP_DEV} > /dev/null 2>&1

    rm -f /dev/${VA_DEV}
    mknod /dev/${VA_DEV} b 9 0

    /sbin/mdadm --create /dev/${VA_DEV} --run \
        --level=raid0 --raid-devices=2 \
        /dev/disk3p6 /dev/disk4p6 > /dev/null 2>&1

    /sbin/mdadm --stop /dev/${VA_DEV} > /dev/null 2>&1

    touch /var/opt/rbt/.rsp_ready
}

###############################################################################
# hal_560_raid_start
#
# Run the RSP array.
#
###############################################################################
hal_560_raid_start()
{
    rm -f /dev/${RSP_DEV}
    mknod /dev/${RSP_DEV} b 9 1
    /sbin/mdadm --assemble /dev/${RSP_DEV} /dev/disk3p7 /dev/disk4p7 > /dev/null 2>&1
    /bin/mount /dev/${RSP_DEV} -o defaults,acl,noauto,user_xattr /proxy > /dev/null 2>&1
}

