#!/usr/bin/perl 

# Copyright (c) 2007-2008, Hewlett-Packard Company.
# All Rights Reserved.
#
# The contents of this software are proprietary and confidential to the
# Hewlett-Packard Company.  No part of this program may be photocopied,
# reproduced, or translated into another programming language without
# prior written consent of the Hewlett-Packard Company.
#
# $Revision: 107 $
# $Date: 2010-01-21 10:10:12 -0800 (Thu, 21 Jan 2010) $


# This script will take as its input, the output of the last command
# or a w command wihtout the headers ( $ w -h ), 
# it will then take the first word as the username and convert this to 
# the UID using the id command.
# One issue is that a username that is more than 8 chars will be 
# truncated to 8 and this causes the id command to fail.  
# The real solution would be to write this in C or C++ using the 
# the wtmp APIs, but this is likely 'good enough' as the real intent is 
# show the activity of user logins.


# Print the header
printf "UID\tPTY\t%18s\tTime\n","Location";

while (<STDIN>) {
	# split the output of LAST / W to user, pty, location and then
	# the rest of the line.
	my ($user, $pty, $location, @lasttime) = split;

	# call the id command and place the result in uid
	chomp (my $uid = `id -u $user 2>/dev/null`);
	
	# check the return.  id will return 0 is successful
	if ( $? ) { 
		if ($user eq "wtmp")  {
			next;
		} else {
			$uid = "???";
		} 

	}
	printf "%s\t%s\t%18s\t", $uid, $pty, $location ;
	print "@lasttime\n";
}
