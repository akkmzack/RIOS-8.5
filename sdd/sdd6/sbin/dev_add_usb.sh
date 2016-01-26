#!/bin/sh
#
# (C) Copyright 2003-2005 Riverbed Technology, Inc.
# $Id: dev_add_usb.sh 4424 2004-10-29 00:58:30Z jcho $
# Script to provide a hint to the SCSI system to pick up the device.  Utilized in hidden cli command "sport usb mount".



echo "scsi add-single-device $1 0 0 0" > /proc/scsi/scsi
