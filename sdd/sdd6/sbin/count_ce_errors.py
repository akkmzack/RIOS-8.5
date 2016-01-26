#!/usr/bin/python
import time
import os
import sys
import glob
import re
import doctest
from optparse import OptionParser

# With the argument "record" this script 
# checks "/sys/devices/blah" for a positive 
# ce_error counter and logs it.

# With the argument "day", "week", "month", "all", or "custom" 
# this script returns the number of ce_errors 
# that occured during that time range.

# each line in the ce_error_log file holds 
# three integers.  The seconds since the epoch and the 
# number of ce_errors recorded at that timestamp

# /var/opt/rbt/.ce_error_log is the default count file location
# customizeable with the "log" option.

def view_ce_errors(ce_error_log_location):
    # displays ce_error_count log in a nice way
    # with a header line but without all of the 
    # comments
    ce_record_file = open(ce_error_log_location, 'r')
    entries = ""
    for line in ce_record_file:
        matches = re.search("^(\d+)\s(\d+)\s(\d+)$", line)
        if matches:
            entries += line
    if entries != "":
        return ("timestamp_of_last_boot timestamp_error_was_discovered current_error_count_for_boot\n%s" % entries)
        
        
        
def record_ce_errors(ce_error_log_location, boot_timestamp, now_timestamp):
    # Logs any recorded ce_errors
    # Count stored in /sys/devices/blah is erased at reboot
    # so we preserve it if we see it.
    ce_total = 0
    target_files = glob.glob("/sys/devices/system/edac/mc/mc*/*/ce_count")
    for target in target_files:
        this_file = open(target)
        ce_total += int(this_file.readlines()[0])
        this_file.close()
    ce_record_file = open(ce_error_log_location, 'r+a')
    last_line_of_log = ce_record_file.readlines()[-1]
    last_line_of_log = last_line_of_log.strip()
    matches = re.search("^(\d+)\s(\d+)\s(\d+)$", last_line_of_log)
    if matches:
        (last_boot_timestamp, ignored, last_ce_count) = matches.groups()
        last_boot_timestamp = int(last_boot_timestamp)
        last_ce_count = int(last_ce_count)
        if (    ( ce_total > last_ce_count ) or
                (( ce_total > 0 ) and (boot_timestamp != last_boot_timestamp))
            ):    
            # l
            ce_record_file.write("%s %s %s\n" % (boot_timestamp, now_timestamp, ce_total ))
    elif ( ce_total > 0 ):
        # last line is a comment, only log a positive value then.
        ce_record_file.write("%s %s %s\n" % (boot_timestamp, now_timestamp, ce_total ))
    ce_record_file.close()


def fetch_ce_errors(ce_record_file , start_timestamp=0, end_timestamp=None):
    """
    Fetches and tallies the errors from the ce_error_log
    
    
    totally empty
    >>> fetch_ce_errors([] , 10)
    0

    blank line
    >>> fetch_ce_errors([" "] , 10)
    0

    comment
    >>> fetch_ce_errors(["# "] , 10)
    0

    indented comments 
    >>> fetch_ce_errors([" # "] , 10)
    0

    malformed line
    >>> fetch_ce_errors(["10 12 1","tyler","10 16 1","10 18 1 1"])
    1

    no start, no reboots, no additional errors
    >>> fetch_ce_errors(["10 12 1","10 14 1","10 16 1","10 18 1"], 0, 18)
    1

    no start, no reboots, incrementing errors
    >>> fetch_ce_errors(["10 12 1","10 14 2","10 16 3","10 18 4"], 0, 18)
    4

    no start or end, no reboots
    >>> fetch_ce_errors(["10 12 1","10 14 1","10 16 1","10 18 1"])
    1

    no start or end, 1 reboot
    >>> fetch_ce_errors(["10 12 1","10 14 1","16 18 1","16 20 1"])
    2

    no start, end before last item, 1 reboot
    >>> fetch_ce_errors(["10 12 1","10 14 1","16 18 1","16 20 1"], 0, 19)
    2
    
    Start earlier than all items, no end, 1 reboot
    >>> fetch_ce_errors(["10 12 1","10 14 2","16 18 4","16 20 5"] , 10)
    7
    
    Start earlier than all items, end before first item, 1 reboot    
    >>> fetch_ce_errors(["10 12 1","10 14 2","16 18 4","16 20 5"] , 10, 11)
    0
    
    Start after all items, no end, 1 reboot
    >>> fetch_ce_errors(["10 12 1","10 14 2","16 18 4","16 20 5"] , 25)
    0

    Start after all items, end after that, 1 reboot
    >>> fetch_ce_errors(["10 12 1","10 14 2","16 18 4","16 20 5"] , 25, 30)
    0
    
    Start after all items, end before first, 1 reboot, just in case.
    >>> fetch_ce_errors(["10 12 1","10 14 2","16 18 4","16 20 5"] , 25, 8)
    0

    Start after 3rd item, end before 2nd, 1 reboot, just in case.
    >>> fetch_ce_errors(["10 12 1","10 14 2","16 18 4","16 20 5"] , 19, 13)
    0

    Start before first item, no end, no reboots
    >>> fetch_ce_errors(["10 12 1","10 14 2","10 16 4","10 18 4"] , 10)
    4

    Start after first item, no end, no additional errors, no reboots
    >>> fetch_ce_errors(["10 12 1","10 14 1","10 16 1","10 18 1"] , 13)
    0
    
    Start on second item, no end, no additional errors, no reboots
    >>> fetch_ce_errors(["10 12 1","10 14 1","10 16 1","10 18 1"] , 14)
    0

    no start, no end, always reboot with 1 error
    >>> fetch_ce_errors(["10 11 1","12 13 1","14 15 1","16 17 1"], 9, 18)
    4

    start before two, end after three, always reboot
    >>> fetch_ce_errors(["10 11 1","12 13 1","14 15 1","16 17 1"], 12, 16)
    2
    
    select a single second in the middle, no reboots
    >>> fetch_ce_errors(["10 11 1","10 12 1","10 15 1","10 17 1"], 15, 15)
    0

    select a single second in the middle, always reboot
    >>> fetch_ce_errors(["10 11 1","12 13 1","14 15 1","16 17 1"], 15, 15)
    1
    
    select a single second in the middle NOT encompasing an error, always reboot
    >>> fetch_ce_errors(["10 11 1","13 14 1","16 17 1","19 20 1"], 15, 15)
    0

    select a single second in the middle, always reboot -- shuffled
    >>> fetch_ce_errors(["12 13 1", "10 11 1","16 17 1","14 15 1"], 15, 15)
    1
    
    start before two, end after three, always reboot -- shuffled
    >>> fetch_ce_errors(["10 11 1","12 13 1","14 15 1","16 17 1"], 12, 16)
    2
    
    Start on second item, no end, no additional errors, no reboots -- shuffled
    >>> fetch_ce_errors(["10 16 1","10 12 1","10 18 1","10 14 1"] , 14)
    0
    """
    
    entries = []
    
    for line in ce_record_file:
        line = line.strip()
        matches = re.search("^(\d+)\s(\d+)\s(\d+)$", line)
        if not matches:
            continue
        (event_boot_time, event_time, ce_since_boot) = matches.groups()
        event_boot_time = int(event_boot_time)
        event_time = int(event_time)
        ce_since_boot = int(ce_since_boot)
        entries.append( [ event_time, [ event_boot_time, ce_since_boot ] ] )
    
    entries.sort() # make sure the entries are sorted.
    
    total = 0
    boot_entries = {}
    prestart_boot_time = 0
    prestart_ce_count = 0
    
    for this_entry in entries:
        this_event_time= this_entry[0]
        this_boot_time = this_entry[1][0]
        this_ce_since_boot = this_entry[1][1]
        if (this_event_time < start_timestamp):
            # capture all of the events before the start time
            if this_boot_time > prestart_boot_time:
                # They're sorted, so this shouldn't matter but just in case... 
                # only save the largest (most recent) boot time.
                prestart_boot_time = this_boot_time
                prestart_ce_count = max(prestart_ce_count,this_ce_since_boot)
        else:
            # capture all events after the start time
            if (this_event_time <= end_timestamp) or (end_timestamp == None):
                # only continue if the event is also before the end time
                if this_boot_time in boot_entries:
                    # old boot -- check to see if the new one is larger
                    boot_entries[this_boot_time] = max(this_ce_since_boot,boot_entries[this_boot_time])
                else:
                    # it's a new boot
                    boot_entries[this_boot_time] =  this_ce_since_boot
    if prestart_boot_time in boot_entries:
        # look for the largest recorded prestart boot time 
        # in the ce_counts we care about.
        # log it to remove it from the total later
        total_before_start = prestart_ce_count
    else:
        total_before_start = 0

    for entry in boot_entries:
        # add 'em up
        total += boot_entries[entry]
    # spit it out,minus the previous ce_errors.
    return total - total_before_start
    # bleargh.


if __name__ == '__main__':
    doctest.testmod()
    
    now_timestamp = int(time.time()) # timestamp for now
    # timestamp for when the machine was last rebooted
    boot_timestamp = os.path.getatime("/var/opt/tms/.unexpected_shutdown")
    
    parser = OptionParser(usage= __file__ + 
    """\n    Records and calculates the number of ce_errors this appliance has experienced.""")
    parser.add_option('-l', '--look', 
                      action="store_true",
                      help="View current ce_error log file."
                      )
    parser.add_option('-r', '--record', 
                      action="store_true",
                      help="Record current ce_error count in ce_error log file."
                      )
    parser.add_option('-f', '--file', 
                      action="store", 
                      help="Specify location of ce_error log file. '/var/opt/rbt/.ce_error_log' is the default location."
                      )
    parser.add_option('-a', '--all', 
                      action="store_true", 
                      help="Return the number of ce_errors recorded during the lifetime of the appliance"
                      )
    parser.add_option('-d', '--day', 
                      action="store_true", 
                      help="Return the number of ce_errors recorded during the last 24 hours"
                      )
    parser.add_option('-w', '--week', 
                      action="store_true", 
                      help="Return the number of ce_errors recorded during the last 7 days"
                      )
    parser.add_option('-m', '--month', 
                      action="store_true", 
                      help="Return the number of ce_errors recorded during the last 30 days"
                      )
    parser.add_option('-c', '--custom', 
                      action="store_true", 
                      help="Return the number of ce_errors recorded during a custom interval. "+
                           "Use '-s' and '-e' to define the interval."
                      )
    parser.add_option('-s', '--start', 
                      action="store", default=None,
                      help="Custom interval start time. (In seconds since epoch)"
                      )
    parser.add_option('-e', '--end', 
                      action="store", default=None, 
                      help="Custom interval end time. (In seconds since epoch)"
                      )
    (options, args) = parser.parse_args()
    if (options.start or options.end) and not options.custom:
        parser.error("start time or end time not valid without selecting 'custom' option")    
    if options.custom:
        if options.start == None and options.end == None:
            parser.error("A start time OR end time must be specified.")
        if options.start:
            try:
                options.start = int(options.start)
            except ValueError:
                parser.error("start time must be a number")
        if options.end:
            try:
                options.end = int(options.end)
            except ValueError:
                parser.error("end time must be a number")
        if (options.start and options.end) and (options.start > options.end):
            parser.error("start time must come before than end time")
            
    if options.file:
        ce_error_log = options.file
    else:
        ce_error_log = "/var/opt/rbt/.ce_error_log"

    # if there is no ce_error log, create it.
    if ( not os.path.exists(ce_error_log) ):
        ce_record_file = open(ce_error_log, 'w')
        ce_record_file.write("#\n")
        ce_record_file.write("# This file generated by: %s\n" % os.path.abspath( __file__ ))
        ce_record_file.write("# This file created on: %s\n" % now_timestamp)
        ce_record_file.write("#\n")
        ce_record_file.write("# Do not edit\n")
        ce_record_file.write("#\n")
        ce_record_file.write("# Keeps track of number of ce_errors discovered on a machine\n")
        ce_record_file.write("# per /sys/devices/system/edac/mc/mc*/*/ce_count\n")
        ce_record_file.write("# Updated daily.\n")
        ce_record_file.write("# Columns are:\n")
        ce_record_file.write("#     timestamp_of_last_boot, timestamp_error_was_discovered, current_error_count_for_boot\n")
        ce_record_file.write("#\n")
        ce_record_file.close()
        if ( not os.path.exists(ce_error_log) ):
            parser.error("Aborting, Unable to create %s" % ce_error_log)    

    if options.record:
        record_ce_errors(ce_error_log, boot_timestamp, now_timestamp)
    elif options.look:
        print view_ce_errors(ce_error_log)
    elif options.all:
        ce_record_file = open(ce_error_log, 'r')
        print fetch_ce_errors(ce_record_file)
        ce_record_file.close()
    elif options.day:
        ce_record_file = open(ce_error_log, 'r')
        print fetch_ce_errors(ce_record_file, now_timestamp - 86400 )
        ce_record_file.close()
    elif options.week:
        ce_record_file = open(ce_error_log, 'r')
        print fetch_ce_errors(ce_record_file, now_timestamp - 604800 )
        ce_record_file.close()
    elif options.month:
        ce_record_file = open(ce_error_log, 'r')
        print fetch_ce_errors(ce_record_file, now_timestamp - 2592000 )
        ce_record_file.close()
    elif options.custom:
        ce_record_file = open(ce_error_log, 'r')
        print fetch_ce_errors(ce_record_file, options.start, options.end)
        ce_record_file.close()
    else:
        parser.error("No action selected.")
