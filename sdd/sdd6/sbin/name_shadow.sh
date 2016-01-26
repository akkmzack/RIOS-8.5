#!/bin/sh

# find hwtool since we need the motherboard string.
#
HWTOOL="/opt/hal/bin/hwtool.py"
CFG_XML_PATH="/opt/tms/lib/hwtool/config/config.xml"
NAME="$1"

if [ "x${NAME}" = "x" ]; then
	exit 1
fi

if [ ! -f ${HWTOOL} ]; then
	HWTOOL="/sbin/hwtool.py"
	if [ ! -f ${HWTOOL} ]; then
		return 1
	fi
fi

if [ ! -f ${CFG_XML_PATH} ]; then
        CFG_XML_PATH="/etc/config.xml"
fi

#
# really a shadow device?
#
npn=`echo ${NAME} | sed 's/[0-9]*$//'`
[ -z "${npn}" ] && exit 1
[ ! -d /sys/block/${npn}/shadow ] && exit 1

lknm=`${HWTOOL} -c ${CFG_XML_PATH} -q disk=map | while read bus disk dev st; do
	[ "$dev" = "$npn" ] && echo $disk && break
done`

[ -z "$lknm" ] && exit 1

part=`echo $NAME | sed 's/^sh[a-z]//1'`
if [ -n "${part}" ]; then
	echo ${lknm}p${part}
else
	echo $lknm
fi

exit 0
