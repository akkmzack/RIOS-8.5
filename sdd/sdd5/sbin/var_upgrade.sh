#
#  Filename:  $URL: svn://svn.nbttech.com/mgmt-fwk/branches/kauai_373_fix_branch/framework/src/base_os/common/script_files/var_upgrade.sh $
#  Revision:  $Revision: 105220 $
#  Date:      $Date: 2013-05-10 13:20:46 -0700 (Fri, 10 May 2013) $
#  Author:    $Author: timlee $
# 
#  (C) Copyright 2002-2005 Tall Maple Systems, Inc.  
#  (C) Copyright 2003-2013 Riverbed Technology, Inc.  
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
          mkdir -p $TCPDUMP_MD5 $SNAPSHOT_MD5 $SYSDUMP_MD5
          chmod 0755 $TCPDUMP_MD5 $SNAPSHOT_MD5 $SYSDUMP_MD5
          chown root.root $TCPDUMP_MD5 $SNAPSHOT_MD5 $SYSDUMP_MD5
          ;;
    250_251)
          # Make sure the images directories exist with correct permissions.
          IMAGE_VERSION=/var/opt/tms/image_version
          IMAGE_VERSION_PARTITION=${IMAGE_VERSION}/partition
          IMAGE_VERSION_TMPDIR=${IMAGE_VERSION}/.tmpdir
          mkdir -p ${IMAGE_VERSION}
          mkdir -p ${IMAGE_VERSION_PARTITION} ${IMAGE_VERSION_TMPDIR}
          chmod 0755 ${IMAGE_VERSION}
          chmod 0755 ${IMAGE_VERSION_PARTITION} ${IMAGE_VERSION_TMPDIR}
          chown root.root ${IMAGE_VERSION}
          chown root.root ${IMAGE_VERSION_PARTITION} ${IMAGE_VERSION_TMPDIR}
          ;;
    251_252)
	  # Make the sched directory writeable by RBM group 
          chmod 1777 /var/opt/tms/sched	
          ;;
    252_253)
          STATS_DIR=/var/opt/tms/stats
          STATS_BACKUP=/var/opt/tms/stats/backup.tgz
          STATS_TEMP_BACKUP=/var/tmp/backup_tmp.tgz
          if [ -f ${STATS_TEMP_BACKUP} ]; then
             rm -rf ${STATS_TEMP_BACKUP}   
          fi
           
          if [ -f ${STATS_BACKUP} ]; then
             rm -rf ${STATS_BACKUP}
          fi
          tar -C ${STATS_DIR} -czSf ${STATS_TEMP_BACKUP} .
          mv ${STATS_TEMP_BACKUP} ${STATS_BACKUP}
          ;;
    299_300)
          # mkdirs and chmods for bug 131498
          if [ ! -d /var/empty/empty ]; then
              mkdir -m 0700 -p /var/empty/empty
          else
              chmod 0700 /var/empty/empty
          fi
          chmod 0000 /var/empty/sshd
          chmod 0700 /var/home/root
          ;;

esac
