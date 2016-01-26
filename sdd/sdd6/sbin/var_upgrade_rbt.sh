#
#  Filename:  $Source$
#  Revision:  $Revision: 95705 $
#  Date:      $Date: 2011-11-17 17:01:38 -0800 (Thu, 17 Nov 2011) $
#  Author:    $Author: cwong $
# 
#  (C) Copyright 2003-2006 Riverbed Technology, Inc.  
#  All rights reserved.
#

# This script is run from firstboot.sh to perform upgrades to the
# /var partition.  If you add a new rule here, make sure to 
# increment the version number in image_files/var_version_rbt.sh.
#
# This script takes one parameter, a string in the form
# "<old_version>_<new_version>".  The new version number must
# be exactly one higher than the old version; thus if multiple 
# upgrades are required, the script must be called multiple times.
# For example, to do an upgrade from version 2 to version 4, the
# script is called twice, once with "2_3" and once with "3_4".

MDDBREQ=/opt/tms/bin/mddbreq
MFDB_ORIG=/bootmgr/mfd/mfdb
MFDB_DIR=/config/mfg
MFDB=${MFDB_DIR}/mfdb
EXPR=/usr/bin/expr
SFDISK=/sbin/sfdisk
CMDS=/var/tmp/cmds
TABLE1=/var/tmp/table1
TABLE2=/var/tmp/table2
FSTAB_PATH=/etc/fstab

versions=$1

# If a given link doesn't point to the desired target, recreate the link with
# the desired target. This function is useful since some buggy kernels running
# on Steelheads don't create long symlinks correctly during upgrades.

check_create_symlink()
{
    symlink=$2
    target=$1
    actual_target=`readlink $symlink`
    if [ "$actual_target" != "$target" ]; then
        rm -f $symlink
        ln -s $target $symlink
    fi
}

case "$versions" in
    1_2)
          # This was a baseline system upgrade; the code for it is
          # elsewhere.
          ;;

    2_3)
          # update the RAID changes
          # XXX note that this upgrade won't work if the
          # /bootmgr becomes read-only.
          logger -p user.info "Fixing new RAID settings"

          # first set the number of RAID disks
          APPLIANCE_MODEL=`/opt/tms/bin/mddbreq -v $MFDB_ORIG query get "" /rbt/mfd/model`
          RAIDDISK_NUM=0
          case "$APPLIANCE_MODEL" in
              3000)
                  RAIDDISK_NUM=4
                  ;;
              5000)
                  RAIDDISK_NUM=6
                  ;;
          esac
          /opt/tms/bin/mddbreq $MFDB_ORIG set modify "" /rbt/mfd/raidnum uint16 $RAIDDISK_NUM
          ;;

    3_4)
          # update for cachepgs value inside the manufacturing db
          APPLIANCE_MODEL=`/opt/tms/bin/mddbreq -v $MFDB_ORIG query get "" /rbt/mfd/model`
          CACHEPGS=1
          case "$APPLIANCE_MODEL" in
              500)
                  CACHEPGS=76745
                  ;;
              1000)
                  CACHEPGS=76745
                  ;;
              2000)
                  CACHEPGS=163141
                  ;;
              3000)
                  CACHEPGS=132427
                  ;;
              5000)
                  CACHEPGS=160041
                  ;;
          esac
          /opt/tms/bin/mddbreq $MFDB_ORIG set modify "" /rbt/mfd/store/cachepgs uint32 $CACHEPGS
          touch /var/opt/rbt/.clean
          ;;

    4_5)
          # update for admission control
          APPLIANCE_MODEL=`/opt/tms/bin/mddbreq -v $MFDB_ORIG query get "" /rbt/mfd/model`
          case "$APPLIANCE_MODEL" in
              500)
                 ADMISSION_ENABLECONN=500
                 ADMISSION_CUTOFFCONN=510
                 ADMISSION_ENABLEMEM=850
                 ADMISSION_CUTOFFMEM=900
                  ;;
              1000)
                  ADMISSION_ENABLECONN=500
                  ADMISSION_CUTOFFCONN=510
                  ADMISSION_ENABLEMEM=850
                  ADMISSION_CUTOFFMEM=900
                  ;;
              2000)
                  ADMISSION_ENABLECONN=1000
                  ADMISSION_CUTOFFCONN=1010
                  ADMISSION_ENABLEMEM=1800
                  ADMISSION_CUTOFFMEM=1850
                  ;;
              3000)
                  ADMISSION_ENABLECONN=2000
                  ADMISSION_CUTOFFCONN=2010
                  ADMISSION_ENABLEMEM=2650
                  ADMISSION_CUTOFFMEM=2700
                  ;;
              5000)
                  ADMISSION_ENABLECONN=4000
                  ADMISSION_CUTOFFCONN=4010
                  ADMISSION_ENABLEMEM=3100
                  ADMISSION_CUTOFFMEM=3150
                  ;;
          esac
          /opt/tms/bin/mddbreq $MFDB_ORIG set modify "" /rbt/mfd/admission_cutoffmem  uint32 $ADMISSION_CUTOFFMEM
          /opt/tms/bin/mddbreq $MFDB_ORIG set modify "" /rbt/mfd/admission_enablemem  uint32 $ADMISSION_ENABLEMEM
          /opt/tms/bin/mddbreq $MFDB_ORIG set modify "" /rbt/mfd/admission_cutoffconn  uint32 $ADMISSION_CUTOFFCONN
          /opt/tms/bin/mddbreq $MFDB_ORIG set modify "" /rbt/mfd/admission_enableconn  uint32 $ADMISSION_ENABLECONN

          # update for cachepgs value inside the manufacturing db
          APPLIANCE_MODEL=`/opt/tms/bin/mddbreq -v $MFDB_ORIG query get "" /rbt/mfd/model`
          CACHEPGS=1
          case "$APPLIANCE_MODEL" in
              500)
                  CACHEPGS=76745
                  ;;
              1000)
                  CACHEPGS=76745
                  ;;
              2000)
                  CACHEPGS=178757
                  ;;
              3000)
                  CACHEPGS=148427
                  ;;
              5000)
                  CACHEPGS=160041
                  ;;
          esac
          /opt/tms/bin/mddbreq $MFDB_ORIG set modify "" /rbt/mfd/store/cachepgs uint32 $CACHEPGS
          touch /var/opt/rbt/.clean
          ;;

    5_6)
          # update for max_graphs value inside the manufacturing db
          APPLIANCE_MODEL=`/opt/tms/bin/mddbreq -v $MFDB_ORIG query get "" /rbt/mfd/model`
          case "$APPLIANCE_MODEL" in
              500)
                  CIFS_MAX_GRAPHS=75
                  ;;
              1000)
                  CIFS_MAX_GRAPHS=75
                  ;;
              2000)
                  CIFS_MAX_GRAPHS=200
                  ;;
              3000)
                  CIFS_MAX_GRAPHS=375
                  ;;
              5000)
                  CIFS_MAX_GRAPHS=600
                  ;;
          esac
          /opt/tms/bin/mddbreq $MFDB_ORIG set modify "" /rbt/mfd/max_graphs uint32 $CIFS_MAX_GRAPHS
          ;;
    
    6_7)
        APPLIANCE_MODEL=`/opt/tms/bin/mddbreq -v $MFDB_ORIG query get "" /rbt/mfd/model`
        CACHEPGS=1
        case "$APPLIANCE_MODEL" in
            2000)
                CACHEPGS=140800
                /opt/tms/bin/mddbreq $MFDB_ORIG set modify "" /rbt/mfd/store/cachepgs uint32 $CACHEPGS
                touch /var/opt/rbt/.clean
                ;;
            3000)
                CACHEPGS=192000
                /opt/tms/bin/mddbreq $MFDB_ORIG set modify "" /rbt/mfd/store/cachepgs uint32 $CACHEPGS
                touch /var/opt/rbt/.clean
                ;;
        esac
        ;;

    7_8)
        rm -rf /var/opt/tms/stats/*
        ;;

    8_9)
        APPLIANCE_MODEL=`/opt/tms/bin/mddbreq -v $MFDB_ORIG query get "" /rbt/mfd/model`
        case "$APPLIANCE_MODEL" in
            500)
                ADMISSION_ENABLECONN=100
                ADMISSION_CUTOFFCONN=110
                ADMISSION_ENABLEMEM=850
                ADMISSION_CUTOFFMEM=900
                CIFS_MAX_GRAPHS=75
                ;;
            1000)
                ADMISSION_ENABLECONN=300
                ADMISSION_CUTOFFCONN=310
                ADMISSION_ENABLEMEM=1300
                ADMISSION_CUTOFFMEM=1350
                CIFS_MAX_GRAPHS=100
                ;;
            2000)
                ADMISSION_ENABLECONN=600
                ADMISSION_CUTOFFCONN=610
                ADMISSION_ENABLEMEM=1800
                ADMISSION_CUTOFFMEM=1850
                CIFS_MAX_GRAPHS=200
                ;;
            3000)
                ADMISSION_ENABLECONN=2000
                ADMISSION_CUTOFFCONN=2010
                ADMISSION_ENABLEMEM=2650
                ADMISSION_CUTOFFMEM=2700
                CIFS_MAX_GRAPHS=375
                ;;
            5000)
                ADMISSION_ENABLECONN=4000
                ADMISSION_CUTOFFCONN=4010
                ADMISSION_ENABLEMEM=3100
                ADMISSION_CUTOFFMEM=3150
                CIFS_MAX_GRAPHS=600
                ;;
        esac
        /opt/tms/bin/mddbreq $MFDB_ORIG set modify "" /rbt/mfd/admission_cutoffmem  uint32 $ADMISSION_CUTOFFMEM
        /opt/tms/bin/mddbreq $MFDB_ORIG set modify "" /rbt/mfd/admission_enablemem  uint32 $ADMISSION_ENABLEMEM
        /opt/tms/bin/mddbreq $MFDB_ORIG set modify "" /rbt/mfd/admission_cutoffconn  uint32 $ADMISSION_CUTOFFCONN
        /opt/tms/bin/mddbreq $MFDB_ORIG set modify "" /rbt/mfd/admission_enableconn  uint32 $ADMISSION_ENABLECONN
        /opt/tms/bin/mddbreq $MFDB_ORIG set modify "" /rbt/mfd/max_graphs uint32 $CIFS_MAX_GRAPHS
        ;;

    9_10)
        APPLIANCE_MODEL=`/opt/tms/bin/mddbreq -v $MFDB_ORIG query get "" /rbt/mfd/model`
        case "$APPLIANCE_MODEL" in
            2000)
                BWLIMIT=4000
                /opt/tms/bin/mddbreq $MFDB_ORIG set modify "" /rbt/mfd/bwlimit uint64 $BWLIMIT
                ;;
        esac
        ;;

    10_11)
        APPLIANCE_MODEL=`/opt/tms/bin/mddbreq -v $MFDB_ORIG query get "" /rbt/mfd/model`
        case "$APPLIANCE_MODEL" in
            500)
                WDT_ENABLE="true"
                ;;
            1000)
                WDT_ENABLE="true"
                ;;
            2000)
                WDT_ENABLE="true"
                ;;
            3000)
                WDT_ENABLE="true"
                ;;
            5000)
                WDT_ENABLE="true"
                ;;
        esac
        /opt/tms/bin/mddbreq $MFDB_ORIG set modify "" /rbt/mfd/wdt bool $WDT_ENABLE
        ;;

    11_12)
        APPLIANCE_MODEL=`/opt/tms/bin/mddbreq -v $MFDB_ORIG query get "" /rbt/mfd/model`
        case "$APPLIANCE_MODEL" in
            500)
                WCCP_DEF_WEIGHT="1"
                ;;
            1000)
                WCCP_DEF_WEIGHT="3"
                ;;
            2000)
                WCCP_DEF_WEIGHT="6"
                ;;
            3000)
                WCCP_DEF_WEIGHT="20"
                ;;
            5000)
                WCCP_DEF_WEIGHT="40"
                ;;
        esac
        /opt/tms/bin/mddbreq $MFDB_ORIG set modify "" /rbt/mfd/wccp_default_weight uint16 $WCCP_DEF_WEIGHT
        ;;

    12_13)
        APPLIANCE_MODEL=`/opt/tms/bin/mddbreq -v $MFDB_ORIG query get "" /rbt/mfd/model`
        case "$APPLIANCE_MODEL" in
            500)
                CASE="500"
                ;;
            1000)
                CASE="1000"
                ;;
            2000)
                CASE="2000"
                ;;
            3000)
                CASE="3000"
                ;;
            5000)
                CASE="5000"
                ;;
        esac
        /opt/tms/bin/mddbreq $MFDB_ORIG set modify "" /rbt/mfd/case string $CASE
        ;;

    13_14)
        mkdir -p -m 0111 /var/empty/sshd
        ;;

    14_15)
        APPLIANCE_MODEL=`/opt/tms/bin/mddbreq -v $MFDB_ORIG query get "" /rbt/mfd/model`
        case "$APPLIANCE_MODEL" in
            500)
                ADMISSION_ENABLECONN=200
                ADMISSION_CUTOFFCONN=210
                ;;
            1000)
                ADMISSION_ENABLECONN=625
                ADMISSION_CUTOFFCONN=635
                ;;
            2000)
                ADMISSION_ENABLECONN=1300
                ADMISSION_CUTOFFCONN=1310
                ;;
            3000)
                ADMISSION_ENABLECONN=2400
                ADMISSION_CUTOFFCONN=2410
                ;;
            5000)
                ADMISSION_ENABLECONN=4000
                ADMISSION_CUTOFFCONN=4010
                ;;
        esac
        /opt/tms/bin/mddbreq $MFDB_ORIG set modify "" /rbt/mfd/admission_cutoffconn  uint32 $ADMISSION_CUTOFFCONN
        /opt/tms/bin/mddbreq $MFDB_ORIG set modify "" /rbt/mfd/admission_enableconn  uint32 $ADMISSION_ENABLECONN
        ;;

    15_16)
        APPLIANCE_MODEL=`/opt/tms/bin/mddbreq -v $MFDB_ORIG query get "" /rbt/mfd/model`
        case "$APPLIANCE_MODEL" in
            500)
                ADMISSION_CUTOFFCONN=220
                ;;
            1000)
                ADMISSION_CUTOFFCONN=650
                ;;
            2000)
                ADMISSION_CUTOFFCONN=1350
                ;;
            3000)
                ADMISSION_CUTOFFCONN=2475
                ;;
            5000)
                ADMISSION_CUTOFFCONN=4100
                ;;
        esac
        /opt/tms/bin/mddbreq $MFDB_ORIG set modify "" /rbt/mfd/admission_cutoffconn  uint32 $ADMISSION_CUTOFFCONN
        ;;

    99_100)
        touch /var/opt/rbt/.dc_name
        mkdir -p -m 0755 /var/log/samba
        mkdir -p -m 0755 /var/log/rcu
        APPLIANCE_MODEL=`/opt/tms/bin/mddbreq -v $MFDB_ORIG query get "" /rbt/mfd/model`
        case "$APPLIANCE_MODEL" in
            500 | 510 | 1000 | 1010 | 3000 | 3010 | 5000 | 5010)
                /opt/tms/bin/mddbreq $MFDB_ORIG set modify "" /rbt/mfd/store/dual bool false
                ;;

            2000 | 2001 | 2010 | 2011)
                /opt/tms/bin/mddbreq $MFDB_ORIG set modify "" /rbt/mfd/store/dual bool true
                ;;
        esac

        # Now copy the database over into the new location which is $MFDB.
        mkdir -p -m 0755 $MFDB_DIR
        cp -f $MFDB_ORIG $MFDB
        ;;

    100_101)
        mkdir -m 0755 /var/racoon
        mkdir -m 0755 /var/cache/samba
        mkdir -m 0755 /var/spool/samba
        mkdir -m 0755 /var/opt/rcu
	;;

    103_104)
        # make sure that the /var/samba directory exists.
        if [ ! -d /var/samba ]; then
            mkdir -m 0755 /var/samba
        fi

        # if /var/samba/var doesn't exist, create it and then
        # recreate the symlink.
        if [ ! -d /var/samba/var ]; then
            mkdir -m 0755 /var/samba/var
        fi
        rm -rf /usr/local/samba/var
        ln -s /var/samba/var /usr/local/samba

        # now check if there's anything inside /var/samba/var and
        # if not, copy the default files over.
        if [ ! -d /var/samba/var/locks ]; then
            rm -rf /var/samba/var/*
            cp -a /usr/local/samba/var_files/* /var/samba/var
        fi

        # if /var/samba/private doesn't exist, create it and then
        # recreate the symlink.
        if [ ! -d /var/samba/private ]; then
            mkdir -m 0755 /var/samba/private
        fi
        rm -rf /usr/local/samba/private
        ln -s /var/samba/private /usr/local/samba

        # now check if there's anything inside /var/samba/private and
        # if not, copy the default files over.
        if [ ! -f /var/samba/private/secrets.tdb ]; then
            rm -rf /var/samba/private/*
            cp -a /usr/local/samba/private_files/* /var/samba/private
        fi
	;;

    104_105)
        # create /var/opt/rbt/sar directory if it doesn't exist
	if [ ! -d /var/opt/rbt/sar ]; then
	    mkdir -m 0755 /var/opt/rbt/sar
	fi
	;;

    105_106)
        # As we are changing stats (samples and chd), files on disk
	# has different header than one in memory. Which result in
	# conflicts. To resolve that conflict we need to remove all
	# .dat files.
	rm -rf /var/opt/tms/stats/*.dat
	;;

    106_107)
        APPLIANCE_MODEL=`/opt/tms/bin/mddbreq -v $MFDB query get "" /rbt/mfd/model`
	repartitioned=0

	case "$APPLIANCE_MODEL" in
	510|1010)
	    DISK=`$MDDBREQ -v $MFDB query get "" /rbt/mfd/diskdev`
	    echo -e ",167772160,," > $CMDS
	    $SFDISK -N11 -uS --force --no-reread $DISK < $CMDS
	    rm -f $CMDS

	    repartitioned=1
	    ;;
	3010|3510|5010)
	    DISK=`$MDDBREQ -v $MFDB query get "" /rbt/mfd/diskdev`
	    echo -e ",377487360,," > $CMDS
	    $SFDISK -N11 -uS --force --no-reread $DISK < $CMDS
	    rm -f $CMSD

	    repartitioned=1
	    ;;
	2010|2011|2510|2511)
	    DATA_PART1=`$MDDBREQ -v $MFDB query get "" /rbt/mfd/store/mdraid1`
            DATA_PART2=`$MDDBREQ -v $MFDB query get "" /rbt/mfd/store/mdraid2`
    	    SMB_PART1=`$MDDBREQ -v $MFDB query get "" /rbt/mfd/smb/mdraid1`
            SMB_PART2=`$MDDBREQ -v $MFDB query get "" /rbt/mfd/smb/mdraid2`
	    DISK1=`echo $DATA_PART1 | sed "s/[0-9]*$//g"`
            DISK2=`echo $DATA_PART2 | sed "s/[0-9]*$//g"`

	    $SFDISK -d $DISK1 > $TABLE1
	    START1=`grep "${DATA_PART1}" $TABLE1 | awk '{print $3}'`
	    sed --in-place -e "\:${DATA_PART1}:d" $TABLE1
	    sed --in-place -e "\:${SMB_PART1}:d" $TABLE1
	    echo -e "$DATA_PART1 : start=$START1 size=146496672, Id=da" >> $TABLE1 
	    echo -e "$SMB_PART1 : start=163477503, size=188763687, Id=83" >> $TABLE1
	    $SFDISK --force --no-reread $DISK1 < $TABLE1
	    rm -f $TABLE1

	    $SFDISK -d $DISK2 > $TABLE2
	    START2=`grep "${DATA_PART2}" $TABLE2 | awk '{print $3}'`
	    sed --in-place -e "\:${DATA_PART2}:d" $TABLE2
	    sed --in-place -e "\:${SMB_PART2}:d" $TABLE2
	    echo -e "$DATA_PART2 : start=$START2 size=146496672, Id=da" >> $TABLE2 
	    echo -e "$SMB_PART2 : start=163477503, size=188763687, Id=83" >> $TABLE2
	    $SFDISK --force --no-reread $DISK2 < $TABLE2
	    rm -f $TABLE2

	    repartitioned=1
	    ;;
	esac

	if [ "x$repartitioned" = "x1" ]; then
	    REBOOT_NEEDED=1
	    export REBOOT_NEEDED
	    REBOOT_RERUN_FIRSTBOOT=1
	    export REBOOT_RERUN_FIRSTBOOT
	    RBT_REPARTITION_IN_PROGRESS=1
	    export RBT_REPARTITION_IN_PROGRESS
	    rm -f /var/opt/rbt/.samba_ready
	    # remove existing samba mount entry from fstab
	    sed --in-place=.back -e '\:LABEL=SMB:d' -e '\:/proxy:d' $FSTAB_PATH
	fi
	;;

    107_108)
	rm -rf /var/opt/tms/stats/*dstore*.dat
	;;

    108_109)
	rm -rf /var/opt/tms/stats/chd-bwt_*.dat
	;;

    109_110)
	# We are chaning counters from 32 to 64 bits
	rm -rf /var/opt/tms/stats/*.dat
	;;

    # note that SSL was not introducted until Tahiti/3.0 but these
    # upgrade rules were added earlier due to the closed beta of SSL
    # being based off of Rapanui/2.1

    110_111)
        # create directories for SSL
        mkdir -m 0755 /var/opt/rbt/ssl
        mkdir -m 0755 /var/opt/rbt/ssl/ca
        mkdir -m 0755 /var/opt/rbt/ssl/ca/default
        mkdir -m 0755 /var/opt/rbt/ssl/ca/user
        mkdir -m 0755 /var/opt/rbt/ssl/server
        mkdir -m 0755 /var/opt/rbt/ssl/server/ca
        mkdir -m 0755 /var/opt/rbt/ssl/server/cert
        ;;

    111_112)
        # create directories for SSL Tunnel
        mkdir -m 0755 /var/opt/rbt/ssl/tunnel
        mkdir -m 0755 /var/opt/rbt/ssl/tunnel/ca
        mkdir -m 0755 /var/opt/rbt/ssl/tunnel/cert
        ;;

    112_113)
        # correct PFS permissions
        chmod 0777 /var/log/rcu
        ;;

    #--------------------------------------------------------------#
    #                                                              #
    #  Tahiti/3.0 upgrades                                         #
    #                                                              #
    #--------------------------------------------------------------#

    199_200)
        # fix a problem that occurred during 2.1.5
        rm -rf /0755
        mkdir -p -m 0755 /var/opt/rcu/backup
        /usr/bin/python /sbin/pfs_30_upgrade.py
        ;;

    200_201)
        APPLIANCE_MODEL=`/opt/tms/bin/mddbreq -v $MFDB query get "" /rbt/mfd/model`
	case "$APPLIANCE_MODEL" in
	5520)
            touch /var/opt/rbt/.clean
	    ;;
        esac
        ;;

    201_202)
	# remove unnecessary CHD .dat files
        rm -f /var/opt/tms/stats/chd-17.dat
        rm -f /var/opt/tms/stats/chd-33.dat
        ;;

    202_203)
        # correct PFS permissions
        chmod 0777 /var/log/rcu
        ;;

    203_204)
        mkdir /var/opt/rbt/alt
        ;;

    #--------------------------------------------------------------#
    #                                                              #
    #  Tonga/4.0 upgrades                                          #
    #                                                              #
    #--------------------------------------------------------------#

    299_300)
        # blow away pre-Tonga SSL state
        rm -rf /var/opt/rbt/ssl
        ;;

    300_301)
	# remove unnecessary CHD .dat files
        rm -f /var/opt/tms/stats/chd-17.dat
        rm -f /var/opt/tms/stats/chd-33.dat
        ;;

    301_302)
        # correct PFS permissions
        chmod 0777 /var/log/rcu
        ;;

    302_303)
        mkdir /var/opt/rbt/alt
        ;;

    303_304)
        # remove potentially devastating (performance-wise) .dat file
        rm -f /var/opt/tms/stats/sample-sw-version.dat
        ;;


    #--------------------------------------------------------------#
    #                                                              #
    #  Tuvalu/4.1 upgrades                                         #
    #                                                              #
    #--------------------------------------------------------------#

    399_400)
        # remove potentially devastating (performance-wise) .dat file
        rm -f /var/opt/tms/stats/sample-sw-version.dat
        ;;

    400_401)
        mkdir /var/opt/rbt/alt
        ;;

    401_402)
        mkdir /var/etc/samba
        ;;

    #--------------------------------------------------------------#
    #                                                              #
    #  Samoa/5.0 upgrades                                          #
    #                                                              #
    #--------------------------------------------------------------#

    499_500)
        mkdir /var/opt/rbt/alt
        ;;

    500_501)
        # set up BIND chroot environment
        /sbin/chroot_bind_50_upgrade.sh
        ;;

    501_502)
        mkdir /var/etc/samba
        ln -s /etc/opt/tms/output/wdt.xml /etc/wdt.xml
        ;;

    #--------------------------------------------------------------#
    #                                                              #
    #  Guam/6.0 upgrades                                          #
    #                                                              #
    #--------------------------------------------------------------#

    549_550)
        ;;

    550_551)
        ;;

    551_552)
        cp /proxy/__RBT_VSERVER_SHELL__/rsp2/.rsp_alt_db /var/etc/opt/tms/output/rsp_alt_db
        ;;

    552_553)
        # Force verification (and possibly correction) of RSP-related symlinks.
        RSP_STORAGE="/proxy/__RBT_VSERVER_SHELL__/vmware_server"
        check_create_symlink $RSP_STORAGE/etc/vmware /etc/vmware
        check_create_symlink $RSP_STORAGE/etc/vmware-vix /etc/vmware-vix
        check_create_symlink $RSP_STORAGE/etc/vmware/pam.d/vmware-authd /etc/pam.d/vmware-authd
        check_create_symlink $RSP_STORAGE/usr/bin/vmware /usr/bin/vmware
        check_create_symlink $RSP_STORAGE/usr/sbin/vmware /usr/sbin/vmware
        check_create_symlink $RSP_STORAGE/usr/lib/vmware /usr/lib/vmware
        check_create_symlink $RSP_STORAGE/usr/share/vmware /usr/share/vmware
        check_create_symlink $RSP_STORAGE/usr/lib/vmware-vix/ /usr/lib/vmware-vix
        check_create_symlink $RSP_STORAGE/usr/share/vmware-vix/ /usr/share/vmware-vix
        check_create_symlink /usr/lib/vmware-vix/libvixAllProducts.so /lib/libvixAllProducts.so
        if [ -d /lib64 ]; then
            check_create_symlink /usr/lib/vmware-vix/libvixAllProducts.so /lib64/libvixAllProducts.so
        fi
        check_create_symlink $RSP_STORAGE/etc/vmware-vix-disklib /etc/vmware-vix-disklib
        check_create_symlink $RSP_STORAGE/usr/lib/vmware-vix-disklib/ /usr/lib/vmware-vix-disklib
        ;;

    553_554)
        mkdir /var/opt/rbt/riversizer
        mkdir /var/opt/rbt/riversizer/output
        ;;

    #--------------------------------------------------------------#
    #                                                              #
    #  Cook/6.1 upgrades                                           #
    #                                                              #
    #--------------------------------------------------------------#

    554_555)
        # Remove pre 6.0 OBR stats
        rm -f /var/opt/tms/stats/sample-20700.dat
        rm -f /var/opt/tms/stats/chd-20701.dat
        rm -f /var/opt/tms/stats/chd-20704.dat
        rm -f /var/opt/tms/stats/sample-20800.dat
        rm -f /var/opt/tms/stats/chd-20801.dat
        rm -f /var/opt/tms/stats/chd-20804.dat
        ;;

    555_556)
        # Remove stats that could contain bad datapoints [bug58646]
        rm -f /var/opt/tms/stats/sample-30700.dat
        rm -f /var/opt/tms/stats/sample-30800.dat
        rm -f /var/opt/tms/stats/sample-30900.dat
        rm -f /var/opt/tms/stats/chd-30701.dat
        rm -f /var/opt/tms/stats/chd-30804.dat
        rm -f /var/opt/tms/stats/chd-30904.dat
        ;;

    #--------------------------------------------------------------#
    #                                                              #
    #  Malta/7.0 upgrades                                          #
    #                                                              #
    #--------------------------------------------------------------#
    556_557)
        # Create the vmware temporary directory
        mkdir -p /var/vmware
        ;;
    557_558)
        # Create the vmware etc directory
        mkdir -p /var/vmware_server
        ;;


esac
