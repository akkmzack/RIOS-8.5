#!/bin/bash

CAT=/bin/cat
# Wellness check for Steelheads
# goes through items and if a problem is found
# reports back with a heartbeat.

# If run with an argument "trigger" then
# return the item that triggered the heartbeat
ARGUMENT=$1
if [ "x${ARGUMENT}" = "xtrigger" ]; then
    REASON=""
    if [ -e /var/opt/rbt/.heartbeat_trigger.tmp ]; then
        REASON=`${CAT} /var/opt/rbt/.heartbeat_trigger.tmp | head -n 1`
        rm -f /var/opt/rbt/.heartbeat_trigger.tmp
    fi
    if [ "x${REASON}" != "x" ]; then
        echo ${REASON}
    else
        echo "none"
    fi
    exit 0
fi

# otherwise continue along...
HEARTBEAT_REASON="" # the reason, if any, for a forced heartbeat

function check_ce_counts
{
    # first log any new ce_errors
    /sbin/count_ce_errors.py -r
    # then check for errors from the last 24 hours
    TODAYS_ERRORS=`/usr/bin/python /sbin/count_ce_errors.py -d`
    if [  ${TODAYS_ERRORS} -gt 0 ]; then
        HEARTBEAT_REASON="ce_error"
    fi     
}

#run through the list of items to check

####
#### BEGIN CHECK LIST
####
check_ce_counts
####
#### END CHECK LIST
####

# We're at the end. Is there a reason?
if [  "x${HEARTBEAT_REASON}" != "x" ]; then
    echo ${HEARTBEAT_REASON} > /var/opt/rbt/.heartbeat_trigger.tmp
    /sbin/uptime_ping.sh
fi
