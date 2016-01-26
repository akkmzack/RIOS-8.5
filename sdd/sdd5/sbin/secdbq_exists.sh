#!/bin/sh

if [ "x`/sbin/secure_vault_check_mount.sh`" != "xtrue" ]
then
    echo false
    exit 0
fi

Q="`/opt/tms/bin/mddbreq -v $*`"
if [ "x$Q" = "x" ]
then
    echo false
else
    echo true
fi
