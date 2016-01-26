#
#  URL:       $URL: svn://svn.nbttech.com/sh-product/branches/kauai_373_fix_branch/mgmt/appliances/rbt_sh/src/base_os/common/script_files/customer.sh $
#  Revision:  $Revision: 131066 $
#  Date:      $Date: 2013-08-05 18:06:11 -0700 (Mon, 05 Aug 2013) $
#  Author:    $Author: cliu $
#
#  (C) Copyright 2003-2012 Riverbed Technology, Inc.
#  All rights reserved.
#

# -----------------------------------------------------------------------------
# See customer/generic/src/base_os/script_files/customer.sh for more
# detailed documentation on how to use the various parts of this file.

MFDB=/config/mfg/mfdb

# -----------------------------------------------------------------------------
# This is used by afail.sh to formulate the subject line of the 
# failure email it sends out.
#
SUBJECT_PREFIX=Steelhead

# -----------------------------------------------------------------------------
# Path to the "rspnettest" executable.
#
RSPNETTEST_PROG=/opt/rbt/bin/rspnettest

# -----------------------------------------------------------------------------
# Path to the VSP state scrub tool.
#
VSP_STATE_SCRUB_TOOL=/sbin/scrub_vsp.sh

# -----------------------------------------------------------------------------
# This is used by ssl-cert-gen.sh to generate the SSL certificate
# for use with the Web UI.
#
SSL_CERT_HEADER="California
San Francisco
Riverbed Technology, Inc.
Steelhead"

# -----------------------------------------------------------------------------
# This is used by sysdump.sh to overwrite number of log lines printed in 
# failure emails from 50 -> 100.
#
NUM_LOG_LINES=100

# -----------------------------------------------------------------------------
# Graft point #1 for sysdump.sh
#
HAVE_SYSDUMP_GRAFT_1=y
sysdump_graft_1()
{
    /sbin/pidof mgmtd > /dev/null 2>&1
    MGMTD_RUNNING=$?
    if [ $MGMTD_RUNNING -eq 0 ]; then
        SERIAL_NUMBER=`/opt/tms/bin/mdreq -v query get - /rbt/manufacture/serialnum`
    else
        SERIAL_NUMBER=`/opt/tms/bin/mddbreq -v $MFDB query get "" /rbt/mfd/serialnum`
    fi
    echo "Serial Number: ${SERIAL_NUMBER}" >> ${SYSINFO_FILENAME}

    MODEL_NUMBER=`/opt/tms/bin/hald_model | awk '{ print $1 }'`
    echo "Model Number: ${MODEL_NUMBER}" >> ${SYSINFO_FILENAME}

    MFG_TYPE=`/opt/tms/bin/hald_model | cut -f56`
    if [ "$MFG_TYPE" = "rvbd_ex" ]; then
	DISK_LAYOUT=`/opt/tms/bin/mddbreq -v $MFDB query get "" \
	    /rbt/mfd/resman/profile`
	echo "Disk Layout: ${DISK_LAYOUT}" >> ${SYSINFO_FILENAME}
    fi
}

# -----------------------------------------------------------------------------
# Graft point #2 for sysdump.sh
#
# This is called after all the summary data at the top.
#
HAVE_SYSDUMP_GRAFT_2=y
sysdump_graft_2()
{
    SERVICE_UPTIME="00:00"
    SPORT_PID=`pidof sport`
    if [ "${SPORT_PID}" ]; then
        SERVICE_UPTIME=`ps -o %t $SPORT_PID | tail -1 | tr -d " "`
    fi
    echo -e "Service Uptime [DD-HH:MM:SS]: ${SERVICE_UPTIME}\n" >> ${SYSINFO_FILENAME}

    do_command_output '/opt/rbt/bin/sport -v'

    if [ -f /opt/rbt/bin/edge ]; then
        do_command_output '/opt/rbt/bin/edge -v'
    fi
    if [ -f /opt/rbt/bin/iscsi_target ]; then
        do_command_output '/opt/rbt/bin/iscsi_target -v'
    fi
}

# -----------------------------------------------------------------------------
# Graft point #3 for sysdump.sh
#
# This is called after all the standard text output has been generated.
#
# NOTE: Please add new /proc and /proc/sys entries under KERNEL_PROC_DIR and
#  KERNEL_PROC_SYS_DIR respectively. See ipv6 and ipblade sections.
#
HAVE_SYSDUMP_GRAFT_3=y
sysdump_graft_3()
{
    do_command_output 'ip rule list'
    do_command_output 'ip -6 rule list'

    if [ -f /etc/iproute2/rt_tables ]; then
        PROXYTABLES=`grep proxytable /etc/iproute2/rt_tables | sed -e 's,.*\t,,'`
        for proxy_table in ${PROXYTABLES}; do
            do_command_output "ip route list table ${proxy_table}"
            do_command_output "ip -6 route list table ${proxy_table}"
        done
        FWMARKTABLES=`grep fwmarktable /etc/iproute2/rt_tables | sed -e 's,.*\t,,'`
        for fwmark_table in ${FWMARKTABLES}; do
            do_command_output "ip route list table ${fwmark_table}"
        done
    fi

    if [ -e /proc/nbt/0 ]; then
        PROC_FILES=`ls /proc/nbt/0`
        for proc_file in ${PROC_FILES}; do
            if [ -r /proc/nbt/0/$proc_file ]; then
                cp -p /proc/nbt/0/$proc_file ${STAGE_DIR}
            fi
        done
    fi

    if [ -e /proc/sys/nbt ]; then
        PROC_FILES=`ls /proc/sys/nbt`
        for proc_file in ${PROC_FILES}; do
	    if [ -r /proc/sys/nbt/$proc_file ]; then
		cp -p /proc/sys/nbt/$proc_file ${STAGE_DIR}
	    fi
        done
    fi

    if [ -e /proc/netflow ]; then
        PROC_FILES=`ls /proc/netflow`
        NETFLOW_DST_DIR="${STAGE_DIR}"/netflow
        mkdir "${NETFLOW_DST_DIR}"
        for proc_file in ${PROC_FILES}; do
            cp -p /proc/netflow/$proc_file ${NETFLOW_DST_DIR}
        done
    fi

    if [ -e /proc/sys/net/ipv4/netfilter ]; then
        PROC_FILES=`ls /proc/sys/net/ipv4/netfilter`
        NETFILTER_DST_DIR="${STAGE_DIR}"/netfilter
        mkdir "${NETFILTER_DST_DIR}"
        for proc_file in ${PROC_FILES}; do
            cp -p /proc/sys/net/ipv4/netfilter/$proc_file ${NETFILTER_DST_DIR}
        done
    fi

    if [ -d /proc/rbtqosmod ]; then
        cp -pr /proc/rbtqosmod ${STAGE_DIR}
    fi

    if [ -d /proc/sys/rbtqosmod ]; then
        RBTQOSMOD_DST_DIR="${STAGE_DIR}"/rbtqosmod
        RBTQOSMOD_SYS_DST_DIR="$RBTQOSMOD_DST_DIR"/sys
        if [ ! -d $RBTQOSMOD_DST_DIR ]; then
            mkdir "${RBTQOSMOD_DST_DIR}"
        fi
        mkdir "${RBTQOSMOD_SYS_DST_DIR}"
        cp -pr /proc/sys/rbtqosmod/* ${RBTQOSMOD_SYS_DST_DIR}
    fi

    if [ -e /proc/rbt-switch/state ]; then
        cp -p /proc/rbt-switch/state $STAGE_DIR/rbtswitch.txt
    fi

    # SaaS redirection entries
    if [ -e /proc/rbtpipe ]; then
        cp -ap /proc/rbtpipe ${STAGE_DIR}
    fi

    do_command_output 'cat /proc/net/ip_conntrack'
    do_command_output 'cat /proc/net/stat/ip_conntrack'

    # Ether-relay entries
    ER_SYSCTL_DIR=/proc/sys/er
    if [ -d $ER_SYSCTL_DIR ]; then
        cp -ap $ER_SYSCTL_DIR ${STAGE_DIR}
    fi
    ER_PROC_DIR=/proc/er
    if [ -d $ER_PROC_DIR ]; then
        cp -ap $ER_PROC_DIR ${STAGE_DIR}
    fi

    # EAL entries
    ER_SYSCTL_DIR=/proc/sys/eal
    if [ -d $ER_SYSCTL_DIR ]; then
        cp -ap $ER_SYSCTL_DIR ${STAGE_DIR}
    fi
    ER_PROC_DIR=/proc/eal
    if [ -d $ER_PROC_DIR ]; then
        cp -ap $ER_PROC_DIR ${STAGE_DIR}
    fi

    # MIP entries
    MIP_SYSCTL_DIR=/proc/sys/mip
    if [ -d $MIP_SYSCTL_DIR ]; then
        cp -ap $MIP_SYSCTL_DIR ${STAGE_DIR}
    fi
    MIP_PROC_DIR=/proc/mip
    if [ -d $MIP_PROC_DIR ]; then
        cp -ap $MIP_PROC_DIR ${STAGE_DIR}
    fi

    # Virtual Memory entries
    VM_PROC_DIR=/proc/sys/vm
    if [ -d $VM_PROC_DIR ]; then
        mkdir -p ${STAGE_DIR}/vm
        VM_PROC_DIR_FILES=`ls ${VM_PROC_DIR}`
        for vm_proc_file in ${VM_PROC_DIR_FILES}; do
            if [ -r ${VM_PROC_DIR}/$vm_proc_file ]; then
                cp -ap ${VM_PROC_DIR}/$vm_proc_file ${STAGE_DIR}/vm
            fi
        done
    fi

    # rbt-bridge entries
    if [ -d /proc/rbt-bridge ]; then
        cp -ap /proc/rbt-bridge ${STAGE_DIR}
    fi

    CAVIUM_SRC_DIR=/proc/cavium
    if [ -e "${CAVIUM_SRC_DIR}" ]; then
        CAVIUM_DST_DIR="${STAGE_DIR}"/cavium
        mkdir "${CAVIUM_DST_DIR}"
        cp -p "${CAVIUM_SRC_DIR}"/* "${CAVIUM_DST_DIR}"
    fi
    
    mkdir -p ${KERNEL_PROC_DIR}/net/
    do_safe_cp /proc/sys/wdt/type ${STAGE_DIR}
    do_safe_cp /proc/slabinfo ${STAGE_DIR}
    do_safe_cp /proc/net/snmp ${STAGE_DIR}
    do_safe_cp /proc/net/netstat ${STAGE_DIR}
    do_safe_cp /proc/modules ${STAGE_DIR}
    do_safe_cp /proc/net/softnet_stat ${STAGE_DIR}
    do_safe_cp /proc/net/scpsstat ${STAGE_DIR}
    do_safe_cp /proc/net/skipw105stat ${STAGE_DIR}
    do_safe_cp /proc/net/skipw105conn ${STAGE_DIR}
    do_safe_cp /proc/net/arp ${KERNEL_PROC_DIR}/net/
    do_safe_cp /proc/net/packet ${KERNEL_PROC_DIR}/net/
    do_safe_cp /proc/net/protocols ${KERNEL_PROC_DIR}/net/
    do_safe_cp /proc/net/raw ${KERNEL_PROC_DIR}/net/
    do_safe_cp /proc/net/rbt-accept-q ${KERNEL_PROC_DIR}/net/
    do_safe_cp /proc/net/route ${KERNEL_PROC_DIR}/net/
    do_safe_cp /proc/net/rt_acct ${KERNEL_PROC_DIR}/net/
    do_safe_cp /proc/net/rt_cache ${KERNEL_PROC_DIR}/net/
    do_safe_cp /proc/net/tcp ${KERNEL_PROC_DIR}/net/
    do_safe_cp /proc/net/tcp_inner_packet_size ${KERNEL_PROC_DIR}/net/
    do_safe_cp /proc/net/tcp_outer_packet_size ${KERNEL_PROC_DIR}/net/
    do_safe_cp /proc/net/udp ${KERNEL_PROC_DIR}/net/
    do_safe_cp /proc/net/udplite ${KERNEL_PROC_DIR}/net/
    do_safe_cp /proc/net/sockstat6 ${KERNEL_PROC_DIR}/net/
    do_safe_cp /proc/net/if_inet6 ${KERNEL_PROC_DIR}/net/
    do_safe_cp /proc/net/ip6_flowlabel ${KERNEL_PROC_DIR}/net/
    do_safe_cp /proc/net/ipv6_route ${KERNEL_PROC_DIR}/net/
    do_safe_cp_zip /proc/net/raw6 ${KERNEL_PROC_DIR}/net/
    do_safe_cp_zip /proc/net/udp6 ${KERNEL_PROC_DIR}/net/
    do_safe_cp_zip /proc/net/udplite6 ${KERNEL_PROC_DIR}/net/

    # server shell files
    if [ -d /proxy/__RBT_VSERVER_SHELL__ ]; then
        du -sk /proxy/__RBT_VSERVER_SHELL__ > ${STAGE_DIR}/server_shell.txt
        find /proxy/__RBT_VSERVER_SHELL__ -print >> ${STAGE_DIR}/server_shell.txt
    fi

    # neural-stats files
    files=$(ls /var/opt/rbt/neural-stats.* 2> /dev/null | wc -l )
    if [ "$files" != 0 ]; then
       NEURAL_STATS=`ls /var/opt/rbt/neural-stats.*`
       for neural_file in ${NEURAL_STATS}; do
          cp -p $neural_file ${STAGE_DIR}
          rm -f $neural_file
       done
    fi

    # generate a memory dump
    SPORTPID=`pidof sport | cut -d' ' -f 1`
    if [ "x$SPORTPID" != "x" ]; then
        kill -USR2 $SPORTPID
        sleep 2
        MEMDUMPS=`ls /var/tmp/mem-dump.$SPORTPID.*`
        for mem_dump in ${MEMDUMPS}; do
            cp -p $mem_dump ${STAGE_DIR}
            rm -f $mem_dump
        done
    fi

    # Oprofile data
    oprofile_files=$(ls /var/tmp/*_oprofile.txt 2> /dev/null | wc -l )
    if [ "$oprofile_files" != 0 ]; then
        OPROFILES=`ls /var/tmp/*_oprofile.txt`
        for oprofile in ${OPROFILES}; do
            cp -p $oprofile ${STAGE_DIR}
        done
    fi

    # PFS files - trim to 1000 lines if brief mode
    PFS_DIR="${STAGE_DIR}/pfs"
    mkdir "${PFS_DIR}"
    pfs_file_cnt_1=$(ls /var/log/rcu/* 2> /dev/null | wc -l )
    pfs_file_cnt_2=$(ls /var/log/samba/* 2> /dev/null | wc -l )
    pfs_file_cnt_3=$(ls /var/log/rcu/rcu_helperd.out 2> /dev/null | wc -l )
    pfs_file_cnt_4=$(ls /var/opt/rcu/net_ads.out 2> /dev/null | wc -l )

    pfs_file_string=""
    if [ "$pfs_file_cnt_1" != 0 ]; then
        pfs_file_string="${pfs_file_string}/var/log/rcu/* "
    fi
    if [ "$pfs_file_cnt_2" != 0 ]; then
        pfs_file_string="${pfs_file_string}/var/log/samba/* "
    fi
    if [ "$pfs_file_cnt_3" != 0 ]; then
        pfs_file_string="${pfs_file_string}/var/log/rcu/rcu_helperd.out "
    fi
    if [ "$pfs_file_cnt_4" != 0 ]; then
        pfs_file_string="${pfs_file_string}/var/opt/rcu/net_ads.out "
    fi

    for pfs_file in $pfs_file_string ; do
        if [ ${BRIEF} -eq 0 ]; then
            cp -p "$pfs_file" "$PFS_DIR"
        else
            tail -1000 $pfs_file > "${PFS_DIR}/"`basename $pfs_file`
        fi
    done

    # Domain-health logs - trim to 1000 lines if brief mode
    DOM_HEALTH_DIR="${STAGE_DIR}/domain_health"
    mkdir "${DOM_HEALTH_DIR}"

    dhealth_file_cnt=$(ls /var/log/domaind/* 2> /dev/null | wc -l)
    if [ "$dhealth_file_cnt" != 0 ]; then
        for dhealth_file in /var/log/domaind/*; do
            if [ ${BRIEF} -eq 0 ]; then
                cp -p "$dhealth_file" "$DOM_HEALTH_DIR"
            else
                tail -1000 $dhealth_file > "${DOM_HEALTH_DIR}/"`basename $dhealth_file`
            fi
        done
    fi
 
    # PFS config
    do_safe_cp /var/opt/rcu/rcud.conf ${STAGE_DIR}
    do_safe_cp /etc/samba/smb.conf ${STAGE_DIR}
    do_safe_cp /etc/krb5.conf ${STAGE_DIR}
    do_safe_cp /etc/krb.realms ${STAGE_DIR}

    # Backup files in case of domain join failure
    do_safe_cp /etc/samba/smb.conf.old ${STAGE_DIR}
    do_safe_cp /var/etc/krb5.conf.old ${STAGE_DIR}
    do_safe_cp /var/etc/krb.realms.old ${STAGE_DIR}

    do_command_output '/bin/netstat -s'

    # Add Delegation and Replication user info to sysdump
    DELEG_REPL_USRINFO_FILE="${STAGE_DIR}/delegrepl_usrinfo.txt"
    /sbin/pidof mgmtd > /dev/null 2>&1
    MGMTD_RUNNING=$?
    if [ $MGMTD_RUNNING -eq 0 ]; then
        USER_TYPES=( "delegation" "replication")
        SECURE_VAULT_UNLOCKED=`/sbin/secure_vault_check_mount.sh`
        MIGRATION_DONE=`/opt/tms/bin/mdreq -v query get - /rbt/sport/domain_auth/local/config/migration_done`
        SECURE_DB=""
        if [ ${MIGRATION_DONE} = "true" ]; then
    	    SECURE_DB="secure/"
        fi
        echo -e "#######################USER INFO########################\n" > ${DELEG_REPL_USRINFO_FILE}
        if [ "${SECURE_VAULT_UNLOCKED}" = "true" ]; then
            for user in ${USER_TYPES[@]}; do 
    	        echo "---------------${user} user information -------------" >> ${DELEG_REPL_USRINFO_FILE}; 
    	        if [ "${user}" = "delegation" ]; then 
    	            REPLICATION_STR="";
    	        else 
    	            REPLICATION_STR="${user}/"; 
                fi 
    	        DOMAINS=`/opt/tms/bin/mdreq -v query pattern_match - /rbt/sport/domain_auth/${SECURE_DB}config/${REPLICATION_STR}domain/*`;
                if [ "${DOMAINS}" ]; then 
                    for domain in ${DOMAINS}; do 
                        echo "    DOMAIN NAME:" ${domain} >> ${DELEG_REPL_USRINFO_FILE}; 	
    		        USER_NAME=`/opt/tms/bin/mdreq -v query get - /rbt/sport/domain_auth/${SECURE_DB}config/${REPLICATION_STR}domain/${domain}/user`;
   		        echo "         User Name:" ${USER_NAME} >> ${DELEG_REPL_USRINFO_FILE};   
  		        if [ "${user}" = "replication" ]; then
  		            USER_DOMAIN=`/opt/tms/bin/mdreq -v query get - /rbt/sport/domain_auth/${SECURE_DB}config/replication/domain/${domain}/user_domain`;
  		            echo "         User Domain:" ${USER_DOMAIN} >> ${DELEG_REPL_USRINFO_FILE};
  		            IS_RODC=`/opt/tms/bin/mdreq -v query get - /rbt/sport/domain_auth/${SECURE_DB}config/replication/domain/${domain}/rodc`;
  		            echo "         RODC:" ${IS_RODC} >> ${DELEG_REPL_USRINFO_FILE}; 
  		            DC_NAME=`/opt/tms/bin/mdreq -v query get - /rbt/sport/domain_auth/${SECURE_DB}config/replication/domain/${domain}/dcname`;
  		            echo "         DC Name:" ${DC_NAME} >> ${DELEG_REPL_USRINFO_FILE}; 
  		        fi
                        echo -e "\n" >> ${DELEG_REPL_USRINFO_FILE};
                    done
                else
                    echo "    No ${user} users" >> ${DELEG_REPL_USRINFO_FILE};
                fi
                echo -e "\n" >> ${DELEG_REPL_USRINFO_FILE};
            done
        else
            echo "Secure Vault is locked, cannot query Delegation and Replication users information" >> ${DELEG_REPL_USRINFO_FILE};
        fi
    else
            echo "Mgmtd is not running, cannot query Delegation and Replication users information" >> ${DELEG_REPL_USRINFO_FILE};
    fi

    # SDR stats information
    if [ ${BRIEF} -eq 0 ]; then
        SDRSTATS=`ls /var/log/sdr.*`
        for sdr_stat in ${SDRSTATS}; do
            cp -p $sdr_stat ${STAGE_DIR}
        done
    else
        do_safe_cp /var/log/sdr.stats ${STAGE_DIR}
    fi

    # binary dumps of segment pages that are corrupt or improperly unrefed
    if [ ${BRIEF} -eq 0 ]; then
        for ref_file in /var/log/refd_pages.*; do
            do_safe_cp "$ref_file" ${STAGE_DIR}
        done
    fi

    # pstorestats files
    do_safe_cp /var/log/h_pstorestats ${STAGE_DIR}
    if [ ${BRIEF} -eq 0 ]; then
        for h_pstorestats_file in /var/log/h_pstorestats.*; do
            do_safe_cp "$h_pstorestats_file" ${STAGE_DIR}
        done
    fi

    do_safe_cp /var/log/n_pstorestats ${STAGE_DIR}
    if [ ${BRIEF} -eq 0 ]; then
        for n_pstorestats_file in /var/log/n_pstorestats.*; do
            do_safe_cp "$n_pstorestats_file" ${STAGE_DIR}
        done
    fi

    do_safe_cp /var/log/w_pstorestats ${STAGE_DIR}
    if [ ${BRIEF} -eq 0 ]; then
        for w_pstorestats_file in /var/log/w_pstorestats.*; do
            do_safe_cp "$w_pstorestats_file" ${STAGE_DIR}
        done
    fi

    # oom profile files
    do_safe_cp /var/log/oom_profile.log ${STAGE_DIR}
        for oom_profile_file in /var/log/oom_profile.log.*; do
            do_safe_cp "$oom_profile_file" ${STAGE_DIR}
        done

    # disk_stats log files
    if [ ${BRIEF} -eq 0 ]; then
        do_safe_cp /var/log/disk_stats.log ${STAGE_DIR}
        for disk_stats_file in /var/log/disk_stats.log.*; do
            do_safe_cp "$disk_stats_file" ${STAGE_DIR}
        done
    fi


    # intercept stats log files. in full sysdump only. not brief
    if [ ${BRIEF} -eq 0 ]; then
        do_safe_cp /var/log/stats_collect.log ${STAGE_DIR}
        for stats_collect_file in /var/log/stats_collect.log.*; do
            do_safe_cp "$stats_collect_file" ${STAGE_DIR}
        done
    fi

    # tcp stats log files
    if [ ${BRIEF} -eq 0 ]; then
        do_safe_cp /var/log/tcp_stats.log ${STAGE_DIR}
        for tcp_stats_file in /var/log/tcp_stats.log.*; do
            do_safe_cp "$tcp_stats_file" ${STAGE_DIR}
        done
    fi

    # LKCD
    lkcd_file_cnt=$(ls /var/log/dump/*/analysis.* 2> /dev/null | wc -l)
    if [ "$lkcd_file_cnt" != 0 ]; then
        for analysis in `ls /var/log/dump/*/analysis.*`; do
            do_safe_cp $analysis ${STAGE_DIR}
        done
    fi
 
   # Collect sysctl -a
   /sbin/sysctl -a | egrep "^net|^kernel|^vm" > ${STAGE_DIR}/sysctls.txt

    # QoS qosd stats log files
    if [ ${BRIEF} -eq 0 ]; then
        do_safe_cp /var/log/qosd_stats.log ${STAGE_DIR}
        if [ $UNLIMITED_LOGS -eq 1 ]; then
            for qosd_stats_file in /var/log/qosd_stats.log.*; do
                do_safe_cp "$qosd_stats_file" ${STAGE_DIR}
            done
        fi
    fi

    # QoS
    cat /proc/net/dev | \
    awk -F : '/^(rios_)?wan[0-9]_[0-9]|primary|prihw/{print $1}' | \
    awk '{print $1}' | while read qos_iface; do
        tc -s -d qdisc show dev "${qos_iface}"
        tc -s -d class show dev "${qos_iface}" parent 1:0
        tc -s -d class show dev "${qos_iface}" parent 2:0
        tc -s -d class show dev "${qos_iface}" parent 8000:0
        tc -s -d filter show dev "${qos_iface}" parent 1:0
        tc -s -d filter show dev "${qos_iface}" parent 2:0
        tc -s -d filter show dev "${qos_iface}" parent 8000:0
    done > ${STAGE_DIR}/qos.txt

    echo -e "\n\nQos kernel header rules:\n" >> ${STAGE_DIR}/qos.txt
    cat /proc/qos_hdr_rules >> ${STAGE_DIR}/qos.txt

    echo -e "\n\nInbound qos filter errors:\n" >> ${STAGE_DIR}/qos.txt
    cat /proc/inb_qos_filter_stats >> ${STAGE_DIR}/qos.txt

    # QoS classification daemon
    QOSDPID=`pidof qosd | cut -d' ' -f 1`
    if [ "x$QOSDPID" != "x" ]; then
        rm -f "/var/tmp/qosd.txt"
        kill -USR2 ${QOSDPID}
        sleep 2
    fi

    if [ -f '/var/tmp/qosd.txt' ]; then
        cp -f "/var/tmp/qosd.txt" ${STAGE_DIR}
    fi

    # Pathmon daemon for QoP
    PATHMONPID=`pidof pathmon | cut -d' ' -f 1`
    if [ "x$PATHMONPID" != "x" ]; then
        kill -USR2 ${PATHMONPID}
        sleep 2
        MEMDUMPS=`ls /var/tmp/mem-dump.$PATHMONPID.*`
        for mem_dump in ${MEMDUMPS}; do
            cp -p $mem_dump ${STAGE_DIR}
            rm -f $mem_dump
        done
    fi

    # Force a run of SAR, so we have the latest data for collection
    SA_32="/usr/lib/sa/sa2"
    SA_64="/usr/lib64/sa/sa2"
    if [ -f $SA_32 ]; then
        $SA_32 -A
    elif [ -f $SA_64 ]; then
        $SA_64 -A
    fi

    if [ ${BRIEF} -eq 0 ]; then
        RBT_SAR_FILES=`ls /var/opt/rbt/sar/*`
        for rbt_sar_file in ${RBT_SAR_FILES}; do
            do_safe_cp $rbt_sar_file ${STAGE_DIR}
        done
    else
        LATEST_SAR_FILE=`ls -t /var/opt/rbt/sar | head -n1`
        do_safe_cp /var/opt/rbt/sar/${LATEST_SAR_FILE} ${STAGE_DIR}
    fi
    
    # Virtualization support files
    RSP_ROOT_DIR=/proxy/__RBT_VSERVER_SHELL__/rsp2
    MFG_TYPE=`/opt/tms/bin/hald_model -m`
    # Is RSP2 ?
    if [ -f $RSP_ROOT_DIR/.rsp_version -a "${MFG_TYPE}" != "rvbd_ex" ]; then
        STAGE_RSP_DIR=${STAGE_DIR}/rsp
        STAGE_RSPNET_DIR=${STAGE_RSP_DIR}/rspnet

        mkdir -p ${STAGE_RSP_DIR}
        mkdir -p ${STAGE_RSPNET_DIR}
        TMP_RSP_FILE=`mktemp`
        do_safe_cp /var/opt/tms/rsp_image_history ${STAGE_RSP_DIR}
        do_safe_cp $RSP_ROOT_DIR/.rsp_version ${STAGE_RSP_DIR}
        do_safe_cp $RSP_ROOT_DIR/build_version.sh ${STAGE_RSP_DIR}
        do_safe_cp $RSP_ROOT_DIR/.rsp_alt_db ${STAGE_RSP_DIR}
        # Kind of a kluge to allow us to use a pipe in our command.
        echo "find $RSP_ROOT_DIR -maxdepth 5 -print0 | xargs -0 ls -ld" >$TMP_RSP_FILE
        find $RSP_ROOT_DIR -maxdepth 5 -print0 | xargs -0 ls -ld >>$TMP_RSP_FILE
        do_command_output "cat $TMP_RSP_FILE"
        rm -f $TMP_RSP_FILE
        for rsp_dir in "/etc/vmware/ /var/log/vmware/ /var/lib/vmware/"; do
            rsp_files=`find $rsp_dir -not -regex '.*ssl.*' -not -regex '.*core\.[0-9]+*' \\
                       -not -regex '.*icudt[0-9]+*l\.dat' -type f -follow`
            for file in $rsp_files; do
                do_safe_cp $file ${STAGE_RSP_DIR}/`basename $file`
            done
        done

        # Get details about downloaded RSP Packages.
        if [ -d /rsp/packages/ ]; then
            cd /rsp/packages/
            PACKAGES=`find . -type f -print`
            STAGE_RSP_PACKAGE_DIR=${STAGE_RSP_DIR}/packages
            for package in $PACKAGES; do
                mkdir -p ${STAGE_RSP_PACKAGE_DIR}/$package
                /usr/bin/7za l $package >/${STAGE_RSP_PACKAGE_DIR}/$package/file_listing 2>/dev/null
                /usr/bin/7za e $package rsp.conf -so >/${STAGE_RSP_PACKAGE_DIR}/$package/rsp.conf 2>/dev/null
                /usr/bin/7za e $package rsp.vmx -so >/${STAGE_RSP_PACKAGE_DIR}/$package/rsp.vmx 2>/dev/null
            done
        fi

        # Get some info about the various RSP utilities.
        if [ -e /opt/tms/bin/vix_wrapperd ]; then
            do_command_output "ldd /opt/tms/bin/vix_wrapperd"
        fi

        for slot_dir in `ls $RSP_ROOT_DIR/slots`; do
            if [ -d $RSP_ROOT_DIR/slots/$slot_dir ]; then
                STAGE_RSP_SLOT_DIR=${STAGE_RSP_DIR}/slots/$slot_dir
                mkdir -p ${STAGE_RSP_SLOT_DIR}
                cd $RSP_ROOT_DIR/slots/$slot_dir
                vm_files=`ls *.vmx *.vmxf *.vmsd *.conf .priority .enabled .installed 2>/dev/null`
                echo "$vm_files" | while read file; do
                    do_safe_cp "$file" ${STAGE_RSP_SLOT_DIR}/"$file"
                done
            fi
        done

        # Run VMware's support tool if so requested.
        VM_SUPPORT="/usr/bin/vmware/vm-support"
        if [ $RSP_VMWARE_SUPPORT -eq 1 ]; then
            if [ -f $VM_SUPPORT ]; then
                $VM_SUPPORT -w ${STAGE_RSP_DIR} 2>&1 >/dev/null
            fi
        fi

        # RSPNET stuff

        if [ -d /proc/rspnet ]; then
            files=`find /proc/rspnet -type f`
            for file in $files; do
                do_command_output_file "cat $file" $STAGE_RSPNET_DIR/rspnet.txt
            done
        fi

        RSPNETTESTIN=/tmp/rspnettestIN
        RSPNETTESTOUT=/tmp/rspnettestOUT
        echo -e "g\nns\nds all\ndS all" >$RSPNETTESTIN
        $RSPNETTEST_PROG -q <$RSPNETTESTIN >$RSPNETTESTOUT
        do_command_output_file "cat $RSPNETTESTOUT" $STAGE_RSPNET_DIR/rspnet.txt
        rm -f $RSPNETTESTIN
        rm -f $RSPNETTESTOUT
        for file in `ls /sys/module/rspnetmod/`; do
            do_command_output_file "cat /sys/module/rspnetmod/$file" $STAGE_RSPNET_DIR/rspnet.txt
        done

        # mactab config & entries
        BR_IFACES=`/sbin/get_bridge_ifaces.py`
        for iface in $BR_IFACES; do
            if [ -d /proc/sys/rspnet/${iface} ]; then
                do_command_output_file "cat /proc/sys/rspnet/${iface}/flap_hold_ms" $STAGE_RSPNET_DIR/rspnet.txt
                do_command_output_file "cat /proc/sys/rspnet/${iface}/flap_thresh_count" $STAGE_RSPNET_DIR/rspnet.txt
                do_command_output_file "cat /proc/sys/rspnet/${iface}/flap_thresh_ms" $STAGE_RSPNET_DIR/rspnet.txt
            fi
        done
    elif [ "${MFG_TYPE}" = "rvbd_ex" ]; then
        # BoBV2
        local EX_BIOS_INI=ex_bios.ini
        local EX_BIOS_PATH=${STAGE_DIR}/ex_bios.ini
        local MOBO=`hwtool -q motherboard`
        if [ "x${MOBO}" = "x425-00135-01" ]; then
            # Bluedell BIOS configuration
            local SAVE_EX_BIOS_CMD="/opt/dell/toolkit/bin/syscfg"
            echo "==================================================" >> ${SYSINFO_FILENAME}
            echo "Output of '${SAVE_EX_BIOS_CMD} -o ${EX_BIOS_INI}':"  >> ${SYSINFO_FILENAME}
            echo "" >> ${SYSINFO_FILENAME}
            echo "`${SAVE_EX_BIOS_CMD} -o ${EX_BIOS_PATH} 2>&1`" >> ${SYSINFO_FILENAME}
            echo "" >> ${SYSINFO_FILENAME}
            echo "==================================================" >> ${SYSINFO_FILENAME}
            echo "" >> ${SYSINFO_FILENAME}
        fi

        STAGE_VSP_DIR=${STAGE_DIR}/vsp
        mkdir -p "${STAGE_VSP_DIR}"

        do_command_output_file "ls -alRh /esxi" ${STAGE_VSP_DIR}/esxi_dir.txt
        dir_files=`ls /etc/vmware/*`
        STAGE_VSP_VMWARE_DIR=$STAGE_VSP_DIR/etc/vmware
        if [ ! -d $STAGE_VSP_VMWARE_DIR ]; then
            mkdir -p ${STAGE_VSP_VMWARE_DIR}
        fi

        for vsp_dir in $dir_files; do
            vsp_files=`find $vsp_dir -not -regex '.*ssl.*' -not -regex '.*core\.[0-9]+*' \\
                       -not -regex '.*icudt[0-9]+*l\.dat' -type f -follow`
            for file in $vsp_files; do
                if [ $file != /etc/vmware/license* -a $file != /etc/vmware/config ]; then
                    cp -p $file ${STAGE_VSP_VMWARE_DIR}/`basename $file`
                fi
            done
        done

        # VIL stacked information

        # cgroups
        CGRP_CONF="/etc/cgconfig.conf"
        CGRP_RULES="/etc/cgrules.conf"
        if [ -f ${CGRP_CONF} ]; then 
            cp -p ${CGRP_CONF} ${STAGE_VSP_DIR}
        fi
        if [ -f ${CGRP_RULES} ]; then
            cp -p ${CGRP_RULES} ${STAGE_VSP_DIR}
        fi
        
        # Add ESXi VM files
        PRIMARY_MAC="`ip link show dev primary | grep 'link\/ether' | awk '{ print $2 }' | sed 's/://g'`"
        ESXI_VM_PATH="/esxi/${PRIMARY_MAC}"
        if [ -d ${ESXI_VM_PATH} ]; then
            cp -p ${ESXI_VM_PATH}/esxi.vmx ${STAGE_VSP_DIR}
            cp -p ${ESXI_VM_PATH}/esxi_history ${STAGE_VSP_DIR}
        fi
       
        # Add ESXi version history file
        ESXI_IMAGE_HISTORY="/var/opt/tms/esxi_version_history"
        if [ -f ${ESXI_IMAGE_HISTORY} ]; then
            cp -p ${ESXI_IMAGE_HISTORY} ${STAGE_VSP_DIR}
        fi
 
        # /proc/vmnet info
        if [ -d /proc/vmnet ]; then
           mkdir -p ${STAGE_VSP_DIR}/proc/vmnet
           for proc_file in `find /proc/vmnet -type f 2>/dev/null| egrep -v "kcore|kmsg|acpi|pagemap"`; do
                dir_name=`(dirname $proc_file)`
                if [ ! -d ${STAGE_VSP_DIR}/$dir_name ]; then
                    mkdir -p ${STAGE_VSP_DIR}/${dir_name}
                fi
               cp -p ${proc_file} ${STAGE_VSP_DIR}/${dir_name}/`basename ${proc_file}` 2>/dev/null
            done
        fi

        # /usr/bin/vmstat info
        VMSTAT_BIN="/usr/bin/vmstat"
        if [ -f $VMSTAT_BIN ]; then 
            do_command_output_file "$VMSTAT_BIN" $STAGE_VSP_DIR/vmstat.txt
        fi
        
        # virtualization thread information
        VMWARE_VMX="/opt/vmware/vmware_vil/lib/vmware/bin/vmware-vmx"
        VMWARE_VMX_DEBUG="/opt/vmware/vmware_vil/lib/vmware/bin/vmware-vmx-debug"
        VMWARE_VMX_STATS="/opt/vmware/vmware_vil/lib/vmware/bin/vmware-vmx-stats"
        VMNET_DHCPD="/opt/vmware/vmware_vil/bin/vmnet-dhcpd"
        VMNET_NETIFUP="/opt/vmware/vmware_vil/bin/vmnet-netifup"
        
        VMX_PID=`pidof ${VMWARE_VMX}`
        if [ "x$VMX_PID" = "x" ]; then
            VMX_PID= `pidof ${VMWARE_VMX_DEBUG}`
            if [ "x$VMX_PID" = "x" ]; then
                VMX_PID=`pidof ${VMWARE_VMX_STATS}`
            fi
        fi

        VIRT_PIDS=(`pidof ${VMNET_DHCPD}` ${VMX_PID} `pidof ${VMNET_NETIFUP}`)
        for pid in ${VIRT_PIDS[*]}; do
            # ignore files that are very large to copy
            if [ -d /proc/${pid} ]; then
                mkdir -p ${STAGE_VSP_DIR}/proc/${pid}
                for proc_file in `find /proc/$pid -type f 2>/dev/null| egrep -v "kcore|kmsg|acpi|pagemap"`; do
                    dir_name=`(dirname $proc_file)`
                    if [ ! -d ${STAGE_VSP_DIR}/${dir_name} ]; then
                        mkdir -p ${STAGE_VSP_DIR}/ ${dir_name}
                    fi
                    cp -p ${proc_file} ${STAGE_VSP_DIR}/${dir_name}/`basename ${proc_file}` 2>/dev/null
                done
            fi
        done
        
        # copy vmware-admin directory

        # /tmp/vmware-admin is moved to /var/tmp/vmware-admin for Lanai-ex
        # If /tmp/vmware-admin is not a symlink, copy content to /var/tmp/vmware-admin,
        # delete directory and symlink it to /var/tmp/vmware-admin
        # /tmp/vmware-admin is hosted on tmfs so reboot can reset this symlink
        TMFS_VMWARE_ADMIN="/tmp/vmware-admin"
        VAR_VMWARE_ADMIN="/var/tmp/vmware-admin"
        if [ -d ${TMFS_VMWARE_ADMIN} -a ! -L ${TMFS_VMWARE_ADMIN} ]; then
            cp -a ${TMFS_VMWARE_ADMIN}/. ${VAR_VMWARE_ADMIN}
            rm -rf ${TMFS_VMWARE_ADMIN}
            ls -s ${VAR_VMWARE_ADMIN} ${TMFS_VMWARE_ADMIN}
        elif [ ! -d ${TMFS_VMWARE_ADMIN} ] ; then
            ln -s ${VAR_VMWARE_ADMIN} ${TMFS_VMWARE_ADMIN}
        fi
        cp -ap ${VAR_VMWARE_ADMIN} $STAGE_VSP_DIR/vmware-admin
        rm -f $STAGE_VSP_DIR/vmware-admin/fuseMount*
        rm -f $STAGE_VSP_DIR/vmware-admin/apploader*
       

       #Write bridge stats
       /usr/bin/printf "================================================================================\n" >  ${STAGE_VSP_DIR}/bridge.txt
       /usr/bin/printf "/usr/sbin/brctl show output\n" >> ${STAGE_VSP_DIR}/bridge.txt
       /usr/bin/printf "================================================================================\n" >>  ${STAGE_VSP_DIR}/bridge.txt
       /usr/sbin/brctl show >> ${STAGE_VSP_DIR}/bridge.txt 2>&1
       /usr/bin/printf "================================================================================\n" >>  ${STAGE_VSP_DIR}/bridge.txt
       /usr/bin/printf "/usr/sbin/brctl showmacs aux output\n" >> ${STAGE_VSP_DIR}/bridge.txt
       /usr/bin/printf "================================================================================\n" >>  ${STAGE_VSP_DIR}/bridge.txt
       /usr/sbin/brctl showmacs aux >> ${STAGE_VSP_DIR}/bridge.txt 2>&1
       /usr/bin/printf "================================================================================\n" >>  ${STAGE_VSP_DIR}/bridge.txt
       /usr/bin/printf "/usr/sbin/brctl showstp aux output\n" >> ${STAGE_VSP_DIR}/bridge.txt
       /usr/bin/printf "================================================================================\n" >>  ${STAGE_VSP_DIR}/bridge.txt
       /usr/sbin/brctl showstp aux >> ${STAGE_VSP_DIR}/bridge.txt 2>&1
       /usr/bin/printf "================================================================================\n" >>  ${STAGE_VSP_DIR}/bridge.txt
       /usr/bin/printf "/usr/sbin/brctl showmacs primary output\n" >> ${STAGE_VSP_DIR}/bridge.txt
       /usr/bin/printf "================================================================================\n" >>  ${STAGE_VSP_DIR}/bridge.txt
       /usr/sbin/brctl showmacs primary >> ${STAGE_VSP_DIR}/bridge.txt 2>&1
       /usr/bin/printf "================================================================================\n" >>  ${STAGE_VSP_DIR}/bridge.txt
       /usr/bin/printf "/usr/sbin/brctl showstp primary output\n" >> ${STAGE_VSP_DIR}/bridge.txt
       /usr/bin/printf "================================================================================\n" >>  ${STAGE_VSP_DIR}/bridge.txt
       /usr/sbin/brctl showstp primary >> ${STAGE_VSP_DIR}/bridge.txt 2>&1 

        #Write ESXi status to vsp_info.txt file
        /sbin/pidof mgmtd > /dev/null 2>&1
        MGMTD_RUNNING=$?
        if [ $MGMTD_RUNNING -eq 0 ]; then
            /usr/bin/printf "enable\nshow vsp\n" | /opt/tms/bin/cli --no-history > ${STAGE_VSP_DIR}/show_vsp_output.txt 2>&1
            /usr/bin/printf "enable\nshow vsp internal\n" | /opt/tms/bin/cli --no-history > ${STAGE_VSP_DIR}/show_vsp_internal_output.txt 2>&1
            /usr/bin/printf "enable\nshow vsp esxi version\n" | /opt/tms/bin/cli --no-history > ${STAGE_VSP_DIR}/show_vsp_esxi_version_output.txt 2>&1
        fi
        
        ESXI_CONFIG_DIR="${STAGE_VSP_DIR}/config/"
        
        #Copy state.tgz's as well
        mkdir -p  ${ESXI_CONFIG_DIR}
        cp -ap "/config/esxi" ${ESXI_CONFIG_DIR}

        # Run VMware's support tool by default, check if user turned it off
        VM_SUPPORT_BIN="/opt/vmware/vmware_vil/bin/vm-support"
        if [ $RSP_VMWARE_SUPPORT -eq 1  -a ${BRIEF} -eq 0 ]; then
            if [ -f $VM_SUPPORT ]; then
                PRIMARY_MAC="`ip link show dev primary | grep 'link\/ether' | awk '{ print $2 }' | sed 's/://g'`"
                ESXI_VM_PATH="/esxi/${PRIMARY_MAC}/esxi.vmx"
                start_time=`date +%s`
                ${VM_SUPPORT_BIN} -v ${ESXI_VM_PATH} -w ${STAGE_VSP_DIR} > /dev/null 2>&1 &

                /sbin/pidof mgmtd > /dev/null 2>&1
                MGMTD_RUNNING=$?
                if [ $MGMTD_RUNNING -eq 0 ]; then
                    #Spawn an mdreq action here to get the ESXi vm-support
                    #Delete left over vm-support-failed file marker if any
                    rm /esxi/.vm-support-failed
                    VM_SUPPORT_OUTPUT=`/opt/tms/bin/mdreq action /rbt/vsp/action/esxi/vm-support vmsupport_path string "${STAGE_VSP_DIR}/"`
                    is_vm_support_failed=`echo $VM_SUPPORT_OUTPUT | grep -E "Return code: 1"`
                    if [ "x$is_vm_support_failed" != "x" ]; then
                        touch /esxi/.vm-support-failed
                    fi
                else
                    echo "ESXi vm-support could not be collected because mgmtd is not running. " >> ${STAGE_VSP_DIR}/vm_support_timing.txt
                fi
                wait
                end_time=`date +%s`
                echo "vm-support took:$((end_time-start_time)) seconds" >> ${STAGE_VSP_DIR}/vm_support_timing.txt
            fi
         fi

    fi # Virtualization support files

    lsmod | grep iptable >& /dev/null
    if [ $? -eq 0 ]; then
        do_command_output_file "iptables-save" ${STAGE_DIR}/iptables.txt
    fi

    # Cloud metadata
    do_safe_cp /var/etc/opt/tms/cloud/instance-metadata ${STAGE_DIR}

    # discovery files
    do_safe_cp /var/opt/tms/discovery_creds.txt ${STAGE_DIR}
    do_safe_cp /var/opt/tms/dshost.txt ${STAGE_DIR}
    do_safe_cp /var/opt/rbt/discovery_config_mgmtd_to_dc.xml ${STAGE_DIR}
    do_safe_cp /var/opt/rbt/discovery_config_dc_to_mgmtd.xml ${STAGE_DIR}

    # watchdog
    do_safe_cp /etc/opt/tms/output/wdt.xml ${STAGE_DIR}

    # top output
    top -n 1 -d 1 -b > ${STAGE_DIR}/top_output

    # copy the sport log and sport.logrc files if they exist
    if [ $BRIEF -eq 0 ]; then
        do_safe_cp "/var/log/sport.log" ${STAGE_DIR}
        do_safe_cp "/etc/sport.logrc" ${STAGE_DIR}
    fi

    do_safe_cp /var/opt/rbt/main_interface ${STAGE_DIR}

    #/proc/rbt_utils & /proc/rbt_conntrack

    if [ -e /proc/rbt_utils ]; then
	cp -ap /proc/rbt_utils ${STAGE_DIR}
    fi

    if [ -e /proc/rbt_conntrack ]; then
        cp -ap /proc/rbt_conntrack ${STAGE_DIR}
    fi

    # ipv6
    if (($IPV6_RUNNING)); then
        local proc_dir=${KERNEL_PROC_DIR}/net
        local proc_sys_dir=${KERNEL_PROC_SYS_DIR}/net/ipv6
        local dst_dir=

        dst_dir=${proc_dir}/dev_snmp6
        mkdir -p ${dst_dir}
        cp -a /proc/net/dev_snmp6/inpath* ${dst_dir}
        cp -a /proc/net/dev_snmp6/primary ${dst_dir}
        cp -a /proc/net/dev_snmp6/aux ${dst_dir}

        dst_dir=${proc_sys_dir}/neigh
        mkdir -p ${dst_dir}
        cp -a /proc/sys/net/ipv6/neigh/inpath* ${dst_dir}
        cp -a /proc/sys/net/ipv6/neigh/primary ${dst_dir}
        cp -a /proc/sys/net/ipv6/neigh/aux ${dst_dir}

        dst_dir=${proc_sys_dir}/conf
        mkdir -p ${dst_dir}
        cp -a /proc/sys/net/ipv6/conf/inpath* ${dst_dir}
        cp -a /proc/sys/net/ipv6/conf/primary ${dst_dir}
        cp -a /proc/sys/net/ipv6/conf/aux ${dst_dir}

        do_safe_cp /proc/net/ip6_route ${proc_dir}
        do_safe_cp /proc/net/rt6_stats ${proc_dir}
        do_safe_cp /proc/net/snmp6 ${proc_dir}

        dst_dir=${proc_dir}/stat
        mkdir -p ${dst_dir}
        do_safe_cp /proc/net/stat/ndisc_cache ${dst_dir}
    fi

    # Useful for ipblade
    mkdir -p ${KERNEL_PROC_DIR}/net/stat
    do_safe_cp /proc/net/packet ${KERNEL_PROC_DIR}/net
    do_safe_cp /proc/net/stat/arp_cache ${KERNEL_PROC_DIR}/net/stat
    do_safe_cp /proc/net/stat/rt_cache ${KERNEL_PROC_DIR}/net/stat

    # rbtring
    local rbtring_entries=" \
                            /proc/net/rbt-packet         \
                            /proc/net/rbt-packet-stats   \
                          "
    for entry in $rbtring_entries; do
        if [ -e "$entry" ]; then
            do_command_output_file "cat $entry" ${STAGE_DIR}/rbtring.txt
        fi
    done

    #
    # aha card output
    #
    if [ -c /dev/sdrcard ] && [ -x /opt/rbt/bin/ahazip ]; then
	do_command_output "/opt/rbt/bin/ahazip -systeminfo"
	do_command_output "/opt/rbt/bin/ahazip -V=0"
	do_command_output "/opt/rbt/bin/ahazip -temp=0"
    fi

    # copy all app level tracing logs
    for app_trace_file in /var/log/app_trace.log*; do
        do_safe_cp "$app_trace_file" ${STAGE_DIR}
    done

    # virtual steelhead silicom bypass files
    if [ -d /var/run/vsh_bypass ]; then
	tar zcvf ${STAGE_DIR}/vsh_bypass.tgz /var/run/vsh_bypass
    fi

    #
    # VE Specific sysdump collection
    #
    if [ -f /etc/ve_sysdump_calls.sh ]; then
        . /etc/ve_sysdump_calls.sh
        ve_sysdump_graft_3
    fi

    #
    # multi nic files
    #
    do_safe_cp /config/mgmt_mac_naming ${STAGE_DIR}

    # Akamai Cloud Proxy configuration
    do_safe_cp /var/etc/opt/tms/output/acp_rvbd.cfg ${STAGE_DIR}

    # Applictaion Visibility stats
    if [ $STATS -ne 0 ] ; then
	/opt/rbt/bin/pg_dump -Fc -f ${STAGE_DIR}/app_vis.db -Uqos
    fi
}

# -----------------------------------------------------------------------------
# Graft point #4 for sysdump.sh
#
# This is called to generate the list of log files to dump
#
HAVE_SYSDUMP_GRAFT_4=y
sysdump_graft_4()
{
    graft4='-o -name memlog* -print -o -name host_messages* -print -o -name mcelog* -print'
}

# -----------------------------------------------------------------------------
# Graft point #5 for sysdump.sh
#
# This is called to copy over SSL certs (not keys) as a part of the dump
# This is also called to copy over SSL server certs global exportable flag 
# as a part of the dump
# 
#
HAVE_SYSDUMP_GRAFT_5=y
sysdump_graft_5()
{
        SERVER_CERTS_PATH='/var/opt/rbt/ssl/server_certs'
        INFO_FILE='ssl_server_certs_exportable_info.txt'
        SEC_VAULT_MOUNTED=`/sbin/secure_vault_check_mount.sh`

        echo "================================================" >> ${STAGE_DIR}/${INFO_FILE}
        echo "Secure Vault Unlocked: " ${SEC_VAULT_MOUNTED} >> ${STAGE_DIR}/${INFO_FILE}
        if [ "x${SEC_VAULT_MOUNTED}" = "xtrue" ]; then
            cp -a ${SERVER_CERTS_PATH}/global_exportable ${STAGE_DIR}/global_exportable
            echo "Allow exporting of SSL server certificates: " `cat ${SERVER_CERTS_PATH}/global_exportable` >> ${STAGE_DIR}/${INFO_FILE}
        fi
        echo "================================================" >> ${STAGE_DIR}/${INFO_FILE}

	# we're including SSL certs only if unlimited logs have
	# been asked for. Support staff know about this behavior.
	if [ $UNLIMITED_LOGS -ne 1 ]
	then
		return
	fi

	ENCFS_MNT_TYPE='encfs' # this indicates an fs of type=encfs is present
	PROC_MOUNTS=`cat /proc/mounts`
	SSL_SERVER_DIR_PATH='/var/opt/rbt/ssl/server_certs/names'
	EXPORTABLE_FILE='exportable'
	CERT_EXTENSION='.cert.pem'
	NO_CERTS_MSG='Secure vault was not mounted. Could not copy certs'
	EXPORTABLE_FLAG_TRUE='true'

	# This is where we'll copy the certs
	SERVER_CERTS_DEST_DIR=${STAGE_DIR}/server_certs

	# Ensure that the dest dir exists
	mkdir -p $SERVER_CERTS_DEST_DIR

	if [ "x$SEC_VAULT_MOUNTED" = "xfalse" ]
	then
        # sec vault was NOT mounted
		echo ${NO_CERTS_MSG} > ${SERVER_CERTS_DEST_DIR}/no_certs.txt
	else
		# sec vault is mounted!
		# copy the certs, if they are marked as exportable
		for server in ${SSL_SERVER_DIR_PATH}/* ;
		do
		  if [ -f ${server}/${EXPORTABLE_FILE} ]
		  then
			  EXPORTABLE_FLAG=`cat $server/$EXPORTABLE_FILE`
		  fi

 		  # copy files with .cert.pem extension if its marked as exportable
		  if [ "$EXPORTABLE_FLAG" = "$EXPORTABLE_FLAG_TRUE" ]
		  then
			  cp -a ${server}/*${CERT_EXTENSION} ${SERVER_CERTS_DEST_DIR}
		  fi
		done
	fi
}

# -----------------------------------------------------------------------------
# Graft point #6 for sysdump.sh
#
# Sysdump entries that require mgmtd to be running
#
HAVE_SYSDUMP_GRAFT_6=y
sysdump_graft_6()
{
    /usr/bin/printf "enable\nshow info\n" | /opt/tms/bin/cli --no-history > ${STAGE_DIR}/show-info-output.txt 2>&1
}

# -----------------------------------------------------------------------------
# Graft point #7 for sysdump.sh
#
# This is called to copy http prepop log files to sysdump.
#
HAVE_SYSDUMP_GRAFT_7=y
sysdump_graft_7()
{
    HTTP_PREPOP_DIR=${STAGE_DIR}/http_prepop

    mkdir -p ${HTTP_PREPOP_DIR}

    # copy all app level tracing logs
    for log_file in /var/tmp/http_prepop/*;
    do
        do_safe_cp "$log_file" ${HTTP_PREPOP_DIR}
    done
}

# -----------------------------------------------------------------------------
# Graft points for firstboot.sh.  Below are functions which get called
# from various points within that script.
#

# .............................................................................
# Graft point #1.  This is called at the very beginning, before the /var
# upgrade is performed
#
HAVE_FIRSTBOOT_GRAFT_1=y
firstboot_graft_1()
{
    #
    # If there is no customer-specific version file, this system is 
    # probably from before we did the customer/generic split of the
    # /var upgrade mechanism.  Copy the baseline version number to the
    # customer version number, so we can do any necessary upgrades.
    # Moving forward, this file will always be here; this is a one-time
    # migration.
    #
    if [ ! -f /var/var_version_rbt.sh ]; then
        cp /var/var_version.sh /var/var_version_rbt.sh
    fi
}

# .............................................................................
# Graft point #2.  This is called after the /var upgrade is performed,
# and after the grub.conf is regenerated.
#
HAVE_FIRSTBOOT_GRAFT_2=y
firstboot_graft_2()
{
    logger -p user.notice "RBT firstboot graft 2"

    chkconfig --add irqbalance

    # make sure rbtkmod gets run during boot
    chkconfig --add rbtkmod
    chkconfig --add csoftwatch
    chkconfig --add softwatch
    chkconfig --add vservers
    chkconfig --add rsisinit
    chkconfig --add link_control
    chkconfig --add mcelogd
    MFG_TYPE=`/opt/tms/bin/hald_model -m`
    if [ "$MFG_TYPE" = "rvbd_ex" ]; then
	chkconfig --add cgconfig
	chkconfig --add cgred
    fi

    # if repartitioning, don't do anything here
    if [ "x$RBT_REPARTITION_IN_PROGRESS" = "x1" ]; then
	unset RBT_REPARTITION_IN_PROGRESS
	return 0
    fi
}

create_symlink()
{
    symlink="$2"
    target="$1"
    actual_target=`readlink "${symlink}"`
    if [ "$actual_target" != "$target" ]; then
        logger -p user.notice "Creating ${symlink} link..."
        rm -f "${symlink}"
        ln -s "${target}" "${symlink}"
    fi

}

# If a given link doesn't point to the desired target, recreate the link with
# the desired target. This function is useful since some buggy kernels running
# on Steelheads don't create long symlinks correctly during upgrades.
check_recreate_bad_symlink()
{
    symlink="$2"
    target="$1"
    actual_target=`readlink "${symlink}"`
    if [ "$actual_target" != "$target" ]; then
        logger -p user.notice "${actual_target} symlink doesn't match ${target} for ${symlink}"
        logger -p user.notice "Recreating ${symlink} link..."
        rm -f "${symlink}"
        ln -s "${target}" "${symlink}"
    fi
}

# Same as check_recreate_bad_symlink() above, but doesn't create a symlink if
# there's not already one (found to be corrupted) there.
check_recreate_bad_existing_symlink()
{
    symlink="$2"
    target="$1"
    actual_target=`readlink "${symlink}"`
    if [[ "$actual_target" != "$target" && "$actual_target" != "" ]]; then
        logger -p user.notice  "${actual_target} symlink doesn't match ${target} for ${symlink}"
        logger -p user.notice "Recreating ${symlink} link..."
        rm -f "${symlink}"
        ln -s "${target}" "${symlink}"
    fi
}

# .............................................................................
# Graft point #3.  This is called at the very end, after the rest of the
# upgrade has been performed
#
HAVE_FIRSTBOOT_GRAFT_3=y
firstboot_graft_3()
{
    logger -p user.notice "RBT firstboot graft 3"

    if [ "${MOBO}" != "BOB-MOBO" ]; then
        MFG_TYPE=`/opt/tms/bin/hald_model -m`
        if [ "$MFG_TYPE" = "rvbd_ex" ]; then
            # EX only needs /etc/vmware linked
            check_recreate_bad_symlink \
                "/opt/vmware/vmware_vil/etc/vmware" "/etc/vmware"
        else
            # Non-EX, non BOBv0 box.
            PREFIX="/proxy/__RBT_VSERVER_SHELL__/vmware_server"
            check_recreate_bad_symlink \
                "${PREFIX}/etc/vmware" "/etc/vmware"
            check_recreate_bad_symlink \
                "${PREFIX}/etc/vmware/pam.d/vmware-authd" "/etc/pam.d/vmware-authd"
            check_recreate_bad_symlink \
                "${PREFIX}/etc/vmware-vix" "/etc/vmware-vix"
            check_recreate_bad_symlink \
                "${PREFIX}/etc/vmware-vix-disklib" "/etc/vmware-vix-disklib"
            check_recreate_bad_symlink \
                "${PREFIX}/usr/bin/vmware" "/usr/bin/vmware"
            check_recreate_bad_symlink \
                "${PREFIX}/usr/sbin/vmware" "/usr/sbin/vmware"
            check_recreate_bad_symlink \
                "${PREFIX}/usr/lib/vmware" "/usr/lib/vmware"
            check_recreate_bad_symlink \
                "${PREFIX}/usr/lib/vmware-vix" "/usr/lib/vmware-vix"
            check_recreate_bad_symlink \
                "${PREFIX}/usr/lib/vmware-vix-disklib" "/usr/lib/vmware-vix-disklib"
            check_recreate_bad_symlink \
                "${PREFIX}/usr/share/vmware" "/usr/share/vmware"
            check_recreate_bad_symlink \
                "${PREFIX}/usr/share/vmware-vix" "/usr/share/vmware-vix"

            check_recreate_bad_existing_symlink \
                "/usr/lib/vmware/webAccess/tomcat/apache-tomcat-6.0.16/webapps/ui/WEB-INF/classes/log4j.properties" \
                "${PREFIX}/etc/vmware/webAccess/log4j.properties"
            check_recreate_bad_existing_symlink \
                "/usr/lib/vmware/webAccess/tomcat/apache-tomcat-6.0.16/webapps/ui/WEB-INF/classes/proxy.properties" \
                "${PREFIX}/etc/vmware/webAccess/proxy.properties"
            check_recreate_bad_existing_symlink \
                "/usr/lib/vmware/webAccess/tomcat/apache-tomcat-6.0.16/webapps/ui/WEB-INF/classes/login.properties" \
                "${PREFIX}/etc/vmware/webAccess/login.properties"
            check_recreate_bad_existing_symlink \
                "${PREFIX}/etc/rc.d/init.d/vmware" \
                "${PREFIX}/etc/rc.d/init.d/vmware-core"
            check_recreate_bad_existing_symlink \
                "${PREFIX}/etc/rc.d/init.d/vmware" \
                "${PREFIX}/etc/rc.d/init.d/vmware-mgmt"
            check_recreate_bad_existing_symlink \
                "${PREFIX}/etc/rc.d/init.d/vmware" \
                "${PREFIX}/etc/rc.d/init.d/vmware-autostart"
            check_recreate_bad_existing_symlink \
                "${PREFIX}/etc/rc.d/init.d/vmware" \
                "${PREFIX}/etc/rc.d/rc0.d/K08vmware"
            check_recreate_bad_existing_symlink \
                "${PREFIX}/etc/rc.d/init.d/vmware" \
                "${PREFIX}/etc/rc.d/rc2.d/S90vmware"
            check_recreate_bad_existing_symlink \
                "${PREFIX}/etc/rc.d/init.d/vmware" \
                "${PREFIX}/etc/rc.d/rc2.d/K08vmware"
            check_recreate_bad_existing_symlink \
                "${PREFIX}/etc/rc.d/init.d/vmware" \
                "${PREFIX}/etc/rc.d/rc3.d/S90vmware"
            check_recreate_bad_existing_symlink \
                "${PREFIX}/etc/rc.d/init.d/vmware" \
                "${PREFIX}/etc/rc.d/rc3.d/K08vmware"
            check_recreate_bad_existing_symlink \
                "${PREFIX}/etc/rc.d/init.d/vmware" \
                "${PREFIX}/etc/rc.d/rc5.d/S90vmware"
            check_recreate_bad_existing_symlink \
                "${PREFIX}/etc/rc.d/init.d/vmware" \
                "${PREFIX}/etc/rc.d/rc5.d/K08vmware"
            check_recreate_bad_existing_symlink \
                "${PREFIX}/etc/rc.d/init.d/vmware" \
                "${PREFIX}/etc/rc.d/rc6.d/K08vmware"
            check_recreate_bad_existing_symlink \
                "/var/log/vmware/webAccess" \
                "${PREFIX}/usr/lib/vmware/webAccess/tomcat/apache-tomcat-6.0.16/logs"
            check_recreate_bad_existing_symlink \
                "/var/log/vmware/webAccess/work" \
                "${PREFIX}/usr/lib/vmware/webAccess/tomcat/apache-tomcat-6.0.16/work"
            check_recreate_bad_existing_symlink \
                "./vmware-hostd" \
                "${PREFIX}/usr/lib/vmware/bin/vmware-vim-cmd"
            check_recreate_bad_existing_symlink \
                "./vmware-hostd" \
                "${PREFIX}/usr/lib/vmware/bin/vmware-vimsh"
            check_recreate_bad_existing_symlink \
                "/usr/share/vmware/EULA" \
                "${PREFIX}/usr/lib/vmware/share/EULA.txt"
            check_recreate_bad_existing_symlink \
                "/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/lib32/libssl.so.0.9.7" \
                "${PREFIX}/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/bin32/libssl.so.0.9.7"
            check_recreate_bad_existing_symlink \
                "/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/lib32/libcrypto.so.0.9.7" \
                "${PREFIX}/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/bin32/libcrypto.so.0.9.7"
            check_recreate_bad_existing_symlink \
                "/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/lib64/libssl.so.0.9.7" \
                "${PREFIX}/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/bin64/libssl.so.0.9.7"
            check_recreate_bad_existing_symlink \
                "/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/lib64/libcrypto.so.0.9.7" \
                "${PREFIX}/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/bin64/libcrypto.so.0.9.7"
            check_recreate_bad_existing_symlink \
                "libvixDiskLib.so.1" \
                "${PREFIX}/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/lib32/libvixDiskLib.so"
            check_recreate_bad_existing_symlink \
                "libvixDiskLibVim.so.1" \
                "${PREFIX}/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/lib32/libvixDiskLibVim.so"
            check_recreate_bad_existing_symlink \
                "libcurl.so.4.0.0" \
                "${PREFIX}/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/lib32/libcurl.so.4"
            check_recreate_bad_existing_symlink \
                "libvixDiskLibVim.so.1.1.0" \
                "${PREFIX}/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/lib32/libvixDiskLibVim.so.1"
            check_recreate_bad_existing_symlink \
                "libgobject-2.0.so.0.1200.9" \
                "${PREFIX}/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/lib32/libgobject-2.0.so.0"
            check_recreate_bad_existing_symlink \
                "libvixDiskLib.so.1.1.0" \
                "${PREFIX}/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/lib32/libvixDiskLib.so.1"
            check_recreate_bad_existing_symlink \
                "libglib-2.0.so.0.1200.9" \
                "${PREFIX}/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/lib32/libglib-2.0.so.0"
            check_recreate_bad_existing_symlink \
                "libgthread-2.0.so.0.1200.9" \
                "${PREFIX}/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/lib32/libgthread-2.0.so.0"
            check_recreate_bad_existing_symlink \
                "libvixDiskLib.so.1" \
                "${PREFIX}/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/lib64/libvixDiskLib.so"
            check_recreate_bad_existing_symlink \
                "libvixDiskLibVim.so.1" \
                "${PREFIX}/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/lib64/libvixDiskLibVim.so"
            check_recreate_bad_existing_symlink \
                "libcurl.so.4.0.0" \
                "${PREFIX}/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/lib64/libcurl.so.4"
            check_recreate_bad_existing_symlink \
                "libvixDiskLibVim.so.1.1.0" \
                "${PREFIX}/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/lib64/libvixDiskLibVim.so.1"
            check_recreate_bad_existing_symlink \
                "libgobject-2.0.so.0.1200.9" \
                "${PREFIX}/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/lib64/libgobject-2.0.so.0"
            check_recreate_bad_existing_symlink \
                "libvixDiskLib.so.1.1.0" \
                "${PREFIX}/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/lib64/libvixDiskLib.so.1"
            check_recreate_bad_existing_symlink \
                "libglib-2.0.so.0.1200.9" \
                "${PREFIX}/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/lib64/libglib-2.0.so.0"
            check_recreate_bad_existing_symlink \
                "libgthread-2.0.so.0.1200.9" \
                "${PREFIX}/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/lib64/libgthread-2.0.so.0"
            check_recreate_bad_existing_symlink \
                "libvixDiskLib.so.1" \
                "${PREFIX}/usr/lib/vmware-vix-disklib/lib/libvixDiskLib.so"

            CUR_ARCH=`/bin/uname -i`
            if [ "$CUR_ARCH" == "x86_64" ]; then
                check_recreate_bad_existing_symlink \
                    "../libjsig.so" \
                    "${PREFIX}/usr/lib/vmware/webAccess/java/jre1.5.0_15/lib/amd64/server/libjsig.so"
                check_recreate_bad_existing_symlink \
                    "libcrypto.so.0.9.8" \
                    "${PREFIX}/usr/lib/vmware-vix/VIServer-2.0.0/64bit/libcrypto.so.0"
                check_recreate_bad_existing_symlink \
                    "libssl.so.0.9.8" \
                    "${PREFIX}/usr/lib/vmware-vix/VIServer-2.0.0/64bit/libssl.so.0"
                check_recreate_bad_existing_symlink \
                    "libcurl.so.4.0.1" \
                    "${PREFIX}/usr/lib/vmware-vix/VIServer-2.0.0/64bit/libcurl.so.4"
                check_recreate_bad_existing_symlink \
                    "libglib-2.0.so.0.1200.9" \
                    "${PREFIX}/usr/lib/vmware-vix/VIServer-2.0.0/64bit/libglib-2.0.so.0"
                check_recreate_bad_existing_symlink \
                    "libgobject-2.0.so.0.1200.9" \
                    "${PREFIX}/usr/lib/vmware-vix/VIServer-2.0.0/64bit/libgobject-2.0.so.0"
                check_recreate_bad_existing_symlink \
                    "libgthread-2.0.so.0.1200.9" \
                    "${PREFIX}/usr/lib/vmware-vix/VIServer-2.0.0/64bit/libgthread-2.0.so.0"
                check_recreate_bad_existing_symlink \
                    "libgmodule-2.0.so.0.1200.9" \
                    "${PREFIX}/usr/lib/vmware-vix/VIServer-2.0.0/64bit/libgmodule-2.0.so.0"
                check_recreate_bad_existing_symlink \
                    "libxml2.so.2.6.26" \
                    "${PREFIX}/usr/lib/vmware-vix/VIServer-2.0.0/64bit/libxml2.so.2"
                check_recreate_bad_existing_symlink \
                    "vix-disklib-64.pc" \
                    "${PREFIX}/usr/lib/vmware-vix-disklib/lib/pkgconfig/vix-disklib.pc"
                check_recreate_bad_existing_symlink \
                    "vmware-vix-disklib/lib64/libvixDiskLib.so.1" \
                    "${PREFIX}/usr/lib/vmware-vix-disklib/lib/libvixDiskLib.so.1"
                check_recreate_bad_existing_symlink \
                    "/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/bin64/vmware-mount" \
                    "${PREFIX}/usr/lib/vmware-vix-disklib/bin/vmware-mount"
                check_recreate_bad_existing_symlink \
                    "/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/bin64/vmware-vdiskmanager" \
                    "${PREFIX}/usr/lib/vmware-vix-disklib/bin/vmware-vdiskmanager"
                check_recreate_bad_existing_symlink \
                    "/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/bin64/vmware-uninstall-vix-disklib.pl" \
                    "${PREFIX}/usr/lib/vmware-vix-disklib/bin/vmware-uninstall-vix-disklib.pl"

            elif [ "$CUR_ARCH" == "i386" ]; then
                check_recreate_bad_existing_symlink \
                    "../libjsig.so" \
                    "${PREFIX}/usr/lib/vmware/webAccess/java/jre1.5.0_15/lib/i386/client/libjsig.so"
                check_recreate_bad_existing_symlink \
                    "../libjsig.so" \
                    "${PREFIX}/usr/lib/vmware/webAccess/java/jre1.5.0_15/lib/i386/server/libjsig.so"
                check_recreate_bad_existing_symlink \
                    "../bin/javaws" \
                    "${PREFIX}/usr/lib/vmware/webAccess/java/jre1.5.0_15/javaws/javaws"
                check_recreate_bad_existing_symlink \
                    "libcrypto.so.0.9.8" \
                    "${PREFIX}/usr/lib/vmware-vix/VIServer-2.0.0/32bit/libcrypto.so.0"
                check_recreate_bad_existing_symlink \
                    "libssl.so.0.9.8" \
                    "${PREFIX}/usr/lib/vmware-vix/VIServer-2.0.0/32bit/libssl.so.0"
                check_recreate_bad_existing_symlink \
                    "libcurl.so.4.0.1" \
                    "${PREFIX}/usr/lib/vmware-vix/VIServer-2.0.0/32bit/libcurl.so.4"
                check_recreate_bad_existing_symlink \
                    "libglib-2.0.so.0.1200.9" \
                    "${PREFIX}/usr/lib/vmware-vix/VIServer-2.0.0/32bit/libglib-2.0.so.0"
                check_recreate_bad_existing_symlink \
                    "libgobject-2.0.so.0.1200.9" \
                    "${PREFIX}/usr/lib/vmware-vix/VIServer-2.0.0/32bit/libgobject-2.0.so.0"
                check_recreate_bad_existing_symlink \
                    "libgthread-2.0.so.0.1200.9" \
                    "${PREFIX}/usr/lib/vmware-vix/VIServer-2.0.0/32bit/libgthread-2.0.so.0"
                check_recreate_bad_existing_symlink \
                    "libgmodule-2.0.so.0.1200.9" \
                    "${PREFIX}/usr/lib/vmware-vix/VIServer-2.0.0/32bit/libgmodule-2.0.so.0"
                check_recreate_bad_existing_symlink \
                    "libxml2.so.2.6.26" \
                    "${PREFIX}/usr/lib/vmware-vix/VIServer-2.0.0/32bit/libxml2.so.2"
                check_recreate_bad_existing_symlink \
                    "vix-disklib-32.pc" \
                    "${PREFIX}/usr/lib/vmware-vix-disklib/lib/pkgconfig/vix-disklib.pc"
                check_recreate_bad_existing_symlink \
                    "vmware-vix-disklib/lib32/libvixDiskLib.so.1" \
                    "${PREFIX}/usr/lib/vmware-vix-disklib/lib/libvixDiskLib.so.1"
                check_recreate_bad_existing_symlink \
                    "/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/bin32/vmware-mount" \
                    "${PREFIX}/usr/lib/vmware-vix-disklib/bin/vmware-mount"
                check_recreate_bad_existing_symlink \
                    "/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/bin32/vmware-vdiskmanager" \
                    "${PREFIX}/usr/lib/vmware-vix-disklib/bin/vmware-vdiskmanager"
                check_recreate_bad_existing_symlink \
                    "/usr/lib/vmware-vix-disklib/lib/vmware-vix-disklib/bin32/vmware-uninstall-vix-disklib.pl" \
                    "${PREFIX}/usr/lib/vmware-vix-disklib/bin/vmware-uninstall-vix-disklib.pl"
            fi
            # Link the /rsp symlinks
            create_symlink \
                "/proxy/__RBT_VSERVER_SHELL__/rsp2/packages" \
                "/rsp/packages"
            create_symlink \
                "/proxy/__RBT_VSERVER_SHELL__/rsp2/backup" \
                "/rsp/backups"
            create_symlink \
                "/proxy/__RBT_VSERVER_SHELL__/rsp2/images" \
                "/rsp/images"
        fi
    else
        # Link the /rsp symlinks
        MAC=`vmware-rpctool 'info-get guestinfo.hostprimarymac' | sed 's/://g'`
        DATASTORE="local_${MAC}"
        create_symlink \
            "/esxi/vmfs/volumes/${DATASTORE}/__RBT_VSERVER_SHELL__/rsp3/packages" \
            "/rsp/packages"
        create_symlink \
            "/esxi/vmfs/volumes/${DATASTORE}/__RBT_VSERVER_SHELL__/rsp3/backup" \
            "/rsp/backups"
    fi
}


# .............................................................................
# Graft point #4.  This is called to fix the Intel 82574 management mode.
# On Redfins we want to disable the BMC management by modifying the NVM 
# settings on the primary interface. This will allow the interface to be
# shutdown when ifconfig primary down is done. Not all products need this 
# hence added as a graft point
#
HAVE_FIRSTBOOT_GRAFT_4=y
firstboot_graft_4()
{
    logger -p user.notice "RBT firstboot graft 4"

    magic=0x10d38086

    if [ ! -x $ETHTOOL ]; then
        echo "$ETHTOOL is missing"
        return 1
    fi

    if [ ! -x $EXPR ]; then
        echo "$EXPR is missing"
        return 1
    fi

    if [ -z $1 ]; then
        return 1
    fi

    eth=$(basename $1)

    #
    # Bug 100557, disable managment mode for Intel 82574
    # The bits 5 and 6 of offset 0x1f on 82574 need to be 0 to dsisable mng mode
    #
    mng=`$ETHTOOL -e $eth offset 0x1f length 1 | grep 1f | tr -d " \t"`
    start=`$EXPR ${#mng} - 1`
    mng=`$EXPR substr $mng $start 2`
    mng="0x${mng}"

    mng=`printf "%d" $mng`

    res=$(( mng & 0x60 ))
    if [ $res -ne 0 ]; then #MNG is enabled
        mng=$((mng & 0x9F))
        `$ETHTOOL -E $eth magic $magic offset 0x1f value $mng 2>/dev/null`
        if [ $? -eq 0 ]; then
            echo "Successfully disabled management mode of interface $eth."
            REBOOT_NEEDED=1
        else
            echo "Failed to disable management mode of interface $eth!"
        fi
    fi

    #
    # Bug 108072: fix potential packets drop problem, change value at offset 0x1e
    # from 0x58 to 0x5a
    #

    pwset=`$ETHTOOL -e $eth offset 0x1e length 1 | grep 1e | tr -d " \t"`

    start=`$EXPR ${#pwset} - 1`
    pwset=`$EXPR substr $pwset $start 2`

    pwset="0x${pwset}"
    pwset=`printf "%d" $pwset`

    if [ $pwset -eq 2 ]; then #the value was wrong, correct it.
        `$ETHTOOL -E $eth magic $magic offset 0x1e value 0x5a 2>/dev/null`
    fi

    res=$(( pwset & 0x2 ))
    if [ $res -eq 0 ]; then #need to disable power saving
        pwset=$((pwset | 0x2))
        `$ETHTOOL -E $eth magic $magic offset 0x1e value $pwset 2>/dev/null`
        if [ $? -eq 0 ]; then
            echo "Successfully disabled problematic power saving of $eth."
            REBOOT_NEEDED=1
        else
            echo "Failed to disable problematic power saving of $eth!"
        fi
    fi

}


# -----------------------------------------------------------------------------
# Graft points for mkver.sh.  Below are functions which get called
# from various points within that script.
#

# .............................................................................
# Graft point #1.  This is called right before the version string is 
# constructed
#
HAVE_MKVER_GRAFT_1=y
mkver_graft_1()
{
    BUILD_PROD_NAME=${BUILD_PROD_CUSTOMER_LC}_${BUILD_PROD_ID_LC}
}

# .............................................................................
# Graft point #2.  This is called right after the version string is
# constructed
#
HAVE_MKVER_GRAFT_2=n
# mkver_graft_2()
# {
# }


# -----------------------------------------------------------------------------
# Graft points for scrub.sh.  Below are functions which get called
# from various points within that script.
#

# .............................................................................
# Graft point #1.  This is called at the very beginning.
#
HAVE_SCRUB_GRAFT_1=y
scrub_graft_1()
{
    # specify licenses for "reset factory"
    BASE_LICENSES="BASE|EXCH|CIFS|PROFSRV"
    FLEX_LICENSES="${BASE_LICENSES}|MSPEC|RSP|GRANITE|SCPS"

    touch /var/opt/rbt/.clean
    touch /var/opt/rbt/.datastore_notif
    touch /var/opt/rbt/.dc_name

    # PFS scrubbing
    echo '
    enable
    configure terminal
    no pfs start
    no pfs enable
    no prepop enable
    ' | /opt/tms/bin/cli > /dev/null

    rm -rf /var/opt/rcu/*
    rm -rf /var/log/rcu/*
    rm -rf /var/log/samba/*
    rm -rf /var/samba/private/*
    rm -rf /var/samba/var/locks/*
    rm -f /etc/samba/smb.conf
    rm -f /etc/krb.realms
    rm -f /etc/krb5.conf
    rm -f /etc/samba/smb.conf.old
    rm -f /var/etc/krb.realms.old
    rm -f /var/etc/krb5.conf.old
    rm -f /var/opt/rbt/.do_autoconf
    rm -f /var/opt/rbt/.autoconf_status
    # remove application level trace logs while reset factory
    rm -f /var/log/app_trace.log*

    # Only do RSP2 specific scrubbing if ${RSP_ROOT_DIR}/.rsp_version exists
    RSP_ROOT_DIR=/proxy/__RBT_VSERVER_SHELL__/rsp2
    if [ -f $RSP_ROOT_DIR/.rsp_version ]; then
        RSP_TMPDIR=rsp_tmpdir
        RSP_TMPDIR_PATH=/proxy/$RSP_TMPDIR
        IMAGES=""
        PACKAGES=""
        rm -rf $RSP_TMPDIR_PATH
        mkdir -p $RSP_TMPDIR_PATH/images
        mkdir -p $RSP_TMPDIR_PATH/packages

        # Save RSP2 images and packages unless the caller explicitly
        # requests that we don't.
        if [ "$1" != "clear-rsp" ]; then 
            if [ -d /rsp/images/ ]; then
                IMAGES=`find /rsp/images/ -type f -print`
            fi
            if [ -d /rsp/packages/ ]; then
                PACKAGES=`find /rsp/packages/ -type f -print`
            fi
            if [ ! -z "$IMAGES" ]; then
                mv $IMAGES $RSP_TMPDIR_PATH/images
            fi
            if [ ! -z "$PACKAGES" ]; then
                mv $PACKAGES $RSP_TMPDIR_PATH/packages
            fi
        fi

        (cd /proxy && rm -rf `ls | grep -v lost+found | grep -v $RSP_TMPDIR`)

        if [ "$1" != "clear-rsp" ]; then
            IMAGES=`find $RSP_TMPDIR_PATH/images/ -type f -print`
            PACKAGES=`find $RSP_TMPDIR_PATH/packages/ -type f -print`
            if [ ! -z "$IMAGES" ]; then
                mkdir -p `readlink /rsp/images`
                mv $IMAGES /rsp/images
            fi
            if [ ! -z "$PACKAGES" ]; then
                mkdir -p `readlink /rsp/packages`
                mv $PACKAGES /rsp/packages
            fi
        fi
        rm -rf $RSP_TMPDIR_PATH
    fi

    # Secure vault conversion scrubbing
    rm -f /var/opt/rbt/.sv_converted
    rm -f /var/opt/rbt/.sv_needs_rekey
    rm -rf /var/opt/rbt/.sv_temp

    # BOB VSP scrubbing
    if [ "${MOBO}" == "BOB-MOBO" ]; then
        ${VSP_STATE_SCRUB_TOOL}
    fi

    # For EX capable models that is a not a G Model
    # BoBV2
    MFG_TYPE=`/opt/tms/bin/hald_model -m`
    if [ "${MFG_TYPE}" = "rvbd_ex" ]; then
        # Zeroed out local data store partitions
        /opt/tms/variants/rvbd_ex/bin/wipe_partitions.py

        for pid in $(pidof python | tr " " "\n" | sort -n)
        do
            cat "/proc/$pid/cmdline" | grep "vsp_vmware_vmx_wrapper.py" > /dev/null
            if [  $? -eq 0 ]
            then
                VMX_WRAPPER_PID=$pid
                break
            fi
        done

        # SIGUSR1 is used to tell vsp wrapper to kill vmware-vmx and sleep. This
        # is so that we can safely rm esxi.vmdk and local_datastore.vmdk
        if [ "x${VMX_WRAPPER_PID}" != "x" ]; then
            kill -s USR1 ${VMX_WRAPPER_PID}
            sleep 3
        fi

        (cd /esxi && rm -rf `ls | grep -v lost+found`)
        rm -rf /var/tmp/vmware-admin/*
    fi

    if [ -f /etc/ve_scrub_calls.sh ]; then
        . /etc/ve_scrub_calls.sh
        ve_scrub_graft_1 $1
    fi

    # Remove CPU check override
    rm -f /config/.no_cpu_check
}

HAVE_SCRUB_GRAFT_2=n
# scrub_graft_2()
# {
# }

# .............................................................................
# Graft point #3. This is called to check if the license is VBASE for VSH
#
HAVE_SCRUB_GRAFT_3=y
scrub_graft_3()
{
    INC_DB_PATH=/config/mfg/mfincdb
    MDDBREQ=/opt/tms/bin/mddbreq
    active_db=`cat /config/db/active`

    is_license_vbase=`echo $1 | grep -E "VBASE"`
    if [ "x$is_license_vbase" != "x" ]; then
        # if the license is VBASE save its token
        token_save=`$MDDBREQ  $active_db query get - /rbt/virtual/config/token | grep -m 1 "Value:" | cut -d' ' -f2`
        $MDDBREQ -c $INC_DB_PATH set modify "" /rbt/virtual/config/token string "$token_save"
    fi
}


INCLUDE_AFAIL_GRAFT=0
HALD_MODEL_PY="/opt/tms/bin/hald_model"
if [ -f ${HALD_MODEL_PY} ]; then
    INCLUDE_AFAIL_GRAFT=1
    MFG_TYPE=`/opt/tms/bin/hald_model -m`
fi

if [ ${INCLUDE_AFAIL_GRAFT} = 1 -a "x${MFG_TYPE}" = "xrvbd_ex" ]; then

# .....................................................................................
# Graft point #2. Check if process name is virtualization thread and prepare staging 
# area if needed
#
HAVE_EX_AFAIL_GRAFT_1=y
ex_afail_graft_1()
{
    if [ "x$PROCESS_NAME" = "xvmware_ws_interface_wrapper" -o \
	"x$PROCESS_NAME" = "xvsp_vmware_vmx_wrapper" ]; then
	IS_VIRT_PROCESS=1
	if [ "x${STAGING_AREA}" = "x" -a "x${PROCESS_NAME}" = "xvsp_vmware_vmx_wrapper" ]; then
	    # extract the process name, strip wrapper specific name
	    PROC_NAME="vmware-vmx"
	    HOSTNAME="`uname -n`"
	    TIMESTAMP="`date +%y%m%d-%H%M%S`"
	    STAGING_AREA="/var/opt/tms/snapshots/.staging/${HOSTNAME}-${PROC_NAME}-${TIMESTAMP}"

	    if [ ! -d ${STAGING_AREA} ]; then
	        /bin/mkdir -p ${STAGING_AREA}
	    fi

	    PRIMARY_MAC="`ip link show dev primary | grep 'link\/ether' | awk '{ print $2 }' | sed 's/://g'`"
	    VM_PATH=/esxi/${PRIMARY_MAC}
	    # pick the latest core file generated
	    CORE_FILE="`ls -tr ${VM_PATH} | grep ^core.* | sed -n '$p'`"
	    CORE_PATH=${VM_PATH}/${CORE_FILE}

	    if [ -f ${CORE_PATH} ]; then
	        BINARY_PATH=`file ${CORE_PATH} | grep vmware-vmx | awk ' { print $13 } ' | sed "s/'//g"`
	        HAS_COREDUMP=1
	    fi
	fi
    fi
}

# .....................................................................................
# Graft point #2. Generate vm_suport as part of snapshot package
#
HAVE_EX_AFAIL_GRAFT_2=y
ex_afail_graft_2()
{
    # staging area may be full while performing this operation
    VM_SUPPORT_OP="/tmp/vm_support_op.txt"
    if [ ! -f ${VM_SUPPORT_OP} ]; then
        touch ${VM_SUPPORT_OP}
    fi

    # generate vm-support before we prepare snapshot file
    FAILURE=0
    PRIMARY_MAC="`ip link show dev primary | grep 'link\/ether' | awk '{ print $2 }' | sed 's/://g'`"
    VM_SUPPORT_BIN="/opt/vmware/vmware_vil/bin/vm-support"
    if [ -f ${VM_SUPPORT_BIN} ]; then
        # /tmp/vmware-admin is moved to /var/tmp/vmware-admin for Lanai-ex
        # If /tmp/vmware-admin is not a symlink, copy content to /var/tmp/vmware-admin,
        # delete directory and symlink it to /var/tmp/vmware-admin
        # /tmp/vmware-admin is hosted on tmfs so reboot can reset this symlink
        TMFS_VMWARE_ADMIN="/tmp/vmware-admin"
        VAR_VMWARE_ADMIN="/var/tmp/vmware-admin"
        if [ ! -L ${TMFS_VMWARE_ADMIN} -a -d ${TMFS_VMWARE_ADMIN} ]; then
            cp -ap ${TMFS_VMWARE_ADMIN}/* ${VAR_VMWARE_ADMIN}
            rm -rf ${TMFS_VMWARE_ADMIN}
            ls -s ${VAR_VMWARE_ADMIN} ${TMFS_VMWARE_ADMIN}
        elif [ ! -d ${TMFS_VMWARE_ADMIN} ] ; then
            ln -s ${VAR_VMWARE_ADMIN} ${TMFS_VMWARE_ADMIN}
        fi

        ESXI_VM_PATH="/esxi/${PRIMARY_MAC}/esxi.vmx"
        ${VM_SUPPORT_BIN} -v ${ESXI_VM_PATH} -w ${STAGING_AREA} > ${VM_SUPPORT_OP} 2>&1 &
        wait
        # vm-support even on failure gives the exit code as '0', but tar operation 
        # internaly may have failed due to many reason (low disk space)
        FAILURE=`grep "The tar did not successfully complete!" ${VM_SUPPORT_OP} | wc -w`
    fi
    # remove the core.X file and vmmcoreX.tgz only if vmsupport is success
    if [ $FAILURE -eq 0 ]; then
        /bin/mv ${VM_SUPPORT_OP} ${STAGING_AREA}/vm_support_op.txt
        core_files=`find /esxi/${PRIMARY_MAC} -type f 2>/dev/null | grep core.*`
        for file in $core_files; do
            rm -f ${file} 2>/dev/null
        done
    fi
}

fi

# .....................................................................................
# Steelhead graft point #1.
# - check if process is wibindd
# - create the staging area
# - copy winbindd binary
# - copy last core
# - copy all other winbindd cores into STAGING/cores dir
#
HAVE_SH_AFAIL_GRAFT_1=y
sh_afail_graft_1()
{
    if [ "x$PROCESS_NAME" = x"winbind" ]; then
        IS_WINBIND_PROCESS=1
        if [ "x${STAGING_AREA}" = "x" -a "x${PROCESS_NAME}" = x"winbind" ]; then
            # extract the process name, strip wrapper specific name
            PROC_NAME="winbindd"
            HOSTNAME="`uname -n`"
            TIMESTAMP="`date +%y%m%d-%H%M%S`"
            STAGING_AREA="/var/opt/tms/snapshots/.staging/${HOSTNAME}-${PROC_NAME}-${TIMESTAMP}"

            WINBINDD_CORE_PATH=/var/log/samba/cores/winbindd
            # pick all the core files that may exist
            LAST_CORE_FILE="`ls -tr ${WINBINDD_CORE_PATH} | grep ^core.* | sed -n '$p'`"
            CORE_FILES="`ls -tr ${WINBINDD_CORE_PATH}/ | grep ^core.*`"
            CORE_PATH=${WINBINDD_CORE_PATH}/${LAST_CORE_FILE}

            if [ ! -z "$CORE_FILES" ]; then
                if [ ! -d ${STAGING_AREA} ]; then
		    /bin/mkdir -p ${STAGING_AREA}/cores
                fi

	        #find the binary name and copy the primary core file into the crash-dump dir
	        if [ -f ${CORE_PATH} ]; then
                   BINARY_PATH=`file ${CORE_PATH} | grep winbindd | awk ' { print $13 } ' | sed "s/'//g"`
	           /bin/cp ${CORE_PATH} ${STAGING_AREA}/
                   rm -f ${CORE_PATH}
                   HAS_COREDUMP=1
                fi
	  
	        #copy the binary
	        if [ -f ${BINARY_PATH} ]; then
		    /bin/cp ${BINARY_PATH} ${STAGING_AREA}/
	        fi

	        #copy other (child) core files over into the cores directory
	        for file in ${CORE_FILES}; do
                    if [ ${file} != ${LAST_CORE_FILE} ]; then
		        /bin/cp ${WINBINDD_CORE_PATH}/${file} ${STAGING_AREA}/cores/
                        rm -f ${WINBINDD_CORE_PATH}/${file}
                    fi
	        done
            fi
        fi
    fi
}

# .....................................................................................
# Graft point #1. 
#
HAVE_AFAIL_GRAFT_1=y
afail_graft_1()
{
    if [ "$HAVE_EX_AFAIL_GRAFT_1" = "y" ]; then 
	ex_afail_graft_1
    fi
    if [ "$HAVE_SH_AFAIL_GRAFT_1" = "y" ]; then 
	sh_afail_graft_1
    fi
}

# .....................................................................................
# Graft point #2. 
#
HAVE_AFAIL_GRAFT_2=y
afail_graft_2()
{
    if [ "$HAVE_EX_AFAIL_GRAFT_2" = "y" ]; then 
	ex_afail_graft_2
    fi
}



