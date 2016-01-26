#!/bin/bash

LOG_ERR="/usr/bin/logger -p user.err -t raid"

model=`/opt/tms/bin/mddbreq -v /config/mfg/mfdb query get - /rbt/mfd/model`
# We will need model to get the disk count for the models 
mobo=`/opt/hal/bin/hwtool.py -q motherboard`
case "${model}" in
    "250"|"550"|"1050"|"2050"|"5050"|"6050"|"0501"|"0601")
        model=`/opt/tms/bin/mddbreq -v /config/mfg/mfdb query get - /rbt/mfd/flex/model`
        ;;
    *)
        ;;
esac

# Run on all 3U models with LSI cards
case "${mobo:0:9}" in
    "CMP-00013"|"CMP-00072"|"CMP-00109"|"400-00100"|"400-00300")
        # Just exit the script on a 6120 1050L/M as they are not handled here
        case "${model}" in
            "1050L"|"1050M"|"6120")
            exit 0;
            ;;
        *)
            ;;
        esac
        ;;
    *)
        exit 0;
        ;;
esac

print_to_log() {

    while [ 1 ]; do 
	read line
	if [ "x$line" = "xSENTINEL" ]; then
	    break
	fi
	
	${LOG_ERR} "$line"
	
    done

}

save_log_snapshot() {
    failed_disks=$1
    ${LOG_ERR} "RAID is in a degraded state, capturing errors."

    DATE_STR=`date '+%Y-%m-%d %H:%M:%S'`
    DATE_STR_FILE=`echo ${DATE_STR} | sed 's/-//g' | sed 's/://g' | sed 's/ /-/g'`
    OUTPUT_PREFIX=raidcheck-`uname -n`-${DATE_STR_FILE}
    FINAL_DIR=/var/opt/tms/snapshots/
    WORK_DIR=/var/tmp/${OUTPUT_PREFIX}-$$
    STAGE_DIR_REL=${OUTPUT_PREFIX}-${failed_disks}
    STAGE_DIR=${WORK_DIR}/${STAGE_DIR_REL}
    DUMP_FILENAME=${WORK_DIR}/${OUTPUT_PREFIX}-${failed_disks}.tgz

    mkdir -p ${WORK_DIR}
    mkdir -p ${STAGE_DIR}

    case "${mobo:0:9}" in
        "CMP-00013"|"CMP-00072"|"CMP-00109")
        (megarc -pdFailInfo -ch0 -a0 -idAll; echo; echo SENTINEL) | print_to_log
        linttylog /F lintty-raid.log 2>&1 > /dev/null
        mv lintty-raid.log ${STAGE_DIR}
        ;;
    *)
        # Save the output of hwtool -q disk=map
        /opt/hal/bin/hwtool.py -q disk=map > diskmap.log
        mv diskmap.log ${STAGE_DIR}
        ;;
    esac

    /bin/dmesg > dmesg.log
    mv dmesg.log ${STAGE_DIR}

    # Tar and gzip up the stage, then remove it
    tar -C ${WORK_DIR} -czf ${DUMP_FILENAME} ${STAGE_DIR_REL}
    mv ${DUMP_FILENAME} ${FINAL_DIR}
    rm -rf ${WORK_DIR}

    ${LOG_ERR} "Dumping ttylog to: ${logfile}.gz"
    echo $failed_disks > /var/opt/tms/raid_degraded

    ${LOG_ERR} "End RAID error log."
}

generate_latency_snapshot () {
    dev="$1"
    DATE_STR=`date '+%Y-%m-%d %H:%M:%S'`
    DATE_STR_FILE=`echo ${DATE_STR} | sed 's/-//g' | sed 's/://g' | sed 's/ /-/g'`
    OUTPUT_PREFIX=raidcheck-`uname -n`-${DATE_STR_FILE}
    FINAL_DIR=/var/opt/tms/snapshots/
    WORK_DIR=/var/tmp/${OUTPUT_PREFIX}-$$
    STAGE_DIR_REL=${OUTPUT_PREFIX}-${dev}
    STAGE_DIR=${WORK_DIR}/${STAGE_DIR_REL}
    DUMP_FILENAME=${WORK_DIR}/${OUTPUT_PREFIX}-${dev}.tgz

    mkdir -p ${WORK_DIR}
    mkdir -p ${STAGE_DIR}


    # Copy the SCSI Record I/O files.
    for j in `ls -1 /sys/block/$dev/device/record_io_* 2>/dev/null`; do
        file=`echo $j | sed -e 's/\//\n/g' | tail -1`
        cp $j ${STAGE_DIR}/$file-$dev
    done

    ${LOG_ERR} "Long latency disk I/O event occurred."
    case "${mobo:0:9}" in
        "CMP-00072"|"CMP-00109"|"CMP-00013")
        (megarc -pdFailInfo -ch0 -a0 -idAll; echo; echo SENTINEL) | print_to_log
        linttylog /F lintty-raid.log 2>&1 > /dev/null
        mv lintty-raid.log ${STAGE_DIR}
        ;;
    *)
        # Save the output of hwtool -q disk=map
        /opt/hal/bin/hwtool.py -q disk=map > diskmap.log
        mv diskmap.log ${STAGE_DIR}
        ;;
    esac

    /bin/dmesg > dmesg.log
    mv dmesg.log ${STAGE_DIR}

    # Tar and gzip up the stage, then remove it
    tar -C ${WORK_DIR} -czf ${DUMP_FILENAME} ${STAGE_DIR_REL}
    mv ${DUMP_FILENAME} ${FINAL_DIR}
    rm -rf ${WORK_DIR}

    ${LOG_ERR} "See `echo ${DUMP_FILENAME} | sed s,${WORK_DIR},${FINAL_DIR},`"

    # Reset the disk I/O event flag back to zero.
    cat > /sys/block/${dev}/device/record_io_event_time <<EOF
0
EOF

}

# Lets start clean, get rid of the old raid count file
rm -f /var/opt/tms/raid_degraded 

mkdir -p /var/log/raidlog
cd /var/log/raidlog

#capture startup log.
#actually don't.  Nothing survives reboot, so the info isn't useful
#date=`date +%d%m%y%H%M`
#linttylog /F raid.log > /dev/null
#mv raid.log /var/log/raidlog/raid_startup_log.${date}
#gzip /var/log/raidlog/raid_startup_log.${date}

while true; do 
    missing=`/opt/hal/bin/hal get_raid_status | grep 'missing' | wc -l`    
    failed_disks=`/opt/hal/bin/hal get_raid_status | egrep -v 'online' | wc -l`
    
    # Using the /var/opt/tms/raid_degraded to check if the logs were already copied
    # has the flaw that it wont recreate the log file if a second disk fails 
    # while one was already down. Instead store the failed disk count in the file 
    # This will fail in the case where a disk turns healthy and another 
    # fails in the 60 second poll interval (thats a chance I will take)
    # It will also log a snapshot when the disks come up
    if [ $failed_disks -gt 0 -o $missing -gt 0 ]; then
        if [ -f /var/opt/tms/raid_degraded ]; then
            if [ `cat /var/opt/tms/raid_degraded` -ne "$failed_disks" ]; then 
                save_log_snapshot $failed_disks
	fi
        else
            save_log_snapshot $failed_disks
	fi
    else
	rm -f /var/opt/tms/raid_degraded
    fi

    # See if we have had a long latency disk I/O event.
    case "${mobo:0:9}" in
        "CMP-00072"|"CMP-00109"|"CMP-00013")
        if [ -f /sys/block/sda/device/record_io_event_time ]; then
            if [ `cat /sys/block/sda/device/record_io_event_time` != "0" ]; then
                generate_latency_snapshot "sda"
            fi
        fi
        ;;
    *)
        for dev in `/opt/hal/bin/hwtool.py -q disk=map | grep disk | awk '{print $3}'`; do
            if [ -f /sys/block/${dev}/device/record_io_event_time ]; then
                if [ `cat /sys/block/${dev}/device/record_io_event_time` != "0" ]; then
                    generate_latency_snapshot "${dev}"
                fi
            fi
        done
        ;;
    esac

    sleep 60
done 
