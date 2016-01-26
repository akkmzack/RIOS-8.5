#
#  Filename:  $Source$
#  Revision:  $Revision: 98350 $
#  Date:      $Date: 2012-07-23 12:34:01 -0700 (Mon, 23 Jul 2012) $
#  Author:    $Author: munirb $
#
#  (C) Copyright 2003-2007 Riverbed Technology, Inc.
#  All rights reserved.
#

MFDB='/config/mfg/mfdb'

usage()
{
    echo "usage: $0 [-s SERIAL_NUMBER] "
    exit 1
}

HAVE_SERIALNUM=0

while getopts 's:' options ; do
    case $options in
        s) HAVE_SERIALNUM=1; OPT_SERIALNUM="${OPTARG}" ;;
        *) echo "/secure_vault.sh parse failure" >&2 ; usage ;;
    esac
done

# On new models, create the encrypted store on flash (/config/rbt)
# and symblink /var/opt/rbt/encrypted to it.
# 
MOBO=`/opt/hal/bin/hwtool.py -q motherboard`
case "x${MOBO:0:9}" in
        "x400-00100"|"x400-00300"|"x400-00099"|"x400-00098")
            PLATFORM=`cat /etc/build_version.sh | grep "^BUILD_PROD_ID=" | sed 's/^BUILD_PROD_ID="//' | sed 's/"//'`
            if [ "x${PLATFORM}" = "xCMC" ] || [ "x${PLATFORM}" = "xCB" ]; then
                DO_CONFIG_SV=0
            else
                DO_CONFIG_SV=1
            fi
        ;;
        *)
            DO_CONFIG_SV=0
        ;;
esac

if [ ${DO_CONFIG_SV} -eq 1 ]; then
        ENCRYPTED_DIR='/config/rbt/encrypted'
        VAR_ENCRYPTED_DIR='/var/opt/rbt/encrypted'
else
        ENCRYPTED_DIR='/var/opt/rbt/encrypted'
fi
DECRYPTED_DIR='/var/opt/rbt/decrypted'
SERIAL_NUM="`/opt/tms/bin/mddbreq -v $MFDB query get '' /rbt/mfd/serialnum`"
MAGIC_STRING='This is not a motorcycle'

if [ $HAVE_SERIALNUM -eq 1 ]; then
    SERIAL_NUM=$OPT_SERIALNUM
fi

PASSWORD="${MAGIC_STRING}_${SERIAL_NUM}"

# create an encrypted store
# XXX move to md_encrypted_store.cc
mkdir -m 0700 "$ENCRYPTED_DIR"
mkdir -m 0700 "$DECRYPTED_DIR"

# create store in paranoid mode (256 bit AES), without filename to IV header
# chaining
echo "x
1
256
4096
1
y
n
y
8
y
$PASSWORD" | /usr/local/bin/encfs -S "$ENCRYPTED_DIR" "$DECRYPTED_DIR"

#If creating secure vault fails, then exit.
STATUS=$?
if [ ${STATUS} != 0 ]; then
    exit ${STATUS}
fi

# finish up with the symlink to the var location for the encrypted store on
# new models. 
#
if [ ${DO_CONFIG_SV} -eq 1 ]; then
        ln -s ${ENCRYPTED_DIR} ${VAR_ENCRYPTED_DIR}
fi

