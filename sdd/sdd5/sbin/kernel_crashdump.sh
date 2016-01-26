#! /bin/sh

# This script runs once every bootup to check for any new kernel crashdumps.
# If there are any new kernel crash dumps, it collects the sysdump and tars it 
# together with the kernel crashdump. 

SNAPSHOT_DIR=/var/opt/tms/snapshots
SYSDUMP_DIR=/var/opt/tms/sysdumps
TEMP_DIR=/var/tmp
CLI=/opt/tms/bin/cli
SYSDUMP_FILE=""

delete_oldest_kernel_dump()
{
	# Deleting any older dumps; We store a max of 5 kernel crash dumps
	DUMP_COUNT=0
	DUMP_LIST=`ls -t ${SNAPSHOT_DIR}/kernel-crashdump-* 2> /dev/null`
	if [ "x$DUMP_LIST" != "x" ]; then
		for FILE in $DUMP_LIST; do
			DUMP_COUNT=$[DUMP_COUNT+1]
	        done
	fi
	if [ $DUMP_COUNT -ge 5 ]; then
		# we have to delete the oldest dump
	        OLDEST_DUMP=`ls -t ${SNAPSHOT_DIR}/kernel-crashdump-* | tail -1`
		rm -rf $OLDEST_DUMP
	fi
}


delete_oldest_sysdump()
{
	last=`echo -e "en\nco t\nshow files debug-dump\n" | $CLI | grep "tgz" | sort | head -n 1`
	`echo -e "en\nco t\nfile debug-dump delete $last" | $CLI`
}

function create_sysdump()
{
	limit=`echo -e "en\nco t\nshow support sysdump limit\n" | $CLI | awk '{print $8}' `
	cur=`echo -e "en\nco t\nshow files debug-dump\n" | $CLI | wc -l`


	if [ "$cur" -ge "$limit" ]; then
		#number of sysdumps reached the limit, delete oldest one
		delete_oldest_sysdump
	fi

	SYSDUMP_FILE_SHORT=`echo -e "en\nco t\ndebug generate dump stats\n" | $CLI | awk '{print $3}' | tr -d '\n'`
	SYSDUMP_FILE="$SYSDUMP_DIR/$SYSDUMP_FILE_SHORT"
}


#wait for 10 mins so that the system is not very busy,hopefully
sleep 600

logger -s "$0 Checking for kernel-crashdumps [if any]. This may take some time."

cd $TEMP_DIR
FLAG=0

#Check if any of following user name is set or not. If none, set one.
#Otherwise, the sysdump will have an error for active-running.txt file.
if [[ -z $LOGNAME && -z $USER && -z $LOGIN_USER ]]; then
	export USER=admin
fi

for dump in $( find $TEMP_DIR -maxdepth 1 -type f -name kernel-crashdump-\* ); do
	# For every new dump generated in /var/tmp delete the oldest dump
	delete_oldest_kernel_dump
	
	# A new crash dump has been generated; generate sysdump
	if [ $FLAG -eq 0 ]; then
		create_sysdump
		FLAG=1
	fi

	# tar the sysdump together with the kernel-crashdump
	cp $SYSDUMP_FILE $TEMP_DIR
        tar -czf $( basename $dump ).tar.gz $( basename $SYSDUMP_FILE ) $( basename $dump ) 2> /dev/null
	mv $( basename $dump ).tar.gz $SNAPSHOT_DIR
	logger -s "$0 Kernel crash dump $dump saved in /var/opt/tms/snapshots"
	rm -f $dump
	rm -f $( basename $SYSDUMP_FILE )
done

