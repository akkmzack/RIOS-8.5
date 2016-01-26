# -*- python -*-
#
# (C) Copyright 2003-2009 Riverbed Technology, Inc.  
# All rights reserved. Confidential.
#
"""IOtrace Parser"""

# Look at the main() function at the end of the file for usage

#------------------------------------------------------------------------------
import sys
import os
from struct import *
import interval
from interval import *

iot_packet_size = 34
class PacketType:
    # iSCSI
    IOT_ISCSI_READ              = 1
    IOT_ISCSI_READ_RESPONSE     = 2
    IOT_ISCSI_WRITE             = 3
    IOT_ISCSI_WRITE_RESPONSE    = 4
    # RDisk
    IOT_RDISK_CMD_READ_REQ          = 5
    IOT_RDISK_CMD_READ_REP          = 6
    IOT_RDISK_CMD_READ_ERR          = 7
    IOT_RDISK_CMD_WRIT_DAT          = 8
    IOT_RDISK_CMD_WRIT_ACK          = 9
    IOT_RDISK_CMD_WRIT_ERR          = 10
    IOT_RDISK_CMD_STOR_DAT          = 11
    IOT_RDISK_CMD_FB_READ           = 12
    IOT_RDISK_CMD_STOR_QUERY        = 13
    IOT_RDISK_CMD_STOR_NACK         = 14
    IOT_RDISK_CMD_COMMIT_SNAP_REQ   = 15
    IOT_RDISK_CMD_COMMIT_SNAP_ACK   = 16
    IOT_RDISK_CMD_COMMIT_SNAP_ERR   = 17
    IOT_RDISK_CMD_REMOVE_LUN_REQ    = 18
    IOT_RDISK_CMD_REMOVE_LUN_ACK    = 19
    IOT_RDISK_CMD_REMOVE_LUN_ERR    = 20
    IOT_RDISK_CMD_TUNNEL_REQ        = 21
    IOT_RDISK_CMD_PREPOP_DAT        = 22
    IOT_RDISK_CMD_PREPOP_ACK        = 23
    IOT_RDISK_CMD_STOR_DATA_ACK     = 24
    IOT_RDISK_CMD_LSN_COMMIT_HANDLE = 25
    # String array for to_string.
    PacketType_strings = []
    PacketType_strings.append("Invalid PacketType")
    PacketType_strings.append("IOT_ISCSI_READ")
    PacketType_strings.append("IOT_ISCSI_READ_RESPONSE")
    PacketType_strings.append("IOT_ISCSI_WRITE")
    PacketType_strings.append("IOT_ISCSI_WRITE_RESPONSE")
    PacketType_strings.append("IOT_RDISK_CMD_READ_REQ")
    PacketType_strings.append("IOT_RDISK_CMD_READ_REP")
    PacketType_strings.append("IOT_RDISK_CMD_READ_ERR")
    PacketType_strings.append("IOT_RDISK_CMD_WRIT_DAT")
    PacketType_strings.append("IOT_RDISK_CMD_WRIT_ACK")
    PacketType_strings.append("IOT_RDISK_CMD_WRIT_ERR")
    PacketType_strings.append("IOT_RDISK_CMD_STOR_DAT")
    PacketType_strings.append("IOT_RDISK_CMD_FB_READ")
    PacketType_strings.append("IOT_RDISK_CMD_STOR_QUERY")
    PacketType_strings.append("IOT_RDISK_CMD_STOR_NACK")
    PacketType_strings.append("IOT_RDISK_CMD_COMMIT_SNAP_REQ")
    PacketType_strings.append("IOT_RDISK_CMD_COMMIT_SNAP_ACK")
    PacketType_strings.append("IOT_RDISK_CMD_COMMIT_SNAP_ERR")
    PacketType_strings.append("IOT_RDISK_CMD_REMOVE_LUN_REQ")
    PacketType_strings.append("IOT_RDISK_CMD_REMOVE_LUN_ACK")
    PacketType_strings.append("IOT_RDISK_CMD_REMOVE_LUN_ERR")
    PacketType_strings.append("IOT_RDISK_CMD_TUNNEL_REQ")
    PacketType_strings.append("IOT_RDISK_CMD_PREPOP_DAT")
    PacketType_strings.append("IOT_RDISK_CMD_PREPOP_ACK")
    PacketType_strings.append("IOT_RDISK_CMD_STOR_DATA_ACK")
    PacketType_strings.append("IOT_RDISK_CMD_LSN_COMMIT_HANDLE")

def PacketType_to_string(packet_type):
    if (packet_type < 1) or (packet_type >= len(PacketType.PacketType_strings)):
        return PacketType.PacketType_strings[0]
    else:
        return PacketType.PacketType_strings[packet_type]

# helper function
def get_number(buf):
    length = len(buf)
    x = buf[0:length]
    if length == 1:
        return ord(x)
    elif length == 2:
        return unpack('<H', x)[0]
    elif length == 4:
        return unpack('<L', x)[0]
    elif length == 8:
        return unpack('<Q', x)[0]
    print " CREATE HAVOC!  get_number got a buffer which is neither of 1, 2, 4, 8 length"
    sys.exit()
    return 0

# Read a C string from a file.
# Return: number bytes read, string
def read_string(file):
    result = ""
    num_bytes = 0
    character = file.read(1)
    while character != "":
        num_bytes += 1
        if character[0] == '\0':
            break
        result += character
        character = file.read(1)
    return num_bytes, result

# Each packet in an iotrace has the following structure
class MyPacket(Interval):
    def __init__(self):
        Interval.__init__(self, 0, 0) # lun offset and count (in terms of lba)
        self.time_ = 0        # time since begining of trace - used to calc inter arrival time/response time
        self.serial_ = ""     # LUN serial
        self.lunid_ = 0       # lunid
        self.id_ = 0          # used for matching req/resp
        self.type_ = 0        # PacketType
        self.has_data_ = 0    # DONT CARE for now since we dont care for the data
        
    def decode(self, buf):
        self.time_ = get_number(buf[0:8])
        self.lunid_ = get_number(buf[8:16])
        self.id_ = get_number(buf[16:20])
        self.type_ = get_number(buf[20:21])
        self.has_data_ = get_number(buf[21:22])
        self.start = get_number(buf[22:30])
        self.num = get_number(buf[30:34])

    # Print function.
    def __str__(self):
        return "MyPacket: time %s, serial %s, lunid %s, id %s, type %s=%s, has_data %s, offset %s, count %s" % (
            str(self.time_),
            str(self.serial_),
            str(self.lunid_),
            str(self.id_),
            str(self.type_),
            PacketType_to_string(self.type_),
            str(self.has_data_),
            str(self.start),
            str(self.num) )

# This is a class to create a parser instance for a given iotrace (ie trace_file)
class IOTParser:
    def __init__(self, trace_file):
        self.curr_offset_ = 0
        self.file_size_ = os.path.getsize(trace_file)
        self.file_ = open(trace_file)

    # Print function.
    def __str__(self):
        return "IOTParser: file open: %s, file_size_ %d, curr_offset_ %s" % (
            str(not self.file_.closed), self.file_size_, self.curr_offset_ )
        
    def get_next_packet(self):
        if self.curr_offset_ >= self.file_size_:
            return MyPacket() # We have reached end of file
        self.file_.seek(self.curr_offset_)
        buffer = self.file_.read(iot_packet_size)
        self.curr_offset_ += iot_packet_size
        pkt = MyPacket()
        pkt.decode(buffer)
        read_count, pkt.serial_ = read_string(self.file_)
        self.curr_offset_ += read_count
        return pkt

# ------------ the code below is just an example of how to use the parser -----------
def main():
    trace_file_name = raw_input("enter iotrace filepath : ")
    parser = IOTParser(trace_file_name) 
    p = parser.get_next_packet()
    while p.time_ > 0: # this indicates end of trace when the condition is false
        if p.type_ == PacketType.IOT_ISCSI_READ:
            print "ISCSI READ req with offset : %lx  length: %d time : %ld lunid %lx" %(p.start, p.num, p.time_, p.lunid_)
        elif p.type_ == PacketType.IOT_ISCSI_WRITE:
            print "ISCSI WRITE req with offset : %lx  length: %d time : %ld lunid %lx" %(p.start, p.num, p.time_, p.lunid_)
        p = parser.get_next_packet()

if __name__ == "__main__":
    main()
