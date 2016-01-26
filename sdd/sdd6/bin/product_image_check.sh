#!/bin/sh
#
# product_image_check
#
# description: check version of non-running partition
# for canary upgradeability
#
# Source function library.
. /etc/init.d/functions

# Skip this script if the version check should not be done for the product.
# You can add here more devices where version check should not be done.
# But the check should be very specific for that product.
#
# Note that some the scripts below may not work right on some products.
# For example, aiget.sh won't work on bob. So, if the version check must be
# done for a product, you must make sure that these scripts work the way you
# want them to work.
MOTHERBOARD=`/opt/tms/bin/hwtool -q motherboard`
if [ "x${MOTHERBOARD}" = "xBOB-MOBO" ]; then
    exit 0
fi

. /etc/image_layout.sh
if [ "x${IL_LAYOUT}" = "xBOBSTD" -o  "x${IL_LAYOUT}" = "xBOBRDM" ]; then
    exit 0
fi


start()
{
 	NON_BOOT_PART=-1

        # Image checks don't apply in an AWS (RSIS) environment. Simply exit
        # without doing anything.
        if [ -f /config/mfg/mfdb ]; then
            DEV_NODE=`/opt/tms/bin/mddbreq -v /config/mfg/mfdb query get - /rbt/mfd/rsis_dev_name`
            if [ $? -ne 0 ]; then
                logger "Unable to determine RSIS device node."
            else
                if [ -n "$DEV_NODE" ]; then
                    logger "RSIS device node found, so exiting product_image check."
                    exit 0
                fi
            fi
        fi

	eval `/sbin/aiget.sh`
	if [ ! -z "${AIG_THIS_BOOT_ID}" ]; then
		if [ $AIG_THIS_BOOT_ID = 1 ]; then
			NON_BOOT_PART=2
		else
			NON_BOOT_PART=1
		fi 
	fi

	echo Non-boot part is $NON_BOOT_PART

        is_sh=`/sbin/imgq.sh -i -d -l $NON_BOOT_PART | grep "RBT_SH"`
        if [ -z "$is_sh" ]; then
                # This is a SH EX, starting from version 1.0.0
                exit 0
        fi

        nonboot_ver=`/sbin/imgq.sh -i -d -l $NON_BOOT_PART | grep BUILD_PROD_RELEASE |  tr -d [:alpha:]-_=\"`

	echo nonboot-ver is $nonboot_ver

	first_dot=`expr index $nonboot_ver .`

	if [ $first_dot -eq 0 ]; then
		#echo Engineering build
		#we assume that user knowns what he is doing, exit an OK
		exit 0
	fi

	major_v=`expr match "$nonboot_ver" '\([0-9]*\)'`
	first_dot=`expr $first_dot + 1`
	s1=`expr substr $nonboot_ver $first_dot 100`

	minor_v=`expr match "$s1" '\([0-9]*\)'`

	second_dot=`expr index $s1 .`
	second_dot=`expr $second_dot + 1`
	s2=`expr substr $s1 $second_dot 100`

	micro_v=`expr match "$s2" '\([0-9]*\)'`

	#echo Major version $major_v
	#echo Minor version $minor_v
	#echo Micro version $micro_v

	if [ $major_v -le 4 ]; then
		exit 1
	fi

	if [ $major_v -eq 5 ]; then
		if [ $minor_v -eq 0 ] || [ $minor_v -eq 5 -a $micro_v -le 7 ]; then
			exit 1
		fi
	fi

        if [ $major_v -eq 6 ] && [ $minor_v -eq 0 ] && [ $micro_v -le 1 ]; then
		exit 1
        fi

	exit 0
}

start

exit


