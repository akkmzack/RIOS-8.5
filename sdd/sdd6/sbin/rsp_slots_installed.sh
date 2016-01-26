#!/bin/sh
#
# determine number of populated rsp slots.
# this is used to populate the heartbeat status word's
# rsp.slots_installed value
#
/opt/tms/bin/mdreq -v query pattern_match - /rbt/rsp2/state/slot/*/installed | grep -ci true
