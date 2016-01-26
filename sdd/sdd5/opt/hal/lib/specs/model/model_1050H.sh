#!/bin/sh
#
# Riverbed Model Data
# $Id: model_1050H.sh 70288 2010-09-22 01:33:10Z vsreekanti $
#
###############################################################################

# Changes made to this file need to be propagated to the official twiki
# applicance model data file located @ 
# http://internal/twiki/bin/view/NBT/ModelSpecificSoftwareParameters

# MODEL_SWAPSIZE  : MB (BINARY)
# MODEL_VARSIZE   : MB (BINARY)
# MODEL_DISKSIZE  : BYTES
# MODEL_BWLIMIT   : kbps

MODEL_MEMCHECK=3800
MODEL_SWAPSIZE=2048
MODEL_VARSIZE=15360
MODEL_ROOTSIZE=512
MODEL_DISKSIZE=200000000000
MODEL_BOOTDEV=/dev/flash0
MODEL_DISKDEV=/dev/disk0
MODEL_STOREDEV=/dev/md0
MODEL_SMBDEV=/dev/md3
MODEL_SMBBYTES=200000000000
MODEL_DUALSTORE=false
MODEL_DUALSTORE_NG=true
MODEL_KERNELTYPE=smp
MODEL_MDRAIDDEV1=/dev/disk0p5
MODEL_MDRAIDDEV2=/dev/disk1p5
MODEL_MDRAIDSMBDEV1=/dev/disk0p6
MODEL_MDRAIDSMBDEV2=/dev/disk1p6
MODEL_ID=C48
MODEL_LAYOUT=FLASHRRDM
MODEL_CLASS="1050"
MODEL_FLEXL="1050U 1050L 1050M 1050H"

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
