#!/usr/bin/python

from sys import exit, argv
from getopt import getopt, GetoptError
from os import system, popen, unlink
from os.path import exists
from string import join

debug = False

temp_file = 'temp.rom'
backup_file = 'backup.rom'
check_primary = '60:50:40:30:20:10'
check_aux = '60:50:40:30:20:11'
verify_position = 0
write = 0

# suppress FutureWarning message
#if sys.version_info >= (2, 3):
#    import warnings
#    warnings.filterwarnings("ignore", category=FutureWarning, append=1)

def usage():
    print "Usage: %s [-n] -b BIOS_FILENAME [-o OUT_FILE]\n" % argv[0]
    print "or: %s [-p PRIMARY_MAC] [-a AUX_MAC] [-s SPORT_ID]\n" % argv[0]
    exit(1)

def parse():
    global debug, mac_primary, mac_aux
    global write, verify_position, temp_file
    err = ''
    try: 
        options, ign = getopt(argv[1:], "b:a:p:s:wdvi:o:")
    except GetoptError, e:
        options = []
        err = e
    if len(options) == 0:
        if err == '':
            print 'Error: not enough arguments'
        else:
            print 'Error:', e
        usage()
        exit(1)

    bios_file = in_file = out_file = ''
    sport_id = -1
    mac_primary = mac_aux = ''
    
    for o,a in options:
        if o == '-d':
            debug = True
        elif o == '-b':
            bios_file = a
        elif o == '-p':
            mac_primary = a
        elif o == '-a':
            mac_aux = a
        elif o == '-i':
            in_file = a
        elif o == '-o':
            out_file = a
            temp_file = out_file
        elif o == '-s':
            sport_id = int(a)
        elif o == '-w':
            write = True
        elif o == '-v':
            verify_position = True

    return (bios_file, mac_primary, mac_aux, in_file, sport_id)

def parse_mac(mac_string):
    mac_hex = mac_string.split(':')
    mac_dec = []
    if len(mac_hex) != 6:
        print "Invalid MAC address %s." % mac_string,
        print "Expected something like AA:BB:CC:DD:EE:FF."
        exit(1)

    for octet in mac_hex:
        mac_dec.append(int(octet, 16))

    return mac_dec

def translate_sport_id_to_mac(sport_id):
    s1 = (sport_id >> 13) & 0x7f;
    s2 = (sport_id >> 5) & 0xff;
    s3 = (sport_id << 3) & 0xf8;
    mac_primary = "00:0E:B6:%02X:%02X:%02X" % (s1, s2, s3)
    s3 |= 0x01;
    mac_aux = "00:0E:B6:%02X:%02X:%02X" % (s1, s2, s3)
    if debug:
        print "Calculated mac addresses for %d ...." % sport_id
        print "pri:", mac_primary
        print "aux:", mac_aux
    return (mac_primary, mac_aux)

def copy_file(original_file, temp_file):
    if debug:
        print "Copying "+original_file+" to "+temp_file+"...",
    #should be checking return value here
    if system("cp -f %s %s" % (original_file, temp_file)):
        print "couldn't copy %s to %s" % (original_file, temp_file)
        exit(1)
    if debug:
        print "done"

def find_mac(adapter):
    if debug:
        print "Finding MAC address for %s..." % adapter,
    mac_address = open("/sys/class/net/%s/address" % adapter).read().strip()
    if debug:
        print "found", mac_address
    return mac_address

def patch_file_with_mac(filename, mac_address, file_position):
    if debug:
        print "Patching %s, writing %s to 0x%X..." % ( filename,
                                                       mac_address,
                                                       file_position),
    bytes = parse_mac(mac_address)
    # this is a bit awkward for reading the file into a buffer...
    fd = open(filename, 'rb')
    sbuf = fd.read() 
    fd.close()

    values = ''
    lbuf = list(sbuf)
    for b in bytes:
        lbuf[file_position] = chr(b)
        values += "%02X " % b
        file_position += 1

    sbuf = join(lbuf, '')
    # ...and writing the patched buffer back out to the file
    fd = open(filename, 'wb')
    fd.write(sbuf)
    fd.close();
    # done	
    if debug:
        print "...wrote", values

def find_block_in_file(filename, header_id):
    if debug:
        print "Locating %s block in %s" % (header_id, filename),
 	# reading the file into a buffer...
    fd = open(filename, 'rb')
    sbuf = fd.read()
    fd.close() 
    # ...finding the string...
    try:
        location = sbuf.index(header_id)
        if sbuf.find(header_id, location + 1) >= 0:
            print "\nWARNING: found multiple blocks with header: %s." \
                  % header_id
    except ValueError:
        print "\nCould not find block with header: %s" % header_id
        exit(1)
    if debug:
        print "...found 0x%X" % location
    return location;

def find_patch_addresses(filename):
    block_mac = find_block_in_file(filename, '$MA')	
    block_checksum = find_block_in_file(filename, '$BCS')
    offset_primary = block_mac + 4
    offset_aux = block_mac + 10
    offset_checksum = block_checksum + 4
    return offset_primary, offset_aux, offset_checksum

def get_mac_from_pos(fd, pos):
    fd.seek(pos)
    octet_list = []
    for i in xrange(6):
        val = "%02X" % ord(fd.read(1))
        octet_list.append(val)

    mac_address = join(octet_list, ':')
    return mac_address

def get_macs_from_file(filename):
    off_p, off_a, ign = find_patch_addresses(filename)
    fd = open(filename, 'rb')
    op = get_mac_from_pos(fd, off_p)
    oa = get_mac_from_pos(fd, off_a)
    return op, oa
 
def verify_mac_in_file(filename, check, file_position):
    if debug:
        print "Reading from %s, location 0x%X..." % (filename, file_position)
    fd = open(filename, 'rb')
    mac_address = get_mac_from_pos(fd, file_position)
    fd.close()
    if mac_address != check:
        print "\n...mac address %s does not match %s." % (mac_address,
                                                          check)
        if (verify_position):
            print "ABORTING"
            exit(1)
    else:
        if debug:
            print "read", mac_address
        
    return mac_address

def add_to_checksum(sum, offset, polarity, mac):
    for octet in mac:
        shift = (offset % 4) * 8
        offset += 1
        sum += (octet << shift) * polarity

    return sum

def patch_checksum(filename,
                   new_primary, new_aux,
                   old_primary, old_aux,
                   offset_checksum, offset_primary, offset_aux):
    file_position = offset_checksum
    sum = 0
    if debug:
        print "Patching %s checksum at 0x%X..." % (filename,file_position)
    # we are comparing the two patched areas, checksum the differences
    # and then add (subtract) the difference to the existing checksum 

    # let's start with reading the checksum
    old_checksum = ''
    checksum_bytes = []
    fd = open(filename, 'rb')
    fd.seek(file_position)
    count = 4
    while count:
        count -= 1
        value = ord(fd.read(1))
        checksum_bytes.append(value)
        old_checksum += "%02X " % value

    fd.close()
    if debug:
        print "...read", old_checksum

    # adding the mac addresses to the checksum
    p1 = parse_mac(new_primary)
    a1 = parse_mac(new_aux)
    p2 = parse_mac(old_primary)
    a2 = parse_mac(old_aux)

    sum += checksum_bytes[3]  << 24
    sum += checksum_bytes[2]  << 16
    sum += checksum_bytes[1]  << 8
    sum += checksum_bytes[0] << 0
    sum = ~sum 
    
    sum = add_to_checksum(sum, offset_primary, 1, p1)
    sum = add_to_checksum(sum, offset_primary, -1, p2)
    sum = add_to_checksum(sum, offset_aux, 1, a1)
    sum = add_to_checksum(sum, offset_aux, -1, a2)

    sum = ~sum
    checksum_bytes[0] = (sum >> 0) & 0xff
    checksum_bytes[1] = (sum >> 8) & 0xff 
    checksum_bytes[2] = (sum >> 16) & 0xff
    checksum_bytes[3] = (sum >> 24) & 0xff
	
    fd = open(filename, 'rb')
    sbuf = fd.read()
    fd.close()

    # ...patching the checksum...
    old_checksum = '';
    new_checksum = '';
    lbuf = list(sbuf) 
    for b in checksum_bytes:
        # checksum ignores carry, I hope
        old_value = ord(lbuf[file_position])
        old_checksum += " %02X" % old_value
        new_checksum += " %02X" % b
        lbuf[file_position] = chr(b)
        file_position += 1

    sbuf = join(lbuf, '')
    # ...and writing the patched buffer back out to the file
    fd = open(filename, 'wb')
    fd.write(sbuf)
    fd.close()
	
    if debug:
        print "...wrote new checksum", new_checksum

def backup_bios(backup_filename):
    if debug:
        print "Reading BIOS into %s..." % backup_filename
    if system("/usr/sbin/flashrom -r %s > /dev/null" % backup_filename):
        print "Could not back up BIOS"
        exit(1)
    if debug:
	print "...done"

def flash_bios(filename):
    if debug:
        print "Flashing BIOS now...", 
    if system("/usr/sbin/flashrom -w %s > /dev/null" % filename):
        print "Could not flash BIOS"
        exit(1)
    if debug:
	print "...done"


def update_bios_keep_mac(bios_file):
    skip_ver = False
    # backup existing bios
    backup_bios(backup_file)
    # make a working copy of the original file
    copy_file(bios_file, temp_file)
    # find patch addresses in file
    offset_primary, offset_aux, offset_checksum = find_patch_addresses(temp_file)
    mac_primary, mac_aux = get_macs_from_file(backup_file)

    if not skip_ver:
        # check if they match the current BIOS (they should if read)
        old_primary = verify_mac_in_file(temp_file, check_primary,
                                         offset_primary)
        old_aux = verify_mac_in_file(temp_file, check_aux, offset_aux)
        
	# patch the new addresses into the file
    patch_file_with_mac(temp_file, mac_primary, offset_primary)
    patch_file_with_mac(temp_file, mac_aux, offset_aux)
	
    # update the checksum
    patch_checksum(temp_file, mac_primary, mac_aux,
                   old_primary, old_aux, offset_checksum,
                   offset_primary, offset_aux)
    
    # invoke flash utility
    if write:
        flash_bios(temp_file);

def update_mac_keep_bios(mac_primary, mac_aux, in_file):
    # read current BIOS
    if in_file:
        if write:
            backup_bios(backup_file)
    else:
        backup_bios(backup_file)
        in_file = backup_file

    #evan: do we really need backup_bios?
    # make a working copy of the original file
    copy_file(in_file, temp_file);
    
    # find patch addresses in file
    offset_primary, offset_aux, offset_checksum = find_patch_addresses(temp_file); 
		 
    # check if it has the mac addresses at the right place
    if exists('/sys/class/net/aux'):
	check_aux = find_mac('aux')
        if exists('/sys/class/net/prihw'):
            check_primary = find_mac('prihw')
        else:
            check_primary = find_mac('primary')
        
        old_primary = verify_mac_in_file(temp_file, check_primary,
                                         offset_primary)
        old_aux = verify_mac_in_file(temp_file, check_aux, offset_aux)
    else:
        old_primary, old_aux = get_macs_from_file(temp_file)

    # patch mac addresses
    patch_file_with_mac(temp_file, mac_primary, offset_primary)
    patch_file_with_mac(temp_file, mac_aux, offset_aux)
        
    # update the checksum
    patch_checksum(temp_file, mac_primary, mac_aux,
                   old_primary, old_aux, offset_checksum,
                   offset_primary, offset_aux)
    
    # flash it
    if write:
        flash_bios(temp_file)

def main():
    if debug:
        print "Riverbed Flash Utility (sturgeon)"
    bios_file, mac_primary, mac_aux, in_file, sport_id = parse()
    if bios_file:
        # update bios using given file
        update_bios_keep_mac(bios_file)
    elif sport_id != -1: 
        # translate sport_id to mac   
        mac_primary, mac_aux = translate_sport_id_to_mac(sport_id)
        update_mac_keep_bios(mac_primary, mac_aux, in_file)
    elif mac_primary and mac_aux: 
        # update mac addresses  
        update_mac_keep_bios(mac_primary, mac_aux, in_file);
    else:
        print "Missing a required argument"
        usage()
        exit(1)
    if exists(backup_file):
        unlink(backup_file)
    if exists(temp_file):
        unlink(temp_file)

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception, (str) :
        print "Error:", str
        exit(1)
    else:
        exit(0)

        
