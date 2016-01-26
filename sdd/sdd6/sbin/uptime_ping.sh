#!/bin/sh

# Al Smith <ajs@riverbed.com> - October 21 2008
# (c) Riverbed Technology Inc.

source /etc/build_version.sh

PATH=/usr/bin:/bin:/sbin
VERSION="$BUILD_PROD_RELEASE"
MODEL=`/opt/tms/bin/mddbreq -v /config/mfg/mfdb query get - /rbt/mfd/flex/model`
if [ "x${MODEL}" = "x" ]
then
    MODEL=`/opt/tms/bin/mddbreq -v /config/mfg/mfdb query get - /rbt/mfd/model`
fi
SERIAL=`/opt/tms/bin/mddbreq -v /config/mfg/mfdb query get "" /rbt/mfd/serialnum`
if [ "x${SERIAL}" = "x0" -o "x${SERIAL}" = "xNA" -o "x${SERIAL}" = "xV70KY00000000" ]
then
    SERIAL=`/opt/tms/bin/mdreq -v query get - /rbt/manufacture/serialnum`
fi

UPTIME=`cut -f1 -d. /proc/uptime`
SERVICE="$BUILD_PROD_UPTIME_BINARY"

SERVICEPID=`pidof $SERVICE`
if [ "x$SERVICEPID" = "x" ]
then
	SERVICEUP=0
else
	SERVICEUP=`cut -f22 -d\  /proc/$SERVICEPID/stat`/100
	SERVICEUP=`echo $SERVICEUP | bc`
fi


PROD_ID=${BUILD_PROD_ID}
if [ "`/opt/hal/bin/hal get_motherboard`" == "VM" ]
then
    PROD_ID=V${PROD_ID}
fi
case "${PROD_ID}" in
"SH")   HBPROD=SHA ;;
"EX")   HBPROD=EX ;;
"IB")   HBPROD=IB ;;
"GW")   HBPROD=SMC ;; 
"VGW")  HBPROD=SVE ;; 
"CMC")  HBPROD=CMC ;; 
"VCMC") HBPROD=CVE ;; 
*)      HBPROD='' ;;
esac

if [ "x${HBPROD}" != "x" ]
then
    STATUS=`/usr/bin/python /sbin/heartbeat_status.py --product=${HBPROD} \
            /opt/rbt/etc/heartbeat.xml`
else
    STATUS=0
fi

HEARTBEAT="$SERIAL.$MODEL.$UPTIME.$SERVICEUP.$STATUS.$VERSION"
if [ $# > 0 ] && [ $1 == '-n' ]
then
    # test this from the commandline by giving a -n argument
    echo ${HEARTBEAT}
else
    # quietly send this out as a dns request.
    nslookup ${HEARTBEAT}.updates.riverbed.com > /dev/null 2> /dev/null
fi

exit 0
