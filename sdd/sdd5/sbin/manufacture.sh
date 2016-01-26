#!/bin/sh

#
#  Filename:  $Source$
#  Revision:  $Revision: 78701 $
#  Date:      $Date: 2011-03-24 17:29:30 -0700 (Thu, 24 Mar 2011) $
#  Author:    $Author: jshilkaitis $
# 
#  (C) Copyright 2002-2005 Tall Maple Systems, Inc.  
#  All rights reserved.
#

PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH

usage()
{
    echo "usage: $0 [-a] [-m MODEL] "
    echo "          [-u URL] [-f FILE] [-L LAYOUT_TYPE] -d /DEV/N1"
    echo "          [-p PARTNAME -s SIZE] [-t] [-k KERNEL_TYPE] "
    echo ""
    echo "Exactly one of '-u' (url) or '-f' (file) must be specified."
    exit 1
}


# Choose if we use 'read -e' (readline)
if [ ! -z "${BASH}" ]; then
    READ_CMD="read -e"
else
    READ_CMD="read"
fi

MFG_MOUNT=/tmp/mfg_mount
MFG_DB_DIR=${MFG_MOUNT}/config/mfg
MFG_DB_PATH=${MFG_DB_DIR}/mfdb
MFG_INC_DB_PATH=${MFG_DB_DIR}/mfincdb

MDDBREQ=/opt/tms/bin/mddbreq

MFG_POST_COPY="\
    /opt/tms/bin/mddbreq \
    /opt/tms/bin/genlicense \
"

IL_PATH=/etc/layout_settings.sh


# XXXXXXXX  testing
# MDDBREQ=./mddbreq
# MFG_DB_DIR=./mfg
# MFG_DB_PATH=${MFG_DB_DIR}/mfdb
# MFG_INC_DB_PATH=${MFG_DB_DIR}/mfincdb
# IL_PATH=./layout_settings.sh

HAVE_OPT_AUTO=0
OPT_AUTO=0
HAVE_OPT_MODEL=0
OPT_MODEL=
HAVE_OPT_KERNEL_TYPE=0
OPT_KERNEL_TYPE=
HAVE_OPT_LAYOUT=0
OPT_LAYOUT=
HAVE_OPT_PART_NAME_SIZE_LIST=0
OPT_PART_NAME_SIZE_LIST=
HAVE_OPT_DEV_LIST=0
OPT_DEV_LIST=
HAVE_OPT_IF_LIST=0
OPT_IF_LIST=
HAVE_OPT_IF_NAMING=0
OPT_IF_NAMING=
HAVE_OPT_VERBOSE=0
OPT_VERBOSE=0

WRITEIMAGE_ARGS=

PARSE=`/usr/bin/getopt 'am:u:f:k:d:p:s:L:tV' "$@"`

if [ $? != 0 ] ; then
    usage
fi

eval set -- "$PARSE"

# Defaults
SYSIMAGE_USE_URL=-1
USE_TMPFS=1


while true ; do
    case "$1" in
        -a) HAVE_OPT_AUTO=1; OPT_AUTO=1; shift ;; 
        -k) HAVE_OPT_KERNEL_TYPE=1; OPT_KERNEL_TYPE=$2; shift 2 ;;
        -v) HAVE_OPT_VERBOSE=1; OPT_VERBOSE=1; 
            WRITEIMAGE_ARGS="${WRITEIMAGE_ARGS} $1";  shift ;;
        -L) HAVE_OPT_LAYOUT=1; OPT_LAYOUT=$2; shift 2 ;;
        -m) HAVE_OPT_MODEL=1; OPT_MODEL=$2; shift 2 ;;
        -d) HAVE_OPT_DEV_LIST=1
            new_disk=$2; shift 2
            echo $new_disk | grep -q "^/dev"
            if [ $? -eq 1 ]; then
                usage
            fi
            OPT_DEV_LIST="${OPT_DEV_LIST} ${new_disk}"
            ;;
        -p) LAST_PART=$2; shift 2 ;;
        -s) LAST_PART_SIZE=$2; shift 2 
            if [ -z "${LAST_PART}" ]; then
                usage
            fi
            HAVE_OPT_PART_NAME_SIZE_LIST=1
            OPT_PART_NAME_SIZE_LIST="${OPT_PART_NAME_SIZE_LIST} ${LAST_PART} ${LAST_PART_SIZE}"
            ;;
        -u) SYSIMAGE_USE_URL=1
            WRITEIMAGE_ARGS="${WRITEIMAGE_ARGS} $1 $2"; shift 2 ;;
        -f) SYSIMAGE_USE_URL=0
            WRITEIMAGE_ARGS="${WRITEIMAGE_ARGS} $1 $2"; shift 2 ;;
        -t) USE_TMPFS=0
            WRITEIMAGE_ARGS="${WRITEIMAGE_ARGS} $1"; shift ;;
        --) shift ; break ;;
        *) echo "manufacture.sh: parse failure" >&2 ; usage ;;
    esac
done

if [ ! -z "$*" ] ; then
    usage
fi

if [ ${SYSIMAGE_USE_URL} -eq -1 ]; then
    usage
fi

# Define graft functions
if [ -f /etc/customer_rootflop.sh ]; then
    . /etc/customer_rootflop.sh
fi

echo ""
echo "=================================================="
echo " Manufacture script starting"
echo "=================================================="
echo ""

MODEL_sd1000_ENABLE=1
MODEL_sd1000_KERNEL_TYPE="uni"
MODEL_sd1000_DEV_LIST="/dev/hda"
MODEL_sd1000_LAYOUT="STD"
MODEL_sd1000_PART_NAME_SIZE_LIST="VAR 1024 SWAP 1024"
MODEL_sd1000_IF_LIST="ether1 ether2"
MODEL_sd1000_IF_NAMING="none"

MODEL_sd2000_ENABLE=1
MODEL_sd2000_KERNEL_TYPE="smp"
MODEL_sd2000_DEV_LIST="/dev/hda"
MODEL_sd2000_LAYOUT="STD"
MODEL_sd2000_PART_NAME_SIZE_LIST="VAR 2048 SWAP 1024"
MODEL_sd2000_IF_LIST="ether1 ether2 ether3 ether4 ether5"
MODEL_sd2000_IF_NAMING="manual"

MODEL_sd1000v_ENABLE=1
MODEL_sd1000v_KERNEL_TYPE="uni"
MODEL_sd1000v_DEV_LIST="/dev/sda"
MODEL_sd1000v_LAYOUT="STD"
MODEL_sd1000v_PART_NAME_SIZE_LIST="VAR 512 SWAP 512"
MODEL_sd1000v_IF_LIST="ether1 ether2"
MODEL_sd1000v_IF_NAMING="mac-sorted"

CFG_MODEL_DEF="sd1000"
CFG_MODEL_CHOICES="sd1000 sd2000 sd1000v"
CFG_KERNEL_TYPE_DEF="uni"
CFG_KERNEL_TYPE_CHOICES="uni smp"
CFG_DEV_LIST_DEF="/dev/hda"
CFG_PART_NAME_SIZE_LIST_DEF=""
CFG_LAYOUT_DEF="STD"
CFG_LAYOUT_CHOICES="STD"
CFG_IF_LIST_CHOICES=""
CFG_IF_LIST_DEF="ether1 ether2 ether3 ether4 ether5 ether6 ether7 ether8"
CFG_IF_NAMING_CHOICES="mac-sorted unsorted manual none"
CFG_IF_NAMING_DEF="none"


# Graft point for models: append to/reset CFG_MODEL_CHOICES, CFG_MODEL_DEF
if [ "$HAVE_MANUFACTURE_GRAFT_1" = "y" ]; then
    manufacture_graft_1
fi


if [ ${HAVE_OPT_MODEL} -eq 0 ]; then
    default_response=${CFG_MODEL_DEF}
    CFG_MODEL="${default_response}"

    if [ ${OPT_AUTO} -eq 0 ]; then
        echo ""
        echo "--------------------"
        echo "Model selection"
        echo "--------------------"
        echo ""
        
        response=""
        echo -n "Product model (${CFG_MODEL_CHOICES}) [${default_response}]: "
        ${READ_CMD} response
        echo ""
        if [ "x${response}" = "x" ]; then
            response=${default_response}
        fi
        CFG_MODEL="${response}"
    fi
else
    CFG_MODEL="${OPT_MODEL}"
fi
echo "== Using model: ${CFG_MODEL}"

eval 'enabled="${MODEL_'${CFG_MODEL}'_ENABLE}"'
if [ "${enabled}" -ne 1 ]; then
    echo "Error: unknown model: ${CFG_MODEL}"
    exit 1
fi

# Now get any model-specific settings
# XXXXX impl


if [ ${HAVE_OPT_KERNEL_TYPE} -eq 0 ]; then
    eval 'model_kernel_type_def="${MODEL_'${CFG_MODEL}'_KERNEL_TYPE}"'
    if [ "x${model_kernel_type_def}" = "x" ]; then
        default_response="${CFG_KERNEL_TYPE_DEF}"
    else
        default_response="${model_kernel_type_def}"
    fi
    CFG_KERNEL_TYPE=${default_response}

    if [ ${OPT_AUTO} -eq 0 ]; then
        echo ""
        echo "--------------------"
        echo "Kernel type selection"
        echo "--------------------"
        echo ""
        
        response=""
        echo -n "Kernel type (${CFG_KERNEL_TYPE_CHOICES}) [${default_response}]: "
        ${READ_CMD} response
        echo ""
        if [ "x${response}" = "x" ]; then
            response=${default_response}
        fi
        CFG_KERNEL_TYPE="${response}"
    fi
else
    CFG_KERNEL_TYPE="${OPT_KERNEL_TYPE}"
fi
echo "== Using kernel type: ${CFG_KERNEL_TYPE}"


if [ ${HAVE_OPT_LAYOUT} -eq 0 ]; then
    eval 'model_layout_def="${MODEL_'${CFG_MODEL}'_LAYOUT}"'
    if [ "x${model_layout_def}" = "x" ]; then
        default_response="${CFG_LAYOUT_DEF}"
    else
        default_response="${model_layout_def}"
    fi
    CFG_LAYOUT=${default_response}

    if [ ${OPT_AUTO} -eq 0 ]; then
        echo ""
        echo "--------------------"
        echo "Layout selection"
        echo "--------------------"
        echo ""
        
        response=""
        echo -n "Layout (${CFG_LAYOUT_CHOICES}) [${default_response}]: "
        ${READ_CMD} response
        echo ""
        if [ "x${response}" = "x" ]; then
            response=${default_response}
        fi
        CFG_LAYOUT="${response}"
    fi
else
    CFG_LAYOUT="${OPT_LAYOUT}"
fi
echo "== Using layout: ${CFG_LAYOUT}"


# XXX We could reasonably want to merge (overlay) the command line options
# on top of the model defaults, but do not do this currently.

if [ ${HAVE_OPT_PART_NAME_SIZE_LIST} -eq 0 ]; then
    eval 'model_part_name_size_list_def="${MODEL_'${CFG_MODEL}'_PART_NAME_SIZE_LIST}"'
    if [ "x${model_part_name_size_list_def}" = "x" ]; then
        default_response="${CFG_PART_NAME_SIZE_LIST_DEF}"
    else
        default_response="${model_part_name_size_list_def}"
    fi
    CFG_PART_NAME_SIZE_LIST=${default_response}

    if [ ${OPT_AUTO} -eq 0 ]; then
        echo ""
        echo "--------------------"
        echo "Partition name-size list selection"
        echo "--------------------"
        echo ""
        
        response=""
        echo -n "Paritition name-size list [${default_response}]: "
        ${READ_CMD} response
        echo ""
        if [ "x${response}" = "x" ]; then
            response=${default_response}
        fi
        CFG_PART_NAME_SIZE_LIST="${response}"
    fi
else
    CFG_PART_NAME_SIZE_LIST="${OPT_PART_NAME_SIZE_LIST}"
fi
echo "== Using partition name-size list: ${CFG_PART_NAME_SIZE_LIST}"

CFG_PART_NAME_SIZE_LIST_WRITEIMAGE=
ps_is_part=1
for part_name_size in ${CFG_PART_NAME_SIZE_LIST}; do
    if [ ${ps_is_part} -eq 1 ]; then
        CFG_PART_NAME_SIZE_LIST_WRITEIMAGE="${CFG_PART_NAME_SIZE_LIST_WRITEIMAGE} -p ${part_name_size}"
        ps_is_part=0
    else
        CFG_PART_NAME_SIZE_LIST_WRITEIMAGE="${CFG_PART_NAME_SIZE_LIST_WRITEIMAGE} -s ${part_name_size}"
        ps_is_part=1
    fi
done


if [ ${HAVE_OPT_DEV_LIST} -eq 0 ]; then
    eval 'model_dev_list_def="${MODEL_'${CFG_MODEL}'_DEV_LIST}"'
    if [ "x${model_dev_list_def}" = "x" ]; then
        default_response="${CFG_DEV_LIST_DEF}"
    else
        default_response="${model_dev_list_def}"
    fi
    CFG_DEV_LIST=${default_response}

    if [ ${OPT_AUTO} -eq 0 ]; then
        echo ""
        echo "--------------------"
        echo "Device list selection"
        echo "--------------------"
        echo ""
        
        response=""
        echo -n "Device list [${default_response}]: "
        ${READ_CMD} response
        echo ""
        if [ "x${response}" = "x" ]; then
            response=${default_response}
        fi
        CFG_DEV_LIST="${response}"
    fi
else
    CFG_DEV_LIST="${OPT_DEV_LIST}"
fi
echo "== Using device list: ${CFG_DEV_LIST}"

CFG_DEV_LIST_WRITEIMAGE=
for dev in ${CFG_DEV_LIST}; do
    CFG_DEV_LIST_WRITEIMAGE="${CFG_DEV_LIST_WRITEIMAGE} -d ${dev}"
done


if [ ${HAVE_OPT_IF_LIST} -eq 0 ]; then
    eval 'model_if_list_def="${MODEL_'${CFG_MODEL}'_IF_LIST}"'
    if [ "x${model_if_list_def}" = "x" ]; then
        default_response="${CFG_IF_LIST_DEF}"
    else
        default_response="${model_if_list_def}"
    fi
    CFG_IF_LIST=${default_response}

    if [ ${OPT_AUTO} -eq 0 ]; then
        echo ""
        echo "--------------------"
        echo "Interface list selection"
        echo "--------------------"
        echo ""
        
        response=""
        echo -n "Interface list [${default_response}]: "
        ${READ_CMD} response
        echo ""
        if [ "x${response}" = "x" ]; then
            response=${default_response}
        fi
        CFG_IF_LIST="${response}"
    fi
else
    CFG_IF_LIST="${OPT_IF_LIST}"
fi
echo "== Using interface list: ${CFG_IF_LIST}"


if [ ${HAVE_OPT_IF_NAMING} -eq 0 ]; then
    eval 'model_if_naming_def="${MODEL_'${CFG_MODEL}'_IF_NAMING}"'
    if [ "x${model_if_naming_def}" = "x" ]; then
        default_response="${CFG_IF_NAMING_DEF}"
    else
        default_response="${model_if_naming_def}"
    fi
    CFG_IF_NAMING=${default_response}

    if [ ${OPT_AUTO} -eq 0 ]; then
        echo ""
        echo "--------------------"
        echo "Interface naming selection"
        echo "--------------------"
        echo ""
        
        response=""
        echo -n "Interface naming [${default_response}]: "
        ${READ_CMD} response
        echo ""
        if [ "x${response}" = "x" ]; then
            response=${default_response}
        fi
        CFG_IF_NAMING="${response}"
    fi
else
    CFG_IF_NAMING="${OPT_IF_NAMING}"
fi
echo "== Using interface naming: ${CFG_IF_NAMING}"


IF_RUNNING_LIST=

# Sets global IF_RUNNING_LIST
update_if_running_list()
{
    IF_RUNNING_LIST=
    IFNF_RAW=`ifconfig -a | sed -e '/./{H;$!d;}' -e 'x;/Ethernet/!d' | egrep 'Ethernet|MTU'`

    # The names of the Ethernet interfaces
    IFNF_NAME_LINES=`echo "${IFNF_RAW}" | sed -n '1,${p;n}' | awk '{print $1}'`
    # The MACs of the Ethernet interfaces
    IFNF_MAC_LINES=`echo "${IFNF_RAW}" | sed -n '1,${p;n}' | sed 's/^.*HWaddr \(.*\)/\1/'`
    # The flags of the Ethernet interfaces
    IFNF_FLAGS_LINES=`echo "${IFNF_RAW}" | sed -n '2,${p;n}' | sed  's/^[ \t]*\(.*\)[ \t]MTU:.*/\1/'`

    uplist=
    line_count=1
    for mac in ${IFNF_MAC_LINES}; do
        flags=`echo "${IFNF_FLAGS_LINES}" | sed -n "${line_count}p"`
        name=`echo "${IFNF_NAME_LINES}" | sed -n "${line_count}p"`

        ##echo "mac: ${mac}"
        ##echo "name: ${name}"
        ##echo "fl: ${flags}"

        running=0
        echo "${flags}" | grep -q "RUNNING" && running=1
        if [ ${running} -eq 1 ]; then
            uplist="${uplist} ${mac}"
        fi

        line_count=$((${line_count} + 1))
    done

    IF_RUNNING_LIST=${uplist}
}


# Get the naming of all the interfaces
# ==================================================

IF_NAME_MAC_RAW=`ifconfig -a | grep 'Ethernet.*HWaddr' | sed 's/^\([^ ]*\) .*HWaddr \(.*\)/\2 \1/'`
IF_KERNNAMES_LIST=`echo "${IF_NAME_MAC_RAW}" | awk '{print $2}' | tr '\n' ' '`
IF_MACS_LIST=`echo "${IF_NAME_MAC_RAW}" | awk '{print $1}' | tr '\n' ' '`

if_num=1
for mac in ${IF_MACS_LIST}; do
    temp_mac_nums=`echo ${mac} | tr -d ':' | sed 's/\(..\)/ 0x\1/g'`
    dec_mac=`printf "%03d%03d%03d%03d%03d%03d" ${temp_mac_nums}`

    kernname=`echo ${IF_KERNNAMES_LIST} | awk '{print $'${if_num}'}'`
    targetname=`echo ${CFG_IF_LIST} | awk '{print $'${if_num}'}'`

    eval 'IF_MAC_'${dec_mac}'_MAC="'${mac}'"'
    eval 'IF_MAC_'${dec_mac}'_KERNNAME="'${kernname}'"'
    eval 'IF_MAC_'${dec_mac}'_TARGETNAME="'${targetname}'"'

    if_num=$((${if_num} + 1))
done


# 'mac-sorted' works by sorting the MAC addresses of the interfaces
if [ "${CFG_IF_NAMING}" = "mac-sorted" ]; then
    echo "- Assigning specified interface names in MAC-sorted order"

    # Build ordered list of decimal mac addresses from the mac list
    # We do this because 'sort -n' does not work for hex numbers.
    for mac in ${IF_MACS_LIST}; do
        temp_mac_nums=`echo ${mac} | tr -d ':' | sed 's/\(..\)/ 0x\1/g'`
        dec_mac=`printf "%03d%03d%03d%03d%03d%03d" ${temp_mac_nums}`

        dec_macs="${dec_macs} ${dec_mac}"
    done

    ORDERED_DEC_MACS=`echo ${dec_macs} | tr ' ' '\n' | sort -n | tr '\n' ' '`

    # Update the IF_MAC_*_TARGETNAME settings
    if_num=1
    for dec_mac in ${ORDERED_DEC_MACS}; do
        eval 'kernname="${IF_MAC_'${dec_mac}'_KERNNAME}"'
        targetname=`echo ${CFG_IF_LIST} | awk '{print $'${if_num}'}'`
        eval 'hex_mac="${IF_MAC_'${dec_mac}'_MAC}"'

        
        echo "-- Mapping MAC: ${hex_mac} from: ${kernname} to: ${targetname}"
        eval 'IF_MAC_'${dec_mac}'_TARGETNAME="'${targetname}'"'

        if_num=$((${if_num} + 1))
    done

elif [ "${CFG_IF_NAMING}" = "unsorted" ]; then
    echo "- Assigning specified interface names in kernel interface order"

    # There is nothing to do, this is currently the default

    # Just print what we'll be doing
    for mac in ${IF_MACS_LIST}; do
        temp_mac_nums=`echo ${mac} | tr -d ':' | sed 's/\(..\)/ 0x\1/g'`
        dec_mac=`printf "%03d%03d%03d%03d%03d%03d" ${temp_mac_nums}`

        eval 'kernname="${IF_MAC_'${dec_mac}'_KERNNAME}"'
        eval 'targetname="${IF_MAC_'${dec_mac}'_TARGETNAME}"'
        eval 'hex_mac="${IF_MAC_'${dec_mac}'_MAC}"'

        echo "-- Mapping MAC: ${hex_mac} from: ${kernname} to: ${targetname}"
    done


elif [ "${CFG_IF_NAMING}" = "manual" ]; then

    # XXX ask them for each kernname, plug in MAC

    for intf in ${CFG_IF_LIST}; do
        update_if_running_list
        prev_uplist=${IF_RUNNING_LIST}
        ##echo "prev ul: ${uplist}"

        echo "=== Change the link state of the interface you want to be '${intf}', and hit enter:"
        ${READ_CMD} junk

        update_if_running_list
        new_uplist=${IF_RUNNING_LIST}
        ##echo "new ul: ${uplist}"

        diff_mac=`echo "${prev_uplist} ${new_uplist}" | tr ' ' '\n' | sort | uniq -u`

        if [ -z ${diff_mac} ]; then
            echo "== Warning: no change in link state detected for ${intf}, ${intf} not assigned"
            continue
        fi

        temp_mac_nums=`echo ${diff_mac} | tr -d ':' | sed 's/\(..\)/ 0x\1/g'`
        dec_mac=`printf "%03d%03d%03d%03d%03d%03d" ${temp_mac_nums}`

        eval 'kernname="${IF_MAC_'${dec_mac}'_KERNNAME}"'
        eval 'IF_MAC_'${dec_mac}'_TARGETNAME="'${intf}'"'

        echo "-- Mapping MAC: ${diff_mac} from: ${kernname} to: ${intf}"
    done

elif [ "${CFG_IF_NAMING}" = "none" ]; then
    echo "- Disabling interface renaming."
else
    echo "*** Error: bad CFG_IF_NAMING setting"
    exit 1
fi




# ==================================================

WI_CMD="/sbin/writeimage.sh -m ${WRITEIMAGE_ARGS} -k ${CFG_KERNEL_TYPE}  \
    -L ${CFG_LAYOUT} ${CFG_DEV_LIST_WRITEIMAGE} ${CFG_PART_NAME_SIZE_LIST_WRITEIMAGE}"

echo "== Calling writeimage to image system"
echo "--- Executing: ${WI_CMD}"

FAILURE=0
${WI_CMD} || FAILURE=1
if [ ${FAILURE} -eq 1 ]; then
    echo "Error: writeimage failed, exiting."
    exit 1
fi

# ==================================================


# Do the post-install stuff plan : slurp in layout_settings.sh, mount all
# partitions, copy over any needed binaries (like mddbreq), write bindings
# into the mfg db (like interface naming bindings).



# --------------------------------------------------
# Get all our partition related settings in

IL_LAYOUT=${CFG_LAYOUT}
export IL_LAYOUT

if [ -r ${IL_PATH} ]; then
    . ${IL_PATH}
else
    echo "*** Invalid image layout settings."
    usage
fi

# Now set the targets (devices) that the user specified

# Set TARGET_NAMES, which are things like 'DISK1'
eval 'TARGET_NAMES="${IL_LO_'${IL_LAYOUT}'_TARGETS}"'
dev_num=1
dev_list="${CFG_DEV_LIST}"
for tn in ${TARGET_NAMES}; do
    nname=`echo ${dev_list} | awk '{print $'${dev_num}'}'`
    if [ ! -z "${nname}" ]; then
        eval 'IL_LO_'${IL_LAYOUT}'_TARGET_'${tn}'_DEV="${nname}"'
    else
        eval 'curr_dev="${IL_LO_'${IL_LAYOUT}'_TARGET_'${tn}'_DEV}"'
        if [ -z "${curr_dev}" ]; then
            echo "*** Not enough device targets specified."
            exit 1
        fi
    fi
    dev_num=$((${dev_num} + 1))
done

if [ -r ${IL_PATH} ]; then
    . ${IL_PATH}
else
    echo "*** Invalid image layout settings."
    usage
fi


# --------------------------------------------------
# Mount everything, arbitrarily from image 1

mkdir -p ${MFG_MOUNT}

inum=1
loc_list=""
eval 'loc_list="${IL_LO_'${IL_LAYOUT}'_IMAGE_'${inum}'_LOCS}"'

for loc in ${loc_list}; do
    add_part=""
    eval 'add_part="${IL_LO_'${IL_LAYOUT}'_LOC_'${loc}'_PART}"'

    if [ ! -z "${add_part}" ]; then
        # Only add it on if it is unique
        eval 'curr_list="${IMAGE_'${inum}'_PART_LIST}"'

        present=0
        echo "${curr_list}" | grep -q " ${add_part} " - && present=1
        if [ ${present} -eq 0 ]; then
            eval 'IMAGE_'${inum}'_PART_LIST="${IMAGE_'${inum}'_PART_LIST} ${add_part} "'
        fi
    fi
done

inum=1
eval 'part_list="${IMAGE_'${inum}'_PART_LIST}"'
UNMOUNT_LIST=

for part in ${part_list}; do
    eval 'part_dev="${IL_LO_'${IL_LAYOUT}'_PART_'${part}'_DEV}"'
    eval 'part_mount="${IL_LO_'${IL_LAYOUT}'_PART_'${part}'_MOUNT}"'
    eval 'part_fstype="${IL_LO_'${IL_LAYOUT}'_PART_'${part}'_FSTYPE}"'

    if [ -z "${part}" -o -z "${part_dev}" \
        -o -z "${part_mount}" -o -z "${part_fstype}" \
        -o "${part_fstype}" = "swap" ]; then
        continue
    fi

    mount_point="${MFG_MOUNT}/${part_mount}"

    mkdir -p ${mount_point}
    unmount ${mount_point} > /dev/null 2>&1
    FAILURE=0
    mount ${part_dev} ${mount_point} || FAILURE=1
    if [ ${FAILURE} -eq 1 ]; then
        echo "*** Could not mount partition ${part_dev} on ${mount_point}"
        exit 1
    fi
    UNMOUNT_LIST="${mount_point} ${UNMOUNT_LIST}"
done

# Copy over files from the image into the mfg environment
for file in ${MFG_POST_COPY}; do
    mkdir -p `dirname $file`
    cp -p ${MFG_MOUNT}/$file $file
done


# Generate a random host id which is 48 bits long
CFG_HOSTID=`dd if=/dev/urandom bs=1 count=6 2> /dev/null | od -x | head -1 | \
    awk '{print $2 $3 $4}'`
echo "-- Writing Host ID: ${CFG_HOSTID}"


# XXXX prompt about other things like licenses, have customer graft point

mkdir -m 755 -p ${MFG_DB_DIR}
rm -f ${MFG_DB_PATH}

${MDDBREQ} -c ${MFG_DB_PATH} set modify "" /mfg/mfdb/system/model string "${CFG_MODEL}"
${MDDBREQ} -c ${MFG_DB_PATH} set modify "" /mfg/mfdb/system/hostid string "${CFG_HOSTID}"

# Write out the list of interface names for the model in /mfg/mfdb/interface/name/#/name
if [ "${CFG_IF_NAMING}" != "none" ]; then
    if_num=1
    for ifn in ${CFG_IF_LIST}; do
        ${MDDBREQ} -c ${MFG_DB_PATH} set modify "" /mfg/mfdb/interface/name/${if_num} uint32 ${if_num}
        ${MDDBREQ} -c ${MFG_DB_PATH} set modify "" /mfg/mfdb/interface/name/${if_num}/name string "${ifn}"
        if_num=$((${if_num} + 1))
    done
fi

#
# Write out the list of mac -> interface name mappings in
#  /mfg/mfdb/interface/map/macifname/1/macaddr and
#  /mfg/mfdb/interface/map/macifname/1/name
#
if [ "${CFG_IF_NAMING}" = "none" ]; then
    ${MDDBREQ} -c ${MFG_DB_PATH} set modify "" /mfg/mfdb/interface/map/enable bool false
else
    ${MDDBREQ} -c ${MFG_DB_PATH} set modify "" /mfg/mfdb/interface/map/enable bool true

    map_num=1
    for mac in ${IF_MACS_LIST}; do
        temp_mac_nums=`echo ${mac} | tr -d ':' | sed 's/\(..\)/ 0x\1/g'`
        dec_mac=`printf "%03d%03d%03d%03d%03d%03d" ${temp_mac_nums}`

        eval 'kernname="${IF_MAC_'${dec_mac}'_KERNNAME}"'
        eval 'targetname="${IF_MAC_'${dec_mac}'_TARGETNAME}"'

        if [ -z "${targetname}" ]; then
            echo "-- Ignoring unmapped mac ${mac} on ${kernname}"
            continue
        fi
        echo "-- Writing mapping for ${mac} from ${kernname} to ${targetname}" 

        ${MDDBREQ} -c ${MFG_DB_PATH} set modify "" /mfg/mfdb/interface/map/macifname/${map_num} uint32 ${map_num}
        ${MDDBREQ} -c ${MFG_DB_PATH} set modify "" /mfg/mfdb/interface/map/macifname/${map_num}/macaddr macaddr802 "${mac}"
        ${MDDBREQ} -c ${MFG_DB_PATH} set modify "" /mfg/mfdb/interface/map/macifname/${map_num}/name string "${targetname}"


        map_num=$((${map_num} + 1))

    done
fi

chmod a+r ${MFG_DB_PATH}



# Unmount all the partitions
for ump in ${UNMOUNT_LIST}; do
    umount ${ump} > /dev/null 2>&1
done

echo "-- Done."
