#!/usr/bin/env python
# -*- python -*-
#
# (C) Copyright 2003-2009 Riverbed Technology, Inc.  
# All rights reserved. Confidential.
#
"""io_analyzer - I/O analyzer"""

#------------------------------------------------------------------------------
import sys
from optparse import OptionParser
import os
from IOTParser import *
from datetime import datetime

#------------------------------------------------------------------------------
_request_dict = {}
def _get_request_handle(req_id):
    global _request_dict
    if req_id in _request_dict:
        return _request_dict[req_id]
    print "Response ignored:" \
          " Did not find corresponsing request for id: %ld" % req_id
    return MyPacket()

#------------------------------------------------------------------------------
def io_analyzer(logfile, verbose):
    global _request_dict
    total_read_ops = 0
    total_write_ops = 0
    total_blocks_read = 0
    total_blocks_write = 0

    read_count = 1
    write_count = 1
    max_parallel_reads = 1
    max_parallel_writes = 1

    
    io_parser = IOTParser(logfile)
    f_packet = io_parser.get_next_packet()
    
    start_time = f_packet.time_
    processing_delay = 0

    #Read/write vars
    last_read_type = 1
    last_write_type = 1
    first_read_time = start_time
    first_write_time = start_time
    prev_read_time = start_time
    prev_write_time = start_time
    read_processing_delay = 0
    write_processing_delay = 0
    total_read_resp_time = 0
    total_write_resp_time = 0
    max_p_read_blks = 0
    max_p_write_blks = 0
    o_read_blks = 0
    o_write_blks = 0
    
    p = f_packet
    while p.time_ > 0:
        if p.type_ == PacketType.IOT_ISCSI_READ:
            total_read_ops += 1
            # first read
            if total_read_ops == 1:
                first_read_time = p.time_
                prev_read_time = p.time_
                
            if last_read_type == 0:
                read_count += 1
            o_read_blks += p.num
            last_read_type = 0
            if verbose:
                print "Read offset: %lx length: %d time %ld" \
                      " serial='%s' lunid %lx inter-arrival delay = %ld ms" % (
                    p.start, p.num, p.time_, p.serial_, p.lunid_,
                    (p.time_ - prev_read_time)/1000)
            total_blocks_read += p.num
            # register request 
            _request_dict[p.id_] = p
            read_processing_delay  += p.time_ - prev_read_time
            prev_read_time = p.time_

            
        elif p.type_ == PacketType.IOT_ISCSI_READ_RESPONSE:
            if read_count > 1:
                if verbose:
                    print " multiple parallel read count : %d blks : %d " % (
                        read_count, o_read_blks)
                if read_count > max_parallel_reads:
                    max_parallel_reads = read_count
                    max_p_read_blks = o_read_blks
            read_count = 1
            o_read_blks = 0
            last_read_type = 1
            req = _get_request_handle(p.id_)
            if req.time_ == 0:
                p = io_parser.get_next_packet()
                continue

            resp_time = p.time_ - req.time_
            if verbose:
                print "    Read Response offset: %lx length: %d" \
                      " resp time %ld ms, serial '%s' lunid %lx " % (
                    req.start, req.num,
                    resp_time/1000, req.serial_, req.lunid_)
            total_read_resp_time += resp_time
            
            prev_read_time = p.time_
            del _request_dict[p.id_]
            
        elif p.type_ == PacketType.IOT_ISCSI_WRITE:
            total_write_ops += 1
            # first write
            if total_write_ops == 1:
                first_write_time = p.time_
                prev_write_time = p.time_
            if last_write_type == 0:
                write_count += 1
            o_write_blks += p.num
            last_write_type = 0
            if verbose:
                print "Write offset: %lx length: %d time %ld" \
                      " serial='%s' lunid %lx inter-arrival delay = %ld ms" % (
                    p.start, p.num, p.time_, p.serial_, p.lunid_,
                    (p.time_ - prev_write_time)/1000)
            total_blocks_write += p.num
            # register request 
            _request_dict[p.id_] = p
            write_processing_delay  += p.time_ - prev_write_time            
            prev_write_time = p.time_

            
        elif p.type_ == PacketType.IOT_ISCSI_WRITE_RESPONSE:
            if write_count > 1:
                if verbose:
                    print " multiple parallel write count : %d  blks : %d" % (
                        write_count, o_write_blks)
                if write_count > max_parallel_writes:
                    max_parallel_writes = write_count
                    max_p_write_blks = o_write_blks
            write_count = 1
            o_write_blks = 0
            last_write_type = 1

            req = _get_request_handle(p.id_)
            if req.time_ == 0:
                p = io_parser.get_next_packet()
                continue

            resp_time = p.time_ - req.time_
            if verbose:
                print "    Write Response offset: %lx length: %d" \
                      " resp time  %ld ms, serial '%s' lunid %lx " % (
                    req.start, req.num,
                    resp_time/1000, req.serial_, req.lunid_)
            total_write_resp_time += resp_time

            prev_write_time = p.time_
            del _request_dict[p.id_]

        p = io_parser.get_next_packet()

    if not verbose:
        print "\n"
        print "NOTE : For details of individual requests use verbose mode, i.e. -v"
    print "\n"
    print " STATS Read : "
    print " total_read_ops : %d  total_read_blocks : %d " %(total_read_ops, total_blocks_read)
    if total_blocks_read > 0:
        print " avg_read_size                : %d blks" % (total_blocks_read/total_read_ops)
        print " max_parallel_reads           : %d " % (max_parallel_reads)
        print " max_parallel_read_blks       : %d " % (max_p_read_blks)
        print " total read time              : %ld ms"  %((prev_read_time - first_read_time)/1000)
        r_iad_pct = (float)(read_processing_delay)/(prev_read_time - first_read_time)*100    
        print " read inter arrival delay     : %ld ms   percentage : %f " %((read_processing_delay/1000), r_iad_pct)
        print " avg inter arrival delay      : %ld ms" %((read_processing_delay/total_read_ops)/1000)        
        tput_time_us = (prev_read_time - first_read_time) - read_processing_delay
        r_tput_time_us = tput_time_us
        print " total read resp time         : %ld ms   percentage : %f"  %(tput_time_us/1000, 100 - r_iad_pct)
        print " avg read resp time           : %ld ms"  %((tput_time_us/total_read_ops)/1000)

        if tput_time_us > 0:
            print " Raw read tput is %f Mbps" %(8*((float)(total_blocks_read*512)/(tput_time_us)))
            print " Overall perceived read tput is %f Mbps" %(8*((float)(total_blocks_read*512)/(prev_read_time - first_read_time)))      
    
        if (r_iad_pct > 20):
            print "\n \n If this is a client side(edge) trace, CLIENT MAY BE TOO SLOW IN ISSUING REQUESTS"
        elif (((r_tput_time_us/total_read_ops)/1000) > 15) :
            print "\n \n If this is a server side(dc) trace, BACKEND MAY BE TOO SLOW"
    print "\n \n"

    print " STATS Write : "
    print " total_write_ops : %d  total_write_blocks : %d " %(total_write_ops, total_blocks_write)
    if total_blocks_write > 0:
        print " avg_write_size                : %d blks" % (total_blocks_write/total_write_ops)
        print " max_parallel_writes           : %d " % (max_parallel_writes)
        print " max_parallel_write_blks       : %d " % (max_p_write_blks)
        print " total write time              : %ld ms"  %((prev_write_time - first_write_time)/1000)
        w_iad_pct = (float)(write_processing_delay)/(prev_write_time - first_write_time)*100
        print " write inter arrival delay     : %ld ms   percentage : %f "  %(write_processing_delay/1000, w_iad_pct)
        print " avg inter arrival delay       : %ld ms" %((write_processing_delay/total_write_ops)/1000) 
        w_tput_time_us = (prev_write_time - first_write_time) - write_processing_delay
        print " total write resp time         : %ld ms   percentage : %f"  %(w_tput_time_us/1000, 100 - w_iad_pct)
        print " avg write resp time           : %ld ms"  %((w_tput_time_us/total_write_ops)/1000)
        
        if w_tput_time_us > 0:
            print " Raw write tput is %f Mbps" %(8*((float)(total_blocks_write*512)/(w_tput_time_us)))  
            print " Overall perceived write tput is %f Mbps" %(8*((float)(total_blocks_write*512)/(prev_write_time - first_write_time)))
        if (w_iad_pct > 20):
            print "\n \n If this is a client side(edge) trace, CLIENT MAY BE TOO SLOW IN ISSUING REQUESTS \n \n"
        elif (((w_tput_time_us/total_write_ops)/1000) > 15) :
            print "\n \nIf this is a server side(dc) trace, BACKEND MAY BE TOO SLOW\n \n"

#------------------------------------------------------------------------------
def _io_analyzer_main():
    usage = "usage: python %prog [options] arg"
    parser = OptionParser(usage)
    parser.add_option("-f", "--log_file", dest="logfile",
                      help="iotrace collected from EDGE/CORE/standalone target ")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
                      help="Detailed analysis showing each request.")
    parser.add_option("-q", "--quiet", action="store_false", dest="verbose",
                      help="Basic analysis showing only the summaries.")
    
    (options, args) = parser.parse_args()

    if options.logfile == None:
        parser.error(" Error: iotrace log file not specified.")

    io_analyzer(options.logfile, options.verbose)

#------------------------------------------------------------------------------
if __name__ == "__main__":
    _io_analyzer_main()
