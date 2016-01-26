#!/bin/sh
#
# determine if fair peering is on in any load balancing rule.
# returns a count of matching rules. 
# this is used to populate the heartbeat status word's
# load_balancing.fair_peering_v1 value (which is actually a boolean)
#
/opt/tms/bin/mdreq -v query pattern_match - /rbt/load/rule/config/rule/*/ruletype | grep -ci 2

