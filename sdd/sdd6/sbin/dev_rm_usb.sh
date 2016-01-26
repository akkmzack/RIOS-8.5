#!/bin/sh
#
# (C) Copyright 2003-2005 Riverbed Technology, Inc.
# $Id: dev_rm_usb.sh 4424 2004-10-29 00:58:30Z jcho $
# Script to remove a device from the system.  Utilized in hidden cli command "sport usb mount".

echo "scsi remove-single-device $1 0 0 0" > /proc/scsi/scsi
