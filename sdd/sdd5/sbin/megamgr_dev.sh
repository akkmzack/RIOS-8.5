#!/bin/sh

if [ ! -c /dev/megadev0 ]; then
        mknod /dev/megadev0 c `cat /proc/devices | grep megadev | awk '{print $1;}'` 0
fi
