#!/bin/sh

# Script runs during the generation of a heartbeat
# Takes one argument, either "day", "week", or "month"
# returns the number of RiOS failures causing reboots
# that occured during that time range.
# Truncates the file to entries less than 30 days old. 


LAST_FAILURE_LOG=/var/opt/rbt/.unscheduled_reboots

TIMEFRAME=$1 # either "month", "week", or "day"

NOW_TIMESTAMP=`date +%s` # timestamp for now

MONTH_TIMESTAMP=$((NOW_TIMESTAMP-2592000)) # timestamp for 30 days ago
WEEK_TIMESTAMP=$((NOW_TIMESTAMP-604800)) # timestamp for 7 days ago
DAY_TIMESTAMP=$((NOW_TIMESTAMP-86400)) # timestamp for 24 hours ago

count_dirty_boots()
{
    CUTOFF_TIMESTAMP=$1
    NUM_DIRTY_BOOTS=0 # "Dirty boots are on - hi dee ho"
    for timestamp in $(cat ${LAST_FAILURE_LOG}) ; do
        if [ "x${timestamp}" != "x" ]; then
            if [ ${timestamp} -gt ${CUTOFF_TIMESTAMP} ]; then
                NUM_DIRTY_BOOTS=$((NUM_DIRTY_BOOTS+1))
            fi
        fi
    done
    echo  ${NUM_DIRTY_BOOTS}
}

# only check for dirty boots if the log file exists
if [ -f ${LAST_FAILURE_LOG} ]; then
    if [ "x${TIMEFRAME}" = "xmonth" ]; then
        count_dirty_boots ${MONTH_TIMESTAMP}  
    elif [ "x${TIMEFRAME}" = "xweek" ]; then
        count_dirty_boots ${WEEK_TIMESTAMP}
    elif [ "x${TIMEFRAME}" = "xday" ]; then
        count_dirty_boots ${DAY_TIMESTAMP}
    else
        # return a zero count for a nonstandard query
        echo "0"
    fi
else
    # no dirty boot count, return a zero count
    echo "0"
fi 

