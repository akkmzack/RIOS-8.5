#!/bin/sh

rm -f /var/tmp/bt.gdb

scriptfile=/var/tmp/bt.gdb
logfile=/var/tmp/backtrace.log
period=5
((rotate=24*60*60))			# rotate each day

rotatelogs() {
    rm -f $logfile.2
    mv -f $logfile.1 $logfile.2 2>/dev/null
    mv -f $logfile $logfile.1 2>/dev/null
    touch $logfile
}

count=0
printf "set height 0\nattach `pidof sport`\nt a a bt\ndetach\n" > $scriptfile
while true; do
        date >> $logfile
        gdb --quiet --batch  --command=$scriptfile >> $logfile 2> /dev/null < /dev/null
        sleep $period
	((count=$count+$period))
	if [ $count -ge $rotate ]; then
	    rotatelogs
	    count=0
	fi
done
