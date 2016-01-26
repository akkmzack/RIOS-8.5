#!/bin/bash

# $URL$
# $Id: fallback.sh,v 1.6 2013/02/14 00:48:19 tsternberg Exp $

#
# Reboots an appliance into its fallback image.
#
# Usage: $0
#

# Defines the shell variable AIG_FALLBACK_BOOT_ID.
eval `/sbin/aiget.sh`

# Makes the next reboot come up in the fallback image.
/sbin/aigen.py -i -l $AIG_FALLBACK_BOOT_ID

/sbin/reboot
