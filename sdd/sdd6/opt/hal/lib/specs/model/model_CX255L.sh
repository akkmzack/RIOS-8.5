#!/bin/sh
#
# Riverbed Model Data
# $Id: model_CX255L.sh 97127 2011-12-19 17:28:00Z munirb $
#
###############################################################################

# Changes made to this file need to be propagated to the official twiki
# applicance model data file located @ 
# http://internal/twiki/bin/view/NBT/ModelSpecificSoftwareParameters

# MODEL_SWAPSIZE  : MB (BINARY)
# MODEL_VARSIZE   : MB (BINARY)
# MODEL_DISKSIZE  : BYTES
# MODEL_BWLIMIT   : kbps
MODEL_MEMCHECK=800
MODEL_SWAPSIZE=4096
MODEL_VARSIZE=15360
MODEL_ROOTSIZE=1024
MODEL_BOOTDEV=/dev/flash0
MODEL_DISKSIZE=40000000000
MODEL_DISKDEV=/dev/disk0
MODEL_DISKDEV_2=
MODEL_STOREDEV=/dev/disk0p5
MODEL_SMBDEV=
MODEL_SMBBYTES=
MODEL_DUALSTORE=false
MODEL_KERNELTYPE=smp
MODEL_MDRAIDDEV1=
MODEL_MDRAIDDEV2=
MODEL_MDRAIDSMBDEV1=
MODEL_MDRAIDSMBDEV2=
MODEL_ID=JA7
MODEL_LAYOUT=FLASHRRDM
MODEL_CLASS="CX255"
MODEL_FLEXL="CX255L"

MODEL_FTS=true
MODEL_FTS_PARTITION=5
MODEL_FTS_MEDIA="HD"
MODEL_FTS_DISKSIZE_MB=40000
MODEL_LAST_PART_FILL=false    # do not fill up the last partition, set to "true" to fill the last partition or leave not add this variable
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

