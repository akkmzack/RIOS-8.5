#!/bin/sh
#
# determine if transparency is enabled in any inpath rule.
# returns a count of matching rules. 
# this is used to populate the heartbeat status word's
# network.transparency_inpath value (which is actually a boolean)
#
/opt/tms/bin/mdreq -v query pattern_match - /rbt/sport/intercept/config/rule/*/transparency_mode | egrep -ci "(port)|(full)"

