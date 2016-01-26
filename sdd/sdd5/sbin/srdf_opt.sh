#!/bin/sh

/opt/tms/bin/mdreq -b query pattern_match - /rbt/sport/srdf/symm/config/id/*/rdf_rule/*/optpolicy  | egrep -ci 'lz-only|none'
