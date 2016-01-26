#!/usr/bin/python
#
# Script to update settings within BIOS nvram
# Original purpose is to enable the virtualization bit
#  for 64 bit virtualization for the 1uxx50, but this
#  script can be extended for other motherboards, and
#  can be used to update other settings.
#
# Returns:
#  0 on update skipped
#  2 on update success (requiring a reboot or power cycle)
#  3 on bits to update already set
#  1 on error
#
# Usage:
# update_bios_nvram.py product=<product> offset=<hex> bits_(on|off)=<hex>
#  product  - the motherboard product name as seen by dmidecode
#  offset   - the hex offset within the nvram image counting from 0x00 where 
#              the change will be made
#  bits_on  - provide a hex value where any set bits (1's) will be turned on
#              within the offset byte specified
#  bits_off - same as bits_on, but any set bits will be turned off within
#              the offset byte specified
# A product, offset, and bits_(on|off) value must be specified
# Any number of offset/bits_(on|off) pairs may be included, to update multiple
#  bytes at once - but there must be the same number of offset/bits_(on|off)
#  parameters specified
# S6631 BIOS v1.06 or later, and S6673 BIOS v1.08 or later supported
#
#
# Example to enable the 64 bit virtualization bit on the 1uxx50:
# update_bios_nvram.py product=S6631 offset=0x97 bits_on=0x08
#

import re
import sys
from os import popen
from os import path
from os import remove
from time import sleep

def calculate_checksum(bytes, which_checksum, motherboard):
    starting_offset = 0x00
    ending_offset = 0x00
    skip_offsets = []
    mask_offsets = []
    masks = []
    if motherboard == "S6631":
        if which_checksum == "standard":
            starting_offset = 0x02
            ending_offset = 0x1f
        if which_checksum == "extended":
            starting_offset = 0x29
            ending_offset = 0xa3
        skip_offsets = [0x20,0x21,0x25,0x26,0x27,0x28,0x30,0x31,0x46,0x52,0x62,
          0x63,0x64,0x66,0xa3]
        mask_offsets = [0xa2]
        masks = [0x07] # only include the last 3 bits of byte 0xa2
    if motherboard == "S6673":
        if which_checksum == "standard":
            starting_offset = 0x02
            ending_offset = 0x1f
        if which_checksum == "extended":
            starting_offset = 0x29
            ending_offset = 0xe2
        skip_offsets = [0x20,0x21,0x25,0x26,0x27,0x28,0x30,0x31,0x52,0x62,0x63,
          0x67,0x69,0x6b,0x6e,0x6f,0x70,0x71,0xa4,0xe2]
        mask_offsets = []
        masks = []

    if ((which_checksum != "standard") and (which_checksum != "extended")) \
      or ((starting_offset == 0x00) and (ending_offset == 0x00)):
        print "calculate_checksum called improperly"
        sys.exit(1)

    offset = 0x0 # current offset within bytes string
    search_checksum_total = 0x0 # calculated checksum

    for i in bytes:
        # check if offset should be within checksum range, 
        # and not skipped by cmos map
        if (offset >= starting_offset) and (offset <= ending_offset):
            if offset not in skip_offsets:
                if offset in mask_offsets:
                    search_checksum_total += (ord(i) \
                      & masks[mask_offsets.index(offset)])
                else:
                    search_checksum_total += ord(i)
        offset += 1
    bytes = write_checksum(bytes, which_checksum, search_checksum_total,
      motherboard) # now lets set the checksum we just calculated
    return bytes

def write_checksum(bytes, which_checksum, checksum, motherboard):
    checksum_offset = 0x00
    if (motherboard == "S6631") or (motherboard == "S6673"):
        if which_checksum == "standard":
            checksum_offset = 0x20
        if which_checksum == "extended":
            checksum_offset = 0x30
    if ((which_checksum != "standard") and (which_checksum != "extended")) \
      or (checksum_offset == 0x00):
        print "write_checksum called improperly"
        sys.exit(1)

    # calculate high and low byte values of the checksum and add to bytes string
    high = checksum / 0x100
    low = checksum - (high * 0x100)
    bytes = bytes[0x00:checksum_offset] + chr(high) + chr(low) \
      + bytes[checksum_offset + 0x02:]
    return bytes

def get_bios_version(motherboard):
    return_value = ""
    if (motherboard == "S6631") or (motherboard == "S6673"):
        dmi = popen("dmidecode | grep -A 2 'BIOS Inform' | grep 'Version'")
        output = dmi.read()
        match = re.match(r"\s+Version:\s+'\s*V(\d+\.\d+\w?)", output)
        if match:
            return_value = match.group(1)
    return return_value

def check_bios_version(motherboard):
    bios_version = get_bios_version(motherboard)
    if motherboard == "S6631":
        if bios_version >= "1.06":
            return True
    if motherboard == "S6673":
        if bios_version >= "1.08":
            return True
    return False

def get_motherboard():
    supported_motherboards = ["S6631","S6673"] # add additional boards to this list
    motherboard = ""
    check_motherboard = popen("dmidecode | grep -A 6 'Base Board'")
    output = check_motherboard.read()
    match = re.search(r"Product\sName:\s(\w+)", output)
    if match:
        motherboard = match.group(1)
    if motherboard in supported_motherboards:
        return motherboard
    else:
        return "not_supported"

def save_nvram_image(binary_file_name):
    modprobe = popen("modprobe nvram")
    time_count = 0.0
    while not path.exists("/dev/nvram"):
        sleep(.5)
        if time_count > 8:
            print "nvram module not loading"
            sys.exit(1)
        time_count += .5
    save = popen("cat /dev/nvram > " + binary_file_name)
    time_count = 0.0
    while not path.exists(binary_file_name):
        sleep(.5)
        if time_count > 2:
            print "nvram did not save"
            sys.exit(1)
        time_count += .5

def get_nvram_contents(binary_file_name):
    try:
        bytes = open(binary_file_name, "rb").read()
    except Exception:
        bytes = []
    return bytes

def set_bits(bytes, offsets, bits, on_or_off):
    looper = 0
    for offset in offsets:
        byte = ord(bytes[offset])
        if on_or_off[looper] == "off":
            # need to do a bitwise not to use the flags in bits to turn off
            # instead of turn on, we will reverse this after setting
            byte = ~byte
        if (byte | bits[looper]) == byte:
            print str(hex(offset)) + " already set"
        else:
            print str(hex(offset)) + " not set, setting..."
            byte = byte | bits[looper]
            if on_or_off[looper] == "off":
                # undo the bitwise not after we have already applied our change
                byte = ~byte
            # now replace the original byte with the modified one
            bytes = bytes[0x00:offset] + chr(byte) + bytes[offset + 0x01:]
        looper += 1
    return bytes

def write_nvram_image(bytes, binary_file_name):
    open(binary_file_name, "wb").write(bytes)

def update_nvram(binary_file_name):
    run = popen("cat " + binary_file_name + " > /dev/nvram")


# capture command line arguments
cla_motherboard = ""
offsets = []
bits = []
on_or_off = []
for i in sys.argv:
    match = re.match(r"product=(\w+)", i)
    if match:
        cla_motherboard = match.group(1)
    match = re.match(r"offset=0x(\d|[a-f]|[A-F])(\d|[a-f]|[A-F])?", i)
    if match:
        append_str = "0x" + match.group(1)
        if match.group(2):
            append_str = append_str + match.group(2)
        offsets.append(int(append_str, 16))
    match = re.match(r"bits_(on|off)=0x(\d|[a-f]|[A-F])(\d|[a-f]|[A-F])?", i)
    if match:
        append_str = "0x" + match.group(2)
        if match.group(3):
            append_str = append_str + match.group(3)
        bits.append(int(append_str, 16))
        on_or_off.append(match.group(1))
# check command line arguments
if cla_motherboard == "":
    print "Product must be specified, such as 'product=S6631'"
    sys.exit(1)
if (len(offsets) == 0) or (len(bits) == 0):
    print "offset and/or bits_(on|off) not properly specified"
    sys.exit(1)
if len(offsets) != len(bits):
    print "An equal number of offset/bits_(on|off) parameters must be specified"
    sys.exit(1)

motherboard = get_motherboard()
if (motherboard != cla_motherboard) and (motherboard != "not_supported"):
    print "Detected motherboard does not match expected, exiting"
    sys.exit(1)

binary_file_name = "/var/tmp/nvram_image"
if motherboard != "not_supported":
    if check_bios_version(motherboard):
        save_nvram_image(binary_file_name)
        bytes = get_nvram_contents(binary_file_name)
        new_bytes = set_bits(bytes, offsets, bits, on_or_off)
        if new_bytes != bytes: # change means the bit(s) were updated
            # now set the checksums
            new_bytes = calculate_checksum(new_bytes, "standard", motherboard)
            new_bytes = calculate_checksum(new_bytes, "extended", motherboard)
            # write the updated image to disk, then update the nvram
            write_nvram_image(new_bytes, binary_file_name)
            update_nvram(binary_file_name)
        try:
            remove(binary_file_name)
        except Exception:
            pass
        run = popen("modprobe -r nvram")

        if new_bytes != bytes:
            # tell calling script to reboot the machine since we made a change
            sys.exit(2)
        else:
            # no change was made, so tell calling script to continue
            sys.exit(3)
    else: # means BIOS version should not use this script
        sys.exit(0)
else: # means script not applicable to this specific motherboard
    sys.exit(0)
