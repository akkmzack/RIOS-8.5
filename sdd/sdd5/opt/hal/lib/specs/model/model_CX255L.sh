#!/bin/sh
#
# Riverbed Model Data
# $Id: model_CX255L.sh 128579 2013-06-12 22:12:48Z etsang $
#
###############################################################################

# Changes made to this file need to be propagated to the official twiki
# applicance model data file located @ 
# http://internal/twiki/bin/view/NBT/ModelSpecificSoftwareParameters

# MODEL_SWAPSIZE  : MB (BINARY)
# MODEL_VARSIZE   : MB (BINARY)
# MODEL_DISKSIZE  : BYTES
# MODEL_BWLIMIT   : kbps
MODEL_MEMCHECK=1800
MODEL_SWAPSIZE=3072
MODEL_VARSIZE=15360
MODEL_ROOTSIZE=3072
MODEL_DISKSIZE=53687091200
MODEL_DISKDEV=/dev/sda
MODEL_DISKDEV_2=
MODEL_STOREDEV=/dev/disk0p10
MODEL_DUALSTORE=false
MODEL_KERNELTYPE=smp
MODEL_MDRAIDDEV1=
MODEL_MDRAIDDEV2=
MODEL_MDRAIDSMBDEV1=
MODEL_MDRAIDSMBDEV2=
MODEL_ID=EC5
MODEL_LAYOUT=STD
MODEL_CLASS="CX255"
MODEL_FLEXL="CX255U CX255L"


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

