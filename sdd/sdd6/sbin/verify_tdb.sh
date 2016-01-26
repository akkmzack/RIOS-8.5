#!/bin/bash

# Verifies tdb files and
# if found corrupted recovers using earlier backup file

# Absolute command names
TDB_CMD=/usr/local/samba/bin/tdbbackup
CLI_CMD="/opt/tms/bin/cli"
LOGGER="/usr/bin/logger -i -s"
COMPONENT="rcu/tdb_backup"
MAX_SIZE=209715200 # 200MB
RCUD_CONF="/var/opt/rcu/rcud.conf"
CORRUPT_TDB_FILES_DIR="/var/log/rcu/tdb_corrupt"

# candidate tdb files
TDB_FILES_LIST=\
"/var/samba/private/secrets.tdb
/var/samba/var/locks/account_policy.tdb
/var/samba/var/locks/brlock.tdb
/var/samba/var/locks/connections.tdb
/var/samba/var/locks/gencache.tdb
/var/samba/var/locks/group_mapping.tdb
/var/samba/var/locks/idmap_cache.tdb
/var/samba/var/locks/locking.tdb
/var/samba/var/locks/messages.tdb
/var/samba/var/locks/netsamlogon_cache.tdb
/var/samba/var/locks/ntdrivers.tdb
/var/samba/var/locks/ntforms.tdb
/var/samba/var/locks/ntprinters.tdb
/var/samba/var/locks/sessionid.tdb
/var/samba/var/locks/share_info.tdb
/var/samba/var/locks/unexpected.tdb
/var/samba/var/locks/winbindd_cache.tdb
/var/samba/var/locks/winbindd_idmap.tdb 
/var/samba/var/locks/notify.tdb"

# function definitions
function message()
{
    SEVERITY=$1
    MSG=$2
    
    LEVEL=`echo $SEVERITY | tr '[:lower:]' '[:upper:]'`
    
    $LOGGER -p "user.$SEVERITY" "[$COMPONENT.$LEVEL] $MSG"
}


function restart_smbd_processes()
{
    echo "enable"
    echo "pm process smb restart"
}

function restart_winbindd_processes()
{
    echo "enable"
    echo "pm process winbind restart"
}

function restart_samba_processes()
{

    NUM_SMBD=`ps auxww | grep smbd | grep -v grep | wc -l`
    echo $NUM_SMBD
    if [ $NUM_SMBD -gt 0 ]; then 
	restart_smbd_processes | $CLI_CMD
    fi
    NUM_WINBINDD=`ps auxww | grep winbindd | grep -v grep | wc -l`
    if [ $NUM_WINBINDD -gt 0 ]; then
	restart_winbindd_processes | $CLI_CMD
    fi
}    

function file_size()
{
    FILE=$1
    SIZE=`stat -c %s $FILE`
    echo $SIZE
}

function run_cmd_with_timeout()
{
    COMMAND=$1
    CMD_TIMEOUT=$2

    # Start the command.
    $COMMAND &
    CMD_PID=$!

    # Start the timeout process (parallel shell).
    ( sleep $CMD_TIMEOUT; message info "$COMMAND timed out (pid $CMD_PID)"; kill $CMD_PID ) &
    SLEEP_PID=$!

    # Block until the command exits or times out.
    wait $CMD_PID
    CMD_STATUS=$?

    if [ $CMD_STATUS -le 128 ] ; then
        kill $SLEEP_PID	 #Kill parallel shell process
    fi
    return $CMD_STATUS
}

function move_corrupt_file()
{
    FILE=$1
    CORRUPT_FILE=`basename $FILE`
    CORRUPT_FILE=$CORRUPT_FILE.$RANDOM
    message error "Moving $FILE to $CORRUPT_TDB_FILES_DIR/$CORRUPT_FILE"
    mkdir -p $CORRUPT_TDB_FILES_DIR
    mv $FILE $CORRUPT_TDB_FILES_DIR/$CORRUPT_FILE
}

function check_domain_status()
{
    if [ ! -f $RCUD_CONF ]; then
        echo 0;
        return;
    fi

    perl -nle 'if(/dom_status\s*status="(\d)"/){ print $1; }' $RCUD_CONF
}

STATUS=`check_domain_status`

if [ $STATUS -eq 0 ]; then
    message debug "Domain status = $STATUS, exiting..."
    exit
fi

CORRUPTED="FALSE"

# check tdb files for corruption
for FILE in `echo $TDB_FILES_LIST`
do
    RECOVER_FILE="FALSE"
    message debug "Verifying tdb file $FILE ..."

    if  [ ! -f $FILE ]; then
        # Continue if file does not exist
        continue;
    fi

    # if tdb file is huge ( > 200 MB), just log an error
    FILE_SIZE=`file_size $FILE`
    if [ $FILE_SIZE -gt $MAX_SIZE ]; then
        message error "Skipping file $FILE. File size is huge ( > $MAX_SIZE Bytes), may be corrupted"
        continue;
    fi
    
    CMD_TIMEOUT=45	#45s Timeout period
    COMMAND="$TDB_CMD -c $FILE"
    run_cmd_with_timeout "$COMMAND" "$CMD_TIMEOUT"
    EXIT_STATUS=$?
    if [ $EXIT_STATUS -eq 0 ]
    then
	message info "$COMMAND for file $FILE successful"
    elif [ $EXIT_STATUS -eq 1 ]
    then
        message error "Corrupted tdb file $FILE found."
	RECOVER_FILE="TRUE"
	CORRUPTED="TRUE"
    else
	message error "command=$COMMAND did not complete in $CMD_TIMEOUT, $FILE is corrupted resulting in infinite loop"
	move_corrupt_file $FILE
	CORRUPTED="TRUE"	
    fi

    if [ $RECOVER_FILE = "TRUE" ]; then
        message error "Recovering corrupted tdb file $FILE ..."
	CMD_TIMEOUT=300
	COMMAND="$TDB_CMD -v $FILE"
	run_cmd_with_timeout "$COMMAND" "$CMD_TIMEOUT"
	EXIT_STATUS=$?
	if [ $EXIT_STATUS -eq 0 ]
	then
	    message info "$COMMAND for file $FILE successful"
	else 
	    message error "Could not recover tdb file $FILE. Error = $EXIT_STATUS"
	    message error "command=$COMMAND did not complete in $CMD_TIMEOUT, $FILE is corrupted resulting in infinite loop"
	    move_corrupt_file $FILE
	fi
    fi
done

# Need to restart samba processes if any of the file was corrupted
if [ $CORRUPTED = "TRUE" ]; then
    message info "Restarting smb processes...."
    restart_samba_processes
fi

