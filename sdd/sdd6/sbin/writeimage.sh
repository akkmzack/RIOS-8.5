#!/bin/sh

#
#  Filename:  $Source$
#  Revision:  $Revision: 106044 $
#  Date:      $Date: 2012-04-30 10:27:33 -0700 (Mon, 30 Apr 2012) $
#  Author:    $Author: clala $
# 
#  (C) Copyright 2002-2005 Tall Maple Systems, Inc.  
#  All rights reserved.
#

# This script is used to write an image or images to a disk.  There are two
# modes for this program: install a single image (possibly also installing
# the boot loader), and manufacture mode, which fully partitions a disk or
# disks, makes relevant file systems, and installs the image.  A disk cannot
# be manufactured when any part of it is mounted, nor can an image be
# installed over the running image in the non-manufacturing case.

# There are a number of supported layouts, see the layout_settings.sh file
# for more information.  The currently supported layouts are: 1) single
# disk, two image (standard) 2) two disks, two images on first, replicated
# layout (no images) on second (replicate) 3) single disk, single image
# (compact) In all layouts, the entire disk is used, and (during
# manufacturing) any existing paritions are destroyed.


# XXXX need way to call in firstboot.sh to generate grub / fstab / do any
# other post-install fixups.  This is because the version of writeimage.sh
# that installed the image may be much older than the image (which does
# contain a new writeimage).

# XXXX the -t parameter does not currently work during manufacturing


PATH=/mfg:/usr/bin:/bin:/usr/sbin:/sbin
export PATH

usage()
{
    echo "usage: $0 -m [-M MODEL] [-u URL] [-f FILE] [-L LAYOUT_TYPE] -d /DEV/N1"
    echo "             [-p PARTNAME -s SIZE] [-t] [-k KERNEL_TYPE] [-S STORAGE PROFILE] "
    echo "usage: $0 -i [-M MODEL] [-u URL] [-f FILE] [-d /DEV/N1] -l {1,2} [-t] [-k KERNEL_TYPE] "

    echo ""
    echo "Either '-u' (url) or '-f' (file) must be specified."
    exit 1
}


# ==================================================
# Cleanup when we are finished or interrupted
# ==================================================
cleanup()
{
    # Get out of any dirs we might remove
    cd /

    # delete temp files and potentially unmount partitions
    if [ ! -z ${UNMOUNT_TMPFS} ]; then
        umount ${UNMOUNT_TMPFS}
    fi

    if [ ! -z ${WORKSPACE_DIR} ]; then
        rm -rf ${WORKSPACE_DIR}
    fi

    rm -f ${SYSIMAGE_FILE_TAR}

    if [ ! -z ${UNMOUNT_WORKINGFS} ]; then
        umount ${UNMOUNT_WORKINGFS}
    fi

    if [ ! -z ${UNMOUNT_EXTRACTFS} ]; then
        umount ${UNMOUNT_EXTRACTFS}
    fi
}


# ==================================================
# Cleanup when called from 'trap' for ^C, signal, or fatal error
# ==================================================
cleanup_exit()
{
    cleanup
    [ $READ_ONLY_ROOT -ne 0 ] && mount / -o remount,ro
    exit $1
}

# ==================================================
# Function to compute and write partition tables
# ==================================================
do_partition_disks()
{
    # We assume caller makes sure any disk we care about is unmounted

    echo "==== Disk partitioning"
    # Calculate a new partition table 


    # Loop over each target (things like DISK1)
    for target in ${TARGET_CHANGE_LIST}; do
        ##echo "target= ${target}"
        eval 'target_size="${IL_LO_'${IL_LAYOUT}'_TARGET_'${target}'_CURR_SIZE_MEGS}"'
        eval 'target_cyl_size="${IL_LO_'${IL_LAYOUT}'_TARGET_'${target}'_CURR_CYL_MEGS}"'
        eval 'target_dev="${IL_LO_'${IL_LAYOUT}'_TARGET_'${target}'_DEV}"'

        # Pass one: calculate total request size, num partitions, aggregate
        # growth
        
        total_size=0
        growth_cap_aggregate=0
        growth_weight_aggregate=0
        num_parts=0
        last_part=

        echo "=== Calculating partition table for ${target}"

        # Loop over each PART / partition (things like BOOTMGR)
        eval 'part_list="${TARGET_'${target}'_ALL_PARTS}"'
        eval 'part_num_list="${TARGET_'${target}'_ALL_PART_NUMS}"'

        if [ -z "${part_list}" ]; then
            echo "*** No partition list for target ${target}"
            cleanup_exit 12 # lc_err_upgrade_partition_failure
        fi

        for part in ${part_list}; do
            ##echo "part= ${part}"

            # Get the size (in MB)
            eval 'num_meg="${IL_LO_'${IL_LAYOUT}'_PART_'${part}'_SIZE}"'
            eval 'IL_LO_'${IL_LAYOUT}'_PART_'${part}'_CURR_SIZE='"${num_meg}"
            if [ -z "$num_meg" ]; then
                continue;
            fi
            
            this_size=${num_meg}
            
            total_size=`expr ${total_size} + ${this_size}`
            
            # Add up growth values as well
            eval 'growth_cap="${IL_LO_'${IL_LAYOUT}'_PART_'${part}'_GROWTHCAP}"'
            eval 'growth_weight="${IL_LO_'${IL_LAYOUT}'_PART_'${part}'_GROWTHWEIGHT}"'

            if [ ! -z "$growth_cap" ]; then
                growth_cap_aggregate=`expr ${growth_cap_aggregate} + ${growth_cap}`
            fi
            if [ ! -z "$growth_weight" ]; then
                growth_weight_aggregate=`expr ${growth_weight_aggregate} + ${growth_weight}`
            fi
            num_parts=`expr ${num_parts} + 1`
            last_part=${part}
        done

        # Be conservative about rounding error: loose a cyl per partition
        unalloc_size=`expr ${target_size} - ${total_size} - ${num_parts} \* \
            ${target_cyl_size}`

        echo "== Device size:                ${target_size} M"
        echo "== Allocated fixed size:       ${total_size} M"
        echo "== Unallocated by fixed:       ${unalloc_size} M"

        #
        # Pass two: calculate final partition sizes
        # 
        # The plan is to give each partition which is growable it's 'fair
        # share' of the unallocated space.  
        #
        # XXX right now the growth weight is ignored
        #
        # We do this by dividing the individual growth cap by the aggregate
        # growth caps and multiplying by the total unallocated size.  This
        # is then clamped at the individual growth cap.
        #

        # Loop over each PART / partition (things like BOOTMGR)
        for part in ${part_list}; do
            ##echo "part= ${part}"

            eval 'growth_cap="${IL_LO_'${IL_LAYOUT}'_PART_'${part}'_GROWTHCAP}"'
            eval 'curr_size="${IL_LO_'${IL_LAYOUT}'_PART_'${part}'_CURR_SIZE}"'

            if [ -z "${curr_size}" -o -z "${growth_cap}" ]; then
                continue;
            fi

            # Now calc this partition's share of the unallocated space
            my_share=`expr \( ${growth_cap} \* 1000 / ${growth_cap_aggregate} \) \
                \* ${unalloc_size} / 1000`

            ##echo "ms= ${my_share}"

            # Clamp at our cap
            new_size=`expr ${curr_size} + ${my_share}`
            if [ ${new_size} -gt ${growth_cap} ]; then
                new_size=${growth_cap}
            fi

            eval 'IL_LO_'${IL_LAYOUT}'_PART_'${part}'_CURR_SIZE='"${new_size}"
            total_size=`expr ${total_size} + \( ${new_size} - ${curr_size} \)`
        done
        unalloc_size=`expr ${target_size} - ${total_size}`

        echo "== Unallocated after growth:   ${unalloc_size} M"


        # Pass three: emit partition lines for each partition

        temp_ptable=/tmp/ptable-${target}.$$
        rm -f ${temp_ptable}

        eval 'last_part_fill="${IL_LO_'${IL_LAYOUT}'_OPT_LAST_PART_FILL}"'
        if [ -z "${last_part_fill}" ]; then
            last_part_fill=1
        fi

        # Loop over each PART / partition (things like BOOTMGR) in number order
        for pn in ${part_num_list}; do
            
            # Find this numbered partition
            found=0
            for part in ${part_list}; do

                eval 'curr_num="${IL_LO_'${IL_LAYOUT}'_PART_'${part}'_PART_NUM}"'
                if [ ${curr_num} -ne ${pn} ]; then
                    continue;
                fi

                start_meg=
                num_meg=
                id=
                bootable=

                eval 'part_id="${IL_LO_'${IL_LAYOUT}'_PART_'${part}'_PART_ID}"'
                eval 'curr_size="${IL_LO_'${IL_LAYOUT}'_PART_'${part}'_CURR_SIZE}"'
                eval 'is_bootable="${IL_LO_'${IL_LAYOUT}'_PART_'${part}'_BOOTABLE}"'

                id=${part_id}
                num_meg=${curr_size}
                if [ ! -z ${is_bootable} ]; then
                    bootable='*'
                fi


                # Special case: the extended partitions partition
                if [ "$id" = "0f" ]; then
                    found=1
                    printf ",,${id},${bootable}\n" >> ${temp_ptable}
                    break
                fi


                # For first partition, we leave some slack for the stuff at
                # the start of the disk

                if [ "$pn" = "1" ]; then
                    num_meg=`expr $num_meg - 1`
                fi

                # If we're the last partition, take all the remaining space
                if [ ${last_part_fill} -eq 1 -a "${part}" = "${last_part}" ]; then
                    num_meg=
                fi

                printf "${start_meg},${num_meg},${id},${bootable}\n" >> ${temp_ptable}

                found=1
                break
            done

            if [ ${found} -ne 1 ]; then
                echo "*** Could not find partition number ${pn} for target ${target}"
                cleanup_exit 12 #lc_err_upgrade_partition_failure
            fi

        done

        echo "=== Zeroing existing partition table on ${target_dev}"

        FAILURE=0
        dd if=/dev/zero of=${target_dev} bs=512 count=1 || FAILURE=1
        if [ ${FAILURE} -eq 1 ]; then
            echo "*** Could not zero out ${target_dev}"
            cleanup_exit 12 #lc_err_upgrade_partition_failure
        fi

        echo "=== Writing partition table to ${target}"
	
	#XXX/evan this is kinda hacky, but we'll need a better 
	#system to get rid of it.
	if [ ${PTOOL} = "parted" -a ${target} = "DISK2" ]; then
	    parted="parted -s"

            #first we want to set the label on the disk.
	    ${parted} ${target_dev} mklabel gpt 
	    if [ $? != 0 ]; then
		echo "*** Could not make partition table on ${target_dev}"
		cleanup_exit 12 #lc_err_upgrade_partition_failure
	    fi
	    
	    pt_num=1
	    disk_pos=0
	    for line in `cat ${temp_ptable}`; do 
		line=`echo $line | tr , " "`
		pt_size=`echo $line | awk '{print \$1}'`
		pt_type=`echo $line | awk '{print \$2}'`
		pt_boot=`echo $line | awk '{print \$3}'`

		#if unspecified, take up the rest of the disk.
		segstore=0
		if [ ${pt_size} = "da" -o ${pt_size} = "83" ]; then 
		    if [ "${pt_type}" != "" ]; then
			#do nothing.
			nop=1
		    else
			blocks_line=`${parted} ${target_dev} print free | grep Free`
			pt_end=`echo ${blocks_line} | tr : " " | awk '{print \$2}'`
			pt_type="da"
			segstore=1
		    fi
		fi

		#parted doesn't care about extended partitions
		#but we have to do something to keep the part #s the same.
		if [ ${pt_size} = "0f" ]; then 
		    pt_size=1
		    pt_type=f
		fi
		
		if [ ${segstore} -eq 0 ]; then
		    pt_end=`expr ${disk_pos} + ${pt_size}`
		fi

		echo "${parted} ${target_dev} mkpart ${pt_type} ${disk_pos} ${pt_end}"
		${parted} ${target_dev} mkpart ${pt_type} ${disk_pos} ${pt_end}
		if [ "x${pt_boot}" != "x" ]; then
		    ${parted} ${target_dev} set ${pt_num} boot on
		fi
		
		pt_num=`expr ${pt_num} + 1` 
		disk_pos=${pt_end}
	    done 

	else 

	    FAILURE=0
	    cat ${temp_ptable} | sfdisk -L -uM --no-reread ${target_dev} || FAILURE=1
	    if [ ${FAILURE} -eq 1 ]; then
		echo "*** Could not make partition table on ${target_dev}"
		cleanup_exit 12 #lc_err_upgrade_partition_failure
	    fi
	fi
    done
}


#
#
#
do_raid_fixup() 
{
    echo "==== Doing RAID Fixup."
    echo 

    if [ "x$1" = "x" ]; then 
        echo "Performing disk/raid configuration"
	rrdm_tool.py -m ${MODEL} -u ${STORAGE_PROFILE_CMD}
        if [ $? -ne 0 ]; then
            echo "Error during disk manufacturing"
            exit 1
        fi
	rrdm_res=`rrdm_tool.py -m ${MODEL} -l ${STORAGE_PROFILE_CMD}`
    else
	rrdm_res=`/opt/hal/bin/raid/rrdm_tool.py -l ${STORAGE_PROFILE_CMD}`
    fi
    if [ $? -ne 0 ]; then 
	echo "Error retrieving volume details from rrdm_tool"
	echo $rrdm_res
	exit 1  
    fi 

    if [ "x${rrdm_res}" = xNOP ]; then
	echo "No RAID setup needed."
	RAID_FIXUP_DONE=true
	return
    else
	echo "No errors during RAID setup." 
	#raids should be running here, fixup the 
	#install values so writeimage puts files
	#in the right place.
	for pair in ${rrdm_res}; do
	    name=`echo $pair | awk 'BEGIN{FS=":"} {print $1}'`
	    dev=`echo $pair | awk 'BEGIN{FS=":"} {print $2}'`
	    fstype=`echo $pair | awk 'BEGIN{FS=":"} {print $3}'`
	    part_id=`echo $pair | awk 'BEGIN{FS=":"} {print $4}'`
	    reserve_sb_space=`echo $pair | awk 'BEGIN{FS=":"} {print $5}'`

	    echo "Fixing $name as /dev/$dev"
	    if [ x$name = 'xswap' ]; then 
		fi_label="SWAP"
		fi_dir=""		
		fi_ext=""
		fi_ext_pre=""
		fi_mount="swap"
		fi_ext_excl=""
	    elif [ x$name = 'xsegstore' ]; then 
		fi_label="DATA"
		fi_dir=""		
		fi_ext=""
		fi_ext_pre=""
		fi_mount=""
		fstype=""
		fi_ext_excl=""
	    elif [ x$name = 'xpfs' ]; then 
		fi_label="SMB"
		fi_dir="/"		
		fi_ext="./proxy"
		fi_ext_pre=$fi_ext
		fi_mount="/proxy"
		fi_ext_excl=""
            elif [ x$name = 'xbootmgr' ]; then
                fi_label="BOOTMGR"
                fi_dir="/"
                fi_ext="./bootmgr"
                fi_ext_pre=$fi_ext
                fi_mount="/bootmgr"
                fi_ext_excl=""
            elif [ x$name = 'xboot_1' ]; then
                fi_label="BOOT_1"
                fi_dir="/"
                fi_ext="./boot"
                fi_ext_pre=$fi_ext
                fi_mount="/boot"
		fi_ext_excl=""
            elif [ x$name = 'xboot_2' ]; then
                fi_label="BOOT_2"
                fi_dir="/"
                fi_ext="./boot"
                fi_ext_pre=$fi_ext
                fi_mount="/boot"
		fi_ext_excl=""
            elif [ x$name = 'xroot_1' ]; then
                fi_label="ROOT_1"
                fi_dir="/"
                fi_ext="./"
                fi_ext_pre=$fi_ext
                fi_mount="/"
                fi_ext_excl="./bootmgr ./boot ./var ./config ./data"
            elif [ x$name = 'xroot_2' ]; then
                fi_label="ROOT_2"
                fi_dir="/"
                fi_ext="./"
                fi_ext_pre=$fi_ext
                fi_mount="/"
                fi_ext_excl="./bootmgr ./boot ./var ./config ./data"
            elif [ x$name = 'xconfig' ]; then
                fi_label="CONFIG"
                fi_dir="/"
                fi_ext="./config"
                fi_ext_pre=$fi_ext
                fi_mount="/config"
		fi_ext_excl=""
            elif [ x$name = 'xdata' ]; then
                fi_label="DATA"
                fi_dir="/"
                fi_ext="./data"
                fi_ext_pre=$fi_ext
                fi_mount="/data"
		fi_ext_excl=""
            elif [ x$name = 'xshadow' ]; then
                fi_label="SHADOW"
                fi_dir=""
                fi_ext=""
                fi_ext_pre=""
                fi_mount=""
		fstype=""
		fi_ext_excl=""
	    elif [ x$name = 'xvar' ]; then 
		fi_label="VAR"
		fi_dir="/"		
		fi_ext="./var"
		fi_ext_pre="/var"
		fi_mount=$fi_ext_pre
		fi_ext_excl=""
            elif [ "x$name" = "xscratch" ]; then
                fi_label="SCRATCH"
                fi_dir="/"
                fi_ext="./scratch"
                fi_ext_pre="/scratch"
                fi_mount=$fi_ext_pre
		fi_ext_excl=""
            elif [ "x$name" = "xvdata" ]; then
                fi_label="VDATA"                                           
                fi_dir=""                                                 
                fi_ext=""                                                 
                fi_ext_pre=""                                               
                fi_mount=""                                          
                fstype=""        
		fi_ext_excl=""
            elif [ "x$name" = "xrsp" ]; then
                fi_label="RSP"
                fi_dir=""
                fi_ext=""
                fi_ext_pre=""
                fi_mount=""
                fstype=""
		fi_ext_excl=""
            elif [ "x$name" = "xhdboot_1" ]; then
                fi_label="HDBOOT_1"
                fi_dir="/"
                fi_ext="./boot"
                fi_ext_pre=$fi_ext
                fi_mount="/tmp/boot1"
		fi_ext_excl=""
            elif [ "x$name" = "xhdboot_2" ]; then
                fi_label="HDBOOT_2"
                fi_dir="/"
                fi_ext="./boot"
                fi_ext_pre=$fi_ext
                fi_mount="/tmp/boot2"
		fi_ext_excl=""
            elif [ "x$name" = "xhdroot_1" ]; then
                fi_label="HDROOT_1"
                fi_dir="/"
                fi_ext="./"
                fi_ext_pre=$fi_ext
                fi_mount="/tmp/root1"
                fi_ext_excl="./bootmgr ./boot ./var ./config ./data"
            elif [ "x$name" = "xhdroot_2" ]; then
                fi_label="HDROOT_2"
                fi_dir="/"
                fi_ext="./"
                fi_ext_pre=$fi_ext
                fi_mount="/tmp/root2"
                fi_ext_excl="./bootmgr ./boot ./var ./config ./data"
            else
                # default to a blank volume
                fi_label=${name}
                fi_dir=""
                fi_ext=""
                fi_ext_pre=""
                fi_mount=""
                fstype=""
		fi_ext_excl=""
	    fi
	    eval 'IL_LO_'${IL_LAYOUT}'_PARTS="$IL_LO_'${IL_LAYOUT}'_PARTS '$fi_label'"'

	    for i in 1 2; do
		eval 'IL_LO_'${IL_LAYOUT}'_IMAGE_'$i'_LOCS="$IL_LO_'${IL_LAYOUT}'_IMAGE_'$i'_LOCS '$fi_label'_1"'
		eval 'IMAGE_'$i'_PART_LIST="$IMAGE_'$i'_PART_LIST '$fi_label'"'
	    done

	    if [ ${DO_MANUFACTURE} -eq 1 ]; then
		eval 'TARGET_DISK1_CHANGE_PARTS="$TARGET_DISK1_CHANGE_PARTS '$fi_label'"'
                case ${fi_label} in
                    "ROOT_1"|"ROOT_2"|"BOOT_1"|"BOOT_2")
		        eval 'TARGET_DISK1_CHANGE_LOCS="$TARGET_DISK1_CHANGE_LOCS '$fi_label'"'
                        ;;
                    *)
		        eval 'TARGET_DISK1_CHANGE_LOCS="$TARGET_DISK1_CHANGE_LOCS '$fi_label'_1"'
                        ;;
                esac
	    fi 

	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$fi_label'_DEV=/dev/'$dev
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$fi_label'_MOUNT='$fi_mount
	    if [ x$fi_label = xSWAP ]; then 
		eval 'IL_LO_'${IL_LAYOUT}'_PART_'$fi_label'_LABEL='
	    else
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$fi_label'_LABEL='$fi_label
	    fi
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$fi_label'_FSTYPE='$fstype
	    eval 'IL_LO_'${IL_LAYOUT}'_PART_'$fi_label'_PART_ID='$part_id
            eval 'IL_LO_'${IL_LAYOUT}'_PART_'$fi_label'_RSV_SB_SPACE='$reserve_sb_space
	    
            # XXX/munirb: For BOOT and ROOT partitions, we already have the 
            # partition number suffix (_X), there is no need to add '_1'
            # like we do for VAR, etc to maintain layout_settings naming
            case ${fi_label} in
                "ROOT_1"|"ROOT_2"|"BOOT_1"|"BOOT_2")
	            eval 'IL_LO_'${IL_LAYOUT}'_LOC_'$fi_label'_PART='$fi_label
   	            eval 'IL_LO_'${IL_LAYOUT}'_LOC_'$fi_label'_DIR='$fi_dir
	            eval 'IL_LO_'${IL_LAYOUT}'_LOC_'$fi_label'_IMAGE_EXTRACT='$fi_ext
	            eval 'IL_LO_'${IL_LAYOUT}'_LOC_'$fi_label'_IMAGE_EXTRACT_PREFIX='$fi_ext_pre
	            eval 'IL_LO_'${IL_LAYOUT}'_LOC_'$fi_label'_IMAGE_EXTRACT_EXCLUDE=${fi_ext_excl}'
                    ;;
                *)
	            eval 'IL_LO_'${IL_LAYOUT}'_LOC_'$fi_label'_1_PART='$fi_label
   	            eval 'IL_LO_'${IL_LAYOUT}'_LOC_'$fi_label'_1_DIR='$fi_dir
	            eval 'IL_LO_'${IL_LAYOUT}'_LOC_'$fi_label'_1_IMAGE_EXTRACT='$fi_ext
	            eval 'IL_LO_'${IL_LAYOUT}'_LOC_'$fi_label'_1_IMAGE_EXTRACT_PREFIX='$fi_ext_pre
	            eval 'IL_LO_'${IL_LAYOUT}'_LOC_'$fi_label'_1_IMAGE_EXTRACT_EXCLUDE=${fi_ext_excl}'
                    ;;
        esac

	done
    fi

    RAID_FIXUP_DONE=true
}

# XXX This assumes a 1K blocksize (which is what mke2fs assumes on the
# cmdline unless you specify -b 4096, at which time you need to divide this
# by 4, if that changes.
# 
RESERVE_BLOCKS=1024 # reserve 1024 x 1024 = 1MB at the end of ext3 partitions.

# for new hw single disk units, we want to reserve space at
# the end of the ext3 partitions so we could add a MD SB in the future.
#
do_calculate_blocks_w_reserve()
{
    dev=$1
    # if we've been told to reserve some space, we need to calc
    # the number of blocks to tell ext3 to use.
    total_blocks=`sfdisk -s ${dev}`     # in kB

    if [ ${total_blocks} -le ${RESERVE_BLOCKS} ]; then
        echo "*** Block size too small when calculating reserve blocks on $dev"
        cleanup_exit 13 #lc_err_upgrade_fs_creation_failure 
    fi

    expr ${total_blocks} - ${RESERVE_BLOCKS}
}

# ==================================================
# Make new filesystems on disk or disks
# ==================================================
do_make_filesystems()
{
    # We assume caller makes sure any partition we care about is unmounted

    echo "==== Making filesystems"

    # ==================================================
    # Create filesystems / swap
    # ==================================================
    for target in ${TARGET_CHANGE_LIST}; do
        ##echo "target= ${target}"

        eval 'change_parts="${TARGET_'${target}'_CHANGE_PARTS}"'

        for part in ${change_parts}; do
            ##echo "part= ${part}"

            eval 'part_id="${IL_LO_'${IL_LAYOUT}'_PART_'${part}'_PART_ID}"'
            eval 'dev="${IL_LO_'${IL_LAYOUT}'_PART_'${part}'_DEV}"'
            eval 'label="${IL_LO_'${IL_LAYOUT}'_PART_'${part}'_LABEL}"'
            eval 'fstype="${IL_LO_'${IL_LAYOUT}'_PART_'${part}'_FSTYPE}"'
            eval 'reserve_sb_space="${IL_LO_'${IL_LAYOUT}'_PART_'${part}'_RSV_SB_SPACE}"'
            # init the number of blocks to use to empty, so that mke2fs would choose
            # the right value on old units
            blocks=
            

            if [ -z "${part_id}" -o -z "${dev}" ]; then
                continue;
            fi

            if [ "$fstype" = "ext2" -o "$fstype" = "ext3" ]; then
                jargs=
                if [ "$fstype" = "ext3" ]; then
                    jargs=-j
                    if [ "x$reserve_sb_space" = "xtrue" ]; then
                        # if we've been told to reserve some space, we need to calc
                        # the number of blocks to tell ext3 to use.
                        blocks=`do_calculate_blocks_w_reserve $dev`
                    fi
                fi

                label_args=
                if [ ! -z "${label}" ]; then
                    label_args="-L ${label}"
                fi

                echo "== Creating filesystem on ${dev} for ${part}"

		lpct=0
                while [ ! -b ${dev} ]; do
		    if [ ${lpct} -lt 10 ]; then 
			sleep 1
			lpct=`expr ${lpct} + 1`
		    else
			echo "*** Could not make filesystem on ${dev} (${dev} does not exist as a block device)"
			cleanup_exit 13 #lc_err_upgrade_fs_creation_failure
		    fi
                done                               

                FAILURE=0
                echo "mke2fs ${MKE2FS_BASE_OPTIONS} -q ${label_args} ${jargs} ${dev} ${blocks}"
                case ${IL_LAYOUT} in
                    "BOBRDM"|"BOBSTD")
                        # At manufacturing time, /etc/fstab isn't present, don't rely on it
                        # to unmount the alternate partitions, everything is unmounted
                        # at manufacturing so just do the formatting as normal
                        if [ ${DO_MANUFACTURE} -eq 1 ]; then
                            mke2fs ${MKE2FS_BASE_OPTIONS} -q ${label_args} ${jargs} ${dev} ${blocks} || FAILURE=1
                            if [ ${FAILURE} -eq 1 ]; then
                                echo "*** Could not make filesystem on ${dev} (mke2fs failed)"
                                cleanup_exit 13 #lc_err_upgrade_fs_creation_failure
                            fi
                        else
                            # Unmount the alternate partition so that we can create the filesystem
                            mount_point=`cat /etc/fstab |grep ${label} |awk '{print $2}'`
                            umount ${mount_point}
                            if [ $? -ne 0 ]; then
                                echo "*** Could not unmount ${mount_point}"
                                cleanup_exit 13 #lc_err_upgrade_fs_creation_failure
                            fi

                            # Create the filesystem
                            mke2fs ${MKE2FS_BASE_OPTIONS} -q ${label_args} ${jargs} ${dev} ${blocks} || FAILURE=1
                            if [ ${FAILURE} -eq 1 ]; then
                                echo "*** Could not make filesystem on ${dev} (mke2fs failed)"
                                cleanup_exit 13 #lc_err_upgrade_fs_creation_failure
                            fi

                            # Mount the alternate partition back
                            mount LABEL=${label}
                            if [ $? -ne 0 ]; then
                                echo "*** Could not mount ${mount_point}"
                                cleanup_exit 13 #lc_err_upgrade_fs_creation_failure
                            fi
                        fi
                        ;;
                    *)
                        mke2fs ${MKE2FS_BASE_OPTIONS} -q ${label_args} ${jargs} ${dev} ${blocks} || FAILURE=1
                        if [ ${FAILURE} -eq 1 ]; then
                            echo "*** Could not make filesystem on ${dev} (mke2fs failed)"
                            cleanup_exit 13 #lc_err_upgrade_fs_creation_failure
                        fi
                        ;;
                esac

            fi

            if [ "$fstype" = "swap" ]; then
                echo "== Making swap on ${dev}"
                FAILURE=0
                mkswap -v1 ${dev} || FAILURE=1
                if [ ${FAILURE} -eq 1 ]; then
                    echo "*** Could not make swap on ${dev}"
                    cleanup_exit 13 #lc_err_upgrade_fs_creation_failure
                fi
            fi

            if [ -z "$fstype" ]; then
                if [ ${part_id} = "da" ]; then
                    echo "== Zero'ing first 4 meg of ${dev}"
                    FAILURE=0
                    dd if=/dev/zero of=${dev} bs=512 count=8192 || FAILURE=1
                    if [ ${FAILURE} -eq 1 ]; then
                        echo "*** Could not zero ${mp}"
                        cleanup_exit 13 #lc_err_upgrade_fs_creation_failure
                    fi
                else
                    echo "No filesystem made for unknown partition id ${part_id} on ${dev}"
                fi
            fi
        done
    done
}

# ==================================================
# Get list of storage profiles supported from the file /opt/hal/lib/specs/specs_storage_profiles
# ==================================================
get_stor_profiles_list()
{
    # get the model name
    MODEL_NAME=`/opt/tms/bin/mddbreq -v /config/mfg/mfdb query get - /rbt/mfd/flex/model`
    
    # get the line corresponding to the model from specs_storage_profiles file
    # this line is of the form <model>: storage_profiles="<stor_prof_1> <stor_prof_2> ... "
    MODEL_LINE=`/bin/grep "^${MODEL_NAME}:" ${SPECS_STOR_PROFILES}`
    
    # get the content of the above line i.e. the part after the colon. storage_profiles="<stor_prof_1> <stor_prof_2> ... "
    MODEL_LINE_CONTENT=`echo ${MODEL_LINE} | /bin/cut -d ":" -f2`
    
    #Now MODEL_LINEi_CONTENT is the line containing the MODEL's storage profiles. Now parse this to get the stor_prof's !
    STOR_PROF_LIST=`echo ${MODEL_LINE_CONTENT} | /bin/cut -d "=" -f2 | /bin/cut -d "\"" -f2`
}   

# ==================================================
# Check if current storage profile is present in the list of storage profiles for that model
# ==================================================
do_check_curr_prof_in_list()
{
    # Now the list of storage profiles supported for that model is present in STOR_PROF_LIST
    # and the current storage profile is present in CURR_STOR_PROFILE
    CURR_PROF_IN_LIST=0
    
    # If current storage profile doesnt exist return; allow upgrade
    if [ "x${CURR_STOR_PROFILE}" = "x${STOR_PROF_LIST}" ]; then
        CURR_PROF_IN_LIST=1
        return
    fi
    
    # If curr storage profile is not blank, check if  its present in the list
    for i in ${STOR_PROF_LIST}; do
        if [ "x${i}" = "x${CURR_STOR_PROFILE}" ]; then
            CURR_PROF_IN_LIST=1
        fi
    done
}

# ==================================================
# Check if storage profile is present in upgraded image
# ==================================================
do_check_storage_profile()
{
    # Get current storage profile of current image
    CURR_STOR_PROFILE=`/opt/tms/bin/mddbreq -v /config/mfg/mfdb query get - /rbt/mfd/resman/profile`

    #untar the image.tar file in EXTRACT_DIR
    tar xvf ${SYSIMAGE_FILE_TAR} -C ${EXTRACT_DIR} > /dev/null

    # EXTRACT_DIR is the place where image.img has been extracted to
    SPECS_STOR_PROFILES=${EXTRACT_DIR}/opt/hal/lib/specs/specs_storage_profiles

    # Check if specs_storage_profiles files exists in this image
    if [ -f "${SPECS_STOR_PROFILES}" ]; then

        # Get to-be-upgraded-to image's supported storage profiles list
        # This list is got from the file /opt/hal/lib/specs/specs_storage_profiles
        # corresponding to the current model

        get_stor_profiles_list

        # check if current storage profile is present in the above list
        do_check_curr_prof_in_list

        if [ ${CURR_PROF_IN_LIST} -eq 0 ]; then
            # Then current storage profile is not present in the list. Abort image upgrade.
            echo "Current Storage profile is not supported by to-be-upgraded-to image. Aborting image upgrade."
            cleanup_exit 21  # lc_err_upgrade_stor_profile_mismatch
        fi
    fi
}

# ==================================================
# Parse command line arguments, setup
# ==================================================

BV_PATH=/etc/build_version.sh
if [ -r ${BV_PATH} ]; then
    . ${BV_PATH}
else
    echo "*** Invalid build version"
    BUILD_PROD_CUSTOMER=invalid
fi

CURRENT_PROD=${BUILD_PROD_NAME}

PARSE=`/usr/bin/getopt -- 'miu:f:k:M:d:l:p:P:s:L:rtVS:z:q:' "$@"`

if [ $? != 0 ] ; then
    usage
fi

eval set -- "$PARSE"

# Defaults
DO_MANUFACTURE=-1
SYSIMAGE_USE_URL=-1
USE_TMPFS=1
SYSIMAGE_FILE=
SYSIMAGE_URL=
INSTALL_IMAGE_ID=-1
DO_REPLICATE_DISK=0
IMAGE_LAYOUT=STD
USER_TARGET_DEVS=
USER_TARGET_DEV_COUNT=0
RESTORE=0
PTOOL=sfdisk
# Hard-coded minimum free space required for ${TMP_LOCAL_WORKSPACE}
# (usually in /var) before attempting to upgrade the image.
# (XXX would really like to have a manifest in the image to know how
# big the image really is and use this). Default is 300MB.
VAR_MIN_AVAIL_SIZE=300000

# XXX the following install options not handled
INSTALL_NEW_BOOTMGR_1=0
# Warning, installing a new var will destroy log files
# XXX INSTALL_NEW_VAR may not work without tmpfs!
INSTALL_NEW_VAR_1=0
INSTALL_NEW_CONFIG_1=0
INSTALL_NEW_DATA_1=0
VERBOSE=0
LAST_PART=
MODEL=0
TMPFSSIZE=1024

while true ; do
    case "$1" in
        -m) DO_MANUFACTURE=1; shift ;;
        -i) DO_MANUFACTURE=0; shift ;;
        -u) SYSIMAGE_USE_URL=1; SYSIMAGE_URL=$2; shift 2 ;;
        -f) SYSIMAGE_USE_URL=0; SYSIMAGE_FILE=$2; shift 2 ;;
        -k) IL_KERNEL_TYPE=$2; shift 2 ;;
	-M) MODEL=$2 shift 2 ;;
        -d) 
            new_disk=$2; shift 2
            echo $new_disk | grep -q "^/dev"
            if [ $? -eq 1 ]; then
                usage
            fi
            USER_TARGET_DEV_COUNT=$((${USER_TARGET_DEV_COUNT} + 1))
            USER_TARGET_DEVS="${USER_TARGET_DEVS} ${new_disk}"
            eval 'USER_TARGET_DEV_'${USER_TARGET_DEV_COUNT}'="${new_disk}"'
            ;;
        -l) INSTALL_IMAGE_ID=$2; shift 2 ;;
        -p) LAST_PART=$2; shift 2 ;;
        -P) PTOOL=$2; shift 2 ;;
        -S) STORAGE_PROFILE=$2; shift 2 ;;
        -s) 
            LAST_PART_SIZE=$2; shift 2 
            if [ -z "${LAST_PART}" ]; then
                usage
            fi
            eval 'USER_PART_'${LAST_PART}'_SIZE="${LAST_PART_SIZE}"'
            ;;
        -L) IMAGE_LAYOUT=$2; shift 2 ;;
        -r) RESTORE=1; shift ;;
        -t) USE_TMPFS=0; shift ;;
        -V) VERBOSE=1; shift ;;
        -z) USER_LAST_PART_OVERRIDE=$2; shift 2;;
        -q) TMPFSSIZE=$2; shift 2 ;;
        --) shift ; break ;;
        *) echo "writeimage.sh: parse failure" >&2 ; usage ;;
    esac
done

if [ ! -z "$*" ] ; then
    usage
fi

# Test all the options that got set for correctness
if [ "x${STORAGE_PROFILE}" = "x" ]; then
    STORAGE_PROFILE_CMD=""
else
    STORAGE_PROFILE_CMD="--profile=${STORAGE_PROFILE}"
fi

if [ ${DO_MANUFACTURE} -eq -1 ]; then
    usage
fi

if [ ${SYSIMAGE_USE_URL} -eq -1 ]; then
    usage
fi

if [ ${DO_MANUFACTURE} -eq 0 ]; then
    if [ ${INSTALL_IMAGE_ID} -eq -1 ]; then
        usage
    fi
    INSTALL_IMAGE_ID_LIST=${INSTALL_IMAGE_ID}
else
    if [ ${INSTALL_IMAGE_ID} -ne -1 ]; then
        usage
    fi
    INSTALL_IMAGE_ID_LIST="1 2"
fi

# XXX/munirb: Bug 83129
# Clean up the /var/tmp/wiw* directory
# If for some reason a previous installation was cancelled, we may have
# some junk directories in /var/tmp which will, if there are multiple failures
# the var partition can fill up. Seen on a CMC
rm -rf /var/tmp/wiw*

echo "Starting script to do background filesystem syncs..."
(/sbin/syncfsexplicit.sh) &

# Define graft functions
if [ -f /etc/customer_rootflop.sh ]; then
    . /etc/customer_rootflop.sh
fi

touch / 2>/dev/null
READ_ONLY_ROOT=$?

[ $READ_ONLY_ROOT -ne 0 ] && mount / -o remount,rw

if [ "$HAVE_WRITEIMAGE_GRAFT_1" = "y" ]; then
    writeimage_graft_1
fi

# Do we want tar to print every file
if [ ${VERBOSE} -eq 0 ]; then
    TAR_VERBOSE=
else
    TAR_VERBOSE=v
fi

RAID_FIXUP_DONE=false

#
# Read in layout stuff: this is done twice.  Once before we set the user's
# device settings, and once after.
#
IL_LAYOUT="${IMAGE_LAYOUT}"

IL_PATH=/etc/layout_settings.sh
if [ -r ${IL_PATH} ]; then
    . ${IL_PATH}
else
    echo "*** Invalid image layout settings."
    usage
fi

if [ ${DO_MANUFACTURE} -eq 0 ]; then
    . /etc/image_layout.sh
    . ${IL_PATH}
fi


###  Downgrade stuff.
#use smp as a fall-through default.
IL_KERNEL_TYPE="smp"

eval `/usr/bin/unzip -qqp ${SYSIMAGE_FILE} build_version.sh | sed -e 's,^BUILD_\([A-Za-z_0-9]*\)=,IMAGE_BUILD_\1=,' -e 's,^export BUILD_\([A-Za-z_0-9]*\)$,export IMAGE_BUILD_\1,' | grep 'IMAGE_BUILD_'`
  
if [ ${CURRENT_PROD} != ${IMAGE_BUILD_PROD_NAME} ]; then
    echo "*** Cannot install ${IMAGE_BUILD_PROD_NAME} type image on a ${CURRENT_PROD}."
    cleanup_exit 4 
fi
 
if [ ! -z "${IMAGE_BUILD_PROD_RELEASE}" \
    -a "${IMAGE_BUILD_PROD_NAME}" = "rbt_sh" \
    -a -f /bootmgr/mfg_version ]; then 
    IMG_MAJ=`echo ${IMAGE_BUILD_PROD_RELEASE} | cut -c 1`
    INS_MAJ=`cat /bootmgr/mfg_version | cut -c 1`
 
    if [ ${IMG_MAJ} -le 4 ]; then 
	IL_KERNEL_TYPE=`/opt/tms/bin/mddbreq -v -c /config/mfg/mfdb query get - /rbt/mfd/kernel`
	#/bin/rm -f /config/db/*-VER-* > /dev/null 2>&1
    fi 
    if [ ${IMG_MAJ} -le 3 ]; then 
	echo ${IL_LAYOUT}
	case ${IL_LAYOUT} in
	    "FLASHSMB")
		OLD_LAYOUT="FLASHSMB"
		IL_LAYOUT="STDSMB"
		;;
	    "FLASHREPLSMB")
		OLD_LAYOUT="FLASHREPLSMB"
		IL_LAYOUT="REPLSMB"
		;;
	    "FLASH")
		OLD_LAYOUT="FLASH"
		IL_LAYOUT="STD"
		;;
	    *)
		;;
	esac
	eval `/bin/cat /etc/image_layout.sh | sed -e "s,$OLD_LAYOUT,$IL_LAYOUT," | grep '_DISK'`
	#nuke configs so we'll come back up OK.
	#/bin/rm -f /config/db/*-VER-* > /dev/null 2>&1
    fi 
fi

eval 'targets="${IL_LO_'${IL_LAYOUT}'_TARGETS}"'
eval 'parts="${IL_LO_'${IL_LAYOUT}'_PARTS}"'
if [ -z "${targets}" -o -z "${parts}" ]; then
    echo "*** Invalid layout ${IL_LAYOUT} specified."
    cleanup_exit 14 #lc_err_upgrade_invalid_layout
fi

# Now set the targets (devices) that the user specified

# Set TARGET_NAMES, which are things like 'DISK1'
eval 'TARGET_NAMES="${IL_LO_'${IL_LAYOUT}'_TARGETS}"'
dev_num=1
for tn in ${TARGET_NAMES}; do
    if [ $RESTORE -eq 1 -a "x$tn" = "xFLASH" ]; then 
	#need to decrement the device number here?
	continue
    fi

    if [ "${dev_num}" -le "${USER_TARGET_DEV_COUNT}" ]; then
        eval 'user_dev="${USER_TARGET_DEV_'${dev_num}'}"'
        eval 'IL_LO_'${IL_LAYOUT}'_TARGET_'${tn}'_DEV="${user_dev}"'
    else
        eval 'curr_dev="${IL_LO_'${IL_LAYOUT}'_TARGET_'${tn}'_DEV}"'
        if [ -z "${curr_dev}" ]; then
            echo "*** Not enough device targets specified."
            cleanup_exit 14 #lc_err_upgrade_invalid_layout
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


# User overrides for partitions sizes
eval 'PART_NAMES="${IL_LO_'${IL_LAYOUT}'_PARTS}"'
for part in ${PART_NAMES}; do
    eval 'user_part_size="${USER_PART_'${part}'_SIZE}"'
    if [ ! -z "${user_part_size}" ]; then
        # First verify there is a part with this name
        eval 'spn="${IL_LO_'${IL_LAYOUT}'_PART_'${part}'_DEV}"'
        if [ ! -z "${spn}" ]; then
            eval 'IL_LO_'${IL_LAYOUT}'_PART_'${part}'_SIZE="${user_part_size}"'
        fi
        eval 'spn="${IL_LO_'${IL_LAYOUT}'_PART_REPL_'${part}'_DEV}"'
        if [ ! -z "${spn}" ]; then
            eval 'IL_LO_'${IL_LAYOUT}'_PART_REPL_'${part}'_SIZE="${user_part_size}"'
        fi
    fi
done

# User override to fill the last partition
if [ "x${USER_LAST_PART_OVERRIDE}" = "xfalse" ]; then
    eval 'IL_LO_'${IL_LAYOUT}'_OPT_LAST_PART_FILL'=0
elif [ "x${USER_LAST_PART_OVERRIDE}" = "xtrue" ]; then
    eval 'IL_LO_'${IL_LAYOUT}'_OPT_LAST_PART_FILL'=1
fi

# Set TARGET_DEVS, which are things like /dev/hda
TARGET_DEVS=""
for tn in ${TARGET_NAMES}; do
    new_dev=""
    eval 'new_dev="${IL_LO_'${IL_LAYOUT}'_TARGET_'${tn}'_DEV}"'

    if [ -z "${new_dev}" ]; then
        echo "*** Target ${tn}: could not determine device"
        cleanup_exit 14 #lc_err_upgrade_invalid_layout
    fi

    TARGET_DEVS="${TARGET_DEVS} ${new_dev}"
done


# ==================================================
# Initial settings and defaults, override for debug/testing
# ==================================================

#DO_MANUFACTURE=0
# Must be 1 or 2, only used if DO_MANUFACTURE=0
#INSTALL_IMAGE_ID=1
#SYSIMAGE_URL=""
#SYSIMAGE_FILE=

NO_PARTITIONING=0
NO_REWRITE_FILESYSTEMS=0

# See if we're in a running image or a bootfloppy
uname -r | grep -q bfuni
if [ $? -eq 1 ]; then
    IS_BOOTFLOP=0
else
    IS_BOOTFLOP=1
fi

UNMOUNT_TMPFS=
UNMOUNT_WORKINGFS=
UNMOUNT_EXTRACTFS=
SYSIMAGE_FILE_TAR=
WORKSPACE_DIR=

trap "cleanup_exit" HUP INT QUIT PIPE TERM

#
# This whole MKE2FS_BASE_OPTIONS thing is because mke2fs now needs to be
# told not to reserve space to resize the partition, or older version of
# linux cannot mount the created filesystem!

MKE2FS_BASE_OPTIONS='-O ^resize_inode'
tmp_me2fs_file=/tmp/tmf.$$
rm -f ${tmp_me2fs_file}
dd if=/dev/zero of=${tmp_me2fs_file} bs=1k count=100 2> /dev/null

FAILURE=0
mke2fs -n ${MKE2FS_BASE_OPTIONS} -q -F ${tmp_me2fs_file} > /dev/null 2>&1  || FAILURE=1
if [ ${FAILURE} -eq 1 ]; then
    MKE2FS_BASE_OPTIONS=
fi
rm -f ${tmp_me2fs_file}

# ==================================================
# Partition settings
# ==================================================

# Set TARGET_NAMES, which are things like 'DISK1'
eval 'TARGET_NAMES="${IL_LO_'${IL_LAYOUT}'_TARGETS}"'

# Set TARGET_DEVS, which are things like /dev/hda
TARGET_DEVS=""
for tn in ${TARGET_NAMES}; do
    new_dev=""
    eval 'new_dev="${IL_LO_'${IL_LAYOUT}'_TARGET_'${tn}'_DEV}"'

    if [ -z "${new_dev}" ]; then
        echo "*** Target ${tn}: could not determine device"
        cleanup_exit 14 #lc_err_upgrade_invalid_layout
    fi

    TARGET_DEVS="${TARGET_DEVS} ${new_dev}"
done

# 
# This sizing information is to make sure the target disk is big enough, and
# to remember the total disk size, and the number of megs in a cylinder (for
# partition padding).

BYTES_PER_SECTOR=512
# Number of sectors in a meg
SEC_PER_MEG=`expr 1048576 / ${BYTES_PER_SECTOR}`

for tn in ${TARGET_NAMES}; do
    eval 'imdev="${IL_LO_'${IL_LAYOUT}'_TARGET_'${tn}'_DEV}"'

    FAILURE=0
    imdev_size_k=`sfdisk -s ${imdev} 2> /dev/null` || FAILURE=1
    if [ ${FAILURE} -eq 1 -o -z "${imdev_size_k}"  ]; then
        echo "*** Target ${imdev}: could not determine size"
        cleanup_exit 14 #lc_err_upgrade_invalid_layout
    fi
    imdev_size_m=`expr ${imdev_size_k} / 1024`

    FAILURE=0
    imdev_geom=`sfdisk -g ${imdev}  2> /dev/null` || FAILURE=1
    if [ ${FAILURE} -eq 1 -o -z "${imdev_geom}" ]; then
        echo "*** Target ${imdev}: could not determine geometry"
        cleanup_exit 14 #lc_err_upgrade_invalid_layout
    fi
    imdev_heads=`echo ${imdev_geom} | awk '{print $4}'`
    imdev_sectrack=`echo ${imdev_geom} | awk '{print $6}'`
    imdev_sec_multiple=`expr ${imdev_heads} \* ${imdev_sectrack}`

    # This number just has to come out to be more than the actual so we
    # don't overallocate

    imdev_cyl_m=`expr ${imdev_sec_multiple} \* ${BYTES_PER_SECTOR} / \
        1048576 + 1`

    # Set CURR_SIZE for our target
    eval 'IL_LO_'${IL_LAYOUT}'_TARGET_'${tn}'_CURR_SIZE_MEGS="${imdev_size_m}"'

    # Set CURR_CYL_MEGS for our target
    eval 'IL_LO_'${IL_LAYOUT}'_TARGET_'${tn}'_CURR_CYL_MEGS="${imdev_cyl_m}"'
done

# Make a per-target list of the names, devices, and partition numbers of all
# the partitions

eval 'part_list="${IL_LO_'${IL_LAYOUT}'_PARTS}"'
for part in ${part_list}; do
    eval 'target="${IL_LO_'${IL_LAYOUT}'_PART_'${part}'_TARGET}"'
    eval 'add_part_num="${IL_LO_'${IL_LAYOUT}'_PART_'${part}'_PART_NUM}"'
    eval 'add_part_dev="${IL_LO_'${IL_LAYOUT}'_PART_'${part}'_DEV}"'

    eval 'TARGET_'${target}'_ALL_PARTS="${TARGET_'${target}'_ALL_PARTS} ${part}"'
    eval 'TARGET_'${target}'_ALL_PART_NUMS="${TARGET_'${target}'_ALL_PART_NUMS} ${add_part_num}"'
    eval 'TARGET_'${target}'_ALL_PART_DEVS="${TARGET_'${target}'_ALL_PART_DEVS} ${add_part_dev}"'
done


# Build up a list of the partitions needed for images 1 and 2 (if any).

for inum in 1 2; do
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

    eval 'curr_parts="${IMAGE_'${inum}'_PART_LIST}"'
    ##echo "IP=${curr_parts}"

done



# Any layout specific checks go here

if [ ${IL_LAYOUT} = "REPL" ]; then

    last=0
    for tn in ${TARGET_NAMES}; do
        tds=-1
        eval 'tds="${IL_LO_'${IL_LAYOUT}'_TARGET_'${tn}'_CURR_SIZE_MEGS}"'
        if [ -z "${tds}" ]; then
            echo "*** No size found for target ${tn}"
            cleanup_exit 14 #lc_err_upgrade_invalid_layout
        fi
        if [ ${last} -ne 0 ]; then
            if [ ${tds} -ne ${last} ]; then
                echo "*** Targets are not the same size: ${last} and ${tds}."
                cleanup_exit 14 #lc_err_upgrade_invalid_layout
            fi
        fi
        last=${tds}
    done
fi


# ==================================================
# Verify no needed partition is mounted
# ==================================================

#
# Calculate what partitions we want to operate on.  Do this by seeing which
# locations need changing, and noting the partitions associated with them.
# 


# Make candidate_loc_list be the list of locations we want to change
if [ ${DO_MANUFACTURE} -eq 1 ]; then
    candidate_loc_list="${IL_LOCS}"
else
    eval 'candidate_loc_list="${IL_LO_'${IL_LAYOUT}'_IMAGE_'${INSTALL_IMAGE_ID}'_INSTALL_LOCS}"'

    if [ "${INSTALL_NEW_BOOTMGR_1}" -eq 1 ]; then
        candidate_loc_list="${candidate_loc_list} BOOTMGR_1"
    fi

    if [ "${INSTALL_NEW_VAR_1}" -eq 1 ]; then
        candidate_loc_list="${candidate_loc_list} VAR_1"
    fi

    if [ "${INSTALL_NEW_CONFIG_1}" -eq 1 ]; then
        candidate_loc_list="${candidate_loc_list} CONFIG_1"
    fi

    if [ "${INSTALL_NEW_DATA_1}" -eq 1 ]; then
        candidate_loc_list="${candidate_loc_list} DATA_1"
    fi
fi

# Print out the candidate_loc_list
# echo "candidate_loc_list=${candidate_loc_list}"

# Make ACTIVE_LOC_LIST be all the locations that have a valid partition with
# a valid target

ACTIVE_LOC_LIST=""
for cl in ${candidate_loc_list}; do 
    eval 'part="${IL_LO_'${IL_LAYOUT}'_LOC_'${cl}'_PART}"'

    if [ -z "${part}" ]; then
        continue
    fi

    eval 'target="${IL_LO_'${IL_LAYOUT}'_PART_'${part}'_TARGET}"'

    if [ -z "${target}" ]; then
        echo "Warning: No target for location ${cl} partition ${part}"
        continue
    fi

    eval 'target_dev="${IL_LO_'${IL_LAYOUT}'_TARGET_'${target}'_DEV}"'

    if [ -z "${target_dev}" ]; then
        echo "Warning: No device for location ${cl} partition ${part} target ${target}"
        continue
    fi

    ACTIVE_LOC_LIST="${ACTIVE_LOC_LIST} ${cl}"
done

# Print out the ACTIVE_LOC_LIST
# echo "ACTIVE_LOC_LIST=${ACTIVE_LOC_LIST}"


PART_CHANGE_LIST=""
TARGET_CHANGE_LIST=""
TARGET_DEV_CHANGE_LIST=""

for cl in ${ACTIVE_LOC_LIST}; do 
    add_part=""
    add_part_dev=""
    add_part_num=""
    add_target=""
    add_target_dev=""

    eval 'add_part="${IL_LO_'${IL_LAYOUT}'_LOC_'${cl}'_PART}"'
    eval 'add_part_dev="${IL_LO_'${IL_LAYOUT}'_PART_'${add_part}'_DEV}"'
    eval 'add_part_num="${IL_LO_'${IL_LAYOUT}'_PART_'${add_part}'_PART_NUM}"'
    eval 'add_target="${IL_LO_'${IL_LAYOUT}'_PART_'${add_part}'_TARGET}"'
    eval 'add_target_dev="${IL_LO_'${IL_LAYOUT}'_TARGET_'${add_target}'_DEV}"'

    if [ ${DO_MANUFACTURE} -eq 0 ]; then

	if [ "${cl}" = BOOTMGR_1 -a "${INSTALL_NEW_BOOTMGR_1}" -ne 1 ]; then
            add_part=""
	fi

	if [ "${cl}" = VAR_1 -a "${INSTALL_NEW_VAR_1}" -ne 1 ]; then
            add_part=""
	fi

	if [ "${cl}" = CONFIG_1 -a "${INSTALL_NEW_CONFIG_1}" -ne 1 ]; then
            add_part=""
	fi

	if [ "${cl}" = DATA_1 -a "${INSTALL_NEW_DATA_1}" -ne 1 ]; then
            add_part=""
	fi
    fi

    if [ ! -z "${add_part}" ]; then
        PART_CHANGE_LIST="${PART_CHANGE_LIST} ${add_part}"
        TARGET_CHANGE_LIST="${TARGET_CHANGE_LIST} ${add_target}"
        TARGET_DEV_CHANGE_LIST="${TARGET_DEV_CHANGE_LIST} ${add_target_dev}"
        eval 'TARGET_'${add_target}'_CHANGE_LOCS="${TARGET_'${add_target}'_CHANGE_LOCS} ${cl}"'
        eval 'TARGET_'${add_target}'_CHANGE_PARTS="${TARGET_'${add_target}'_CHANGE_PARTS} ${add_part}"'
        eval 'TARGET_'${add_target}'_CHANGE_PART_NUMS="${TARGET_'${add_target}'_CHANGE_PART_NUMS} ${add_part_num}"'

    fi
done

# Uniquify the lists we just made
PART_CHANGE_LIST=`echo "${PART_CHANGE_LIST}" | \
    tr ' ' '\n' | sort | uniq | tr '\n' ' '`
TARGET_CHANGE_LIST=`echo "${TARGET_CHANGE_LIST}" | \
    tr ' ' '\n' | sort | uniq | tr '\n' ' '`
TARGET_DEV_CHANGE_LIST=`echo "${TARGET_DEV_CHANGE_LIST}" | \
    tr ' ' '\n' | sort | uniq | tr '\n' ' '`

for target in ${TARGET_CHANGE_LIST}; do
    eval 'curr_part_nums="${TARGET_'${target}'_CHANGE_PART_NUMS}"'
    new_part_nums=`echo "${curr_part_nums}" | \
        tr ' ' '\n' | sort -n | uniq | tr '\n' ' '`
    eval 'TARGET_'${target}'_CHANGE_PART_NUMS="${new_part_nums}"'

    ##echo "NPNL: ${target} is: ${new_part_nums}"

    eval 'curr_parts="${TARGET_'${target}'_CHANGE_PARTS}"'
    new_parts=`echo "${curr_parts}" | \
        tr ' ' '\n' | sort -n | uniq | tr '\n' ' '`
    eval 'TARGET_'${target}'_CHANGE_PARTS="${new_parts}"'

    ##echo "NPL: ${target} is: ${new_parts}"

done

##echo "PCL: ${PART_CHANGE_LIST}"
##echo "TCL: ${TARGET_CHANGE_LIST}"
##echo "TCL: ${TARGET_DEV_CHANGE_LIST}"



if [ ! -z "${PART_CHANGE_LIST}" -a ${NO_REWRITE_FILESYSTEMS} -eq 0 ]; then

    echo "==== Verifying no needed partitions currently mounted"
    
    MPL=`mount -t ext3 | grep /dev | grep -v "^none" | awk '{print $1}'`
    SPL=`cat /proc/swaps | grep /dev | awk '{print $1}'`

    for testp in ${PART_CHANGE_LIST}; do
        curr_dev=""
        eval 'curr_dev="${IL_LO_'${IL_LAYOUT}'_PART_'${testp}'_DEV}"'

        for mpl in $MPL; do
            if [ "${mpl}" = "${curr_dev}" ]; then
                FAILURE=1
                if [ ${FAILURE} -eq 1 ]; then
                    echo "*** Partition $mpl was mounted and should not be"
                    cleanup_exit 15 #lc_err_upgrade_partitions_mounted
                fi
            fi
        done

        # Check for swap too
        for spl in $SPL; do
            if [ "${spl}" = "${curr_dev}" ]; then
                FAILURE=1
                if [ ${FAILURE} -eq 1 ]; then
                    echo "*** Partition $spl was swap'd on and should not be"
                    cleanup_exit 15 #lc_err_upgrade_partitions_mounted
                fi
            fi
        done

    done
fi


# ==================================================
# Verify disk can be repartitioned, if requested
# ==================================================

if [ ${DO_MANUFACTURE} -eq 1  -a ! -z "${PART_CHANGE_LIST}" -a \
    ${NO_PARTITIONING} -eq 0 ]; then

    echo "==== Verifying targets can be repartitioned"
    # Verify that the kernel thinks nothing is using the disk(s)
    for td in ${TARGET_DEV_CHANGE_LIST}; do
        sfdo=""
        FAILURE=0
        sfdo=`sfdisk -R --force ${td} 2>&1` || FAILURE=1
        if [ ${FAILURE} -eq 1 -o "${sfdo}" != "" ]; then
            echo "${sfdo}" | grep -q " busy"
            if [ $? -ne 0 ]; then
                echo "--- Target ${td}: warning: could not verify partition table"
                echo "--- Zero'ing existing partition table"
                dd if=/dev/zero of=${td} bs=512 count=1
            else
                echo "*** Target ${td}: error verifying could write partition table: disk busy"
                cleanup_exit 12 #lc_err_upgrade_partition_failure
            fi
        fi
    done
fi

# ==================================================
# Setup our work area, making TMPFS for scratch space, if requested
# ==================================================

TMP_MNT_IMAGE=/tmp/mnt_image

if [ ${USE_TMPFS} -eq 1 ]; then
    echo "==== Mounting tmpfs for working area"
    target_dir=${TMP_MNT_IMAGE}/tmpfs
    mkdir -p ${target_dir}
    FAILURE=0

    mount -t tmpfs -o size="${TMPFSSIZE}M" none ${target_dir} || FAILURE=1

    if [ ${FAILURE} -eq 1 ]; then
        if [ ${DO_MANUFACTURE} -eq 1 ]; then
            echo "*** Could not mount tmpfs for retrieving image"
            cleanup_exit 18 #lc_err_partition_mount_error
        fi
        # XXX could fall back to handling below and use var
        echo "*** Could not mount tmpfs for retrieving image"
        cleanup_exit 18 #lc_err_partition_mount_error
    fi
    WORKSPACE_DIR=${target_dir}
    UNMOUNT_TMPFS=${target_dir}
else
    echo "==== Setting up working area"

    #
    # If we are manufacturing, we make the partitions a little earlier.
    # Of course the wget could fail, but that's a risk we're taking.
    #
    if [ ${DO_MANUFACTURE} -eq 1 ]; then

        # We're going to use somewhere in VAR as our workspace
        location=VAR_1

        curr_part=
        eval 'curr_part="${IL_LO_'${IL_LAYOUT}'_LOC_'${location}'_PART}"'
        if [ -z "${curr_part}" ]; then
            echo "*** No partition found for location ${location}"
            cleanup_exit 12 #lc_err_upgrade_partition_failure
        fi
        eval 'curr_dev="${IL_LO_'${IL_LAYOUT}'_PART_'${curr_part}'_DEV}"'
        eval 'curr_target="${IL_LO_'${IL_LAYOUT}'_PART_'${curr_part}'_TARGET}"'
        eval 'curr_extract_prefix="${IL_LO_'${IL_LAYOUT}'_LOC_'${location}'_IMAGE_EXTRACT_PREFIX}"'
        mount_point="${TMP_MNT_IMAGE}/${curr_target}/${curr_part}/${curr_extract_prefix}"


        # Write the new partition table
        if [ ${NO_PARTITIONING} -eq 0 ]; then
            do_partition_disks
        fi


	if [ ${NO_PARTITIONING} -eq 0 -a ${NO_REWRITE_FILESYSTEMS} -eq 0 ]; then
	    do_raid_fixup
	fi

        # Make new filesystems on disk or disks
        if [ ${NO_REWRITE_FILESYSTEMS} -eq 0 ]; then
            do_make_filesystems
        fi

        # Setup our workspace
        mkdir -p ${mount_point}
        FAILURE=0
        echo "== Mounting ${curr_dev} on ${mount_point}"
        mount ${curr_dev} ${mount_point} || FAILURE=1
        if [ ${FAILURE} -eq 1 ]; then
            echo "*** Could not mount partition ${curr_dev} on ${mount_point}"
            cleanup_exit 18 #lc_err_partition_mount_error
        fi

        UNMOUNT_WORKINGFS=${mount_point}
        eval 'PART_PRE_MOUNTED_'${curr_part}'=1'
        TMP_LOCAL_WORKSPACE_ROOT=${mount_point}
        TMP_LOCAL_WORKSPACE=${TMP_LOCAL_WORKSPACE_ROOT}/wiw-scratch-$$
    else
        TMP_LOCAL_WORKSPACE_ROOT=/var/tmp/wiw
        TMP_LOCAL_WORKSPACE=${TMP_LOCAL_WORKSPACE_ROOT}/scratch-$$
    fi


    # XXX if we allowed var to get overwritten, this is an issue for
    # installs (not manufactures)!

    #
    # For both install and manufacture, we now make a tmp dir under /var
    #

    rm -f ${TMP_LOCAL_WORKSPACE}
    FAILURE=0
    mkdir -p ${TMP_LOCAL_WORKSPACE} || FAILURE=1
    if [ ${FAILURE} -eq 1 ]; then
        echo "*** Could not make work directory ${TMP_LOCAL_WORKSPACE}"
    fi
    WORKSPACE_DIR=${TMP_LOCAL_WORKSPACE}

    # Check if there is enough space in the workspace area to do the install
    var_avail_size=`df -k ${TMP_LOCAL_WORKSPACE_ROOT} | tail -1 | awk '{print $4}'`
    if [ ${VAR_MIN_AVAIL_SIZE} -gt ${var_avail_size} ]; then
        echo "*** Not enough available workspace in ${TMP_LOCAL_WORKSPACE_ROOT}: ${var_avail_size} bytes need at least ${VAR_MIN_AVAIL_SIZE} bytes"
        cleanup_exit 19 #lc_err_partition_out_of_space
    fi

fi


# ==================================================
# Retrieve system image: we use wget to retrieve the image to our workspace
#    in the url case, otherwise we copy the file to our workspace
# ==================================================

if [ $SYSIMAGE_USE_URL -eq 1 ]; then
    local_filename=`echo $SYSIMAGE_URL | sed 's/^.*\/\([^\/]*\)$/\1/'`
    echo "==== Retrieving image file from ${SYSIMAGE_URL}"
    ##echo "lfn: ${local_filename}"

    target_dir=${WORKSPACE_DIR}/image
    mkdir -p ${target_dir}
    SYSIMAGE_FILE=${target_dir}/${local_filename}
    rm -f ${SYSIMAGE_FILE}

    ##echo "wget: -O ${SYSIMAGE_FILE} ${SYSIMAGE_URL}"
    FAILURE=0
    /usr/bin/wget -O ${SYSIMAGE_FILE} ${SYSIMAGE_URL} || FAILURE=1
    if [ ${FAILURE} -eq 1 ]; then
        echo "*** Could not retrieve image from ${SYSIMAGE_URL}"
        cleanup_exit 16 #lc_err_upgrade_image_failure
    fi
else
    if [ -z "${SYSIMAGE_FILE}" -o ! -f "${SYSIMAGE_FILE}" ]; then
        echo "*** No system image file:  ${SYSIMAGE_FILE}"
        cleanup_exit 16 #lc_err_upgrade_image_failure
    fi
    local_filename=`echo $SYSIMAGE_FILE | sed 's/^.*\/\([^\/]*\)$/\1/'`
    target_dir=${WORKSPACE_DIR}/image
    mkdir -p ${target_dir}
    NEW_SYSIMAGE_FILE=${target_dir}/${local_filename}
    if [ "${SYSIMAGE_FILE}" != "${NEW_SYSIMAGE_FILE}" ]; then
        rm -f ${NEW_SYSIMAGE_FILE}
        cp -p ${SYSIMAGE_FILE} ${NEW_SYSIMAGE_FILE}
    fi
    ORIG_SYSIMAGE_FILE=${SYSIMAGE_FILE}
    SYSIMAGE_FILE=${NEW_SYSIMAGE_FILE}
fi


# ========================================
# Extract / uncompress the image we wish to write.  This goes to our
# workspace, which will normally be a tmpfs.  There are two supported file
# formats, a 'zip' file and a 'bzip2' file.  The zip file has a bzip2'd tar
# inside it, as well as some version and hash info to describe and validate
# the bzip'd tar.  The bzip2 file has just a tar inside it.  We auto
# identify each based on the first 3-4 bytes, so we can support both formats
# transparently.
#
# .img (zip):   4 bytes: 0120 0113  003  004  ('PK\003\004')
# .tbz (bzip2): 3 bytes: 0102 0132  150       ('BZh')
# ========================================

IMG_FIRST_4_BYTES="120 113 003 004"
TBZ_FIRST_3_BYTES="102 132 150"

FILE_TYPE=none

first_four_bytes=`dd if=${SYSIMAGE_FILE} bs=1 count=4 2> /dev/null | od -b | awk '{print $2" "$3" "$4" "$5}' | sed 's, *$,,' | tr -d '\n'`
first_three_bytes=`echo ${first_four_bytes} | awk '{print $1" "$2" "$3}'`

if [ "${first_four_bytes}" = "${IMG_FIRST_4_BYTES}" ]; then
    FILE_TYPE=img
fi

if [ "${first_three_bytes}" = "${TBZ_FIRST_3_BYTES}" ]; then
    FILE_TYPE=tbz
fi

if [ "${FILE_TYPE}" = "none" ]; then
    echo "*** Could not identify image type of ${SYSIMAGE_FILE}"
    cleanup_exit 17 #lc_err_upgrade_image_integrity_failure
fi

# This is the name of the file in the image that has the MD5s
MD5SUMS_NAME=md5sums

EXTRACT_DIR=${WORKSPACE_DIR}/extract
rm -f ${EXTRACT_DIR}
mkdir -p ${EXTRACT_DIR}

# For new style images, we first verify the image integrity
if [ "${FILE_TYPE}" = "img" ]; then
    echo "==== Verifying image integrity for ${SYSIMAGE_FILE}"
    FAILURE=0
    /usr/bin/unzip -q -d ${EXTRACT_DIR} ${SYSIMAGE_FILE} || FAILURE=1
    if [ ${FAILURE} -eq 1 ]; then
        echo "*** Could not extract image ${SYSIMAGE_FILE}"
        cleanup_exit 17 #lc_err_upgrade_image_integrity_failure
    fi
    
    FAILURE=0
    (cd ${EXTRACT_DIR}; /usr/bin/md5sum -c ${MD5SUMS_NAME} > /dev/null) || \
        FAILURE=1
    if [ ${FAILURE} -eq 1 ]; then
        echo "*** Invalid image: bad hashes for ${SYSIMAGE_FILE}"
        cleanup_exit 17 #lc_err_upgrade_image_integrity_failure
    fi
    SYSIMAGE_FILE_IMAGE=`ls ${EXTRACT_DIR}/image-*.* | head -1`
    SYSIMAGE_FILE_TAR=`echo ${EXTRACT_DIR}/${local_filename} | sed -e 's/.img$/.tar/'`
    if [ "${SYSIMAGE_FILE_TAR}" = "${EXTRACT_DIR}/${local_filename}" ]; then
        SYSIMAGE_FILE_TAR=${SYSIMAGE_FILE_TAR}.tar
    fi

    # Slurp in the image's build version information.  The current (running
    # system) version information is in BUILD_xxx, so we rewrite the version
    # information of the image to be installed to be IMAGE_BUILD_xxx.

    # Print the version strings
    echo "== Running version: ${BUILD_PROD_VERSION}"
    echo "== Image version:   ${IMAGE_BUILD_PROD_VERSION}"
 

    if [ ${DO_MANUFACTURE} -eq 0 ]; then 
        MDDBREQ=/opt/tms/bin/mddbreq
        MFDB=/config/mfg/mfdb
        MODEL=`${MDDBREQ} -v ${MFDB} query get - /rbt/mfd/flex/model`

        # XXX/munirb: The idea here is to check if the upgrade image
        # has the support flag set, if not cancel upgrade as the model
        # isn't supported in that version
	if [ "x${IMAGE_BUILD_1050RAIDUP_SUPPORT}" = "x" ]; then
	    case ${MODEL} in
		"1050_LR"|"1050_MR"|"1050_HR")
		    echo "*** Cannot upgrade to version that doesn't support raided model upgrades"
		    cleanup_exit 4 #lc_err_upgrade_model_unsupported
		    ;;
		*)
		    ;;
	    esac
	fi

	if [ "x${IMAGE_BUILD_1050U_SUPPORT}" = "x" ]; then
	    case ${MODEL} in
		"1050U")
		    echo "*** Cannot upgrade to version that doesn't support current model"
		    cleanup_exit 4 #lc_err_upgrade_model_unsupported
		    ;;
		*)
		    ;;
	    esac
	fi

	if [ "x${IMAGE_BUILD_5050L_SUPPORT}" = "x" ]; then
	    case ${MODEL} in
		"5050L")
		    echo "*** Cannot upgrade to version that doesn't support current model"
		    cleanup_exit 4 #lc_err_upgrade_model_unsupported
		    ;;
		*)
		    ;;
	    esac
	fi

	if [ "x${IMAGE_BUILD_V150M_SUPPORT}" = "x" ]; then
	    case ${MODEL} in
		"V150M")
		    echo "*** Cannot upgrade to version that doesn't support current model"
		    cleanup_exit 4 #lc_err_upgrade_model_unsupported
		    ;;
		*)
		    ;;
	    esac
	fi

        if [ "x${IMAGE_BUILD_8150_SV_ON_VAR_SUPPORT}" = "x" ]; then
            # CMC model node is different to the flex node
            # Use a different variable and don't overwrite the MODEL var
            # SH builds will have the IMAGE_BUILD_8150_SV_ON_VAR_SUPPORT set/unset
            # as well and we will overwrite the flex model here unintentionally
            MODEL_CMC=`${MDDBREQ} -v ${MFDB} query get - /rbt/mfd/model`
            case ${MODEL_CMC} in
                "8150")
                    echo "*** Cannot upgrade to version as your secure vault may be corrupted with this operation"
                    cleanup_exit 20 #lc_err_sv_moved_back_to_var
                    ;;
                *)
                    ;;
            esac
        fi
    fi

    # See if this is going to be okay
    if [ "$HAVE_WRITEIMAGE_GRAFT_4" = "y" ]; then
        writeimage_graft_4
    else
        # By default, we make sure the product matches
        if [ ${BUILD_PROD_PRODUCT} != ${IMAGE_BUILD_PROD_PRODUCT} ]; then
            echo "*** Bad product: image ${IMAGE_BUILD_PROD_PRODUCT} on system ${BUILD_PROD_PRODUCT}"
	    cleanup_exit 2; # lc_err_upgrade_product_mismatch
        fi
    fi

    # We no longer need the system image file in our workspace
    if [ "x${BUILD_FLASH_SUPPORT}" = "x" ]; then 
	rm -f ${SYSIMAGE_FILE}
    fi
    # otherwise we need this.  (need to make sure that we're not going to
    # run out of space
	    

else
    echo "==== Old-style image, not verifying image integrity for ${SYSIMAGE_FILE}"
    SYSIMAGE_FILE_IMAGE=${SYSIMAGE_FILE}
    SYSIMAGE_FILE_TAR=`echo ${EXTRACT_DIR}/${local_filename} | sed -e 's/.tbz$/.tar/' -e 's/.tgz$/.tar/' -e 's/.img$/.tar/'`
fi

sysimage_file_extension=`echo ${SYSIMAGE_FILE_IMAGE} | sed 's/^\(.*\)\.\([^\.]*\)$/\2/'`

if [ ${SYSIMAGE_FILE_IMAGE} != ${SYSIMAGE_FILE_TAR} ]; then
    rm -f ${SYSIMAGE_FILE_TAR}
fi

# Uncompress image file first, for speed
echo "==== Uncompressing source image file: ${SYSIMAGE_FILE_IMAGE} to ${SYSIMAGE_FILE_TAR}"
FAILURE=0

# This is the common case
if [ "${sysimage_file_extension}" = "tbz" ]; then
    cat ${SYSIMAGE_FILE_IMAGE} | bzcat - > ${SYSIMAGE_FILE_TAR} || FAILURE=1
    if [ ${FAILURE} -eq 1 ]; then
        echo "*** Could not uncompress image ${SYSIMAGE_FILE_IMAGE}"
        cleanup_exit 17 #lc_err_upgrade_image_integrity_failure
    fi
elif [ "${sysimage_file_extension}" = "tgz" ]; then
    cat ${SYSIMAGE_FILE_IMAGE} | zcat - > ${SYSIMAGE_FILE_TAR} || FAILURE=1
    if [ ${FAILURE} -eq 1 ]; then
        echo "*** Could not uncompress image ${SYSIMAGE_FILE_IMAGE}"
        cleanup_exit 17 #lc_err_upgrade_image_integrity_failure
    fi
elif [ "${sysimage_file_extension}" = "tar" ]; then
    if [ ${SYSIMAGE_FILE_IMAGE} != ${SYSIMAGE_FILE_TAR} ]; then
        mv ${SYSIMAGE_FILE_IMAGE} ${SYSIMAGE_FILE_TAR} || FAILURE=1
        if [ ${FAILURE} -eq 1 ]; then
            echo "*** Could not uncompress image ${SYSIMAGE_FILE_IMAGE}"
            cleanup_exit 17 #lc_err_upgrade_image_integrity_failure
        fi
    fi
else
    echo "*** Invalid extension on image inner ball: ${sysimage_file_extension}"
    cleanup_exit 17 #lc_err_upgrade_image_integrity_failure
fi

# We no longer need the compressed tarball in our workspace
if [ ${SYSIMAGE_FILE_IMAGE} != ${SYSIMAGE_FILE_TAR} ]; then
    rm -f ${SYSIMAGE_FILE_IMAGE}
fi

if [ ${USE_TMPFS} -eq 1 ]; then

    # If we get here, any disk we care about is thought to be unmounted

    # Write the new partition table
    if [ ${DO_MANUFACTURE} -eq 1 -a ${NO_PARTITIONING} -eq 0 ]; then
        do_partition_disks
    fi

    if [ ${DO_MANUFACTURE} -eq 1 -a ${NO_PARTITIONING} -eq 0 -a ${NO_REWRITE_FILESYSTEMS} -eq 0 ]; then

	do_raid_fixup
    fi

    # Make new filesystems on disk or disks
    if [ ${DO_MANUFACTURE} -eq 1 -o ${NO_REWRITE_FILESYSTEMS} -eq 0 ]; then
        do_make_filesystems
    fi
else
    # In the manufacturing case, we already made the filesystems above.

    # Run do_check_storage_profile before choosing to upgrade.
    do_check_storage_profile

    if [ ${DO_MANUFACTURE} -eq 0 -a ${NO_REWRITE_FILESYSTEMS} -eq 0 ]; then
        do_make_filesystems
    fi
fi

if [ ${RAID_FIXUP_DONE} = false ]; then 
    do_raid_fixup no_part_change
fi

#test for if we're doing the sh100 workaround 
MOD_100=
			    
# At this point we've either created all the paritions, or they already existed
# and this is a running system.

echo "==== Extracting image contents from: ${SYSIMAGE_FILE_TAR}"

for target in ${TARGET_CHANGE_LIST}; do
    
    echo "=== Extract to target ${target}"

    eval 'loc_list="${TARGET_'${target}'_CHANGE_LOCS}"'

    # Print out the LOC_LIST
    # echo "LOC_LIST = ${loc_list}"

    for location in ${loc_list}; do

        eval 'curr_part="${IL_LO_'${IL_LAYOUT}'_LOC_'${location}'_PART}"'
        eval 'curr_dev="${IL_LO_'${IL_LAYOUT}'_PART_'${curr_part}'_DEV}"'
        eval 'curr_target="${IL_LO_'${IL_LAYOUT}'_PART_'${curr_part}'_TARGET}"'
        eval 'curr_target_dev="${IL_LO_'${IL_LAYOUT}'_TARGET_'${curr_target}'_DEV}"'
        eval 'curr_fstype="${IL_LO_'${IL_LAYOUT}'_PART_'${curr_part}'_FSTYPE}"'
        eval 'curr_dir="${IL_LO_'${IL_LAYOUT}'_LOC_'${location}'_DIR}"'
        eval 'curr_extract="${IL_LO_'${IL_LAYOUT}'_LOC_'${location}'_IMAGE_EXTRACT}"'
        eval 'curr_extract_exclude="${IL_LO_'${IL_LAYOUT}'_LOC_'${location}'_IMAGE_EXTRACT_EXCLUDE}"'
        eval 'curr_extract_prefix="${IL_LO_'${IL_LAYOUT}'_LOC_'${location}'_IMAGE_EXTRACT_PREFIX}"'

        echo "== Extracting for location ${location} onto ${curr_dev}"

        if [ -z "${curr_fstype}" -o "${curr_fstype}" = "swap" ]; then
            echo "-- Nothing to do for this location."
            continue
        fi

        mount_point="${TMP_MNT_IMAGE}/${curr_target}/${curr_part}/${curr_extract_prefix}"
        chdir_to="${TMP_MNT_IMAGE}/${curr_target}/${curr_part}"

        exclude_arg=""
        if [ ! -z "${curr_extract_exclude}" ]; then
            for xa in ${curr_extract_exclude}; do
                new_ex="--exclude ${xa}"
                exclude_arg="${exclude_arg} ${new_ex}"
            done
        fi

        ##echo "exclude_arg= ${exclude_arg}"

        # Make sure it isn't already mounted, like in the -t case
        already_mounted=
        eval 'already_mounted="${PART_PRE_MOUNTED_'${curr_part}'}"'

        if [ -z "${already_mounted}" ]; then
            mkdir -p ${mount_point}
            FAILURE=0
            echo "-- Mounting ${curr_dev} on ${mount_point}"
            mount ${curr_dev} ${mount_point} || FAILURE=1
            if [ ${FAILURE} -eq 1 ]; then
                echo "*** Could not mount partition ${curr_dev} on ${mount_point}"
                cleanup_exit 18 #lc_err_partition_mount_error
            fi
            UNMOUNT_EXTRACTFS=${mount_point}
        fi

        # Pre-extract special processing for standard locations

        case "${location}" in
	    #I'm not sure that the REPL_BOOTMGR thing is entirely safe...
	    #XXX/evan
            BOOTERMGR_1|BOOTMGR_1|BOOTMGR_2|REPL_BOOTMGR_1|CFG) 
                if [ "x${IL_LAYOUT}" = "xHDRRDM" ]; then
                    case "${location}" in
                        BOOTMGR_1|BOOTMGR_2|REPL_BOOTMGR_1|CFG)
                            continue
                            ;;
                        *)
                            ;;
                    esac
                fi
                echo "-- Putting grub on ${curr_target_dev}"

                # Allow customer to emit things into:
                #      ${mount_point}/boot/grub/device.map
                # This might be needed if the grub auto probing does not work.
                if [ "$HAVE_WRITEIMAGE_GRAFT_5" = "y" ]; then
		    #might need to add something here to get this to work.
                    writeimage_graft_5
                fi

                #grub-install --recheck --root-directory=${mount_point} ${curr_target_dev}
                grub-install --root-directory=${mount_point} ${curr_target_dev}
                ;;
	    ROOT_1|ROOT_2)
		# if we're on a 100, we need to mount /opt specially
		#MOD_100_SUPPORT stuff for downgrades.
		case "${MODEL}" in 
		    50|100|200|300|305)
			if [ -f /opt/.100-opt-move* \
			    -a "x${IMAGE_BUILD_MOD_100_SUPPORT}" != "x" ]; then
			    MOD_100=true
			    img=`mount | grep "/boot " | awk '{print $1}' | sed -e 's,/dev/hda,,'`
			    if [ ${img} = 2 ]; then
				dev=/dev/hda13
			    else
				dev=/dev/hda12
			    fi

                            # XXX/munirb: Bug 55054
                            # We need to reformat the hda12|13 partition before copying
                            # the files, we don't want stale files to be left in the
                            # partition
                            echo "-- Mount the additional MOD100 partition" 
                            echo "mke2fs ${MKE2FS_BASE_OPTIONS} -q ${jargs} ${dev}"
                            mke2fs ${MKE2FS_BASE_OPTIONS} -q ${jargs} ${dev} || FAILURE=1
                            if [ ${FAILURE} -eq 1 ]; then
                                echo "*** Could not make filesystem on ${dev} (mke2fs failed)"
                                cleanup_exit 13 #lc_err_upgrade_fs_creation_failure
                            fi

			    mkdir ${mount_point}/${curr_dir}/opt/
			    mount $dev ${mount_point}/${curr_dir}/opt/

			fi
			;;
		    *)
			;;
		esac
        esac


        echo "-- Extracting files for ${location}"

	#we can't do this on the flash, the parts are too small
	if [ "${location}" = "CFG" -o "${location}" = "IMG1" -o "${location}" = "IMG2" ]; then 
	    #I think that this is all we need to do here.
	    continue
	fi

        FAILURE=0
        tar -x${TAR_VERBOSE} -f ${SYSIMAGE_FILE_TAR} -C ${chdir_to} ${exclude_arg} ${curr_extract} 2>&1 || FAILURE=1

        if [ ${FAILURE} -eq 1 ]; then
            echo "*** Could not extract files for bootmgr from ${SYSIMAGE_FILE_TAR}"
            cleanup_exit 17 #lc_err_upgrade_image_integrity_failure
        fi


        # Post-extract special processing for standard locations
        case "${location}" in
            BOOT_1|BOOT_2|BOOT_3|BOOT_4)
                echo "-- Post-extraction work for: ${location}"

                cd ${mount_point}/${curr_dir}
		if [ ! -f vmlinuz-${IL_KERNEL_TYPE} ]; then
		    if [ x${IL_KERNEL_TYPE} = xsmp ]; then 
			IL_KERNEL_TYPE=uni
		    else
			IL_KERNEL_TYPE=smp
		    fi
		fi
		ln -sf vmlinuz-${IL_KERNEL_TYPE} vmlinuz
		ln -sf System.map-${IL_KERNEL_TYPE} System.map
                ;;

            ROOT_1|ROOT_2)
                echo "-- Post-extraction work for: ${location}"

                cd ${mount_point}/${curr_dir}

                mkdir -p -m 755 ./boot
                mkdir -p -m 755 ./bootmgr
                mkdir -p -m 755 ./var
                mkdir -p -m 755 ./config
                mkdir -p -m 755 ./data

                if [ "$HAVE_WRITEIMAGE_GRAFT_2" = "y" ]; then
                    writeimage_graft_2
                fi

		#XXX/evan
		# this code contains the hidden assumption that 
		# / is big enough to store image.img, which is 
		# somewhat dangerous to make
		if [ "x${BUILD_FLASH_SUPPORT}" != "x" ]; then 
		    case  ${IL_LAYOUT} in
			FLASH|FLASHSMB|FLASHREPL|FLASHREPLSMB)
                            if [ "${BUILD_PROD_PRODUCT}" != "RBT_CMC" ]; then 
			        cp -f ${SYSIMAGE_FILE} ${mount_point}/image.img
                            fi
             		    #assume that we're getting to ROOT_1 first...
			    if [ ${location} = "ROOT_2" -o ${DO_MANUFACTURE} -eq 0 ]; then
				rm ${SYSIMAGE_FILE}
			    fi 

			    ;;
			*)
			    ;;
		    esac
		fi

                # The graft point script may have done a cd, so cd again
                cd ${mount_point}/${curr_dir}

                LAYOUT_FILE=etc/image_layout.sh
                rm -f ./${LAYOUT_FILE}
                echo "# Automatically generated file: DO NOT EDIT!" >> ./${LAYOUT_FILE}
                echo "#" >> ./${LAYOUT_FILE}
                echo "IL_LAYOUT=${IL_LAYOUT}" >> ./${LAYOUT_FILE}
                echo "export IL_LAYOUT" >> ./${LAYOUT_FILE}
                echo "IL_KERNEL_TYPE=${IL_KERNEL_TYPE}" >> ./${LAYOUT_FILE}
                echo "export IL_KERNEL_TYPE" >> ./${LAYOUT_FILE}

		#XXX/evan
		#this code assumes that the flash device is always listesd last...
		FLASHDEV=""
                for rtn in ${TARGET_NAMES}; do
                    if [ ${DO_MANUFACTURE} -ne 1 ]; then
                        # Do not do this for manufacturing as it will get the disks correctly
                        case  ${IL_LAYOUT} in
                            "BOBRDM")
                                # The BOBRDM layout is a special layout where the disks 
                                # change order on reboots. Note the disk order for 
                                # BOB VM's is defined by the VMX file, on upgrades we 
                                # make the disk with the current image disk0 and the backup
                                # image disk disk1. Due to the switch-a-roo the hardcoded values
                                # in layout_settings become invalid. To get around that problem we
                                # overwrite the layout_settings valriables here.
                                eval 'tnd="${IL_LO_'${IL_LAYOUT}'_TARGET_'${rtn}'_DEV}"'
                                eval 'tnd_name=IL_LO_'${IL_LAYOUT}'_TARGET_'${rtn}'_DEV'
                                if [ "x${INSTALL_IMAGE_ID}" = "x1" ]; then
                                    case "x${tnd_name}" in
                                        "xIL_LO_BOBRDM_TARGET_DISK1_DEV")
                                            tnd="/dev/disk128"
                                            ;;
                                        "xIL_LO_BOBRDM_TARGET_DISK2_DEV")
                                            tnd="/dev/disk129"
                                            ;;
                                        *)
                                            ;;
                                    esac
                                else
                                    case "x${tnd_name}" in
                                        "xIL_LO_BOBRDM_TARGET_DISK1_DEV")
                                            tnd="/dev/disk129"
                                            ;;
                                        "xIL_LO_BOBRDM_TARGET_DISK2_DEV")
                                            tnd="/dev/disk128"
                                            ;;
                                        *)
                                            ;;
                                    esac
                                fi
                                echo "IL_LO_${IL_LAYOUT}_TARGET_${rtn}_DEV=${tnd}" >> ./${LAYOUT_FILE}
                                echo "export IL_LO_${IL_LAYOUT}_TARGET_${rtn}_DEV" >> ./${LAYOUT_FILE}
                                ;;
                            *)
                                eval 'tnd="${IL_LO_'${IL_LAYOUT}'_TARGET_'${rtn}'_DEV}"'
                                echo "IL_LO_${IL_LAYOUT}_TARGET_${rtn}_DEV=${tnd}" >> ./${LAYOUT_FILE}
                                echo "export IL_LO_${IL_LAYOUT}_TARGET_${rtn}_DEV" >> ./${LAYOUT_FILE}
	                        FLASHDEV="${tnd}"
                                ;;
                        esac
                    else
                        eval 'tnd="${IL_LO_'${IL_LAYOUT}'_TARGET_'${rtn}'_DEV}"'
                        echo "IL_LO_${IL_LAYOUT}_TARGET_${rtn}_DEV=${tnd}" >> ./${LAYOUT_FILE}
                        echo "export IL_LO_${IL_LAYOUT}_TARGET_${rtn}_DEV" >> ./${LAYOUT_FILE}
	                FLASHDEV="${tnd}"
                    fi
                done
		case  ${IL_LAYOUT} in 
		    FLASH|FLASHSMB|FLASHREPL|FLASHREPLSMB) 
			echo "IL_FLASH_DEVICE=${FLASHDEV} " >> ./${LAYOUT_FILE}
			echo "export IL_FLASH_DEVICE" >> ./${LAYOUT_FILE}
			;;
		    *) 
			;;
		esac
		    
                chmod 0644 ./${LAYOUT_FILE}

                # Generate the fstab for this target

                # XXX ordering of these lines?

                FSTAB_FILE=etc/fstab
                rm -f ./${FSTAB_FILE}

                if [ "${location}" = "ROOT_1" ]; then
                    part_list="${IMAGE_1_PART_LIST}"
                else
                    part_list="${IMAGE_2_PART_LIST}"
                fi

                for mpart in ${part_list}; do
                    ##echo "part= ${mpart}"
                    eval 'part_dev="${IL_LO_'${IL_LAYOUT}'_PART_'${mpart}'_DEV}"'
                    eval 'part_label="${IL_LO_'${IL_LAYOUT}'_PART_'${mpart}'_LABEL}"'
                    eval 'part_mount="${IL_LO_'${IL_LAYOUT}'_PART_'${mpart}'_MOUNT}"'
                    eval 'part_fstype="${IL_LO_'${IL_LAYOUT}'_PART_'${mpart}'_FSTYPE}"'
                    eval 'part_options="${IL_LO_'${IL_LAYOUT}'_PART_'${mpart}'_OPTIONS}"'
                    if [ -z "${part_options}" ]; then
                        part_options=defaults
                    fi
                    part_dumpfreq=1
                    part_fsckpass=2

                    if [ "${part_fstype}" = "swap" ]; then
                        part_dumpfreq=0
                        part_fsckpass=0
                    fi

		    # make all the flash partitions noatime
                    # XXX/evan Assuming where things are mounted, though
		    case "${part_mount}" in
			"/")
                        part_fsckpass=1
                        part_options="${part_options},noatime"
			    ;;
			"/boot"|"/bootmgr"|"/config")
			    part_options="${part_options},noatime"
			    ;;
			*)
			    ;;
		    esac
			
                    # XXX! One of the issues with all this is that we are
                    # assuming the place where we are mounting the device
                    # now is where we want to mount the device later.  This
                    # is not correct if we have some manufacturing box!

                    if [ ! -z "${part_fstype}" -a ! -z "${part_mount}" ]; then
                        if [ ! -z "${part_label}" ]; then
			    if [ "${part_label}" = "SMB" ]; then
                                case ${IL_LAYOUT} in
				    "FLASHRRDM"|"BOBRDM"|"BOBSTD")
                                        # Skip the loop and don't add fstab
                                        continue
                                        ;;
                                    *)
                                        # Keep going to modify fstab for SMB
                                        ;;
                                esac
			    fi
                            # Shadow partition should not be mounted so no entry in fstab
			    if [ "${part_label}" = "SHADOW" \
				-a "${IL_LAYOUT}" = "FLASHRRDM" ]; then
				continue
			    fi

                            # XXX/munirb: Check to see if the BOOTMGR, BOOT or the ROOT partition
                            # are for the current or other partition for the UPGRADE image
                            # if current, mount to /, /boot, /bootmgr
                            # if other mount to /alt/mnt/root, /alt/mnt/boot, /alt/mnt/bootmgr
                            # This applies only to the BOB boxes, if you want it for your box,
                            # modify the layout_setting file and update the IL_LO_<layout>_IMAGE_1_LOCS
                            # with all the locations you want mounted

                            case ${part_label} in
                                "BOOT_1"|"BOOT_2"|"BOOTMGR_1"|"BOOTMGR_2"|"ROOT_1"|"ROOT_2")
                                    lab_suffix=`echo -n ${part_label} | tail -c 1`
                                    loc_suffix=`echo -n ${location} | tail -c 1`
                                    if [ "${lab_suffix}" != "${loc_suffix}" ]; then
                                        # Other partition for the upgrade image
                                        # use the mount points for this label
                                        # If partition is alternate partition, we will have to 
                                        # mount it to /alt/mnt/root, not /alt/mnt
                                        # note that by default the ROOT partition is mounted
                                        # to '/', but the alternate root partition needs to be
                                        # mounted to /alt/mnt/root
                                        case ${part_label} in
                                            "ROOT_1"|"ROOT_2")
                                                echo "LABEL=${part_label}   /alt/mnt/root   ${part_fstype}  ${part_options} ${part_dumpfreq} ${part_fsckpass}" >> ./${FSTAB_FILE}
                                                ;;
                                            *)
                                                echo "LABEL=${part_label}   /alt/mnt${part_mount}   ${part_fstype}  ${part_options} ${part_dumpfreq} ${part_fsckpass}" >> ./${FSTAB_FILE}
                                                ;;
                                        esac
                                    else
                                        echo "LABEL=${part_label}	${part_mount}	${part_fstype}	${part_options}	${part_dumpfreq} ${part_fsckpass}" >> ./${FSTAB_FILE}
                                    fi
                                    ;;
                                *)
                                    echo "LABEL=${part_label}	${part_mount}	${part_fstype}	${part_options}	${part_dumpfreq} ${part_fsckpass}" >> ./${FSTAB_FILE}
                                    ;;
                            esac

                        else
                            echo "${part_dev}	${part_mount}	${part_fstype}	${part_options}	${part_dumpfreq} ${part_fsckpass}" >> ./${FSTAB_FILE}
                        fi
                    else
                        echo "-- No fstab entry for ${mpart}"
                    fi
                        
                done

				echo "none		/proc           proc    defaults        0 0" >> ./${FSTAB_FILE}
				echo "none		/dev/pts        devpts  gid=5,mode=620  0 0" >> ./${FSTAB_FILE}
				echo "none		/dev/shm        tmpfs   defaults        0 0" >> ./${FSTAB_FILE}
				echo "none		/tmp            tmpfs   size=16M        0 0" >> ./${FSTAB_FILE}
				echo "/dev/cdrom	/mnt/cdrom      iso9660 noauto,ro       0 0" >> ./${FSTAB_FILE}
				echo "/dev/fd0	/mnt/floppy     auto    noauto          0 0" >> ./${FSTAB_FILE}

                if [ "$HAVE_WRITEIMAGE_GRAFT_3" = "y" ]; then
                    writeimage_graft_3
                fi


                chmod 0644 ./${FSTAB_FILE}
		if [ $MOD_100 ]; then
		    mv ${mount_point}/${curr_dir}/opt/hal /var/tmp
		    mv ${mount_point}/${curr_dir}/opt/tms/release /var/tmp
		    if [ -d ${mount_point}/${curr_dir}/opt/lost+found ]; then
			rmdir ${mount_point}/${curr_dir}/opt/lost+found
		    fi
		    umount ${mount_point}/${curr_dir}/opt/
		    mv /var/tmp/hal ${mount_point}/${curr_dir}/opt/
		    mkdir ${mount_point}/${curr_dir}/opt-mnt
		    mkdir ${mount_point}/${curr_dir}/opt-mnt/tms
		    mkdir ${mount_point}/${curr_dir}/opt-mnt/rbt
                    mkdir ${mount_point}/${curr_dir}/opt/tms
                    mkdir ${mount_point}/${curr_dir}/opt/rbt
		    ln -s /opt-mnt/tms/web2 ${mount_point}/${curr_dir}/opt/tms/web2
		    ln -s /opt-mnt/tms/bin ${mount_point}/${curr_dir}/opt/tms/bin
		    ln -s /opt-mnt/tms/lib ${mount_point}/${curr_dir}/opt/tms/lib
                    # XXX/munirb: Do not symlink the /opt/tms/release dir
                    # The build_version.sh file is needed if you boot into the older version
                    # The symlink will be dead once you boot in the older partition
                    mv /var/tmp/release ${mount_point}/${curr_dir}/opt/tms/release

		    ln -s /opt-mnt/rbt/bin ${mount_point}/${curr_dir}/opt/rbt/bin
		    ln -s /opt-mnt/rbt/etc ${mount_point}/${curr_dir}/opt/rbt/etc
		    ln -s /opt-mnt/rbt/lib ${mount_point}/${curr_dir}/opt/rbt/lib
		    ln -s /opt-mnt/rbt/share ${mount_point}/${curr_dir}/opt/rbt/share
		    ln -s /opt/hal/bin/axiomtek/hal ${mount_point}/${curr_dir}/opt/hal/bin/hal
                    # XXX/munirb: .100-opt-move was the initial attempt
                    # Changing file name so that we do the correct move from now on
		    touch ${mount_point}/${curr_dir}/opt/.100-opt-move-second
		fi
                ;;

        esac

        cd /

        if [ -z "${already_mounted}" ]; then
            umount ${mount_point}
            UNMOUNT_EXTRACTFS=
        fi

    done

done

# Fixup the grub.conf in the bootmgr
echo "== Updating grub.conf"
if [ "x${IL_LAYOUT}" != "xHDRRDM" ]; then
    if [ ${DO_MANUFACTURE} -eq 1 ]; then
        /sbin/aigen.py -m -d ${USER_TARGET_DEV_1} -l 1

        # For BOB models we need to setup the BOOTMGR partition for the other
        # disk as well, BOOTMGR_2
        if [ "${IL_LAYOUT}" = "BOBSTD" -o "${IL_LAYOUT}" = "BOBRDM" ]; then
            /sbin/aigen.py -m -d ${USER_TARGET_DEV_2} -l 1
        fi
    else
        if [ "${IL_LAYOUT}" = "BOBSTD" -o "${IL_LAYOUT}" = "BOBRDM" ]; then
            /sbin/aigen.py -i -l ${INSTALL_IMAGE_ID}
        else
            /sbin/aigen.py -i
        fi
    fi
else
    echo "Will need to write next boot ID to EEPROM"
fi


# ==================================================
# Cleanup: delete temp files and potentially unmount
# ==================================================

cleanup

[ $READ_ONLY_ROOT -ne 0 ] && mount / -o remount,ro

echo "==== writeimage.sh finished."
