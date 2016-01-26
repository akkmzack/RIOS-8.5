#!/bin/bash
#
# Filename:  $Source$
# Revision:  $Revision: 41027 $
# Date:      $Date: 2008-11-21 13:01:51 -0800 (Fri, 21 Nov 2008) $
# Author:    $Author: admytrenko $
#
# (C) Copyright 2008 Riverbed Technology, Inc.
# All rights reserved.
#
# This tool generates guest state hash. It can be executed in interactive mode
# by starting it without parameters. Non interactive mode takes password and
# guest OS root directory as its parameters:
# ./guest_hash [password] [guest root directory]

ROOT=
INTERACTIVE=TRUE

if [ $# -eq 2 ]; then
    PASSWORD="$1"
    ROOT="$2"
    INTERACTIVE=FALSE
else
    echo
    echo "WARNING:"
    echo "WARNING: Riverbed Internal Use Only - do not distribute this tool"
    echo "WARNING:"
    echo

    echo -n "Enter RSP2 Print License Password Code: "
    read PASSWORD
fi

CONTROL=(/etc/rc.d /etc/inittab /etc/rc0.d /etc/rc1.d /etc/rc2.d /etc/rc3.d \
/etc/rc4.d /etc/rc5.d /etc/rc6.d /etc/rcS.d /etc/init.d /etc/event.d \
/etc/rc.local /etc/rc.sysinit)

VM_HASH=`(
echo ${PASSWORD}
while read FILE; do
    echo "${FILE}"
    if [ -z "${ROOT}" ]; then
        cat "${FILE}"
    else
        chroot "${ROOT}" cat "${FILE}"
    fi
done < <(
for DIR in ${CONTROL[@]}; do
    if [ -e "${ROOT}${DIR}" ]; then
        if [ -z "${ROOT}" ]; then
            find "${DIR}" -xtype f
        else
            chroot "${ROOT}" find "${DIR}" -xtype f
        fi
    fi
done
)
) | sha1sum | awk '{print $1}'`

if [ ${INTERACTIVE} == TRUE ]; then
    echo -n "Virtual Machine State Hash: "
fi

echo ${VM_HASH}

