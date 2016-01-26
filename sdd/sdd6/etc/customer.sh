#
#  Filename:  $Source$
#  Revision:  $Revision: 113228 $
#  Date:      $Date: 2012-07-20 11:50:35 -0700 (Fri, 20 Jul 2012) $
#  Author:    $Author: dano $
#
#  (C) Copyright 2003-2009 Riverbed Technology, Inc.
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
# This is used to run HP blade grafts if needed
#
HPP1_BLADE=0
if [ "${MOBO}" == "CMP-00HP1" ]; then
    HPP1_BLADE=1
fi

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
    SERIAL_NUMBER=`/opt/tms/bin/mdreq -v query get - /rbt/manufacture/serialnum`
    if [ $? -ne 0 ]; then
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
    if [ -f /etc/iproute2/rt_tables ]; then
        PROXYTABLES=`grep proxytable /etc/iproute2/rt_tables | sed -e 's,.*\t,,'`
        for proxy_table in ${PROXYTABLES}; do
            do_command_output "ip route list table ${proxy_table}"
        done
        FWMARKTABLES=`grep fwmarktable /etc/iproute2/rt_tables | sed -e 's,.*\t,,'`
        for fwmark_table in ${FWMARKTABLES}; do
            do_command_output "ip route list table ${fwmark_table}"
        done
    fi

    if [ -e /proc/nbt/0 ]; then
        PROC_FILES=`ls /proc/nbt/0`
        for proc_file in ${PROC_FILES}; do
            cp -p /proc/nbt/0/$proc_file ${STAGE_DIR}
        done
    fi

    if [ -e /proc/sys/nbt ]; then
        PROC_FILES=`ls /proc/sys/nbt`
        for proc_file in ${PROC_FILES}; do
            cp -p /proc/sys/nbt/$proc_file ${STAGE_DIR}
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
        cp -ap $VM_PROC_DIR ${STAGE_DIR}
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

    do_safe_cp /proc/sys/wdt/type ${STAGE_DIR}
    do_safe_cp /proc/slabinfo ${STAGE_DIR}
    do_safe_cp /proc/net/snmp ${STAGE_DIR}
    do_safe_cp /proc/modules ${STAGE_DIR}
    do_safe_cp /proc/net/softnet_stat ${STAGE_DIR}
    do_safe_cp /proc/net/scpsstat ${STAGE_DIR}
    do_safe_cp /proc/net/skipw105stat ${STAGE_DIR}
    do_safe_cp /proc/net/skipw105conn ${STAGE_DIR}

    # server shell files
    if [ -d /proxy/__RBT_VSERVER_SHELL__ ]; then
        du -sk /proxy/__RBT_VSERVER_SHELL__ > ${STAGE_DIR}/server_shell.txt
        find /proxy/__RBT_VSERVER_SHELL__ -print >> ${STAGE_DIR}/server_shell.txt
    fi

    # neural-stats files
    NEURAL_STATS=`ls /var/opt/rbt/neural-stats.*`
    for neural_file in ${NEURAL_STATS}; do
	cp -p $neural_file ${STAGE_DIR}
        rm -f $neural_file
    done

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
    OPROFILES=`ls /var/tmp/*_oprofile.txt`
    for oprofile in ${OPROFILES}; do
        cp -p $oprofile ${STAGE_DIR}
    done

    # PFS files - trim to 1000 lines if brief mode
    PFS_DIR="${STAGE_DIR}/pfs"
    mkdir "${PFS_DIR}"

    for pfs_file in /var/log/rcu/* /var/log/samba/* \
                    /var/log/rcu/rcu_helperd.out /var/opt/rcu/net_ads.out; do
        if [ ${BRIEF} -eq 0 ]; then
            cp -p "$pfs_file" "$PFS_DIR"
        else
            tail -1000 $pfs_file > "${PFS_DIR}/"`basename $pfs_file`
        fi
    done

    # Domain-health logs - trim to 1000 lines if brief mode
    DOM_HEALTH_DIR="${STAGE_DIR}/domain_health"
    mkdir "${DOM_HEALTH_DIR}"
    
    for dhealth_file in /var/log/domaind/*; do
        if [ ${BRIEF} -eq 0 ]; then
            cp -p "$dhealth_file" "$DOM_HEALTH_DIR"
        else
            tail -1000 $dhealth_file > "${DOM_HEALTH_DIR}/"`basename $dhealth_file`
        fi
    done

    # PFS config
    do_safe_cp /var/opt/rcu/rcud.conf ${STAGE_DIR}
    do_safe_cp /etc/samba/smb.conf ${STAGE_DIR}
    do_safe_cp /etc/krb5.conf.rcud ${STAGE_DIR}
    do_safe_cp /etc/krb5.conf ${STAGE_DIR}
    do_safe_cp /etc/krb.realms ${STAGE_DIR}

    # Backup files in case of domain join failure
    do_safe_cp /etc/samba/smb.conf.old ${STAGE_DIR}
    do_safe_cp /var/etc/krb5.conf.old ${STAGE_DIR}
    do_safe_cp /var/etc/krb.realms.old ${STAGE_DIR}

    do_command_output '/bin/netstat -s'

    # Add Delegation and Replication user info to sysdump
    DELEG_REPL_USRINFO_FILE="${STAGE_DIR}/delegrepl_usrinfo.txt"
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
    
    # ESPD files - trim to 1000 lines if brief mode
    for espd_file in /var/log/espd*; do
        if [ -f ${espd_file} ]; then
            if [ ${BRIEF} -eq 0 ]; then
                cp -p "$espd_file" "$STAGE_DIR"
            else
                tail -1000 $espd_file > "${STAGE_DIR}/${espd_file}"
            fi
        fi
    done

    # LKCD
    for analysis in `ls /var/log/dump/*/analysis.*`; do
        do_safe_cp $analysis ${STAGE_DIR}
    done
    
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
    cp -f "/var/tmp/qosd.txt" ${STAGE_DIR}

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

    # RSP2
    RSP_ROOT_DIR=/proxy/__RBT_VSERVER_SHELL__/rsp2
    STAGE_RSP_DIR=${STAGE_DIR}/rsp
    STAGE_RSPNET_DIR=${STAGE_RSP_DIR}/rspnet
    MFG_TYPE=`/opt/tms/bin/hald_model | cut -f56`
    if [ -f $RSP_ROOT_DIR/.rsp_version -o "$MFG_TYPE" = "rvbd_ex" ]; then

        mkdir -p ${STAGE_RSP_DIR}
        mkdir ${STAGE_RSPNET_DIR}
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
        for file in `ls /sys/module/rbtnfmod/`; do
            do_command_output_file "cat /sys/module/rbtnfmod/$file" $STAGE_RSPNET_DIR/rspnet.txt
        done

        # mactab config & entries
        BR_IFACES=`/sbin/get_bridge_ifaces.sh`
        for iface in $BR_IFACES; do
            if [ -d /proc/sys/rspnet/${iface} ]; then
                do_command_output_file "cat /proc/sys/rspnet/${iface}/flap_hold_ms" $STAGE_RSPNET_DIR/rspnet.txt
                do_command_output_file "cat /proc/sys/rspnet/${iface}/flap_thresh_count" $STAGE_RSPNET_DIR/rspnet.txt
                do_command_output_file "cat /proc/sys/rspnet/${iface}/flap_thresh_ms" $STAGE_RSPNET_DIR/rspnet.txt
            fi
        done

    fi # Is RSP2 installed?

    lsmod | grep ip_tables >& /dev/null
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

    # To dump alarmd information, we need
    # both alarmd and mgmtd functional
    ALARMD_PID=`pgrep -f 'alarmd'`
    if [ "x$ALARMD_PID" != "x" ]; then
        ALARMD_INFO_FILE=${STAGE_DIR}/alarmd_info.txt
        echo "---- Alarm Hierarchy ------------------------------------------------------" >> ${ALARMD_INFO_FILE}
        /opt/tms/bin/mdreq action /dbgshell/alarmd/dump/alarmhier >> ${ALARMD_INFO_FILE}
        echo "---- Alarm Table ----------------------------------------------------------" >> ${ALARMD_INFO_FILE}
        /opt/tms/bin/mdreq action /dbgshell/alarmd/dump/alarmtab >> ${ALARMD_INFO_FILE}
        echo "---- Alarm Statistics -----------------------------------------------------" >> ${ALARMD_INFO_FILE}
        /opt/tms/bin/mdreq action /dbgshell/alarmd/dump/stats >> ${ALARMD_INFO_FILE}
        echo "---- Alarm Config Override Cache-------------------------------------------" >> ${ALARMD_INFO_FILE}
        /opt/tms/bin/mdreq action /dbgshell/alarmd/dump/usercache >> ${ALARMD_INFO_FILE}
    fi

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
}

# -----------------------------------------------------------------------------
# Graft point #4 for sysdump.sh
#
# This is called to generate the list of log files to dump
#
HAVE_SYSDUMP_GRAFT_4=y
sysdump_graft_4()
{
    graft4='-o -name memlog* -print -o -name host_messages* -print'
}

# -----------------------------------------------------------------------------
# Graft point #5 for sysdump.sh
#
# This is called to copy over SSL certs (not keys) as a part of the dump
#
HAVE_SYSDUMP_GRAFT_5=y
sysdump_graft_5()
{
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
	SEC_VAULT_MOUNTED=
	NO_CERTS_MSG='Secure vault was not mounted. Could not copy certs'
	EXPORTABLE_FLAG_TRUE='true'

	# This is where we'll copy the certs
	SERVER_CERTS_DEST_DIR=${STAGE_DIR}/server_certs

	# Ensure that the dest dir exists
	mkdir -p $SERVER_CERTS_DEST_DIR

	# Checking if secure vault is mounted
	for word in $PROC_MOUNTS;
	do
	  if [ "$word" = "$ENCFS_MNT_TYPE" ]
	  then
		  # okay so encfs type is present, it can only
		  # mean that secure vault is mounted
		  SEC_VAULT_MOUNTED='y'
		  break
	  fi
	done

	if [ "x$SEC_VAULT_MOUNTED" = "x" ]
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
# This is called to copy over SSL server certs global exportable flag 
# as a part of the dump
#
HAVE_SYSDUMP_GRAFT_6=y
sysdump_graft_6()
{
    GLOBAL_EXPORTABLE_FILE='/var/opt/rbt/ssl/server_certs/global_exportable'
    INFO_FILE='ssl_server_certs_exportable_info.txt'
    VAULT_MOUNTED=`/sbin/secure_vault_check_mount.sh`

    echo "================================================" >> ${STAGE_DIR}/${INFO_FILE}
    echo "Secure Vault Unlocked: " ${VAULT_MOUNTED} >> ${STAGE_DIR}/${INFO_FILE}
    if [ "x${VAULT_MOUNTED}" = "xtrue" ]; then
        cp -a ${GLOBAL_EXPORTABLE_FILE} ${STAGE_DIR}/global_exportable
        echo "Allow exporting of SSL server certificates: " `cat ${GLOBAL_EXPORTABLE_FILE}` >> ${STAGE_DIR}/${INFO_FILE}
    fi
    echo "================================================" >> ${STAGE_DIR}/${INFO_FILE}
}

# -----------------------------------------------------------------------------
# Graft point for sysdump on a HP blade.
#
if (($HPP1_BLADE)); then
    HAVE_HPBLADE_SYSDUMP_GRAFT=y
else
    HAVE_HPBLADE_SYSDUMP_GRAFT=n
fi
hpblade_sysdump_graft()
{
    HPNET_DST_DIR=${STAGE_DIR}/hpnet
    local HPCTL_DST_FILE=${STAGE_DIR}/hp_respd.txt
    local HP_CTL_BIN=/opt/hal/bin/hp_ctl

    mkdir -p ${HPNET_DST_DIR}/proc/sys
    mkdir -p ${HPNET_DST_DIR}/sys/module

    ASH_MOD_ARGS=/sys/module/ash
    if [ -d ${ASH_MOD_ARGS} ]; then
        cp -a ${ASH_MOD_ARGS} ${HPNET_DST_DIR}/sys/module
    fi

    FTBLS_PROC_DIR=/proc/filtertables
    if [ -d ${FTBLS_PROC_DIR} ]; then
        # Reset all idx values before copying over the corresponding tables.
        FTBLS_IDX_ENTRIES=`find ${FTBLS_PROC_DIR} -name '*_idx' \
                            -printf "%f "`
        for idx in ${FTBLS_IDX_ENTRIES}
        do
            echo 0 > ${FTBLS_PROC_DIR}/${idx}
        done

        cp -a ${FTBLS_PROC_DIR} ${HPNET_DST_DIR}/proc

        # If not a brief dump, get complete filtertables.
        if ((!$BRIEF)); then
            for idx in ${FTBLS_IDX_ENTRIES}
            do
                local tabname=`echo ${idx} | sed -e "s/_idx//"`
                local dst_filename=${HPNET_DST_DIR}/proc/filtertables/${tabname}

                # Paranoid check
                if [ -e ${FTBLS_PROC_DIR}/${tabname} ] &&  \
                   [ -e ${dst_filename} ]; then
                   local prev_idx=-1
                   local curr_idx=0
                   local tab_start_time=`date +%s%N`
                    # Keep taking a dump till we run out of tp.
                    while [ $curr_idx -gt $prev_idx ]
                    do
                        cat ${FTBLS_PROC_DIR}/${tabname} >> ${dst_filename}
                        prev_idx=${curr_idx}
                        curr_idx=`cat ${FTBLS_PROC_DIR}/${idx}`
                    done

                    # A table may wrap around and dump the same entries.
                    if [ `grep -c "^[ ]*0" ${dst_filename}` -gt 1 ]; then
                        local lines_before_wrap=$((`grep -n -m2 "^[ ]*0" \
                            ${dst_filename} | grep -o "^[0-9]\+" | \
                            tail -1` - 1))
                        if [ ${lines_before_wrap} -gt 0 ]; then
                            head -${lines_before_wrap} ${dst_filename} > \
                                /var/tmp/hpnet_filtertables_tmp
                            mv -f /var/tmp/hpnet_filtertables_tmp \
                                ${dst_filename}
                        fi
                    fi
                    local tab_end_time=`date +%s%N`
                    local tab_time=$(echo "(${tab_end_time} - " \
                                    "${tab_start_time}) / 1000000" | bc)
                    echo "It took ${tab_time}ms to dump table ${tabname}" >> \
                        ${HPNET_DST_DIR}/proc/filtertables/__table_dump_times
                fi
            done
        fi
    fi

    HPP1_MOD_ARGS=/sys/module/hpp1mod
    if [ -d ${HPP1_MOD_ARGS} ]; then
        cp -a ${HPP1_MOD_ARGS} ${HPNET_DST_DIR}/sys/module
    fi

    HPP1_PROC_DIR=/proc/hpp1
    if [ -d ${HPP1_PROC_DIR} ]; then
        cp -a ${HPP1_PROC_DIR} ${HPNET_DST_DIR}/proc
    fi

    HPP1_SYSCTL_DIR=/proc/sys/hpp1
    if [ -d ${HPP1_SYSCTL_DIR} ]; then
        cp -a ${HPP1_SYSCTL_DIR} ${HPNET_DST_DIR}/proc/sys
    fi

    PAL_MOD_ARGS=/sys/module/palmod
    if [ -d ${PAL_MOD_ARGS} ]; then
        cp -a ${PAL_MOD_ARGS} ${HPNET_DST_DIR}/sys/module
    fi

    PAL_PROC_DIR=/proc/pal
    if [ -d ${PAL_PROC_DIR} ]; then
        cp -a ${PAL_PROC_DIR} ${HPNET_DST_DIR}/proc
    fi

    # platform respd specific sysdump information
    # we'll capture zone/policy and chassis info
    #
    if [ -x ${HP_CTL_BIN} ]; then
        do_command_output_file "${HP_CTL_BIN} display_info" "${HPCTL_DST_FILE}"
        do_command_output_file "${HP_CTL_BIN} display_policies" "${HPCTL_DST_FILE}"
        do_command_output_file "${HP_CTL_BIN} display_zones" "${HPCTL_DST_FILE}"
        
    fi
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
        # TODO -- Temporary script until we get a properly supported call
        # to get the manufactured type.
        MFG_TYPE=`/opt/tms/bin/hald_model | cut -f56`
        if [ "$MFG_TYPE" = "rvbd_ex" ]; then
            PREFIX="/opt/vmware/vmware_server"
            # Special case /etc/vmware due to ro root partition issues
            check_recreate_bad_symlink \
                "/var/vmware_server/etc/vmware" "/etc/vmware"
            # Copy /opt/vmware/vmware_server/etc/vmware into /var since the
            # root partition is read-only
            mkdir -p /var/vmware_server/etc
            cp -pr ${PREFIX}/etc/vmware /var/vmware_server/etc
        else
            PREFIX="/proxy/__RBT_VSERVER_SHELL__/vmware_server"
            check_recreate_bad_symlink \
                "${PREFIX}/etc/vmware" "/etc/vmware"
        fi
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
    BASE_LICENSES="BASE|EXCH|CIFS"
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

    if [ -f /etc/ve_scrub_calls.sh ]; then
        . /etc/ve_scrub_calls.sh
        ve_scrub_graft_1 $1
    fi
}

if (($HPP1_BLADE)); then
    HAVE_HPBLADE_FIRSTBOOT_GRAFT=y
else
    HAVE_HPBLADE_FIRSTBOOT_GRAFT=n
fi
hpblade_firstboot_graft_1()
{
    chkconfig --add acpid
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

# BOB by default includes VMware ESXi sysdump data. RSP_VMWARE_SUPPORT=1
# indicates that we do not want to include this data.
if [ "${MOBO}" == "BOB-MOBO" ]; then
    if [ "x$RSP_VMWARE_SUPPORT" != "x" ]; then
        if [ $RSP_VMWARE_SUPPORT -eq 0 ]; then
            HAVE_BOB_SYSDUMP_GRAFT=y
        fi
    fi
fi

bob_sysdump_graft_1()
{

    #Note: update the ip address when it changes
    ESXi_IP_ADDR=169.254.131.2
    LAUNCH_ESXI_SSH=launch_esxi_ssh.py

    if [ $# -eq 0 ]; then
        echo "Destination directory unavailable for host sysdump"
        return
    fi

    STAGE_DIR=$1

    # Create tmp directories first in case there are previous files
    TMP_DIR=`date '+%Y-%m-%d-%H-%M-%S'`

    # Grab data from /dev/proc-* files
    PROC_FILES_TMP_DIR=/tmp/${TMP_DIR}-proc-files

    ${LAUNCH_ESXI_SSH} mkdir ${PROC_FILES_TMP_DIR}

    PROC_FILES="/esxi/dev/proc-*"
    for PROCFILE in $PROC_FILES
    do
        bname=`basename $PROCFILE`
        ${LAUNCH_ESXI_SSH} "cat /dev/$bname >$PROC_FILES_TMP_DIR/$bname"
    done
    mkdir ${STAGE_DIR}/host_proc_files
    cp /esxi${PROC_FILES_TMP_DIR}/* ${STAGE_DIR}/host_proc_files/
    # clean up
    rm -rf /esxi/${PROC_FILES_TMP_DIR}

    # Generate host sysdump
    VM_SUPPORT_TMP_DIR=/tmp/${TMP_DIR}
    ${LAUNCH_ESXI_SSH} mkdir ${VM_SUPPORT_TMP_DIR}

    # Run vm-support -w
    ${LAUNCH_ESXI_SSH} vm-support -w ${VM_SUPPORT_TMP_DIR} > /dev/null 2>&1 &

    hdump_pid=$!

    #Set a timer, 10min, for vm-support
    count=20
    while [ $count -ne 0 ]
    do
        ((count--))
        sleep 30
        ps -p $hdump_pid > /dev/null
        if [ $? -ne 0 ]; then
            # the vm-support is done, exit
            break
        fi
    done

    if [ $count -eq 0 ]; then
        # Timeout, need to kill the host sydump ssh process.
        kill $hdump_pid
        # Leave some time to allow the process terminate
        sleep 5

        # Force the process to terminate
        ps -p $hdump_pid > /dev/null
        if [ $? -eq 0 ]; then
            kill -SIGKILL $hdump_pid
        fi

        # Leave some message in the RiOS sysdump if can't get host sysdump
        touch ${STAGE_DIR}/host_sysdump_failed

        # Get the running vm-support pids on ESXi
        pids=`${LAUNCH_ESXI_SSH} ps -c | awk '/vm-support/ { printf("%s ",$1) }'`

        # Log back in ESXi and kill the vm-support process(es)
        ${LAUNCH_ESXI_SSH} kill -SIGKILL $pids > /dev/null 2>&1

    else
        # Copy the vm-support file directly if esxi file system is mounted
        if [ -d /esxi/${VM_SUPPORT_TMP_DIR} ]; then
            cp /esxi/${VM_SUPPORT_TMP_DIR}/* ${STAGE_DIR}
            # Delete the dump
            rm -rf /esxi/${VM_SUPPORT_TMP_DIR}
        else
            # Use scp as a backup
            scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
                root@${ESXi_IP_ADDR}:${VM_SUPPORT_TMP_DIR}/* ${STAGE_DIR}
            # Delete the dump
            ${LAUNCH_ESXI_SSH} rm -rf ${VM_SUPPORT_TMP_DIR}
        fi

    fi

    # Capture the state of RSPNet.
    RSPNET_STAGE_DIR="${STAGE_DIR}/rsp/rspnet"
    mkdir -p "${RSPNET_STAGE_DIR}"
    RSPNETTEST_FILE="${RSPNET_STAGE_DIR}/rspnettest.txt"
    $RSPNETTEST_PROG -b -c "ns" > ${RSPNETTEST_FILE}
    $RSPNETTEST_PROG -b -c "ds all" >> ${RSPNETTEST_FILE}
    $RSPNETTEST_PROG -b -c "dS all" >> ${RSPNETTEST_FILE}

    # Grab datastores from /esxi/vmfs/volumes
    mkdir -p ${STAGE_DIR}/vsp
    mkdir -p ${STAGE_DIR}/vsp/vms
    VMFS_VOLUMES_DIR="/esxi/vmfs/volumes/"
    for datastore in `/opt/tms/variants/bob/bin/virt_wrapperd -q datastore-list`; do
        datastore_ready=`/opt/tms/variants/bob/bin/virt_wrapperd -q datastore-ready "${datastore}"`
        if [ $datastore_ready == "true" ]; then
                #Dump the contents into $STAGE_DIR/vsp/datastore_contents.txt
                ls -lR /esxi/vmfs/volumes/$datastore/ >> ${STAGE_DIR}/vsp/datastore_contents.txt

        	EXCLUDE_FILE_TMP_DIR=/tmp/${TMP_DIR}-exclude-$datastore.txt
        	mkdir -p ${STAGE_DIR}/vsp/vms/$datastore
        	find /esxi/vmfs/volumes/$datastore/ -size +65536c 2>/dev/null >> ${EXCLUDE_FILE_TMP_DIR}
        	echo *-flat.vmdk >> ${EXCLUDE_FILE_TMP_DIR}
        	echo *.vswp >> ${EXCLUDE_FILE_TMP_DIR}
        	tar -c -X ${EXCLUDE_FILE_TMP_DIR} /esxi/vmfs/volumes/$datastore/* | tar -x -C ${STAGE_DIR}/vsp/vms/$datastore
        	rm -f ${EXCLUDE_FILE_TMP_DIR}
        fi
    done

    # Get mux and switch info
    mkdir -p ${STAGE_DIR}/mux
    mkdir -p ${STAGE_DIR}/switch

    cp /proc/mux/* ${STAGE_DIR}/mux
    cp /proc/switch/* ${STAGE_DIR}/switch


}
