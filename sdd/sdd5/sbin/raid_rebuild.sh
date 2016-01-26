#! /bin/sh

# This script is invoked by mdadm --monitor -f daemon that monitors
# all the raid arrays for any events. If the event is RebuildFinished
# send a SIGHUP to hald.

LOG_INFO="/usr/bin/logger -p user.info -t raid_rebuild"

PID=`pidof rbt_hald`
EVENT=$1 # The event that happned
ARRAY=$2 # The array on which the event happened.
if [ "$PID" != "" -a "$EVENT" = "RebuildFinished" ]; then
        # send sighup to hald
        ${LOG_INFO} "Sending sighup to hald[$PID] for event $EVENT for $ARRAY"
        kill -s HUP $PID
fi

# Update the LED status and check for raid consistency
/opt/hal/bin/raid/rrdm_tool.py --check-raid-consistency

