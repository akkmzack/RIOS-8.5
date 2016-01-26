#!/bin/bash

# Note that the firmware versions are hardcoded below, so if you change, make 
# sure you change the logic as well.
FIRMWARE_FILE=/opt/hal/lib/disk/SN06C0FE.lod
MEGARAID_FILE=/usr/sbin/megaraid_tool
TOUCH_FILE=/var/opt/tms/.firmware_upgrade_failed_
HWTOOL_PY=/opt/hal/bin/hwtool.py

# check for motherboard
BOARD=`$HWTOOL_PY -q motherboard`
if [ "x$BOARD" != "xCMP-00109" ]; then
	# only for certain machines, otherwise silently exit
	exit 1;
fi

# check megaraid and firmware
MEGARAID_FIRMWARE=`$MEGARAID_FILE -v -c 0 | grep FirmWare | awk '{print $4}'`
if [ "x$MEGARAID_FIRMWARE" = "x815F" ]; then
        echo "MegaRAID controller detected with firmware: $MEGARAID_FIRMWARE"
        echo "checking disk firmware..."
else
        echo "MegaRAID controller not detected or has wrong firmware: $MEGARAID_FIRMWARE"
        echo "skipping firmware check"
        exit 0
fi

# check for firmware file
if [ ! -e $FIRMWARE_FILE ]; then
	echo "firmware file not found: $FIRMWARE_FILE"
	exit 1;
fi
 
for target in 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 ; do
        if [ -e $TOUCH_FILE_$target ]; then
                echo "skipping check for target $target"
                echo "previous error detected"
                echo "to reset run:  rm $TOUCH_FILE_${i}"
                continue;
        fi
        PRODUCT=`$MEGARAID_FILE -v -c 0 -t $target |grep 'Product Info' | awk '{print $4}'`
        VERSION=`$MEGARAID_FILE -v -c 0 -t $target |grep 'Product Version' | awk '{print $4}'`
        if [ "x$PRODUCT" = "xST3250310NS" -o "x$PRODUCT" = "xST3500320NS" ]; then
                if [ "x$VERSION" = "xSN04" -o "x$VERSION" = "xSN05" ]; then
                        echo upgrading target $target: $PRODUCT $VERSION ...
                        $MEGARAID_FILE -v -c 0 -t $target -m 10000 -f $FIRMWARE_FILE
                        if [ $? -eq 1 ]; then
                                touch $TOUCH_FILE_$target
                                echo "...upgrade failed"
                        else
                                echo "upgraded $target: $PRODUCT $VERSION to SN06"
                        fi
                else
                        echo "no upgrade needed for target $target: $PRODUCT $VERSION
"
                fi
        fi
done

