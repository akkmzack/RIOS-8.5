RSP_VMWARE_SUPPORT=0
BLOCKSTORE_LOGS=0
BLOCKSTORE_FIFO_LOGS=0

# Append any product specific sysdump options
SYSDUMP_OPTIONS=${SYSDUMP_OPTIONS}pkf

# -----------------------------------------------------------------------------
# Path to the hwtool.
#
HWTOOL=/opt/hal/bin/hwtool.py

MOBO=
if [ -e ${HWTOOL} ]; then
    MOBO=`${HWTOOL} -q motherboard`
fi


# Define product specific options' usage
customer_usage()
{
    # By default, BOB includes vmware support dump while rsp2 does not.
    # The sysdump script handles RSP_VMWARE_SUPPORT=1 different for each case
    if [ "${MOBO}" != "BOB-MOBO" ]; then
        echo "-p    Do not include RSP vmware support dump"
    else
        echo "-p    include VSP vmware support dump"
    fi
    echo "-k    blockstore"
    echo "-f    blockstore fifo"
}

# Condition for matching product specific case statements
# Multiple product specific option should be ORed together
CUSTOMER_OPTIONS="-[kfp]"

# Define product specific option handlers
customer_opt_handler()
{
    case "$1" in
        -p) RSP_VMWARE_SUPPORT=1 ;;
        -k) BLOCKSTORE_LOGS=1 ;;
        -f) BLOCKSTORE_FIFO_LOGS=1 ;;
    esac
}

