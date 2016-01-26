#!/bin/sh
#
# (C) Copyright 2003-2005 Riverbed Technology, Inc.
# $Id: mount_usb.sh 13402 2006-06-27 17:33:53Z phamson $
# Script to mount a device.  Utilized in hidden cli command "sport usb mount".

if [ -b $1 ]; then
    /bin/mount $1 /mnt
else
    echo "Usb block device node $1 does not exist"
fi
