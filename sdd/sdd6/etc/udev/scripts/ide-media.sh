#!/bin/bash 

if [ -a /proc/ide/$1/media ] ; then 
	/bin/cat /proc/ide/$1/media
	exit 0
fi

i=0
while [[ ! -a /proc/ide/$1/media && $i -lt 10 ]]; do 
	/bin/usleep 100000; 
	i=$[i+1];
done
/bin/cat /proc/ide/$1/media
