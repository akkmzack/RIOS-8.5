#
#  Filename:  $Source$
#  Revision:  $Revision: 103467 $
#  Date:      $Date: 2012-03-28 13:32:35 -0700 (Wed, 28 Mar 2012) $
#  Author:    $Author: wtai $
# 
#  (C) Copyright 2003-2005 Riverbed Technology, Inc.  
#  All rights reserved.
#

#
# This file contains customer-specific definitions and graft functions
# for use in the root floppy environment, as well as while running the
# full image.  It is separate from customer.sh so we can avoid installing
# the full customer.sh (which may be large) onto the root floppy (which
# is a very space-limited environment).
#

MFDB=/config/mfg/mfdb

# -----------------------------------------------------------------------------
# Graft point #1 for writeimage.sh.  This is called during initialization.
#
HAVE_WRITEIMAGE_GRAFT_1=y
writeimage_graft_1()
{
    # If no IL_KERNEL_TYPE was specified, then we should attempt to read it out
    # of the loaded database which should be available at $MFDB.
    # If that fails, then we set it to uni.
    if [ -z $IL_KERNEL_TYPE ]; then
        if [ -f $MFDB -a -x /opt/tms/bin/mddbreq ]; then
            IL_KERNEL_TYPE=`/opt/tms/bin/mddbreq -v $MFDB query get "" /rbt/mfd/kernel`
        else
            IL_KERNEL_TYPE="uni"
        fi
    fi
}

# -----------------------------------------------------------------------------
# Graft point #2 for writeimage.sh.  Please see the writeimage.sh script
# for specifics on where this is called from.
#
HAVE_WRITEIMAGE_GRAFT_2=y
writeimage_graft_2()
{
    if [ -d ./opt/rbt/lib ]; then
        cd ./opt/rbt/lib
        ln -sf modules-$IL_KERNEL_TYPE modules
    fi
}

# -----------------------------------------------------------------------------
# Graft point #3 for writeimage.sh.  Please see the writeimage.sh script
# for specifics on where this is called from.
#
HAVE_WRITEIMAGE_GRAFT_3=y
writeimage_graft_3()
{
    MODEL_SMBDEV=
    MODEL_DUALSTORE=
    if [ "${DO_MANUFACTURE}" = 1 ]; then
        MODEL_SMBDEV=${RBT_MODEL_SMBDEV}
        MODEL_DUALSTORE=${RBT_MODEL_DUALSTORE}
    else
        MODEL_SMBDEV=`/opt/tms/bin/mddbreq -v $MFDB query get "" /rbt/mfd/smb/dev`
        MODEL_DUALSTORE=`/opt/tms/bin/mddbreq -v $MFDB query get "" /rbt/mfd/store/dual`
    fi

    if [ "x${MODEL_SMBDEV}" = "x/dev/md1" ]; then
        if [ "x${MODEL_DUALSTORE}" = "xtrue" ]; then
            echo "/dev/md1        /proxy  ext3    defaults,acl,noauto     0       0" >> ./${FSTAB_FILE} 
        fi
    fi
}

# -----------------------------------------------------------------------------
# Graft point #4 for writeimage.sh.  This is called right after the version
# of the image to be used is determined.  It can be used to do customer
# specific determinations about what images should be allowed to be
# installed or manufactured.  
#
# ERROR codes in this section are defined in framework/src/include/errors.h
#
HAVE_WRITEIMAGE_GRAFT_4=y
writeimage_graft_4()
{
    #
    # we want to make sure that the new image being installed is one that can
    # be installed on the current hardware. but we can only do this check
    # during an upgrade, not a fresh manufacture so we check this condition
    # by checking for the presence of the manufacturing database because during
    # a fresh manufacture, the manufacturing database will not exist.
    #
    if [ -f /config/mfg/mfdb -a -x /opt/tms/bin/mddbreq ]; then
        #
        # first make sure we are installing a Steelhead image and not
        # one of our OEM images.
        #
        CHECK_PROD_ID=`/usr/bin/unzip -qqp ${SYSIMAGE_FILE} build_version.sh | grep BUILD_PROD_ID= | sed 's/BUILD_PROD_ID=//' | tr -d '"'`
        echo "== Image product id: ${CHECK_PROD_ID}"
        # typically the customer graft would enforce only a single product,
        # the problem is that since EX and SH share this code, we have to allow both
        # and we'll need to filter out invalid images in the calling layers
        if [ "x$CHECK_PROD_ID" != "xSH" -a "x${CHECK_PROD_ID}" != "xEX" ]; then
            #/usr/bin/logger -s -i -p user.err -t "writeimage" -- "ERR: Invalid image: Not a Steelhead image"
            echo "ERR: Invalid image: Not a Steelhead image"
            exit 2 #lc_err_upgrade_version_mismatch
        fi

        #
        # now that we know we are in the upgrade scenario, we need to check
        # the model and make sure that the image is compatible with the hardware.
        #
        MODEL=`/opt/tms/bin/mddbreq -v /config/mfg/mfdb query get "" /rbt/mfd/model`
        CHECK_PROD_RELEASE=`/usr/bin/unzip -qqp ${SYSIMAGE_FILE} build_version.sh | grep BUILD_PROD_RELEASE= | sed 's/BUILD_PROD_RELEASE=//' | tr -d '"'`
        echo "== Image product release: ${CHECK_PROD_RELEASE}"
        MAJOR_VERSION_NUMBER=`echo "$CHECK_PROD_RELEASE" | tr '.' ' ' | cut -d' ' -f1`
        MINOR_VERSION_NUMBER=`echo "$CHECK_PROD_RELEASE" | tr '.' ' ' | cut -d' ' -f2`
        SUB_VERSION_NUMBER=`echo "$CHECK_PROD_RELEASE" | tr '.' ' ' | cut -d' ' -f3`
        if [ ! -z $MAJOR_VERSION_NUMBER -a ! -z $MINOR_VERSION_NUMBER ]; then
            case $MODEL in
                "510"|"1010"|"2010"|"2011"|"2510"|"2511"|"3010"|"3510"|"5010")                    
                    #
                    # these models can only be installed with v1.2 or higher
                    #
                    if [ $MAJOR_VERSION_NUMBER = 1 -a $MINOR_VERSION_NUMBER -lt 2 ]; then
                        #/usr/bin/logger -s -i -p user.err -t "writeimage" -- "ERR: Invalid image: hardware requires v1.2 or greater"
                        echo "ERR: Invalid image: hardware requires v1.2 or greater"
                        exit 10 #lc_err_upgrade_image_too_old
                    fi
                    ;;
            esac
        fi
	#
	# Make sure that we're upgrading to an image with the right arch.
	#

	CURR_ARCH=`/bin/uname -i`

	#
	# Have BUILD_PROD_MODELS be set to the models supported by this image. 
	# Have BUILD_PROD_MODELS_32 be set to the 32 bit supported models.
	# Have BUILD_PROD_MODELS_64 be set to the 64 bit supported models.
	#
	# * If a model is not in BUILD_PROD_MODELS, it is not supported by this
	#   specific build, but it might be supported by the other build type
	#   (32 or 64 bit).
	# * If a model is not in BUILD_PROD_MODELS_32 or BUILD_PROD_MODELS_64, it
	#   is not supported by either the 32 or 64 bit flavors of the build.
	#
	# Logic
	# * Check if BUILD_PROD_MODELS is set in the build. If not, allow the
	#   upgrade to occur using the old logic of matching 32 or 64 bit
	#   types.
	# * Is model in BUILD_PROD_MODELS list? Is so, allow upgrade. If not
	#   check if model is in BUILD_PROD_MODELS_32 or BUILD_PROD_MODELS_64.
	#   If it is not in either, say that the version of software is not
	#   supported on this model.
	#
	
	CHECK_PROD_MODELS=`/usr/bin/unzip -qqp ${SYSIMAGE_FILE} build_version.sh | grep BUILD_PROD_MODELS= | sed 's/BUILD_PROD_MODELS=//' | tr -d '"'`
	CHECK_PROD_MODELS_32=`/usr/bin/unzip -qqp ${SYSIMAGE_FILE} build_version.sh | grep BUILD_PROD_MODELS_32= | sed 's/BUILD_PROD_MODELS_32=//' | tr -d '"'`
	CHECK_PROD_MODELS_64=`/usr/bin/unzip -qqp ${SYSIMAGE_FILE} build_version.sh | grep BUILD_PROD_MODELS_64= | sed 's/BUILD_PROD_MODELS_64=//' | tr -d '"'`

	if [ "x$CHECK_PROD_MODELS" != "x" ]; then

	    # Check if either the 32 or 64 bit images run on this model
	    echo "${CHECK_PROD_MODELS_32} ${CHECK_PROD_MODELS_64}" | sed -e 's/  */\n/g' | egrep "^${MODEL}$" > /dev/null
	    if [ $? -ne 0 ]; then
		# Model not found in list, do not allow this upgrade
		#/usr/bin/logger -s -i -p user.err -t "writeimage" -- "ERR: The update image does not support this hardware model."
                echo "ERR: The update image does not support this hardware model."
		exit 4 #lc_err_upgrade_model_unsupported
	    fi
	    
	    # Find if this model is supported by this specific upgrade image
	    echo ${CHECK_PROD_MODELS} | sed -e 's/  */\n/g' | egrep "^${MODEL}$" > /dev/null
	    if [ $? -ne 0 ]; then
		# Model was available in either the 32 or 64 bit build, but not in this one
		echo ${CHECK_PROD_MODELS_32} | sed -e 's/  */\n/g' | egrep "^${MODEL}$" > /dev/null
		if [ $? -ne 0 ]; then
		    #/usr/bin/logger -s -i -p user.err -t "writeimage" -- "ERR: This hardware requires an x86_64 image."
                    echo "ERR: This hardware requires an x86_64 image."
		    exit 5 #lc_err_upgrade_arch_mismatch_need_x86_64
		else
		    #/usr/bin/logger -s -i -p user.err -t "writeimage" -- "ERR: This hardware requires an i386 image."
                    echo "ERR: This hardware requires an i386 image."
		    exit 6 #lc_err_upgrade_arch_mismatch_need_i386
		fi
	    fi

	    # At this point, we've found this model should be supported by this image. It would be
	    # cool to do checks for revisions of hardware here too.

	else
	    # Looks like we are using a historical build type. Use old logic.

	    CHECK_PROD_VERSION=`/usr/bin/unzip -qqp ${SYSIMAGE_FILE} build_version.sh | grep BUILD_PROD_VERSION= | sed 's/BUILD_PROD_VERSION=//' | tr -d '"'`
	    if [ "x $CHECK_PROD_VERSION" != "x " ]; then

                # NOTE: the model field stores the class not the individual model name (for new hw)
                # This check does not depend on the spec model [LMH]. 
                # 
		case $MODEL in 
		    "3020"|"3520"|"5520"|"6020"|"6120"|"9200"|"5020"|"1050"|"2050"|"5050"|"6050"|"0501"|"0601")
		    #these are x86_64 models
		    echo $CHECK_PROD_VERSION | grep x86_64 > /dev/null 2>&1
		    if [ $? -ne 0 ]; then 
			#/usr/bin/logger -s -i -p user.err -t "writeimage" -- "ERR: This hardware requires an x86_64 image."
                        echo "ERR: This hardware requires an x86_64 image."
			exit 5 #lc_err_upgrade_arch_mismatch_need_x86_64
		    fi
		    ;;
		    *)
		    #these are everything else is a i386 model
		    echo $CHECK_PROD_VERSION | grep i386 > /dev/null 2>&1
		    if [ $? -ne 0 -a $CURR_ARCH != x86_64 ]; then 
			#/usr/bin/logger -s -i -p user.err -t "writeimage" -- "ERR: This hardware requires an i386 image."
                        echo "ERR: This hardware requires an i386 image." >&2
			exit 6 # lc_err_upgrade_arch_mismatch_need_i386
		    fi
		    ;;
		esac
	    fi
        fi

    fi
}

# -----------------------------------------------------------------------------
# Graft point #5 for writeimage.sh.
#
HAVE_WRITEIMAGE_GRAFT_5=y
writeimage_graft_5()
{

    REWRITE_DM=0

    mkdir -p ${mount_point}/boot/grub
    echo "${curr_target_dev}" | grep "cciss" > /dev/null 2>&1
    if [ $? = 0 ]; then
        new_disk_device=`echo ${curr_target_dev} | sed -e 's,c\([0-7]\)d\([0-9]\)p,c\1d\2,'`
        echo "(hd0) ${new_disk_device}" >> ${mount_point}/boot/grub/device.map
	REWRITE_DM=1
    fi

    echo "${curr_target_dev}" | grep "flash" > /dev/null 2>&1
    if [ $? = 0 ]; then
        new_disk_device="/dev/`ls -l ${curr_target_dev} | awk '{print $11}'`"
        echo "(hd0) ${new_disk_device}" >> ${mount_point}/boot/grub/device.map
	REWRITE_DM=1
    fi

    # device.map should look like "(hd0) /dev/sda" & not like "(hd0) /dev/disk0"
    echo "${curr_target_dev}" | grep "disk" > /dev/null 2>&1
    if [ $? = 0 ]; then
        new_disk_device="/dev/`ls -l ${curr_target_dev} | awk '{print $11}'`"
        echo "(hd0) ${new_disk_device}" >> ${mount_point}/boot/grub/device.map
	REWRITE_DM=1
    fi

    if [ ${REWRITE_DM} -eq 0 ]; then
        echo "(hd0) ${curr_target_dev}" >> ${mount_point}/boot/grub/device.map
    fi
}
