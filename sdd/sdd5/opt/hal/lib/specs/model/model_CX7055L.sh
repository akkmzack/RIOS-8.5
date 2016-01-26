#!/bin/sh
#
# Riverbed Model Data
# $Id: model_CX7055L.sh 129149 2013-06-25 18:15:39Z balajir $
#
###############################################################################

# Changes made to this file need to be propagated to the official twiki
# applicance model data file located @ 
# http://internal/twiki/bin/view/NBT/ModelSpecificSoftwareParameters

# MODEL_SWAPSIZE  : MB (BINARY)
# MODEL_VARSIZE   : MB (BINARY)
# MODEL_DISKSIZE  : BYTES
# MODEL_BWLIMIT   : kbps
MODEL_MEMCHECK=29400
MODEL_SWAPSIZE=2047
MODEL_VARSIZE=30720
MODEL_ROOTSIZE=1024
MODEL_BOOTDEV=/dev/flash0
MODEL_DISKSIZE=159384600576
MODEL_DISKDEV=/dev/disk2
MODEL_DISKDEV_2=
MODEL_STOREDEV=/dev/disk2p2
MODEL_SMBDEV=
MODEL_SMBBYTES=
MODEL_DUALSTORE=false
MODEL_KERNELTYPE=smp
MODEL_MDRAIDDEV1=
MODEL_MDRAIDDEV2=
MODEL_MDRAIDSMBDEV1=
MODEL_MDRAIDSMBDEV2=
MODEL_ID=F86
MODEL_LAYOUT=FLASHRRDM
MODEL_CLASS="CX7055"
MODEL_FLEXL="CX7055L"
MODEL_FTS_PARTITION=2
MODEL_FTS_MEDIA="SSD"
# on this model we identify the segstore size
# as the size of the segstore on a single disk
# as this is the minimum segstore size for the unit.
MODEL_FTS_DISKSIZE_MB=152001

MODEL_FTS=true
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

