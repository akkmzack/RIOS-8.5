#!/bin/sh

# Print alarm status of alarmed named by $1.
#
# See heartbeat.xml for where this is used.
#
# The output of this script should be:
#   ""  - if there was an error accessing the alarm information.
#   true - if the alarm has been triggered in the last week.
#   false  - otherwise (i.e. false if it did not happen, or unknown)

DAY=$(( 60 * 60 * 24 ))

TIME_PERIOD=0
case $3 in
(day)   TIME_PERIOD=$DAY;;
(week)  TIME_PERIOD=$((  7 * $DAY ));;
(month) TIME_PERIOD=$(( 30 * $DAY ));;
(*) echo "Third arg should be the time period (day|week|month)."; exit 1;;
esac

BEGINING_OF_TIME_PERIOD=$(( `date +%s`-$TIME_PERIOD ))
EVENT_DATE_STR="`/opt/tms/bin/mdreq -v query get - /alarm/state/alarm/$1/last_$2_time`"
if [ $? -ne 0 ] && [ ! $EVENT_DATE_STR ]; then 
    exit 1
fi

EVENT_TIME=$(/bin/date --date="$EVENT_DATE_STR" +%s)

# UPTIME=$(( (`uptime | sed -r 's/^.*up (([0-9]+) days)?.*$/\2/'` + 0) * $DAY ))
if [ ! "$EVENT_DATE_STR" ]; then
    echo false
    exit
fi

if [[ "$(( $BEGINING_OF_TIME_PERIOD - $EVENT_TIME ))" -lt 0 ]]; then
    # happened in the $TIME_PERIOD
    echo true
else
    echo false
fi
