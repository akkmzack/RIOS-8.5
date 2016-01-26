#!/bin/bash

# Run a loop of sync every two seconds if an image uprgade is carried
# is being done. We do not want the dirty page ration to go too high
while [ 1 ]; do
    /bin/ps ax | /bin/grep writeimage | /bin/grep -v 'grep' 2>&1 > /dev/null
    if [ $? -ne 0 ]; then
        # writeimage is done with the upgrade
        # One last sync before exit the script
        /bin/sync
        exit 0
    fi

    /bin/sync
    sleep 2
done
