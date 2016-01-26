#!/bin/sh

/opt/tms/bin/mdreq -v query iterate - $* | wc -l
