#!/bin/sh

DD=/bin/dd
CKSUM=/usr/bin/cksum
CUT=/usr/bin/cut
EXPR=/usr/bin/expr
SED=/bin/sed

RANDOM_NUMBER_1=`$DD if=/dev/urandom count=1 bs=4 2> /dev/null | $CKSUM | $CUT -f1 -d" "`
RANDOM_NUMBER_2=`$DD if=/dev/urandom count=1 bs=4 2> /dev/null | $CKSUM | $CUT -f1 -d" "`
RANDOM_NUMBER_3=`$DD if=/dev/urandom count=1 bs=4 2> /dev/null | $CKSUM | $CUT -f1 -d" "`

# calculate the day of the week to use [0-6]
DAY=`$EXPR $RANDOM_NUMBER_1 % 7`
if [ "x$DAY" = "x" ]; then
  DAY=0
fi

# calculate the hour to use [0-6]
HOUR=`$EXPR $RANDOM_NUMBER_2 % 6`
if [ "x$HOUR" = "x" ]; then
  HOUR=0
fi

# calculate the minute to use [0-59]
MINUTE=`$EXPR $RANDOM_NUMBER_3 % 60`
if [ "x$MINUTE" = "x" ]; then
  MINUTE=0
fi

# Only run uptime_checkup.sh days that a 
# regular uptime_ping.sh is not scheduled.
CHECKUP_DAYS=`echo "0,1,2,3,4,5,6" | $SED "s/\($DAY,\)\|\(,$DAY\)//"`

# Generate TWO cron lines with one shot.
PING_LINE="$MINUTE $HOUR * * $DAY root /sbin/uptime_ping.sh > /dev/null 2>&1"
CHECKUP_LINE="$MINUTE $HOUR * * $CHECKUP_DAYS root /sbin/uptime_checkup.sh > /dev/null 2>&1"
echo -e "${PING_LINE}\n${CHECKUP_LINE}"
