#!/bin/sh
#
# Riverbed Model Data
# $Id: model_0501H.sh 55801 2009-08-19 16:30:27Z rbecker $
#
###############################################################################

# Changes made to this file need to be propagated to the official twiki
# applicance model data file located @ 
# http://internal/twiki/bin/view/NBT/ModelSpecificSoftwareParameters

# MODEL_SWAPSIZE  : MB (BINARY)
# MODEL_VARSIZE   : MB (BINARY)
# MODEL_DISKSIZE  : BYTES
# MODEL_BWLIMIT   : kbps
MODEL_MEMCHECK=11600
MODEL_SWAPSIZE=2047
MODEL_VARSIZE=30720
MODEL_ROOTSIZE=512
MODEL_BOOTDEV=/dev/flash0
MODEL_DISKSIZE=800000000000
MODEL_DISKDEV=/dev/disk0
MODEL_DISKDEV_2=
MODEL_STOREDEV=/dev/md0
MODEL_SMBDEV=
MODEL_SMBBYTES=
MODEL_DUALSTORE=false
MODEL_KERNELTYPE=smp
MODEL_MDRAIDDEV1=
MODEL_MDRAIDDEV2=
MODEL_MDRAIDSMBDEV1=
MODEL_MDRAIDSMBDEV2=
MODEL_ID=R66
MODEL_LAYOUT=FLASHRRDM
MODEL_CLASS="0501"
MODEL_FLEXL="0501M 0501H"

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

