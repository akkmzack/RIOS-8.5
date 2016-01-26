#!/bin/busybox sh

DATE='busybox date'
SLEEP='busybox sleep'

period=1
max=3

renice -5 -p $$ > /dev/null

while true; do
	t0=`$DATE +%s`
	$SLEEP $period
	now=`$DATE +%s`
	diff=$((($now - $t0) % 3600))
	if [ $diff -gt $max ]; then
		logger -p local0.warning -t softwatch \
			"WARNING: slept too long: $diff, expecting $period-$max"
	fi
done
