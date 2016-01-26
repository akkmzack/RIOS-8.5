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

if [ x$1 = x ]; then
    echo "usage: $0 sizeof-sport-partition-MB"
    exit 1
fi

DISK_DEV=`/opt/tms/bin/mddbreq -v $MFDB query get "" /rbt/mfd/diskdev`

# Delete old sport partition
echo -e "d\n10\n" > create_partitions.cfg
                                                                                
# Create new sport partition
echo -e "n\n\n${1}\n" >> create_partitions.cfg
                                                                                
# Create new samba partition
echo -e "n\n\n\n" >> create_partitions.cfg
                                                                                
# Set sport partition id
echo -e "t\n10\nda\nw\n" >> create_partitions.cfg
                                                                                
fdisk ${DISK_DEV} < create_partitions.cfg

exit 0
