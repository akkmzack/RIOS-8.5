#!/bin/sh

watch -n 1 --no-title /sbin/tc -s -d filter show dev $1 parent $2 prio $3 
