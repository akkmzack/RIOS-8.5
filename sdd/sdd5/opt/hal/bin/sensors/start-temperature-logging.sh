#!/bin/sh

rm /var/opt/rbt/no-temperature-logging &>/dev/null

ps -e | grep temperature-log &>/dev/null

if [ $? -eq 0 ]; then
    echo "Temperature logging already started."
    exit 0
fi

(/opt/hal/bin/sensors/temperature-logging.sh &>/dev/null &)

if [ $? -eq 0 ]; then
    echo "Temperature logging started."
else
    echo "Error starting temperature logging."
fi
