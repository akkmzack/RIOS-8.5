#!/bin/bash

LINUX_FADVISE="/bin/linux-fadvise"
LOSETUP="/sbin/losetup"
UDEVADM="/sbin/udevadm"

monitor=""
halt=""
cmnt=""
[ "$1" = "-m" ] && monitor=T && shift
[ "$1" = "-h" ] && halt=T && shift
[ "$1" = "-c" ] && cmnt="$2" && cdev=$3 && shift 3

[ "$#" -ne 1 ] && echo "usage: `basename $0` sh<x>" && exit 1
sh=$1

#
# halting?
#
if [ "$halt" = "T" ]; then
	if [ -f /var/run/shnotify.pid ]; then 
		kill -TERM `cat /var/run/shnotify.pid`
		for ((i=0; i<30; i++)); do
			[ ! -f /var/run/shnotify.pid ] && break
			sleep 1
		done
	fi
	exit 0
fi

# function does shadow prepopulation in background
background_shadow_prepop() {
    local kbytes="${1}"

    # Check if there is a local file backing shadow. And if so, prevent it
    # from generating a large buffer cache
    local dev_num=$(cat "/sys/block/${sh}/shadow/shadow_device")
    local dev_name=$("${UDEVADM}" info --query=name \
        --path="/sys/dev/block/${dev_num}")
    local backing_file=$("${LOSETUP}" "/dev/${dev_name}" 2>/dev/null | tr -d \
        '()' | awk {'print $3'})
    if [ -f "${backing_file}" ]; then
        echo "Shadow device ${sh} is backed by local file"
        local blocks=$((1 + kbytes / 1024 / 8))
        for ((block = 0; block < ${blocks}; block++)); do
            # When the shadow device is backed by a local file periodically
            # flush memory associated with data buffered by loopback device.
            # Buffered memory is not released by default allocator in order to
            # achieve memory locality on NUMA systems. This change may improve
            # performance on systems with multiple CPU sockets
            dd if=/dev/${sh} of=/dev/null bs=8M iflag=direct skip=${block} \
                count=1 >/dev/null 2>&1
            "${LINUX_FADVISE}" "${backing_file}" POSIX_FADV_DONTNEED 0 0 >/dev/null
        done
    else
        dd if=/dev/${sh} of=/dev/null bs=8M iflag=direct >/dev/null 2>&1
    fi
    echo "Background shadow prepopulation complete"
}

#
# create and attach the shadow device to
# the shadow block driver.
#

#
# make sure driver is loaded
#
! grep ' shadow$' /proc/devices >& /dev/null && exit 1

echo shadow driver loaded

[ ! -d /sys/block/${sh}/shadow ] && echo "${sh}: not found" && exit 1
[ ! -b /dev/${sh} ] && echo "${sh}: /dev/${sh} not found" && exit 1

echo ${sh} found

grep '^0:0$' /sys/block/${sh}/shadow/backing_device > /dev/null && \
	echo "${sh}: no backing device" && exit 1

echo ${sh} backing device attached

#
# are we just monitoring?
#
if [ "$monitor" = "T" -a -c /dev/ipmi0 ]; then
	! /opt/tms/bin/shsetup /dev/${sh} -m /sys/block/${sh}/shadow && \
		echo "${sh}: unable to monitor /sys/block/${sh}/shadow" && \
		exit 1

	exit 0
fi

! grep '^0:0$' /sys/block/${sh}/shadow/shadow_device > /dev/null && \
	echo "${sh}: shadow device already attached" && exit 1

echo ${sh} shadow device not attached


# Get type of motherboard
MOBO=`/opt/hal/bin/hwtool.py -q motherboard`

#
# get size of shadow device in pages...
#
nsectors=`blockdev --getsize /dev/${sh}`
nk=$(( ($nsectors + 1) / 2 ))
tmpfsk=$(( $nk + 1000000 ))
npages=$(( ($nk + 3) / 4 ))

echo ${sh} nsectors=$nsectors nk=$nk npages=$npages

shpart=`/opt/hal/bin/raid/rrdm_tool.py -l 2> /dev/null | \
	awk -F ':' '$1 ~ /^shadow/ { print $2; }'`

[ -n "$shpart" ] && [ ! -b /dev/$shpart ] && \
	echo "`basename $0`: warning: shadow partition $shpart not found" && \
	shpart=""

if [ -n "$shpart" ]; then
	echo "${sh}: Found shadow partition on block dev /dev/$shpart"	

	shdev=/dev/$shpart
else
	# Only for Barramundi/Redfin CX and EX platforms
	if [ "x$MOBO" == "x400-00100-01" -o "x$MOBO" == "x425-00140-01"  -o "x$MOBO" == "x425-00205-01" ]; then
		if [ -e /var/${sh}/store ]; then
			echo  "${sh}: /var/${sh}/store already exists; reuse it"
		else
			if [ ! -d /var/${sh} ]; then
			    ! mkdir /var/${sh} && echo "${sh}: unable to create /var/${sh}" \
				&& exit 1
			fi
			
			# Check if var has enough free space
			usb_size=$tmpfsk
			var_free_space=$( df -Pk /var | awk 'FNR>1{print $4}' )
			usb_size_overhead=$(( $usb_size + 1000000 ))
			if [ $var_free_space -lt $usb_size_overhead ]; then
				# Not enough space for shadow; exit
				echo "${sh}: unable to create store file on /var/${sh}/store"
				# Touch file so that mgmtd raises an alarm
				touch /var/shadow_not_setup
				# Echo store file size (in GB) to the above file
				echo "$usb_size_overhead 1048576" | awk '{print int( ($1/$2) + 1 )}' > /var/shadow_not_setup
                                exit 1
			fi
	
			dd if=/dev/zero of=/var/${sh}/store bs=${tmpfsk} count=1024 >& /dev/null
			echo "Created shadow store file in /var/${sh}/"
			if [ -f /var/shadow_not_setup ]; then
				rm -f /var/shadow_not_setup
			fi
		fi

		shdev=/dev/loop0
		! losetup $shdev /var/${sh}/store && \
			echo "${sh}: unable to setup $shdev on /var/${sh}/store" && \
			exit 1
	else
		# Only for Sturgeon/Gar platforms which have shadow on tmpfs
		[ -e /tmp/${sh} ] && echo "${sh}: /tmp/${sh} already exists" && exit 1
		! mkdir /tmp/${sh} && echo "${sh}: unable to create /tmp/${sh}" \
			&& exit 1

		! mount -t tmpfs -o size=${tmpfsk}k tmpfs /tmp/${sh} && \
			echo "${sh}: unable to mount tmpfs on /tmp/${sh}" && exit 1

		echo "mounted tmpfs on /tmp/${sh}"

		! dd if=/dev/zero of=/tmp/${sh}/store bs=4k count=${npages} >& /dev/null && \
			echo "${sh}: unable to create store file on /tmp/${sh}/store" && \
			exit 1

		shdev=/dev/loop0
		! losetup $shdev /tmp/${sh}/store && \
			echo "${sh}: unable to setup $shdev on /tmp/${sh}/store" && \
			exit 1
	fi
fi

# For Barramundi/Redfin CX and EX, tweak the staging list length.
# Based on experiments, 4096 is fine
if [ "x$MOBO" == "x400-00100-01" -o "x$MOBO" == "x425-00140-01" -o "x$MOBO" == "x425-00205-01" ]; then
	# Change the staging list size for this platform
	! /opt/tms/bin/shsetup /dev/${sh} -t 4096 && \
		echo "${sh}: unable to change staging size for /dev/${sh} to 4096" && \
		exit 1
fi

# For Sturgeon/Gar set it to 512, since in some cases we've seen them going
# over 256
if [ "x$MOBO" == "x400-00300-01" -o "x$MOBO" == "x400-00300-10" ]; then
	# Change the staging list size for this platform
	! /opt/tms/bin/shsetup /dev/${sh} -t 512 && \
		echo "${sh}: unable to change staging size for /dev/${sh} to 512" && \
		exit 1
fi

! /opt/tms/bin/shsetup /dev/${sh} -s $shdev && \
	echo "${sh}: unable to attach $shdev to /dev/${sh}" && \
	exit 1

#
# now that /var is mounted, let's check to see if we need to
# move /config to a loopback mount on /var.
#
cbdev=`echo "$cdev" | sed -e 's,^/dev/,,1' -e 's/[0-9]*$//1'`
dateb="no"
while [ "${cbdev}" = "sha" ]; do
    if [ -f /lib/modules/.config_fresh_on_flash ]; then
        if [ -f /var/lib/config/config.img ]; then
            # XXX/munirb:
            # Delete the file as we don't want the config to be overwritten
            # after a hardware upgrade or a profile change, we have updated 
            # the config files on the flash device and we do not want them
            # to be overwritten.
            # To prevent losing any config changes before the upgrade we
            # are disabling upgrades unless the flash device was up and 
            # synched when the command to upgrade/change was executed.
            echo "cleaning stale config.img"
            rm -f /var/lib/config/config.img
        fi
        rm -f /lib/modules/.config_fresh_on_flash
    else
	#
	# if we didn't boot from our image, we need
	# to delete /var/lib/config/config.img
	#
	if [ -f /var/lib/config/config.img ]; then
		# For the case when we boot into this image from
		# one that uses the timestamp logic to determine if
		# someone mounted config behind our backs.
		# Here we check if the format of the file was date
		# based or not. If it was date based consider the
		# VAR based config.img to be the latest one. 
		# See Bug 71369 
		if [ -f /var/lib/config/last.mount ]; then
			ncmnt="`cat /var/lib/config/last.mount`"
			# Check for format
			grep "^Last mount time:" /var/lib/config/last.mount > /dev/null 2>&1
			if [ $? -eq 0 ]; then
			    # Format is date based
			    dateb="yes"
			fi
		else
			ncmnt=""
		fi

	    # only clear the config if the file 
	    # format is not date based
	    if [ "x${dateb}" = "xno" ]; then
		if [ ! "${cmnt}" = "${ncmnt}" ]; then
		    echo "cleaning stale config.img"
		    rm -f /var/lib/config/config.img
		fi
	    fi
	fi
    fi
	#
	# if there is no loopback image to mount, we need to
	# create it -- we umount /config first to make sure
	# that it doesn't change after the copy...
	#
	umount $cdev
	if [ ! -f /var/lib/config/config.img ]; then
		echo "creating config.img, this may take a few minutes..."
		mkdir -p /var/lib/config
		dd if=$cdev of=/var/lib/config/config.img 2> /dev/null
		if [ $? -ne 0 ]; then
			echo "unable to create config.img"
			mount -t ext3 -o noatime $cdev /config
			break
		fi
	fi

	#
	# we use losetup to map the image to a block device
	#
	echo "mapping config.img to /dev/loop1"
	losetup /dev/loop1 /var/lib/config/config.img
	if [ $? -ne 0 ]; then
		echo "unable to create setup /dev/loop1"
		mount -t ext3 -o noatime $cdev /config
		break
	fi

	#
	# mount the new /config on /var
	#
	echo "mounting /config on /dev/loop1"
	mount -t ext3 -o noatime /dev/loop1 /config
	if [ $? -ne 0 ]; then
		echo "unable to mount /config on /dev/loop1"
		mount -t ext3 -o noatime $cdev /config
		losetup -d /dev/loop1
		break
	fi

	#
	# put the old config somewhere so we can sync it...
	#
	mkdir -p /tmp/mnt/config
	! mount -t ext3 -o noatime $cdev /tmp/mnt/config && \
		echo "unable to mount $cdev on /tmp/mnt/config -- not syncing"

	#
	# mark our last mount of config...
	#
	cmnt="`/sbin/tune2fs -l ${cdev} | grep 'Mount count:' | awk '{print $3}'`"
	echo "$cmnt" > /var/lib/config/last.mount

	#
	# start the sync application...
	#
	[ -x /opt/tms/bin/shnotify ] && /opt/tms/bin/shnotify

	break
done

#
# start eager reads of flash so that future reads will
# already be in the cache...
#
echo "Starting shadow prepopulation"
b=0
b=`sfdisk -s /dev/${sh}`
SIZEGB=`expr $b / 1000 / 1000`
# If eUSB size is 2 GB or less synch the entire thing at once.
if [ $SIZEGB -le 2 ]; then
    time dd if=/dev/${sh} of=/dev/null bs=8M > /dev/null 2>&1
    sync
    echo "Shadow prepopulation complete"
else
    echo "Shadow prepopulation in background"
    background_shadow_prepop "${b}" &
fi

