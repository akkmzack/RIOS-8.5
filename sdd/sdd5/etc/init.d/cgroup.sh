#!/bin/bash
#
#  Filename:  $Source$
#  Revision:  $Revision: 100391 $
#  Date:      $Date: 2012-02-22 11:37:01 -0800 (Wed, 22 Feb 2012) $
#  Author:    $Author: dradovanovic $
#
#  (C) Copyright 2012 Riverbed Technology, Inc.
#  All rights reserved.
#
#
# cgroup.sh        cgroup and irqbalance configuration script
#
# description: Configures cgroups and irqbalance based on hardware info.
#

# Detect hardware type
. /opt/tms/bin/rbt_set_mobo
# Configure cgroups for VSP supported models
if [ "$VSP_SUPPORTED" != "true" ]; then
	exit 0
fi

# Get the current CPU and memory info
TOTALCPUS=`/opt/tms/bin/hwtool -q cpu | grep cores | awk '{ print $4 }'`
MEMNODES=`cat /sys/devices/system/node/online`
DEFCPU=$((TOTALCPUS / 2 - 1))
ESXCPU1=$((DEFCPU + 1))
ESXCPU2=$((TOTALCPUS - 1))

CPU_MASK=0

touch / 2>/dev/null
READ_ONLY_ROOT=$?

[ $READ_ONLY_ROOT -ne 0 ] && mount / -o remount,rw


# Update irqbalance configuration file
for ((ESXCPU=$ESXCPU1; ESXCPU <= $ESXCPU2 ; ESXCPU++)) ; do
	CPU_MASK=$((CPU_MASK | 1 << ESXCPU))
done;
IRQ_AFFINITY_MASK=$(printf %016x ${CPU_MASK})

echo "## This file was AUTOMATICALLY GENERATED.  DO NOT MODIFY.
## Any changes will be lost.
##
## Generated by /etc/rc.d/init.d/cgroup.sh
##

# irqbalance is a daemon process that distributes interrupts across
# CPUS on SMP systems.  The default is to rebalance once every 10
# seconds.  There is one configuration option:
#
# ONESHOT=yes
#    after starting, wait for a minute, then look at the interrupt
#    load and balance it once; after balancing exit and do not change
#    it again.
ONESHOT=

#
# IRQ_AFFINITY_MASK
#    64 bit bitmask which allows you to indicate which cpu's should
#    be skipped when reblancing irqs.  Cpu numbers which have their
#    corresponding bits set to one in this mask will not have any
#    irq's assigned to them on rebalance
#
IRQ_AFFINITY_MASK=$IRQ_AFFINITY_MASK
" > /etc/sysconfig/irqbalance

# Assign the first half of physical CPUs to RIOS (group def)
# Assign the last CPU in the first half of CPUs to WS8 processes (group def/ws8)
# Assign the second half of CPUs to ESX (group esx)
echo '##
## This file was AUTOMATICALLY GENERATED.  DO NOT MODIFY.
## Any changes will be lost.
##
## Generated by /etc/rc.d/init.d/cgroup.sh
##

mount {
	cpuset = /cgroup/cpuset;
}

group / {
	cpuset {
		cpuset.memory_migrate="1";
		cpuset.memory_pressure_enabled="1";
	}
}

group def {
	cpuset {
		cpuset.memory_spread_slab="0";
		cpuset.memory_spread_page="0";
		cpuset.memory_migrate="1";
		cpuset.sched_relax_domain_level="-1";
		cpuset.sched_load_balance="1";
		cpuset.mem_hardwall="0";
		cpuset.mem_exclusive="0";
		cpuset.cpu_exclusive="1";
		cpuset.mems="'$MEMNODES'";
		cpuset.cpus="0-'$DEFCPU'";
	}
}

group esx {
	cpuset {
		cpuset.memory_spread_slab="0";
		cpuset.memory_spread_page="0";
		cpuset.memory_migrate="1";
		cpuset.sched_relax_domain_level="-1";
		cpuset.sched_load_balance="0";
		cpuset.mem_hardwall="0";
		cpuset.mem_exclusive="0";
		cpuset.cpu_exclusive="1";
		cpuset.mems="'$MEMNODES'";
		cpuset.cpus="'$ESXCPU1'-'$ESXCPU2'";
	}
}

' > /etc/cgconfig.conf

[ $READ_ONLY_ROOT -ne 0 ] && mount / -o remount,ro

