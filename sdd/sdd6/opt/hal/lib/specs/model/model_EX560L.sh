#!/bin/sh
#
# Riverbed Model Data
# $Id: model_EX560L.sh 98579 2012-01-19 22:22:12Z munirb $
#
###############################################################################

# Changes made to this file need to be propagated to the official twiki
# applicance model data file located @ 
# http://internal/twiki/bin/view/NBT/ModelSpecificSoftwareParameters

# MODEL_SWAPSIZE  : MB (BINARY)
# MODEL_VARSIZE   : MB (BINARY)
# MODEL_DISKSIZE  : BYTES
# MODEL_BWLIMIT   : kbps
MODEL_MEMCHECK=7800
MODEL_SWAPSIZE=8000
MODEL_VARSIZE=30720
MODEL_ROOTSIZE=2200
MODEL_BOOTDEV=/dev/disk0
MODEL_BOOTDEV_2=
MODEL_DISKSIZE=40000000000
MODEL_DISKDEV=/dev/disk1
MODEL_DISKDEV_2=
MODEL_STOREDEV=/dev/disk0p9
MODEL_SMBDEV=
MODEL_SMBBYTES=
MODEL_DUALSTORE=false
MODEL_KERNELTYPE=smp
MODEL_MDRAIDDEV1=
MODEL_MDRAIDDEV2=
MODEL_MDRAIDSMBDEV1=
MODEL_MDRAIDSMBDEV2=
MODEL_ID=DA2
MODEL_LAYOUT=SSGSTD
MODEL_CLASS="EX560"
MODEL_FLEXL="EX560L"
MODEL_GCACHESIZE=2048
MODEL_TMPFSSIZE=2048
# The virtual mfg tag indicates that mfg should not use
# a sport id in mfg.
#MODEL_BOB_MFG=true
MODEL_FTS=true
MODEL_FTS_PARTITION=9
MODEL_FTS_MEDIA="SSD"
MODEL_FTS_DISKSIZE_MB=38140
MODEL_ERASE_BLOCK_SIZE_SSD=524288 # In bytes

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
