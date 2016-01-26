#!/bin/sh
#
# Riverbed Model Data
# $Id: model_V550H.sh 63260 2010-03-13 01:13:51Z clala $
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
MODEL_SWAPSIZE=2047
MODEL_VARSIZE=15360
MODEL_ROOTSIZE=512
MODEL_BOOTDEV=/dev/disk0
MODEL_DISKSIZE=80000000000
MODEL_DISKDEV=/dev/disk1
MODEL_DISKDEV_2=
MODEL_STOREDEV=/dev/disk1p2
MODEL_SMBDEV=
MODEL_SMBBYTES=
MODEL_DUALSTORE=false
MODEL_KERNELTYPE=smp
MODEL_MDRAIDDEV1=
MODEL_MDRAIDDEV2=
MODEL_MDRAIDSMBDEV1=
MODEL_MDRAIDSMBDEV2=
MODEL_ID=V70
MODEL_LAYOUT=VSHSTD
MODEL_CLASS="Virtual"
MODEL_FLEXL="V550M V550H"
# The virtual mfg tag indicates that mfg should not use
# a sport id in mfg.
MODEL_VIRTUAL_MFG=true

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

