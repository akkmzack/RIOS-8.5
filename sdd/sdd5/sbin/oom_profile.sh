#!/bin/sh

do_cmd_output() {
    echo "$*"
    $*
    echo
}

do_file_output() {
    for file; do
        [ -f $file ] && do_cmd_output cat $file
    done
}

oom_output() {
    echo '================================================================================'
    date
    echo '================================================================================'
    echo
    do_file_output /proc/meminfo
    do_cmd_output  ps -ALww -o pid,ppid,tid,pcpu,psr,vsize,rss,majflt,tty,stat,wchan=WIDE-WCHAN-COLUMN -o command

    do_file_output /sys/block/sda/queue/stats
    do_file_output /sys/block/hda/queue/stats

    do_file_output /cgroup/cpuset/cpuset.memory_pressure
    do_file_output /cgroup/cpuset/def/cpuset.memory_pressure
    do_file_output /cgroup/cpuset/esx/cpuset.memory_pressure
    do_file_output /proc/vmstat
    do_file_output /proc/zoneinfo
    do_file_output /proc/pagetypeinfo

    do_cmd_output  /usr/bin/slabtop -o -s c 
    do_cmd_output  /bin/df -h 
    do_cmd_output  /bin/df -i

}

disk_stats() {
    echo '================================================================================'
    date
    echo '================================================================================'

#  we want the top 5 cpu intensive processes.
    echo "Top commands by cpu usage"
    top -b -n 1 | head -n 12 | tail -n 5
    echo

#
#  we want to get the disk stats for the disks:
#  a.  the partition which holds /var
#  b.  partition holds the segment store
#  c.  partition holds /proxy (RSP2) or /scratch (VSP).
#

    DISKS=$( mount |grep var |cut -d" " -f1 |gawk 'match($0, "(/dev/)([sh]d[a-z])([0-9]+)",a) { printf "/sys/block/%s\n", a[2] }')
    DISKS=$DISKS" "$( grep "<dis"  /var/etc/opt/tms/output/configfile.xml |gawk 'match($2, "/dev/([sh]d[a-z])([0-9]+)",a) {printf "/sys/block/%s\n", a[1]}')
    DISKS=$DISKS" "$( mount |grep -e proxy -e scratch |cut -d" " -f1 |gawk 'match($0, "(/dev/)([sh]d[a-z])([0-9]+)",a) { printf "/sys/block/%s\n", a[2] }')

    for disk in $(echo -e ${DISKS// /'\n'} |sort -n |uniq)
    do
      for rbt_file in $disk/rbt_*
      do
      do_file_output ${rbt_file}
      done
    done

#  mount table hold info on which partition hold /var
#
    for file in $( mount |grep var |cut -d" " -f1 |gawk 'match($0, "(/dev/)([sh]d[a-z])([0-9]+)",a) { printf "/sys/block/%s/%s%s/rbt_*\t", a[2], a[2], a[3] }');
    do
      [ -e $file ] && do_file_output $file
    done

#  segstore partition stats

    for file in $( grep "<dis"  /var/etc/opt/tms/output/configfile.xml |gawk 'match($2, "/dev/([sh]d[a-z])([0-9]+)",a) {printf "/sys/block/%s/%s%s/rbt_*\t", a[1], a[1], a[2]}');
    do
      [ -e $file ] && do_file_output $file;
    done


#  proxy & RSP / scratch & VSP partition stats

    for file in $( mount |grep -e proxy -e scratch |cut -d" " -f1 |gawk 'match($0, "(/dev/)([sh]d[a-z])([0-9]+)",a) { printf "/sys/block/%s/%s%s/rbt_*\t", a[2], a[2], a[3] }');
    do
      [ -e $file ] && do_file_output $file;
    done

    do_file_output /proc/diskstats
}

tcp_stats_output() {
    echo '================================================================================'
    date
    echo '================================================================================'
    echo
    do_cmd_output netstat -stwu
    do_file_output /proc/net/sockstat
    do_file_output /proc/net/rbt-packet-stats
}


stats_output() {
    echo '================================================================================'
    date
    echo '================================================================================'
    echo
    do_file_output /proc/nbt/0/icore_stats
    do_file_output /proc/nbt/0/icore_dstats
    do_file_output /proc/nbt/0/icore_mstats

    do_file_output /proc/rbt_stats/nbt/msgq_stats
    do_file_output /proc/rbt_stats/netflow/msgq_stats
    do_file_output /proc/rbt_stats/nbt/conn_est_time_stats
    do_file_output /proc/rbt_stats/nbt/conn_per_sec_stats

    do_file_output /proc/eal/state
    do_file_output /proc/er/state
    do_file_output /proc/er/*/mactab_stats

    do_file_output /proc/rbtpipe/state

    do_file_output /proc/nbt/0/saas_stats
    do_file_output /proc/nbt/0/saas_acshtab_stats

#
# if mgmtd is up, in memory config node is checked to see if rsp is enabled
# else the active db is queried for last saved value of config node
# stats is collected when rsp is on.
#
# do this only for rvbd_sh
#
    MFG_TYPE=`/opt/tms/bin/hald_model -m`
    RSP_SUPPORT=`/opt/tms/bin/hald_model|cut -f37`

    if [ x$RSP_SUPPORT == "xtrue" -a x$MFG_TYPE == "xrvbd-sh" ]; then
        /sbin/pidof mgmtd > /dev/null 2>&1
        MGMTD_RUNNING=$?
        if [ $MGMTD_RUNNING -eq 0 ]; then
            RSP_IS_ON=`/opt/tms/bin/mdreq -v query get - /rbt/rsp2/config/enable`
        else
            ACTIVE_DB=`cat /config/db/active`
            RSP_IS_ON=`/opt/tms/bin/mddbreq -v /config/db/${ACTIVE_DB} query get - /rbt/rsp2/config/enable`
        fi

        [ "x${RSP_IS_ON}" = "xtrue" ] && echo -e "g\nns\nds all\ndS all" | /opt/rbt/bin/rspnettest -q
    fi

}

# only allow a single instance of oom_profile
OOM_PROFILE_SH=oom_profile.sh
/sbin/pidof -x -o $$ $OOM_PROFILE_SH > /dev/null && exit

while true
do
    oom_output >> /var/log/oom_profile.log
    disk_stats >> /var/log/disk_stats.log
    stats_output >> /var/log/stats_collect.log
    tcp_stats_output >> /var/log/tcp_stats.log

    sleep 30
done
