#!/bin/sh

/opt/tms/bin/mdreq -b query iterate - /rbt/sport/srdf/symm/state/id | egrep -ci -v DefaultSymm
