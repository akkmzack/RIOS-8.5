#!/usr/bin/env python

# detect if root is a shadow device backed by the swap partition.

import commands
from os.path import exists

# path to tmpfs backed shadow store
TMP_SHA_STORE="/tmp/sha/store"

def main():
    status, root_dev_number = commands.getstatusoutput(
        "ls -l /dev/root | gawk '{ print $5 }' | tr -d ,")

    if status != 0:
        return 1

    status, shadow_dev_number = commands.getstatusoutput(
        "cat /proc/devices | grep shadow | gawk '{ print $1 }'")

    if status != 0:
        return 1

    # if shadow is in the output, the shadow device is backed by a new
    # partition. else, there is no shadow device or it is backed by swap.
    swap_shadow_rc, output = commands.getstatusoutput(
        "/opt/hal/bin/raid/rrdm_tool.py -l | grep shadow")

    shadowed_root     = (root_dev_number == shadow_dev_number)
    shadowed_root_str = str(shadowed_root).lower()

    # if shadow is on tmpfs it should be backed by a file /tmp/sha/store
    # if this file does not exists, then we are not backed by tmpfs/swap
    swap_shadow = False
    if shadowed_root:
        # only if root is shadowed do we check to see if we have a shadow 
        # store
        if swap_shadow_rc != 0:
            if exists(TMP_SHA_STORE):
                swap_shadow = True

    print '%s %s' % (shadowed_root_str, str(swap_shadow).lower())

    return 0

if __name__ == '__main__':
    main()

