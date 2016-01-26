
ve_sysdump_graft_3()
{
    do_safe_cp /proc/slabinfo ${STAGE_DIR}
    do_safe_cp /proc/modules ${STAGE_DIR}

    do_safe_cp /var/opt/rbt/edge-cfg.xml ${STAGE_DIR}
    do_safe_cp /var/opt/rbt/dynamic.xml ${STAGE_DIR}

    EDGEPID=`pidof edge | cut -d' ' -f 1`

    # only allow blockstore info command to run if the edge process is not running
    if [ -e /var/opt/rbt/edge-cfg.xml -a "x$EDGEPID" == "x" ]; then
        local BS_DEV=`/opt/tms/bin/mddbreq -v /config/mfg/mfdb query get - /rbt/mfd/blockstore_device`
        local ENC_PARAMS=`/usr/bin/python /etc/ve_blockstore_enc_params.py`
        local BLOCKSTORE_INFO="/opt/rbt/bin/blockstore_info --storefile ${BS_DEV} ${ENC_PARAMS}"

        #${BLOCKSTORE_INFO} --superblock \
        #        > ${STAGE_DIR}/blockstore_superblock.txt 2>&1
    
        if [ $BLOCKSTORE_LOGS -eq 1 ]; then
            /sbin/timed_exec.py -t 300 ${BLOCKSTORE_INFO} --superblock \
                --phash 2>&1 | gzip -c > ${STAGE_DIR}/blockstore_phash.txt.gz
        fi
    
        if [ $BLOCKSTORE_FIFO_LOGS -eq 1 ]; then
            ${BLOCKSTORE_INFO} --superblock --fifo 2>&1 | gzip -c > ${STAGE_DIR}/blockstore_fifo.txt.gz
        fi
    else
        /usr/bin/logger -s -i -p user.warning -t "sysdump" -- "Did not generate blockstore info because the edge process was still running."
    fi

    # generate a memory dump
    if [ "x$EDGEPID" != "x" ]; then
        kill -USR2 $EDGEPID
        sleep 2
        MEMDUMPS=`ls /var/tmp/mem-dump.$EDGEPID.*`
        for mem_dump in ${MEMDUMPS}; do
            cp -p $mem_dump ${STAGE_DIR}
            rm -f $mem_dump
        done

        do_safe_cp /var/log/memlog ${STAGE_DIR}
    fi
        
    # copy command server stats 
    CMD_SERVER_STATS_LIST=`find /var/log -name edge.stats\*`
    for cmd_stat_file in ${CMD_SERVER_STATS_LIST}; do
        do_safe_cp ${cmd_stat_file} ${STAGE_DIR}
    done 

    RBCMD="/opt/rbt/bin/rbcmd"
    RBCMD_OUT_FILE="${STAGE_DIR}/rbcmd.txt"
    if [ -f ${RBCMD} ]; then
        ${RBCMD} -s \* > ${RBCMD_OUT_FILE} 2>&1
    fi
}
