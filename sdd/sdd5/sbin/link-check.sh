#!/bin/sh
#
# link-check.sh
# $Id: link-check.sh 4424 2004-10-29 00:58:30Z jcho $
#
# (C) Copyright 2003-2005 Riverbed Technology
#
# This shell script checks the link status of a port.
#
# Requires:
#   /bin/sed
#   /sbin/mii-tool
#

MIITOOL=/sbin/mii-tool

if [ x$1 = x ]; then
    echo "You must specify an interface to test."
    exit 1
else
    DEV=$1
fi

check_device() {
    FAILURE=0
    RESULT=`$MIITOOL $1` || FAILURE=1
    if [ ${FAILURE} -eq 1 ]; then
        echo "Device not found."
        exit 1
    fi
    RESULT=`echo $RESULT | /bin/sed -e "s,.*: ,,"`
    if [ "$RESULT" = "no link" ]; then
        echo "$1 is down."
        exit 1
    fi

    echo "$1 is up."
}


check_device $DEV
exit 0
