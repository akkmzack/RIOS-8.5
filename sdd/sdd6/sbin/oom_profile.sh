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
    do_cmd_output  ps -Aww -o pid,ppid,pcpu,vsize,rss,majflt,tty,stat,wchan=WIDE-WCHAN-COMMAND -o command
    do_file_output /sys/block/sda/queue/stats
    do_file_output /sys/block/hda/queue/stats
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
#  c.  partition holds /proxy.
#

    DISKS=$( mount |grep var |cut -d" " -f1 |gawk 'match($0, "(/dev/)([sh]d[a-z])([0-9]+)",a) { printf "/sys/block/%s\n", a[2] }')
    DISKS=$DISKS" "$( grep "<dis"  /var/etc/opt/tms/output/configfile.xml |gawk 'match($2, "/dev/([sh]d[a-z])([0-9]+)",a) {printf "/sys/block/%s\n", a[1]}')
    DISKS=$DISKS" "$( mount |grep proxy |cut -d" " -f1 |gawk 'match($0, "(/dev/)([sh]d[a-z])([0-9]+)",a) { printf "/sys/block/%s\n", a[2] }')

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


#  proxy & RSP partition stats

    for file in $( mount |grep proxy |cut -d" " -f1 |gawk 'match($0, "(/dev/)([sh]d[a-z])([0-9]+)",a) { printf "/sys/block/%s/%s%s/rbt_*\t", a[2], a[2], a[3] }');
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

    do_file_output /proc/eal/state
    do_file_output /proc/er/state
    do_file_output /proc/er/*/mactab_stats

#
# the cli cmd "sh rsp" shows if rsp is turned on.
# stats is collected when rsp is on.
#
    RSP_IS_ON=`echo -e "en\n con t\n sh rsp\n" |cli |grep "RSP Enabled" |grep Yes`
    [ "x$RSP_IS_ON" != "x" ] && echo -e "g\nns\nds all\ndS all" | /opt/rbt/bin/rspnettest -q

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
