#!/bin/sh
HAL='/opt/hal/bin/hal'
HAL_SET_LED="${HAL} set_system_led_state"

while [ 1 ]; do
    PID=`pidof /opt/tms/bin/pm`
    if [ $? -ne 0 ]; then
	$HAL_SET_LED critical
    fi
    sleep 3600
done
