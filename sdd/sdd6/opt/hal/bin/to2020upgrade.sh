#!/bin/bash

# reformat the disk

SFDISK=/sbin/sfdisk

$SFDISK -d /dev/sda | $SFDISK /dev/sdb > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "could not partiton second drive"
    exit 1
fi

touch / 2>/dev/null
READ_ONLY_ROOT=$?

[ $READ_ONLY_ROOT -ne 0 ] && mount / -o remount,rw


# format the PFS partition and set up the raid

#kill old smb partiton, remove line from fstab.
umount /proxy > /dev/null 2>&1
dd if=/dev/zero of=/dev/sda11 bs=1024k count=10 > /dev/null 2>&1

grep -v proxy /etc/fstab > /var/tmp/fstab.tmp
mv /var/tmp/fstab.tmp /etc/fstab

#remove various hal markers.
rm -f /var/opt/rbt/.samba_ready
rm -f /var/opt/rbt/.sdb8_ready_rerun
rm -f /var/opt/rbt/.sdb8_read #bug 
rm -f /var/opt/rbt/.sdb8_ready

#run the hal 2020 routines.

/sbin/mke2fs -O ^resize_inode -q -j /dev/sdb8 > /dev/null 2>&1

/opt/hal/bin/hal hal_2020_upgrade
if [ $? -ne 0 ]; then
    echo "could not set up second disk for raid."
    exit 1
fi

#do some additional fstab fixup
/bin/grep -v LABEL=SMB /etc/fstab > /tmp/fstab
/bin/mv -f /tmp/fstab /etc/fstab
/bin/rm -f /etc/image_layout.sh

cat > /etc/image_layout.sh <<EOF
# Automatically generated file: DO NOT EDIT!
#
IL_LAYOUT=REPLSMB
export IL_LAYOUT 
IL_KERNEL_TYPE=smp
export IL_KERNEL_TYPE
IL_LO_REPLSMB_TARGET_DISK1_DEV=/dev/sda
export IL_LO_REPLSMB_TARGET_DISK1_DEV
IL_LO_REPLSMB_TARGET_DISK2_DEV=/dev/sdb
export IL_LO_REPLSMB_TARGET_DISK2_DEV

EOF


[ $READ_ONLY_ROOT -ne 0 ] && mount / -o remount,ro

# tweak all of the mfgdb settings
MDDBREQ=/opt/tms/bin/mddbreq
DB_PATH=/config/mfg/mfdb

$MDDBREQ -c $DB_PATH set modify "" /rbt/mfd/model string "2020"

$MDDBREQ -c $DB_PATH set modify "" /rbt/mfd/store/dual bool "true"
$MDDBREQ -c $DB_PATH set modify "" /rbt/mfd/store/dev string "/dev/md0"
$MDDBREQ -c $DB_PATH set modify "" /rbt/mfd/store/mdraid1 string "/dev/sda10"
$MDDBREQ -c $DB_PATH set modify "" /rbt/mfd/store/mdraid2 string "/dev/sdb10"
$MDDBREQ -c $DB_PATH set modify "" /rbt/mfd/smb/dev string "/dev/md1"
$MDDBREQ -c $DB_PATH set modify "" /rbt/mfd/smb/size uint32 "215041"
$MDDBREQ -c $DB_PATH set modify "" /rbt/mfd/smb/mdraid1 string "/dev/sda11"
$MDDBREQ -c $DB_PATH set modify "" /rbt/mfd/smb/mdraid2 string "/dev/sdb11"

#clear the segstore.
dd if=/dev/zero of=/dev/sda10 bs=1024k count=10 > /dev/null 2>&1
dd if=/dev/zero of=/dev/sdb10 bs=1024k count=10 > /dev/null 2>&1


