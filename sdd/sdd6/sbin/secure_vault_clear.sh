#!/bin/sh

#
#  Filename:  $Source$
#  Revision:  $Revision$
#  Date:      $Date$
#  Author:    $Author$
#
#  (C) Copyright 2003-2009 Riverbed Technology, Inc.
#  All rights reserved.
#

# if "nostop" is passed as an argument, then all we need is to remove the
# SV folders
OPTION=$1

if [ x${OPTION} != "xnostop" ]; then
    /etc/init.d/pm stop
fi

umount /var/opt/rbt/decrypted
rm -rf /var/opt/rbt/encrypted /var/opt/rbt/decrypted

# on new units with the SV on flash, remove the on flash entry for it.
MOBO=`/opt/hal/bin/hwtool.py -q motherboard`
case "x${MOBO:0:9}" in
        "x400-00100"|"x400-00300"|"x400-00099"|"x400-00098")
                rm -rf /config/rbt/encrypted
        ;;
        *)
        ;;
esac

if [ x${OPTION} != "xnostop" ]; then
    reboot
fi
