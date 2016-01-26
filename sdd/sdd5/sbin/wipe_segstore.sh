#!/bin/sh

# XXX/ARG I would like to stop pm but then the CLI disconnects

MDDBREQ='/opt/tms/bin/mddbreq'
DB_PATH='/config/mfg/mfdb'
ZERO_STORE="false"
KEY='segstore'
RVBD_SUPER='/opt/tms/bin/rvbd_super'
DD_FILE_OUT='/var/tmp/dd_out'
WHEN_FINISHED='halt'

# Script invocation:
# wipe_segstore.sh <ZERO_STORE=true|false> <FINISH=reboot|halt|exit>

# Check the number of arguments to the script
if [ $# -ge 1 ]; then
    ZERO_STORE=$1
fi

if [ $# -ge 2 ]; then
        WHEN_FINISHED=$2
fi

has_dual_store() {
    DUAL_STORE=`$MDDBREQ -v $DB_PATH query get - /rbt/mfd/store/dual`
    [ $DUAL_STORE = true ]
}

get_segstore_devices() {
    NODES='/rbt/mfd/store/dev'
    if has_dual_store; then
        NODES='/rbt/mfd/store/mdraid1 /rbt/mfd/store/mdraid2'
    fi
    $MDDBREQ -v $DB_PATH query get - $NODES
}

get_segstore_device_vsh() {
    NODES='/rbt/mfd/store/dev'
    $MDDBREQ -v $DB_PATH query get - $NODES
}

get_proxy_devices() {
    NODES='/rbt/mfd/smb/dev'
    if has_dual_store; then
        NODES='/rbt/mfd/smb/mdraid1 /rbt/mfd/smb/mdraid2'
    fi
    $MDDBREQ -v $DB_PATH query get - $NODES
}

stop_service() {
    echo -e "\
    enable
    configure terminal
    no service enable
    no pfs enable
    no rsp enable" | cli > /dev/null
    # Signal sport to start clean the next time
    touch /var/opt/rbt/.clean
}

start_service() {
    # Start service again
    echo -e "\
    enable
    configure terminal
    service enable
    pfs enable
    rsp enable" | cli > /dev/null
}

check_segstore_ready() {
    RESULT=`${RVBD_SUPER} -g /dev/disk1p1 | grep -i ${KEY}`
    if [ $? -ne 0 ]; then
        echo 'False'
    else
        echo 'True'
    fi
}

delete_kvp() {
    RESULT=`${RVBD_SUPER} -d ${KEY} /dev/disk1p1 >/dev/null 2>&1`
    if [ $? -ne 0 ]; then
        echo 'Error removing Key-Value pair from RVBD_SUPER'
        exit 1
    fi
}

add_segstore_kvp () {
    RESULT=`${RVBD_SUPER} -a ${KEY}=true /dev/disk1p1 >/dev/null 2>&1`
    if [ $? -ne 0 ]; then
        echo 'Error adding Key-Value pair to RVBD_SUPER'
        exit 1
    fi
}

on_die()
{
        # print message
        #
        echo "Detected Ctrl+C...Exiting!"

        # Need to exit the script explicitly when done.
        # Otherwise the dd would live on, until system
        # really goes down, and KILL signals are send.

        PID=$1
        cnt=0
        kill -9 $PID > /dev/null 2>&1
        while [ $? -ne 0 -a $cnt -lt 5 ]; do
            sleep 2
            kill -9 $PID > /dev/null 2>&1
            cnt=`expr $cnt + 1`
        done
        if [ $cnt -gt 4 ]; then
            echo "
              Unable to stop disk init process.
              Exit current terminal and re-login."
        fi
        exit 0
}



# Check if the request is to zero the segstore or to scrub all datastores
if [ "${ZERO_STORE}" == "true" ]; then
    # Check if this is a VSH - if not exit with a message
    MOBO_IS_VM=`/opt/hal/bin/hal get_motherboard_is_vm`
    if [ ! "x${MOBO_IS_VM}" == "xtrue" ]; then
        echo "Command not valid for this model."
        exit 0
    fi

    # Ask the user if he/she wants to bail
    echo "
       This command will delete your segstore !
       Please press Ctrl-C within the next 5 seconds if you wish to cancel !"
    sleep 7

    # Stop the service
    stop_service

    # Check if the disk had the segstore=ready in the super-block
    # if yes, then delete it, since we do not want to send incorrect
    # status. During an upgrade if a disk is expanded (as opposed
    # to deleted & recreated), this check will cause the script to bail
    # & the newly added disk will not be zero'd. So we remove the KVP.
    if [ `check_segstore_ready` == 'True' ]; then
        delete_kvp
    fi

    echo "
       Zeroing the data store which may take several hours.
       The system will not optimize during this time.

       Please do not start the optimization service via another console.
       Service will restart automatically after this process completes.

       If you cancel the operation while it is in progress (with Ctrl-C),
       please restart the service using service enable CLI command."

    # Run the dd process in background and add save PID
    pid=0
    dev=`get_segstore_device_vsh`
    /bin/dd if=/dev/zero of=$dev > ${DD_FILE_OUT} 2>&1 & pid=$!
    echo "
                           0 MB completed"

    # Execute function on_die() receiving INT signal
    #
    trap 'on_die $pid' INT

    until [ "$done" = "true" ]
    do
        if [ "$(pidof dd)" = "$pid" ]
        then
                sleep 30;
                done="false";
                echo > ${DD_FILE_OUT}
                # dd would dump stuff into ${DD_FILE_OUT} each time to gets USR1
                kill -USR1 $pid >/dev/null 2>&1
                # Parse the file to get the block written till now (512 bytes each)
                cnt=`cat ${DD_FILE_OUT} | tail -1 | awk '{print $1}' | awk 'BEGIN { FS = "+" } ; { print $1 }'`
                if [[ $cnt = [0-9]* ]]; then
                    # Calculate the total size written in mega-bytes
                    total_mb=`expr $cnt / 2048`
                    if [ $? -eq 0 ]; then
                        echo "
                           $total_mb MB completed"
                    fi
                fi
        else
                done="true"
                echo "datastore zeroing completed."
        fi
    done

    # Disk zeroing is done.
    # Add a segstore=ready into the disk's rvbd superblock.
    add_segstore_kvp

    # Restart service
    start_service
else
    stop_service
    if [ "${WHEN_FINISHED}" == "reboot" ]; then
        echo "
        Wiping the data store then rebooting the system.
        This may take several hours."
    elif [ "${WHEN_FINISHED}" == "exit" ]; then
        echo "
        Wiping the data store.
        This may take several hours."
    else
        echo "
        Wiping the data store then halting the system.
        This may take several hours."
    fi

    for dev in `get_segstore_devices` `get_proxy_devices`; do
        /usr/bin/scrub -f $dev
    done

    if [ "${WHEN_FINISHED}" == "reboot" ]; then
        echo 'Now rebooting the system...please wait.'
        /sbin/reboot
        exit 0
    elif [ "${WHEN_FINISHED}" == "exit" ]; then
        echo 'Data store wipe complete.'
        exit 0
    else
        echo 'Now halting the system... please wait.'
        /sbin/halt
    fi
fi
