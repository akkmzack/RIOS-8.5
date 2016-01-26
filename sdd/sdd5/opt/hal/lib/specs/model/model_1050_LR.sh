#!/bin/sh
#
# Riverbed Model Data
# $Id: model_1050_LR.sh 70288 2010-09-22 01:33:10Z vsreekanti $
#
###############################################################################

# Changes made to this file need to be propagated to the official twiki
# applicance model data file located @ 
# http://internal/twiki/bin/view/NBT/ModelSpecificSoftwareParameters

# MODEL_SWAPSIZE  : MB (BINARY)
# MODEL_VARSIZE   : MB (BINARY)
# MODEL_DISKSIZE  : BYTES
# MODEL_BWLIMIT   : kbps
MODEL_MEMCHECK=1900
MODEL_SWAPSIZE=4094
MODEL_VARSIZE=30720
MODEL_ROOTSIZE=512
MODEL_BOOTDEV=/dev/flash0
MODEL_DISKSIZE=100000000000
MODEL_DISKDEV=/dev/disk0
MODEL_DISKDEV_2=
MODEL_STOREDEV=/dev/md0
MODEL_SMBDEV=/dev/md3
MODEL_SMBBYTES=200000000000
MODEL_DUALSTORE=false
MODEL_KERNELTYPE=smp
MODEL_MDRAIDDEV1=
MODEL_MDRAIDDEV2=
MODEL_MDRAIDSMBDEV1=
MODEL_MDRAIDSMBDEV2=
MODEL_ID=C48
MODEL_LAYOUT=FLASHRRDM
MODEL_CLASS="1050"
MODEL_FLEXL="1050U 1050L 1050_LR"

do_pre_writeimage_actions()
{
    return
}

do_extra_mfdb_actions()
{
    return
}

do_extra_initialdb_actions()
{
    return
}

