#!/bin/sh
# Workaround script for aha cards.
# Irqbalance is told not to manage the interrupt(s) for these cards, which 
# are instead managed by this script. 
# The argument(s) passed to the script are the aha card irq number(s)
#
# What this script does is make sure that multiple aha interrupts are 
# never on the same core, or even on associated even and odd cores 
# (e.g. 8 and 9), and keeps them moving often enough that no one cpu 
# has excessive load when examined at the 15 second interval used by the data 
# that feeds cpu load alarms. 
#
# This roughly emulates the behaviour of irqbalance on some earlier releases
# except that they didn't avoid placing an interrupt successively on adjacent 
# even and odd cores 
AHAS=$@
NAHAS=$#
AHA_ARR=($@)
NCPU=`cat /proc/cpuinfo | grep processor | wc -l`
MAXCPU=$[${NCPU}-1]
SPACING=$[${NCPU}/${NAHAS}]
MAXIDX=$[$NAHAS-1]

# seconds before moving the interrupts; must be less than 15
INTERVAL=2

# place interrupts at cores starting $base_cpu, and spaced every $SPACING 
# $base_cpu acts as an argument, via a global var (yuck)
# $SPACING is a true global, effectively const once initialized
function place_once {
	for idx in `seq 0 $MAXIDX`; do 
	    irq=${AHA_ARR[$idx]}
	    cpu_offset=$[$idx*$SPACING]
	    cpu=$[($base_cpu+$cpu_offset)%$NCPU]
	    mask=$[1<<$cpu]
	    printf "%x\n" ${mask} > /proc/irq/${irq}/smp_affinity
	done
}

# Loop forever, moving interrupts
#
# Step through cores in steps of 2 - e.g. 0,2,4,6,8,1,3,5,7 - because 
# we observed that when the interrupt was on e.g. 8, there was a little 
# bit of extra load on 9 as well. So to reduce the sum over short time 
# intervals, we jump by 2
while true; do
    for base_cpu in `seq 0 2 $MAXCPU`; do
	place_once
	sleep $INTERVAL
    done
    for base_cpu in `seq 1 2 $MAXCPU`; do
	place_once
	sleep $INTERVAL
    done
done

exit
