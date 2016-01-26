#!/bin/sh
#
# Riverbed Model Data
# $Id: model_CX1555H.sh 98574 2012-01-19 21:58:32Z munirb $
#
###############################################################################

# Changes made to this file need to be propagated to the official twiki
# applicance model data file located @ 
# http://internal/twiki/bin/view/NBT/ModelSpecificSoftwareParameters

# MODEL_SWAPSIZE  : MB (BINARY)
# MODEL_VARSIZE   : MB (BINARY)
# MODEL_DISKSIZE  : BYTES
# MODEL_BWLIMIT   : kbps
MODEL_MEMCHECK=7900
MODEL_SWAPSIZE=2047
MODEL_VARSIZE=15360
MODEL_ROOTSIZE=1024
MODEL_BOOTDEV=/dev/flash0
MODEL_DISKSIZE=159388794880
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
MODEL_ID=F82
MODEL_LAYOUT=FLASHRRDM
MODEL_CLASS="CX1555"
MODEL_FLEXL="CX1555H"
MODEL_FTS=true
MODEL_FTS_PARTITION=2
MODEL_FTS_MEDIA="SSD"
# on this model we identify the segstore size
# as the size of the segstore on a single disk
# as this is the minimum segstore size for the unit.
MODEL_FTS_DISKSIZE_MB=152005
MODEL_FORTEST=false
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

