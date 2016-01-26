#!/bin/sh

rdfs=`/opt/tms/bin/mdreq -b query pattern_match - /rbt/sport/srdf/symm/state/id/*/rdf_group/* | awk ' {printf("%s ", $3);}'`

max=0;
for rdf in $rdfs; do
    if [ $rdf != 255 -a $rdf -gt $max ]; then
	max=$rdf;
    fi
done

echo $max
