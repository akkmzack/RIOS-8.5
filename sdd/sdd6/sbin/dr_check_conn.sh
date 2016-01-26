#!/bin/sh

if [ $# -eq 0 ]; then
   echo "no"
   exit
fi

port=":$1 "; 
shift;

for p in $*; do
    port="$port|:$p ";
done

cat /proc/nbt/0/connection_table | egrep -ci "$port" 
