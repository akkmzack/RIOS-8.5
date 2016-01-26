#!/bin/sh

# find hwtool since we need the motherboard string.
#
HWTOOL="/opt/hal/bin/hwtool.py"
CFG_XML_PATH="/opt/tms/lib/hwtool/config/config.xml"
BUS="$1"
KNUM="$2"

if [ "x${BUS}" = "x" ]; then
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

DLINE=`${HWTOOL} -c ${CFG_XML_PATH} -q disk=map | grep "${BUS}"`
if [ $? -eq 0 ]; then
        ROOTDEV=`echo "${DLINE}" | awk '{print $2}'`

	# do not call it an sd disk if it's shadowed...
	BDEV=`echo "${DLINE}" | awk '{print $3}'`
	[ -d /sys/block/${BDEV}/shadow ] && exit 1

	if [ "x${KNUM}" != "x" ]; then
		echo "${ROOTDEV}p${KNUM}"
	else
		echo "${ROOTDEV}"
	fi
	exit 0
else
	exit 1
fi

exit 1
