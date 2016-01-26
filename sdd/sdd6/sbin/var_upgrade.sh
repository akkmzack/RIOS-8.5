#
#  Filename:  $Source$
#  Revision:  $Revision: 80569 $
#  Date:      $Date: 2011-04-21 12:58:00 -0700 (Thu, 21 Apr 2011) $
#  Author:    $Author: mkumar $
# 
#  (C) Copyright 2002-2005 Tall Maple Systems, Inc.  
#  All rights reserved.
#

# This script is run from firstboot.sh to perform upgrades to the
# /var partition.  If you add a new rule here, make sure to 
# increment the version number in image_files/var_version.sh.
#
# This script takes one parameter, a string in the form
# "<old_version>_<new_version>".  The new version number must
# be exactly one higher than the old version; thus if multiple 
# upgrades are required, the script must be called multiple times.
# For example, to do an upgrade from version 2 to version 4, the
# script is called twice, once with "2_3" and once with "3_4".

versions=$1

case "$versions" in
    1_2)
          logger -p user.info "Fixing admin home directory"
          mkdir -p /var/home/root
          cp -p /etc/skel/.* /var/home/root
          ;;

    2_3)
          # This upgrade was customer-specific and has been moved elsewhere.
          ;;

    3_4)
          # This upgrade was customer-specific and has been moved elsewhere.
          ;;

    4_5)
          # This upgrade was customer-specific and has been moved elsewhere.
          ;;

    5_6)
          # This upgrade was customer-specific and has been moved elsewhere.
          ;;
    6_7)
          # Empty upgrade rule to get from 7 to 11, since previous release
          # was at 10.
          ;;
    7_8)
          # Empty upgrade rule to get from 7 to 11, since previous release
          # was at 10.
          ;;
    8_9)
          # Empty upgrade rule to get from 7 to 11, since previous release
          # was at 10.
          ;;
    9_10)
          # Empty upgrade rule to get from 7 to 11, since previous release
          # was at 10.
          ;;
    10_11)
          # Make sure the /var/opt/tms/stats/reports directory exists.
          mkdir -p /var/opt/tms/stats/reports
          chmod 0755 /var/opt/tms/stats/reports
          chown root.root /var/opt/tms/stats/reports
          ;;

    49_50)
          # touch this file to make sure that HAL flushes the IPMI
          # event log.
          mkdir -p /var/opt/rbt
          touch /var/opt/rbt/.hal_ipmi_clear
          ;;

    99_100)
          # read-only root
          mkdir -p /var/etc/opt/tms/output
          ;;

    100_101)
          # read-only root
          mkdir -p /var/etc/ntp
          ;;

    101_102)
          # read-only root
          # remove the previous upgrade rule to get rid of invalid
          # user messages in the logs
          # chown ntp:ntp /var/etc/ntp
          ;;
    102_103)
          # read-only root
          # the previous upgrade chown ntp:ntp /var/etc/ntp 
          # does not work since /etc/passwd doesn't have ntp
          # as a user during firstboot. Will use UID:GID to 
          # get around this issue. 
          chown 38:38 /var/etc/ntp
          ;;

    149_150)
          # Make sure the /var/tmp/tcpdumps directory exists
          # with correct permissions.
          mkdir -p /var/tmp/tcpdumps
          chmod 0755 /var/tmp/tcpdumps
          chown root.root /var/tmp/tcpdumps
          ;;
    150_151)
          # read-only root
          # Duplicate 102_103 change since Hellcat did not have 102_103,
          # and need to keep the numbers in sync.
          chown 38:38 /var/etc/ntp
          ;;
    200_201)
          # Make sure the md5 directories exist with correct permissions.
          TCPDUMP_MD5=/var/opt/tms/tcpdumps/md5
          SNAPSHOT_MD5=/var/opt/tms/snapshots/md5
          SYSDUMP_MD5=/var/opt/tms/sysdumps/md5
          mkdir -p $TCPDUMP_DD5 $SNAPSHOT_MD5 $SYSDUMP_MD5
          chmod 0755 $TCPDUMP_DD5 $SNAPSHOT_MD5 $SYSDUMP_MD5
          chown root.root $TCPDUMP_DD5 $SNAPSHOT_MD5 $SYSDUMP_MD5
          ;;
esac
