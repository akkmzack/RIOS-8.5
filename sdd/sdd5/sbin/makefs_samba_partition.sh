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

mkfs.ext3 -q ${DISK_DEV}11

mount ${DISK_DEV}11 /proxy

# Add partition to /etc/fstab
FSTAB_ENTRY_EXIST=`cat /etc/fstab | tail +2 | grep proxy -c`

if [ $FSTAB_ENTRY_EXIST = 0 ]; then
    echo "${DISK_DEV}11    /proxy  ext3    defaults,acl    1 2" >> /etc/fstab
fi

exit 0
