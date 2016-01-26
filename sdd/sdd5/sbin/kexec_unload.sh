#! /bin/sh

# Unload the crash kernel and its ramdisk from memory
/sbin/kexec -p -u

# Release the crash kernel memory back to the system
echo 0 > /sys/kernel/kexec_crash_size

# if the /var/kexec_enable file exists; delete it
# this is for the case where we disable the mechanism
# after it had been enabled from the CLI
if [ -f /var/kexec_enable ]; then
        rm -f /var/kexec_enable
fi

