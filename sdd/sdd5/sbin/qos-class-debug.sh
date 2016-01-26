#!/bin/sh

watch -n 1 --no-title /sbin/tc -s -d class show dev $1 parent $2
