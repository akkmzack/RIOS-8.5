#!/bin/sh
# Here's the assumption:
# the image is a tar file, containing a plain image, an ESXi upgrade image,
# and a signature file;
# the plain image is always called "image.img",
# the ESXi upgrade image is called "esxi_upgrade_image.tgz,
# and the signature is always called "signaturefile"
#
# This script will only be run on BOB appliances, not classic models

# ===================================================
# Remove the untarred files from the temp directory
# ===================================================
cleanup()
{
    cd ${image_extract_dir}

    if [ -e ${ESXI_UPGRADE_IMAGE} ]; then
        rm -f ${ESXI_UPGRADE_IMAGE}
    fi

    if [ -e ${SIGNATURE_FILE} ]; then
        rm -f ${SIGNATURE_FILE}
    fi

    if [ -e ${SH_UPGRADE_IMAGE} ]; then
        rm -f ${SH_UPGRADE_IMAGE}
    fi
}


# ===================================================
# Extract the files from image file and verify them
# ===================================================
ESXI_UPGRADE_IMAGE="esxi_upgrade_image.tgz"
SIGNATURE_FILE="signaturefile"
SH_UPGRADE_IMAGE="image.img"

image_file=$1
pubkey=$2
image_extract_dir=/var/opt/tms # don't use /var/opt/tms/images to avoid file name conflicts

cd $image_extract_dir
tar xvf $image_file

# ensure that the ESXi upgrade file is present
if [ ! -e ${ESXI_UPGRADE_IMAGE} ]; then
    cleanup
    exit 1
fi

# verify the signature is valid
openssl dgst -sha1 -verify $pubkey -signature ${SIGNATURE_FILE} ${SH_UPGRADE_IMAGE} ${ESXI_UPGRADE_IMAGE}

# looks like openssl returns 0 on some errors(like signaturefile missing),
# so don't rely on the return code, just look for "Verified OK" string
cleanup
exit 0

