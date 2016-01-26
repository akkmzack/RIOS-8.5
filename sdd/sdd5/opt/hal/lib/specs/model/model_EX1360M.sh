#!/bin/sh
#
# Riverbed Model Data
# $Id: model_EX1360M.sh 103319 2013-01-10 19:46:19Z balajir $
#
###############################################################################

# Changes made to this file need to be propagated to the official twiki
# applicance model data file located @ 
# http://internal/twiki/bin/view/NBT/ModelSpecificSoftwareParameters

# MODEL_SWAPSIZE  : MB (BINARY)
# MODEL_VARSIZE   : MB (BINARY)
# MODEL_DISKSIZE  : BYTES
# MODEL_BWLIMIT   : kbps

MODEL_MEMCHECK=129178
MODEL_ROOTSIZE=3096
MODEL_BOOTDEV=/dev/flash0
MODEL_DUALSTORE=false
MODEL_KERNELTYPE=smp
MODEL_ID=F88
MODEL_LAYOUT=FLASHRRDM
MODEL_CLASS="EX1360"
MODEL_FLEXL="EX1360L EX1360M"
MODEL_FTS=true
MODEL_FTS_PARTITION=2
MODEL_FTS_MEDIA="SSD"
MODEL_TMPFSSIZE=4096
MODEL_STOREDEV=/dev/disk20p2

# Size taken from specs.xml 
MODEL_FTS_DISKSIZE_MB=75800

# Segstore size in bytes 
MODEL_DISKSIZE=79482060800

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

