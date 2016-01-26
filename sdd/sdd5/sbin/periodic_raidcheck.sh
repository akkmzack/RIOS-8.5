#!/bin/sh
# shell script for periodic raidcheck
# keeps the same info in /tmp/periodic_raidcheck

TMPFS_FILE=/tmp/periodic_raidcheck
MISSING_DISK=-1
LOCK=/tmp/periodic_raidcheck_lock

LOG_WARN="/usr/bin/logger -p user.warn -t periodic_raidcheck"
LOG_INFO="/usr/bin/logger -p user.info -t periodic_raidcheck"

cleanup()
{
	flock -u 8	    # Unlock
	rm -rf $LOCK        # Remove lock file
	rm -rf $TMPFS_FILE  # Remove state file

	# Now regenerate the state file
	
	# Open FD 8 to the lock file
	exec 8>> $LOCK
	# wait until you grab lock
	flock -x 8
	echo "Idle" > $LOCK
	check_if_first_time # This function exits and when it does, the flock is automatically released.
}

compare()
{
        # Now re-read the output of hwtool -q disk=map and compare
        # it with the output stored in TMPFS_FILE
	PGREP=$( pgrep hwtool.py )
        if [ -n "$PGREP" ]; then
                ${LOG_WARN} "Another instance of hwtool running. Sleeping for one second"
                sleep 1
        fi
	for i in 1 2 3; do
		NEW_DISK_MAP=`/opt/hal/bin/hwtool.py -q disk=map | grep disk | tr ' ' ','`
		if [ -z "$NEW_DISK_MAP" ]; then
			${LOG_INFO} "disk map empty, sleeping for 1 second"
                        /sbin/udevadm settle --timeout=1
                        sleep 1
                else
                        break
                fi
	done
        if [ -z "$NEW_DISK_MAP" ]; then
		${LOG_WARN} "disk map still empty. Returning from compare function"
                return
        fi
	if [ -f $TMPFS_FILE ]; then
        	OLD_DISK_MAP=`cat $TMPFS_FILE`
	else
		${LOG_WARN} "cache file $TMPFS_FILE is empty or absent"
		return # if for some weird reason we are here; return
	fi
        local array1=($NEW_DISK_MAP)
        local array2=($OLD_DISK_MAP)

        #delete the old file
        echo -n "" > $TMPFS_FILE

        count=${#array1[@]}
        for i in `seq 1 $count` ; do
                local NEW_STATUS=`echo ${array1[$i-1]} | cut -d ',' -f4`
                local OLD_STATUS=`echo ${array2[$i-1]} | cut -d ',' -f4`

                local NEW_BUS_NUM=`echo ${array1[$i-1]} | cut -d ',' -f1`
                local OLD_BUS_NUM=`echo ${array2[$i-1]} | cut -d ',' -f1`

                local NEW_UNIQ_ID=`cat /sys/bus/scsi/devices/$NEW_BUS_NUM/uniq_id`
                local OLD_UNIQ_ID=`echo ${array2[$i-1]} | cut -d ',' -f5`

		local NEW_DISK_NUM=`echo ${array1[$i-1]} | cut -d ',' -f2` 
		local OLD_DISK_NUM=`echo ${array2[$i-1]} | cut -d ',' -f2` 
		local NEW_DISK_NAME=`echo ${array1[$i-1]} | cut -d ',' -f3`

                if [ -e /sys/bus/scsi/devices/$NEW_BUS_NUM ]; then
                        if [ "${NEW_BUS_NUM}" != "${OLD_BUS_NUM}" ]; then
                                # disk was added
                                /sbin/sw_raidcheck.py add $NEW_BUS_NUM
                        else
                                # On barramundis, the bus number stays the same after pulling out
                                # and putting a disk back in. Check the uniq_id in this case
                                if [ "${NEW_UNIQ_ID}" != "${OLD_UNIQ_ID}" ]; then
                                        # disk was added to a barramundi
                                        /sbin/sw_raidcheck.py add $NEW_BUS_NUM
                                fi
                        fi
                else
                        if [ "${NEW_STATUS}" == "missing" -a "${OLD_STATUS}" == "online" ]; then
                                #disk was removed
                                /sbin/sw_raidcheck.py remove $NEW_DISK_NUM
                        fi
                fi

                # Update the tmpfs file
                if [ -e /sys/bus/scsi/devices/$NEW_BUS_NUM ]; then
                        echo ${array1[$i-1]},$NEW_UNIQ_ID >> $TMPFS_FILE
                else
                        echo $OLD_BUS_NUM,$OLD_DISK_NUM,$NEW_DISK_NAME,$NEW_STATUS,$OLD_UNIQ_ID >> $TMPFS_FILE
                fi
        done
}

check_if_first_time()
{
	if [ ! -f $TMPFS_FILE ]; then
        	# read the disk list from hwtool and store it there
		${LOG_INFO} "State info file not present in /tmp; creating it"
		for i in 1 2 3; do
                    DISK_MAP=`/opt/hal/bin/hwtool.py -q disk=map | grep disk | tr ' ' ','`
                    if [ -z "$DISK_MAP" ]; then
			    ${LOG_INFO} "disk map empty, sleeping for 1 second"
			    /sbin/udevadm settle --timeout=1
                            sleep 1
                    else
                            break
                    fi
                done
		if [ -z "$DISK_MAP" ]; then
			${LOG_WARN} "disk map still empty. Exiting..."
			echo -n "" > $LOCK	
			exit
		fi
        	for DISK in $DISK_MAP; do
                	# Parse disk_map output and store it in /tmp/periodic_raidcheck
	                BUS_NUM=`echo $DISK | cut -d ',' -f1`
        	        if [ -f /sys/bus/scsi/devices/$BUS_NUM/uniq_id ]; then
                	        UNIQ_ID=`cat /sys/bus/scsi/devices/$BUS_NUM/uniq_id`
                        	echo $DISK,$UNIQ_ID >> $TMPFS_FILE
	                else
        	                echo $DISK,$MISSING_DISK >> $TMPFS_FILE
                	fi
	        done
        	# This is the first time; we have no older data to compare to.
	        # In the next iteration we have TMPFS_FILE to compare to.
        	exit
	fi
}

# Script starts here

# Set signal handlers. Upon receiving any of these signals, delete tmpfs and lock files
trap cleanup SIGINT SIGTERM

# Open FD 8 to the lock file
exec 8>> $LOCK

# wait until you grab lock
flock -x 8

# Got lock; not read the lock file and traverse the state machine
STATUS=`cat $LOCK`
case "$STATUS" in
	"Idle")
		# Idle state
		${LOG_INFO} "Initial state: Idle"
		echo "Running" > $LOCK
		STATUS="Running"
		;;
	"Running")
		# Running state
		${LOG_INFO} "Initial state: Running"
		echo "Rescan" > $LOCK
		STATUS="Rescan"
		;;
	"Rescan")
		# Rescan state
		${LOG_INFO} "Initial state: Rescan"
		# NOP
		;;
	*)
		# Unknown/Empty state
		if [ "${STATUS}" = "" ]; then
			${LOG_INFO} "Initial state: Empty"
	                # Write idle to lock file
        	        echo "Idle" > $LOCK
                	STATUS="Idle"
			check_if_first_time
		fi
		exit 0
		;;
esac

# Unlock
flock -u 8

if [ "${STATUS}" = "Running" ]; then
	# Check if any disk was added/removed
	compare
	# Check if another instance was invoked; if so, run again before dying
	while [ true ]; do
		# Grab lock again
	        flock -x 8
	
        	STATUS=`cat $LOCK`
	        ${LOG_INFO} "In state: $STATUS. Checking to run again."
        	case "$STATUS" in
                	"Running")
                        	# Go back to Idle state
	                        echo "Idle" > $LOCK
        	                STATUS="Idle"
                	        ${LOG_INFO} "was in state Running. Now in state: $STATUS"
				# Unlock
		                flock -u 8
				break # Nothing more to check, exit loop
                        	;;
	                "Rescan")
        	                # Go back to Running state
                	        echo "Running" > $LOCK
                        	STATUS="Running"
	                        ${LOG_INFO} "Another instance of this script was invoked. Now in state: $STATUS"
        	                # Unlock
                	        flock -u 8
                        	# Check if any disk was added/removed
	                        compare
	                       	;;
        	        *)
                	        # Came here in error; exit
                        	${LOG_WARN} "Error: cannot be in state $STATUS while checking to run again. Exiting..."
	                        cleanup # this exits after cleaning-up   
        	                ;;
	        esac
	done
else
	# exit
	exit 1
fi


