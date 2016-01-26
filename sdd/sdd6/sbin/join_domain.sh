#!/bin/sh

#
# (C) Copyright 2003-2005 Riverbed Technology, Inc.
# $Id: join_domain.sh 6881 2005-08-05 20:24:33Z jcho $
# samba domain join script

if [ x$4 = x ]; then
    echo "usage: $0 <admin_login> <admin_passwd> <test> <debug>"
    exit 1
fi

admin_login=$1
admin_passwd=$2
testjoin=$3
debug=$4

if [ "x$3" = "xtrue" ]; then
    # test join
    /usr/bin/net ads testjoin -U${admin_login}%${admin_passwd}
    if [ "$?" != "0" ]; then
        exit 1
    fi
elif [ "x$4" = "xtrue" ]; then
    # debug join
    /usr/bin/net ads join -U${admin_login}%${admin_passwd} -d 10 > /var/opt/rcu/net_ads.out 2>&1
    if [ "$?" != "0" ]; then
        exit 1
    fi
else
    # join
    net ads leave -U${admin_login}%${admin_passwd}
    /usr/bin/net ads join -U${admin_login}%${admin_passwd}
    if [ "$?" != "0" ]; then
        exit 1
    fi
fi

exit 0
