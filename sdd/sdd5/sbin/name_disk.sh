#!/bin/sh

# find hwtool since we need the motherboard string.
#
HWTOOL="/opt/hal/bin/hwtool.py"
CFG_XML_PATH="/opt/tms/lib/hwtool/config/config.xml"
BUS_OR_DEVNAME="$1"
KNUM="$2"

# On 2.6.9 the %k parameter in the udev rule gives the PCI bus ID,
# while on 2.6.32 it gives the device name (e.g. sdg3) with the
# partition number (if any). It's expedient to strip the partition
# here, though perhaps we could do something simpler overall.
case $BUS_OR_DEVNAME in
    sd*)
	BUS_OR_DEVNAME=`echo $BUS_OR_DEVNAME | sed -e 's/[0-9]//g'`
	;;
esac

# hwtool may blow up in site intitialization if we do not have $HOME
export HOME=${HOME:-"/"}

if [ "x${BUS_OR_DEVNAME}" = "x" ]; then
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

# The " " after ${BUS_OR_DEVNAME} is needed for 2.6.32 systems with
# more than 26 disks so that grep for "sda" doesn't match "sdaa",
# "sdab", etc...
DLINE=`${HWTOOL} -c ${CFG_XML_PATH} -q disk=map | grep "${BUS_OR_DEVNAME} "`
retval=$?

# Workaround/hack for bug 97056
# Sometimes hwtool doesn't know about the dev on the first try.  This is
# probably some sort of hwtool-hwtool or udev-hwtool race.  Until that
# gets sorted out, if the hwtool query fails, try again a few times.
for i in 1 2 3 4 5; do
	[ $retval -eq 0 ] && break
	sleep 1
	DLINE=`${HWTOOL} -c ${CFG_XML_PATH} -q disk=map | grep "${BUS_OR_DEVNAME} "`
	retval=$?
done

if [ $retval -eq 0 ]; then
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
