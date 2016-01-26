#!/bin/sh

touch /var/opt/rbt/no-temperature-logging &>/dev/null

ps -e | grep temperature-log &>/dev/null

if [ $? -ne 0 ]; then
    echo "No temperature logging to stop."
    exit 0
fi

pid=`ps -e | grep temperature-log | awk '{print $1}'` &>/dev/null

kill -9 $pid &>/dev/null

if [ $? -eq 0 ]; then
    echo "Stopped temperature logging."
else
    echo "Error stopping temperature logging."
fi

