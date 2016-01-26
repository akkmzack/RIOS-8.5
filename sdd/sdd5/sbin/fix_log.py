#! /usr/bin/env python

import sys, os, fnmatch

# --------------------------------------------------------------------------------
# Useful stuff for debugging
# Redirecting stdout to a file
# Dont forget to uncomment two more lines at the end of this script
# --------------------------------------------------------------------------------
#saveout = sys.stdout
#fstdout = open('/var/foo.out', 'a+')
#sys.stdout = fstdout

# --------------------------------------------------------------------------------
# All Globals go here
# --------------------------------------------------------------------------------

# Path of the logging files
LOGPATH = "/var/log/rcu"

# The format of the samba log is as follows: 
# TIME|USER@IP|SHARE_NAME|ACTION|SUCCESS|FILE(or share if connect)|ACTION_SPECIFIC_STUFF
# Defining following variables for ease of indexing
TIME_F = 0;
ACTION_F = 3;
SUCCESS_F = 4;
FILE_F = 5;
REN_F = 6;

# The format of frequently used 'operation' list is:
# [action, paramas, time]
# Following are the indexes for it
ACTION_O = 0
PARAMS_O = 1
TIME_O = 2

#Introduce time fudge factor to make the timstamps on renam_to ops
#very close to their parent names, but not the same
BLINK = 0.000001

# Command line arguments
clean_old_log = 0
btime = 0
etime = 0
outputpath = ''
logpath = ''
share = ''
sharepath = ''

#All Shares: Currently working with only one share
shares = []

#Dictionary of all entries from log files of all shares: indexed by given share
entries = {}

#XXX: All the renames that occur, it is indexed by new name and has info on the old name.
#XXX/PM: This will faily horribly if we need to do multiple share parsing again,
#it will be to be fixed to be present on a per-share basis!
ren_from = {}

# Bug 9074 -- handle infinite looping in find_first_ren()
MAX_FIND_FIRST_REN = 10;
INVALID_RENAME_PATH = "__RBT_INVALID_RENAME_PATH__"


# --------------------------------------------------------------------------------
# print_args: (Only for debugging purpose) to print all command line arguments
# 	      parsed
# --------------------------------------------------------------------------------
def print_args(clean_old_log, btime, etime, outputpath, logpath, share, sharepath):
    print "clean old log = ", clean_old_log
    print "btime = ", btime
    print "etime = ", etime
    print "outputpath = ", outputpath
    print "logpath = ", logpath
    print "share = ", share
    print "sharepath = ", sharepath
    return

# --------------------------------------------------------------------------------
# get_cmd_args: parse all command line arguments provided to the script
# 		and returns it to the caller. Provides usage help if needed
# --------------------------------------------------------------------------------
def get_cmd_args(argv):
    global clean_old_log
    global btime
    global etime
    global outputpath 
    global logpath
    global share
    global sharepath

    from time import time
    current_time = time()

    from optparse import OptionParser

    usage = "%prog [options] -s <share> -l <sharepath>"
    parser = OptionParser(usage)
    parser.add_option("-b", "--btime", 
		      type="float",
		      default=0.0,
		      dest="btime", 
		      help="log begin time")
    parser.add_option("-e", "--etime",
		      type="float",
		      default=current_time,
		      dest="etime",
		      help="log end time")
    parser.add_option("-l", "--sharepath",
		      dest="sharepath",
		      help="path to share")
    parser.add_option("-s", "--share",
		      dest="share",
		      help="share whose log files should be parsed")
    parser.add_option("-p", "--logpath",
		      dest="logpath",
		      help="path to log files")
    parser.add_option("-o", "--opath",
		      dest="outputpath",
		      help="path for output files")
    parser.add_option("-c", "--clean",
		      default=False,
		      action="store_true",
		      dest="clean_old_log",
		      help="delete any old .rot files after the script generates output")

    (options, args) = parser.parse_args(argv)

    clean_old_log = options.clean_old_log
    btime = options.btime
    etime = options.etime
    outputpath = options.outputpath
    logpath = options.logpath
    share = options.share
    sharepath = options.sharepath

    #If not output path is given, asssume it as current directory
    if (outputpath == None):
	outputpath = "./"

    #share name and sharepath must be provided
    if (share == None or sharepath == None):
	parser.error("share or sharepath is empty")

#    print_args(clean_old_log, btime, etime, outputpath, logpath, share, sharepath)
    return 

#delete_logs

################################################################################
########################    START: Debugging Functions     #####################

#dump_complete_log

# --------------------------------------------------------------------------------
#  Print all dictionary values
# --------------------------------------------------------------------------------
def print_dict(str, dictionary):
    print str
    for key in sorted(dictionary.keys()):
	value = dictionary[key]
	print key, ':', "|".join(value)
    return


# --------------------------------------------------------------------------------
#  Print all actions associated with a file from dictionary 'files'
#  sort order: default
#  Puts everything in outputpath/logfile_name file
# --------------------------------------------------------------------------------
def print_file_actions(files, logfile_name):
    logfile_name = outputpath + "/" + logfile_name
    logfh = open(logfile_name, 'w')

    for key in sorted(files.keys()):
	value = files[key]
	print >>logfh, "----------------------------------------"
	print >>logfh, "File: %s" % key
	operation_list = value
	for i in range(len(operation_list)):
	    operation = operation_list[i]
	    print >>logfh, "action: %s params: %s" % (operation[ACTION_O], operation[PARAMS_O])
    logfh.close()


# --------------------------------------------------------------------------------
#  Print all actions associated with a file from dictionary 'files'
#  sort order: depth_first
#  Puts everything in outputpath/logfile_name file
# --------------------------------------------------------------------------------
def print_file_actions_2(files,logfile_name):
    logfile_name = outputpath + "/" + logfile_name
    logfh = open(logfile_name, 'w')

    for key in sorted(files.keys(), depth_first):
	value = files[key]
	print >>logfh, "----------------------------------------"
	print >>logfh, "File: %s" % key
	operation_list = value
	for i in range(len(operation_list)):
	    operation = operation_list[i]
	    print >>logfh, "action: %s params: %s" % (operation[ACTION_O], operation[PARAMS_O])
    logfh.close()

########################      END: Debugging Functions     #####################
################################################################################

# --------------------------------------------------------------------------------
# numerically(x,y): Sort compare function to do numeric comparison
# --------------------------------------------------------------------------------
def numerically(x,y):
    if (x < y):
	return -1
    elif (x > y):
	return 1
    else:
	return 0

# --------------------------------------------------------------------------------
# descending(x,y): Sort compare function to sort descending
# --------------------------------------------------------------------------------
def descending(x,y):
    if (y < x):
	return -1
    elif (y > x):
	return 1
    else:
	return 0

# --------------------------------------------------------------------------------
# depth_first(x,y): Sort compare function to compare "file paths" in depth first
# way
# --------------------------------------------------------------------------------
def depth_first(x,y):
    #calculating the depth of path
    x_count=x.count('/')
    y_count=y.count('/')

    #first compare path's depth
    if (y_count < x_count):
	return -1
    elif (y_count > x_count):
	return 1
    #if equal, compare alphabetically
    elif (x.lower() < y.lower()):
	return -1
    elif (x.lower() > y.lower()):
	return 1
    else:
	return 0

# --------------------------------------------------------------------------------
# delete_logs(share): Clean up any log files that have either been rotated, or
#                     are no longer in use, and have times that are older than
#                     the specified time
# --------------------------------------------------------------------------------
def delete_logs(dtime, share):
    print "Cleaning old logs\n"
   
    # Form a list of all the logs that could be rotated.
    # Bug 7740: We now grab all files present (rbt_audit.*), instead of
    # just .rot files -- thats because we will do a check to figure out which
    # logs are in use down below

    # Bug 3417: One dir per share so that's why the 'share' in path below need
    # to use readdir since ls or find in a shell context can break if thre are
    # too many files

    dir = logpath + "/" + share

    # XXX: No need to create backup directory

    # For loop: for each log file in 'dir'
    pattern = "rbt_audit." + share + ".*"
    all_file_list = os.listdir(dir)
    file_list = fnmatch.filter(all_file_list, pattern)

    for tmp_file in file_list:
	log = logpath + "/" + share + "/" + tmp_file

	# For each log file, figure out the pid, and make sure that there is
	# nothing else running with that pid
	try:
	    fields = log.split('.')
	except ValueError:
	    print "split error\n"
	    sys.exit(-1)

	pid = fields[2]   #always the 3rd entry	

	# XXX: need to delete the file even if process created them is still
	#      running
	# Skip this log if samba is running with that pid -- we will get it next
	# time around
	proc_path = "/proc/" + pid
	running = os.path.exists(proc_path)

	if (running):
	    print "Keeping file %s because smbd is running\n" % log
	    continue

	# Get last time in the log
	fo = open(log, 'r')
	line_list = fo.readlines()
	# Equivalent of perl's chomp
	line_list = [l.rstrip('\n') for l in line_list]
	fo.close()
	last_entry = []
	last_ts = 0
	if (len(line_list) > 0):
	    last_line = line_list[len(line_list) - 1]
	    last_entry = last_line.split("|")
	    last_ts = last_entry[TIME_F]
	    last_ts = float(last_ts)

	# If last_ts is 0, delete the log OR
	# If last_ts is less than dtime, delete the log
	if ((not last_ts) or (last_ts < dtime)):
	    print "DELETING: FILE: %s last_ts: %f dtime: %f" % (log, last_ts, dtime)
	    # delete log
	    os.remove(log)
	else:
	    print "KEEPING: FILE: %s last_ts: %f dtime: %f" % (log, last_ts, dtime)
    return



# --------------------------------------------------------------------------------
# find_first_ren: Find the 1st directory in a rename list chain
#
# --------------------------------------------------------------------------------
def find_first_ren(ren_to, ren_time):
    # Bug 9074: This is to avoid directories that were renamed to each other
    #           multiple times between runs of this script. Current heuristic 
    #           is that if the rename chain is too long, we will NOT try to do 
    #           a rename, and instead handle this rename in the way we do files 
    #		return INVALID_RENAME_PATH 

    count = 0

    fst_name = ren_to
    tmp_name = ren_to

    done = 0
    #Do if 'tmp_name' key exist in 'ren_from' dictionary
    while(tmp_name in ren_from):
	my_dict = ren_from[tmp_name]
	if (count > MAX_FIND_FIRST_REN):
	    return INVALID_RENAME_PATH
	count += 1

	#get the last entry in the list that occured before the specified time
	for time in sorted(my_dict.keys(), descending):
	    old_name = my_dict[time]
	    if (time < ren_time):
		#if the name is New Folder then we're done
		path = old_name
		if (path == "New Folder"):
		    #Go out of outer while loop
		    done = 1
		    break
		else:
		    tmp_name = path
		    #Go to next iteration of outer for loop
		    break
	#end of inner for
	if (done):
	    break
    #end of while loop
    return tmp_name


# --------------------------------------------------------------------------------
# pass_4: Print out a list of any files that changed, and those that were deleted.
#         changed implies either previously existed, or newly created.
#         also, note that we may say certain files were deleted that don't 
#         exist, because they were created during the run and then unlinked. 
#	  This is not a bug!
# --------------------------------------------------------------------------------
def pass_4(files, outfh):
    final_output = {}

    for file in sorted(files.keys(), depth_first):
	value = files[file]
#	print file, value
	operation_list = value
	size = len(operation_list)

	#Skip files with no entries
	if (size == 0):
	    continue

	last_operation = operation_list[size-1]
	last_action = last_operation[ACTION_O]
	last_time = last_operation[TIME_O]

	if (last_action == "rename" or
	    last_action == "rmdir" or
	    last_action == "unlink"):
	    if (file not in final_output):
		str = "DELETE: " + file
		final_output[file] = str
	else:
	    #If its a rename and we know that the file is a dir, then we find
	    #1st dir in the rename chain
	    #XXX: We need to improve this later for fixing rename bugs, for now
	    #     we are doing what perl script does
	    full_path = sharepath + "/" + file
	    orig_file = file

	    if (last_action == "rename_to" and os.path.isdir(full_path)):
		first_file = find_first_ren(file, last_time)

		# Bug 9074: Error case, if we get back INVALID_RENAME_PATH 
		#	    then its likely we would have ended up in an 
		#	    infinite loop, so instead note that the file 
		#	    has "CHANGED"
		if (first_file == INVALID_RENAME_PATH):
		    str = "CHANGED_DATA: " + file
		    final_output[orig_file] = str
		    continue

		# Bug 3723: We should also handle renames from New Folder to
		# 	    something else in this case, find_first_ren returns
		# 	    the file you passed as argument to function
		if (first_file == file):
		    str = "RENAME_OLD: New FOlder\nRENAME_NEW: " + file
		    final_output[file] = str
		    final_output["New Folder"] = ""
		else:
		    str = "RENAME_OLD: " + first_file + "\nRENAME_NEW: " + file
		    final_output[file] = str
		    final_output[first_file] = ""
	    else:
		# Go through all the operations to see if the file has a
		# (p)write/truncate/open/fsync/rename_to. In these cases, the
		# data has changed, otherwise attributes are changed.
		# NOTE: open in this case already implies open w/ create/write
		#       flags set
		data_modified = 0
		for i in range(len(operation_list)):
		    action = (operation_list[i])[ACTION_O]
		    if (action == "write" or
			action == "pwrite" or
			action == "truncate" or
			action == "ftruncate" or
			action == "fsync" or
			action == "open" or
			action == "rename_to"):
			data_modified = 1
			#XXX: We should break here, why perl script doesn't ?
			#break
		if (data_modified == 1):
		    str = "CHANGED_DATA: " + file
		else:
		    str = "CHANGED_ATTR: " + file
		final_output[file] = str
    
    for file in sorted(final_output.keys(), depth_first):
	value = final_output[file]
	if (value == ""):
	    continue
	print >>outfh, value
#	print value

    return

# --------------------------------------------------------------------------------
# pass_3: Purge subsequent cancelling operations. Only do this if 
# 	  they immediately follow each other
# --------------------------------------------------------------------------------
def pass_3(files):

    for key in sorted(files.keys()):
	value = files[key]
	operation_list = value
	size = len(operation_list)
	kept_ops_list = []

	#Skip ops list which dont have atleast 2 operations
	if (size < 2):
	    continue

	i = 0
	while (i < len(operation_list)):
	    operation = operation_list[i]
	    #if this is last entry, store it
	    if (i == (size - 1)):
		#Store this
		kept_ops_list.append(operation)
		break
	    next_operation = operation_list[i+1]

	    action = operation[ACTION_O]
	    next_action = next_operation[ACTION_O]

	    #Case1: if mkdir then rename or rmdir
	    if (action == "mkdir" and 
		(next_action == "rename" or next_action == "rmdir")):

		# Do not store this, but skip to next set of actions
		i += 2
	    #Case2: if rename_to then unlink or rename
	    elif (action == "rename_to" and 
		  (next_action == "unlink" or next_action == "rename")):
		# Do not store
		i += 2
	    else:
		#Store this
		kept_ops_list.append(operation)
		i += 1
	files[key] = kept_ops_list
	

# --------------------------------------------------------------------------------
# pass_2: At this point files[filename] contains all ops for a given file for 
# 	  this share we purge actions that are cancelled by other actions, 
#	  see rules.txt for more info
# --------------------------------------------------------------------------------
def pass_2(files):

    for key in sorted(files.keys()):
	value = files[key]
	operation_list = value
	kept_ops_list = []
	should_keep = 1
	for i in reversed(range(len(operation_list))):
	    operation = operation_list[i]
	    action = operation[ACTION_O]
	    if (action == "rename_to" or
		action == "mkdir" or
		action == "open"):
		should_keep = 1
		kept_ops_list.insert(0, operation)
	    elif (action == "rename" or
		  action == "rmdir" or
		  action == "unlink"):
		should_keep = 0
		kept_ops_list.insert(0, operation)
	    else:
		if (should_keep == 1):
		    kept_ops_list.insert(0, operation)
	files[key] = kept_ops_list



# --------------------------------------------------------------------------------
# pass_1: 
# For each share,
# 	For each log file
#		do {
#			add "rename_to" entry to each "rename" entry found.
#			Add all entries in dictionary "share_entry".
#		}
#	Add "share_entry" in dictionary "entries"
#
# Fills in global dictionary entries
# --------------------------------------------------------------------------------
def pass_1():
    global entries

    for share in shares:

	#Dictionary of all entries from log files of this share: 
	#Indexed by TIME_F
	share_entries = {}

	#Get all log files for this share
	dir = logpath + "/" + share

	pattern = "rbt_audit." + share + ".*"
	all_file_list = os.listdir(dir)
	file_list = fnmatch.filter(all_file_list, pattern)

	for tmp_file in file_list:
	    file = dir + "/" + tmp_file 
	    fo = open(file, 'r')
	    line_list = fo.readlines()
	    #Equivalent of perl's chomp
	    line_list = [l.rstrip('\n') for l in line_list]
	    fo.close()
	    if (len(line_list) > 0):
		last_line = line_list[len(line_list) - 1]
		last_entry = last_line.split("|")
		if (last_entry[TIME_F] and last_entry[TIME_F] < btime):
		    print "Skipping file: %s last_ts:"  % (file)
	    else:
		continue

	    for line in line_list:
		try:
		    entry = line.split("|")
		except ValueError:
		    continue
		entry[FILE_F] = entry[FILE_F].lstrip('./')

		#Convert time from string to float
		entry[TIME_F] = float(entry[TIME_F])

		if ((entry[TIME_F] < btime) or (entry[TIME_F] > etime)):
		    continue	#continue to next line

		#Add this line to dictionary
		share_entries[entry[TIME_F]] = entry

		#See if this is rename operation and add 
		#'rename_to' entry into dictionary
		if (entry[ACTION_F] == "rename"):
		    entry[REN_F] = entry[REN_F].lstrip('./')

		    #Make copy of list
		    twin_entry = entry[:]
		    twin_entry[ACTION_F] = "rename_to"
		    twin_entry[TIME_F] += BLINK
		    #Swap src file and target file
		    source_file = twin_entry[FILE_F]
		    twin_entry[FILE_F] = twin_entry[-1]
		    twin_entry[-1] = source_file

		    #Add 'rename_to' entry
		    share_entries[twin_entry[TIME_F]] = twin_entry

		    #Add it to ren_from dictionary
		    old_file = entry[FILE_F]
		    time = entry[TIME_F]
		    new_file = entry[REN_F]

		    if (new_file in ren_from):
			my_dict = ren_from[new_file]
		    else:
			my_dict = {}

		    my_dict[time] = old_file
		    ren_from[new_file] = my_dict

	    #This log is done for this share
	#All log files for this share are done, add share_entries to entries
	entries[share] = share_entries
    #Done with all shares
    return


# --------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------
def main(argv):
    global btime
    global etime
    #Get cmd line arguments
    get_cmd_args(argv);

    #NOTE: Currently this script works with only one share
    #Add share to share list
    shares.append(share);

    print_args(clean_old_log, btime, etime, outputpath, logpath, share, sharepath)

    #Open output file
    output_file = outputpath + "/" + share + ".out"
    try:
	#XXX: append mode? write mode?
	outfh = open(output_file, 'a+')
    except IOError:
	print "Unable to open %s file for writing" % output_file

    #Pass 1: pass_1
    pass_1()
#    print "After pass 1"
#    logfh = open("./pass_1", 'w')
#    for key in sorted(entries.keys()):
#	value = entries[key]
#	print "Share: %s" % key
#	for key_t in sorted(value.keys(), numerically):
#	    value_t = value[key_t]
#	    print >>logfh, "%f: %s: %s" % (value_t[TIME_F], value_t[FILE_F], value_t[ACTION_F])
#    logfh.close()

    #2nd for loop
    for one_share in shares:
	share_entries = entries[one_share]
	#The output file for the share is share.out

	#Actions on a give file for this share
	files = {}

	#Sorted by time
	for key in sorted(share_entries.keys(), numerically):
	    entry = share_entries[key]
	    #Skip any failed actions
	    if (entry[SUCCESS_F] == "fail"):
		continue

	    #Skip connect and disconnect actions
	    if (entry[ACTION_F] == "connect" or 
		entry[ACTION_F] == "disconnect"):
		continue

	    #Get rid of ./ that may be present at beginning of the file
	    entry[FILE_F] = entry[FILE_F].lstrip('./')

	    #Assert if we have out of bounds time
	    if (entry[TIME_F] < btime or entry[TIME_F] > etime):
		print "Out of bounds time %f btime: %f etime: %f" % (entry[TIME_F], btime, etime)
		sys.exit(-1);	

	    #For each action, store action and associated params w/ the file
	    file_name = entry[FILE_F]
	    action = entry[ACTION_F]
	    params = entry[FILE_F+1:]
	    operation = [action, params, entry[TIME_F]]

	    #Append one more operation for file file_name
	    if (file_name in files):
		files[file_name].append(operation)
	    else:
		files[file_name] = [operation]

#	print "Before pass_2"
#	print_file_actions(files, "before_pass_2")

	#Pass 2: pass_2
	pass_2(files)
#	print "After pass_2"
#	print_file_actions(files, "pass_2")

	#Pass 3: pass_3
	pass_3(files)
#	print "After pass_3"
#	print_file_actions(files, "pass_3")
#	print_file_actions_2(files, "depth_pass_3")

	print >>outfh, "FINAL_OUTPUT. Share: %s btime: %f etime: %f" % (share, btime, etime)

	#Pass 4: pass_4
	pass_4(files, outfh)

    #cleanup is asked, only works for one share for now
    if (clean_old_log):
	delete_logs(etime, share)
	print "Cleaned old logs\n"

    outfh.close()

if __name__ == "__main__":
    main(sys.argv[1:])

#Only for debugging purpose
#sys.stdout = saveout
#fstdout.close()
