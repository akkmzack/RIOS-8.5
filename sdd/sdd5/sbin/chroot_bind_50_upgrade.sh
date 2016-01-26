#!/bin/sh
# chroot_bind_50_upgrade.sh
# sets up environment for BIND to run chrooted

BINDDIR=/var/named
CHROOTDIR=/var/named/chroot
GID=25
BUID=25

# Keep umask from messing with install settings
SAVED_UMASK=`umask -p`
umask 002

install -d -o 0 -g $GID $BINDDIR
install -d -o 0 -g $GID $CHROOTDIR
install -d -o 0 -g 0 $CHROOTDIR/proc
install -d -o 0 -g $GID $CHROOTDIR/dev
install -d -o 0 -g $GID $CHROOTDIR/etc
install -d -o 0 -g $GID $CHROOTDIR/var
install -d -o 0 -g $GID $CHROOTDIR/var/named
install -d -m 775 -o 0 -g $GID $CHROOTDIR/var/named/data
install -d -o 0 -g $GID $CHROOTDIR/var/named/slaves
install -d -o $BUID -g $GID $CHROOTDIR/var/tmp
install -d -m 775 -o 0 -g $GID $CHROOTDIR/var/run
install -d -m 775 -o 0 -g $GID $CHROOTDIR/var/run/named
$SAVED_UMASK

mknod /var/named/chroot/dev/null c 1 3
mknod /var/named/chroot/dev/random c 1 8
mknod /var/named/chroot/dev/urandom c 1 9
mknod /var/named/chroot/dev/zero c 1 5
