#!/bin/sh

if [ x$1 = x ]; then
    echo "usage: $0 <account>"
    exit 1
fi

account=$1

ulimit -l 31457280

if [ $account = "rcud" ]; then
    echo -e "\n\n" > /var/tmp/tmp_pd
    /usr/bin/smbpasswd -a -L -s rcud < /var/tmp/tmp_pd
    if [ "$?" != "0" ]; then
        exit $?
    fi
elif [ $account = "administrator" ]; then
    /usr/bin/smbpasswd -a -L -s administrator < /var/tmp/tmp_pd 
    if [ "$?" != "0" ]; then
        exit $?
    fi
fi

exit 0
