#!/bin/sh
source /etc/build_version.sh

# bug 98927 - make sure that any python stuff that happens to run doctests
# doesn't spit out escape sequences to the tty
TERM=dumb
export TERM

FQDN=`/usr/bin/python /sbin/heartbeat_status.py --dnsversion=1 --fqdn /opt/rbt/etc/heartbeat.xml`
if [ "x$FQDN" = "x" ]; then
    echo "no output from heartbeat encoder. bailing"
    exit 1
fi
if [ "x$1" = "x-n" ] ; then
    echo $FQDN
else
    nslookup $FQDN
fi

exit 0

