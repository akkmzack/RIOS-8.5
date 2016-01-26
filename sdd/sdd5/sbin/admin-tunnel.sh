#!/bin/sh

account=autotunnel@autotunnel.riverbed.com
logfile=/var/log/admintunnel.log
pidfile=/var/opt/rbt/admintunnel.pid
portfile=/var/opt/rbt/admintunnel.port
idfile=/var/opt/rbt/admintunnel.sshid
opt_p=
opt_f=no
op=
while [ $# -ne 0 ]; do
	case $1 in
	-p)
		shift
		opt_p=$1
		;;
	-f)
		opt_f=yes
		;;
        -a)     
                shift
                account=$1
                ;;
	*)
		break
		;;
	esac
	shift
done

[ $# -eq 1 ] || {
	echo "Usage: $0 [-f] [-p port] [-a account] {setup|start|stop|restart|status}"
	exit 1
}
op=$1

#
# Check the pid file to see if we are running.
#
pid=
running=no
if [ -r $pidfile ]; then
	pid=`cat $pidfile`
	if [ $pid -eq 0 -o $pid -eq -1 ]; then
		echo "Error: pidfile has invalid pid $pid"
		exit 1
	fi
	if kill -0 $pid 2>/dev/null; then
		running=yes
	else
		# Remove a stale pid file.
		rm -f $pidfile
		pid=
	fi
fi

do_syslog() {
	level=$1
	shift
	logger -i -t admintunnel "[admintunnel.$level]" $*
	echo "[`date`]" $level $*
}

#
# Normally we don't write directly to the debug log, it is handled by
# redirecting everything to it before the loop.
# But there are some special cases when we want to log something.
#
debuglog() {
	echo "[`date`]" $* >>$logfile
}

###---------------------------------------------------------------------
### Set up the admin tunnel config files.  This includes the port and
### SSH private key.
###---------------------------------------------------------------------
setup() {
	if [ -z $opt_p ]; then
		echo "Error: port must be specified for setup"
		exit 1
	fi

	if [ $running = yes ]; then
            echo "% Admin tunnel is running. Please stop it first."
            exit 1
	fi

	if [ -f $idfile ]; then
		if [ $opt_f = yes ]; then
			echo "Removing existing id file."
			rm -f $idfile
		else
			echo "Error: Id file already exists, run with -f to overwrite"
			exit 1
		fi
	fi

	mkdir -p `dirname $idfile`
	touch $idfile || {
		echo "Error: cannot create $idfile"
		exit 1
	}
	chmod 600 $idfile

	echo ""
	echo "Please enter private key file and end with EOF (typically Ctrl-D):"
	cat >$idfile
        idfile_len=`cat $idfile | wc -c`
        if [ $idfile_len = 0 ]; then
            rm -f $idfile
            echo ""
            echo "No private key entered. Admin tunnel is NOT configured."
        else
            echo $opt_p >$portfile
            echo "Admin tunnel is configured and may be started"
        fi
}

###---------------------------------------------------------------------
### Start the admin tunnel process if not already.
###---------------------------------------------------------------------
start() {
	if [ $running = yes ]; then
		echo "Error: Admin tunnel process already running, pid $pid"
		echo "Error: You might want to use the \"restart\" command"
		exit 1
	fi

	# Ok, we're running now.
	echo $$ >$pidfile
	trap "rm -f $pidfile" 0

	#
	# Check for the id file
	#
	[ -r $idfile ] || {
		echo "Error: Identity file $idfile is not readable"
		echo "Error: You may need to run with \"setup\""
		exit 1
	}

	#
	# Get port from the config file
	#
	[ -r $portfile ] || {
		echo "Error: Port file not readable"
		echo "Error: You might need to re-run setup"
		exit 1
	}
	local port_=`cat $portfile`

	#
	# Start the loop.  From now on our output goes to the log file
	# and to syslog.
	#
	echo "Starting admin tunnel ssh"
	exec >$logfile 2>&1
	do_syslog INFO Starting admin tunnel ssh
	while true; do
		ssh -gnN -o ServerAliveInterval=60 -o StrictHostKeyChecking=no -i $idfile \
			-R $port_:localhost:22 $account
		sleep 10		# don't loop if problem
		do_syslog INFO Re-starting admin tunnel ssh
	done
}

###---------------------------------------------------------------------
### Stop the admin tunnel process.
###---------------------------------------------------------------------
stop() {
	if [ $running = yes ]; then
                # Save the pid of ssh
		sshpid=`ps -e -o pid,ppid,cmd | grep -e ".*[ ]$pid[ ]ssh" | sed -e 's,[ ]*,,;s,\([0-9]\+\)\(.*\),\1,'`

		do_syslog INFO "Stopping admin tunnel process"
		debuglog "Stopping admin tunnel process"
		local killed_=no
		for sig in TERM HUP KILL; do
			# Be sure to kill the group (via negative pid)
			# to make sure the sub-ssh procs get killed.
			kill -$sig $pid
                        kill -$sig $sshpid
			sleep 2
			if kill -0 $pid 2>/dev/null; then
				continue
			fi
			killed_=yes
			break
		done
		if [ $killed_ = no ]; then
			echo "Warning: Unable to kill pid $pid"
		fi

		running=no
		rm -f $pidfile
		pid=
	else
		echo "No Admin tunnel process running"
	fi
}

case $op in
setup)
	setup
	;;
start)
	start
	;;
stop)
	stop
	;;
restart)
	stop
	start
	;;
status)
	if [ $running = yes ]; then
		echo "Admin tunnel process is running"
	else
		echo "Admin tunnel process is not running"
	fi
	;;
*)
	echo "Error: $op is not a recognized command"
	exit 1
	;;
esac

exit 0
