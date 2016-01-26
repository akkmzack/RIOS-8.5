#!/bin/sh

#
#  Filename:  $Source$
#  Revision:  $Revision: 5691 $
#  Date:      $Date: 2005-02-24 17:32:58 -0800 (Thu, 24 Feb 2005) $
#  Author:    $Author: jcho $
#
#  (C) Copyright 2003-2005 Riverbed Technology, Inc.
#  All rights reserved.
#

MFDB=/config/mfg/mfdb

DISK_DEV=`/opt/tms/bin/mddbreq -v $MFDB query get "" /rbt/mfd/diskdev`
                                                                                
SAMBA_PARTITION_EXIST=`sfdisk -l ${DISK_DEV} | grep -c ${DISK_DEV}11`
                                                                                
# Delete old sport partition
echo -e "d\n10\n" > create_partitions.cfg
                                                                                
if [ $SAMBA_PARTITION_EXIST = 1 ]; then
        echo -e "d\n10\n" >> create_partitions.cfg
fi

# Create new sport partition
echo -e "n\n\n\n" >> create_partitions.cfg

# Set sport partition id
echo -e "t\n10\nda\nw\n" >> create_partitions.cfg

fdisk ${DISK_DEV} < create_partitions.cfg

# Remove partition from /etc/fstab
FSTAB_ENTRY_EXIST=`cat /etc/fstab | tail -1 | grep proxy -c`

if [ $FSTAB_ENTRY_EXIST = 1 ]; then
    tac /etc/fstab | tail +2 | tac > /etc/fstab.samba
fi

mv -f /etc/fstab.samba /etc/fstab

exit 0
