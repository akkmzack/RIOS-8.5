#!/bin/sh
#
# Riverbed Model Data
# $Id: model_CX5055L.sh 103970 2012-04-05 22:39:57Z clala $
#
###############################################################################

# Changes made to this file need to be propagated to the official twiki
# applicance model data file located @ 
# http://internal/twiki/bin/view/NBT/ModelSpecificSoftwareParameters

# MODEL_SWAPSIZE  : MB (BINARY)
# MODEL_VARSIZE   : MB (BINARY)
# MODEL_DISKSIZE  : BYTES
# MODEL_BWLIMIT   : kbps
MODEL_MEMCHECK=11900
MODEL_SWAPSIZE=2047
MODEL_VARSIZE=30720
MODEL_ROOTSIZE=512
MODEL_BOOTDEV=/dev/flash0
MODEL_DISKSIZE=79694397440
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
MODEL_ID=F83
MODEL_LAYOUT=FLASHRRDM
MODEL_CLASS="CX5055"
MODEL_FLEXL="CX5055L"
MODEL_FTS_PARTITION=2
MODEL_FTS_MEDIA="SSD"
# on this model we identify the segstore size
# as the size of the segstore on a single disk
# as this is the minimum segstore size for the unit.
MODEL_FTS_DISKSIZE_MB=76002

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

