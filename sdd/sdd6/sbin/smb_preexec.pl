#!/usr/bin/perl
use Sys::Hostname;

$username = $ARGV[0];
# make sure that case is consistent for hostname...
# issue seen at Benham
$userhost = uc($ARGV[1]);
$should_allow = $ARGV[2];
$thishost = uc(hostname);

#open LOG, ">>/tmp/plog2" or die "couldn't open /tmp/plog";

$retval = 0;

# if username is rcud, and localhost, then always allow.
# if username is rcud, and not localhost, always deny. simple, eh?
if($username eq "rcud") {
    # always allow if this host
    if($userhost eq $thishost) {
	exit(0);
    } else { #always deny otherwise
	exit(1)
    }
}

#if not sharing, then don't allow anyone (already did RCUd check above)
if(($should_allow eq "no")) {
    $retval = 1;
}

#print LOG "user: $username host: $userhost this_host: $thishost retval: $retval\n";
#close $LOG;

exit($retval);
