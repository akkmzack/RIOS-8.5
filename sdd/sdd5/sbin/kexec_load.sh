#! /bin/sh

WDT_ITERATIONS=$1

if [ -z "$WDT_ITERATIONS" ]; then
	# Set to default value of 96 iterations
	# i.e 96*25=2400 seconds
	WDT_ITERATIONS=96
fi

# Save kernel crash dump to /var before starting swap
SWAP_PARTITION=`/opt/hal/bin/raid/rrdm_tool.py --get-partition swap`
if [ "x$SWAP_PARTITION" == "x" ]; then
        # This is a VSH model
        SWAP_PARTITION=`blkid | grep swap | cut -d':' -f1 | awk '{print substr($0, length($0), 1)}'`
fi
# If the model is a Redfin model, then reset the USB
MOBO=`/opt/hal/bin/hwtool.py -q motherboard`
if [ "x${MOBO}" = "x425-00205-01" -o "x${MOBO}" = "x425-00140-01" ]; then
        # This is a redfin box check to see if it's NOT Redfin 2.5
        MOBO_TYPE=`/opt/hal/bin/hwtool.py -q mobo-type`
        if [ "x${MOBO_TYPE}" = "x2U25_LSI" ]; then
                RESET_USB=0
        else
                RESET_USB=1
        fi
else
        RESET_USB=0
fi

LOOPS_PER_JIFFY=""
if [ "x${MOBO}" = "xHyperV" ]; then
    lpj_mhz=$(cat /proc/cpuinfo | grep -m 1 'cpu MHz' | awk '{print($4)}')
    lpj=$(echo "($lpj_mhz * 1000) / 1" | bc)
    LOOPS_PER_JIFFY="lpj=${lpj}"
fi

/sbin/kexec -p /boot/vmlinuz-crash-kernel --initrd=/boot/kexec_rootflop.img \
    --append="nmi_watchdog=0 1 irqpoll maxcpus=1 reset_devices console=tty0 \
    console=ttyS0,9600n8 dumppartition=${SWAP_PARTITION} reset_usb=${RESET_USB} \
    wdtiterations=${WDT_ITERATIONS} ${LOOPS_PER_JIFFY}" > /dev/null
