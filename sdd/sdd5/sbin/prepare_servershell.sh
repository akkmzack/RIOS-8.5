#!/bin/sh
#
# Prepare the server shell.
#
# Copyright (C) 2006 Riverbed Technology, Inc.
# All right reserved.
#
###############################################################################

SHELL_DIR=/proxy/__RBT_VSERVER_SHELL__

BIN_FILES=" \
    /bin/bash
    /bin/cat \
    /bin/chgrp \
    /bin/chmod \
    /bin/chown \
    /bin/cp \
    /bin/date \
    /bin/echo \
    /bin/egrep \
    /bin/false \
    /bin/fgrep \
    /bin/grep \
    /bin/gunzip \
    /bin/gzip \
    /bin/hostname \
    /bin/kill \
    /bin/ln \
    /bin/ls \
    /bin/mkdir \
    /bin/more \
    /bin/mv \
    /bin/ping \
    /bin/pwd \
    /bin/rm \
    /bin/rmdir \
    /bin/sed \
    /bin/sh \
    /bin/sleep \
    /bin/stty \
    /bin/tar \
    /bin/touch \
    /bin/true \
    /bin/vi \
    /bin/zcat \
    /usr/bin/ftp \
    /usr/bin/getopt \
    /usr/bin/scp \
    /usr/bin/ssh \
    "

LIB_FILES=" \
    /lib/ld-* \
    /lib/libacl* \
    /lib/libattr* \
    /lib/libaudit* \
    /lib/libblkid* \
    /lib/libc-* \
    /lib/libc.* \
    /lib/libcom_err* \
    /lib/libcrypt* \
    /lib/libdl-* \
    /lib/libdl.* \
    /lib/libe2p* \
    /lib/libext2fs* \
    /lib/libgcc* \
    /lib/libm-* \
    /lib/libm.* \
    /lib/libnsl* \
    /lib/libnss* \
    /lib/libpcre* \
    /lib/libpthread* \
    /lib/libresolv* \
    /lib/librt* \
    /lib/libselinux* \
    /lib/libtermcap* \
    /lib/libuuid* \
    /lib/libutil* \
    /usr/lib/libgssapi_krb5* \
    /usr/lib/libkrb5* \
    /usr/lib/libk5crypto* \
    /usr/lib/libncurses* \
    /usr/lib/libreadline* \
    /usr/lib/libz* \
    "

LIB_64_FILES=" \
    /lib64/ld-* \
    /lib64/libacl* \
    /lib64/libattr* \
    /lib64/libaudit* \
    /lib64/libblkid* \
    /lib64/libc-* \
    /lib64/libc.* \
    /lib64/libcom_err* \
    /lib64/libcrypt* \
    /lib64/libdl-* \
    /lib64/libdl.* \
    /lib64/libe2p* \
    /lib64/libext2fs* \
    /lib64/libgcc* \
    /lib64/libm-* \
    /lib64/libm.* \
    /lib64/libnsl* \
    /lib64/libnss* \
    /lib64/libpcre* \
    /lib64/libpthread* \
    /lib64/libresolv* \
    /lib64/librt* \
    /lib64/libselinux* \
    /lib64/libtermcap* \
    /lib64/libuuid* \
    /lib64/libutil* \
    /usr/lib64/libgssapi_krb5* \
    /usr/lib64/libkrb5* \
    /usr/lib64/libk5crypto* \
    /usr/lib64/libncurses* \
    /usr/lib64/libreadline* \
    /usr/lib64/libz* \
    "

echo "Running this command will initialize the server shell on "
echo "on this appliance. Note that this command will erase the "
echo "entire contents of the existing server shell. Any changes "
echo "you have made previously inside the server shell will be "
echo "lost."
echo ""
echo -n "Do you want to proceed? (yes/no) [no] "

read ANSWER

if [ "x${ANSWER}" != "xyes" ]; then
    echo "Nothing done. Exiting."
    exit 0
fi

echo -n "Initializing the server shell..."
cd /

# note that we only support this functionality on PFS enabled
# appliances.
if [ ! -d /proxy ]; then
    echo "Server shell is not supported on this appliance."
    exit 0
fi

/bin/mount | /bin/grep "/proxy" > /dev/null
if [ $? != 0 ]; then
    echo "Server shell is not supported on this appliance."
    exit 0
fi

# erase the existing server shell
find ${SHELL_DIR} -mindepth 1 -maxdepth 1 '!' -name rsp -exec rm -r '{}' \;

# create the new server shell
mkdir -pm 0755 ${SHELL_DIR}

# indicate that vserver-shell has been initialized on this machine
touch ${SHELL_DIR}/.vserver-shell

# create the subdirs
mkdir -m 0755 ${SHELL_DIR}/bin
mkdir -m 0755 ${SHELL_DIR}/etc
mkdir -m 0755 ${SHELL_DIR}/dev
mkdir -m 0755 ${SHELL_DIR}/home
mkdir -m 0755 ${SHELL_DIR}/lib

# populate the bin directory
for BIN_FILE in ${BIN_FILES}; do
    cp ${BIN_FILE} ${SHELL_DIR}/bin
done

# populate the dev directory
(
    cd ${SHELL_DIR}/dev
    mknod console c 5 1
    mknod null c 1 3
    mknod random c 1 8
    mknod urandom c 1 9
    mknod zero c 1 5
)

# populate the home directory
cat <<EOF > ${SHELL_DIR}/home/.bashrc
PATH=/bin
export PATH

HOSTNAME=\`/bin/hostname\`
export HOSTNAME

LOGNAME=\$USER
export LOGNAME

ulimit -S -c 0 > /dev/null 2>&1

EOF

# populate the lib directory
for LIB_FILE in ${LIB_FILES}; do
    if [ -f ${LIB_FILE} ]; then
        cp -f ${LIB_FILE} ${SHELL_DIR}/lib
    fi
done

if [ -d /lib64 ]; then
    mkdir -m 0755 ${SHELL_DIR}/lib64
    for LIB_FILE in ${LIB_64_FILES}; do
        if [ -f ${LIB_FILE} ]; then
            cp -f ${LIB_FILE} ${SHELL_DIR}/lib64
        fi
    done
fi

# fix ownerships
chown -R vserveruser:vserveruser ${SHELL_DIR}

echo "done."
