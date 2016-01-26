#
# Revision:  $Rev: 93022 $
# Date:      $Date: 2011-10-06 13:43:21 -0700 (Thu, 06 Oct 2011) $
# Author:    $Author: msmith $
# Id:        $Id: scrub_vsp.sh 93022 2011-10-06 20:43:21Z msmith $
# URL:       $URL: svn://svn/mgmt/branches/malta_529_fix_branch/products/rbt_sh/src/base_os/common/script_files/scrub_vsp.sh $
#
# (C) Copyright 2011 Riverbed Technology, Inc.
# All rights reserved.
#

VIRT_WRAPPERD=/opt/tms/variants/bob/bin/virt_wrapperd

# Get our MAC addr to use in the local datastore and RiOS VM name
export MAC_ADDR=`vmware-rpctool 'info-get guestinfo.hostprimarymac' | sed 's/://g'`

# Get our local datastore name
export LOCAL_DATASTORE_NAME="local_${MAC_ADDR}"

# Get our RiOS VM Name
export RIOS_VM_NAME="RiOS_${MAC_ADDR}"

# Hard stop/disable all VMs except our RiOS VM using virt_wrapperd one-shot
${VIRT_WRAPPERD} -o force-disable-all-vms "excluded_vm_name" string ${RIOS_VM_NAME} 

# Sleep for a few seconds to make sure ESXi's had enough time to handle the
# above function
sleep 5

# Unregister all VMs except our RiOS VM using virt_wrapperd one-shot
${VIRT_WRAPPERD} -o unregister-all-vms "excluded_vm_name" string ${RIOS_VM_NAME} 

# Sleep for a few seconds to make sure ESXi's had enough time to handle the
# above function
sleep 5

# Delete the contents of the local datastore
${VIRT_WRAPPERD} -o datastore-remove "name" string ${LOCAL_DATASTORE_NAME}

# Blow away our ESXi side state.  The effects of blowing away the state aren't
# seen until the next reboot.  Since this script is part of factory reset, it's
# expected that a reboot will be happening soon.
launch_esxi_ssh.py "/sbin/firmwareConfig.sh --reset-only"

