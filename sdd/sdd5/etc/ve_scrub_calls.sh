
ve_scrub_graft_1()
{
    # don't scrub anything in Granite unless the special granite
    # flags have been specified
    if [ "x$1" == "xclear-granite" -o "x$1" == "xclear-granite-fast" -o "x$1" == "xclear-granite-secure" ]; then
        # notice of scrubbing delay
        echo "Scrubbing the system. This might take a while."
        echo "System will reboot after completing."
        echo ""

        # stop the edge process
        /usr/bin/printf "enable\nconfigure terminal\npm process edge terminate\nexit\nexit\n" | /opt/tms/bin/cli
        sleep 5

        # toast files
        rm -rf /var/tmp/0/*.dat
        rm -rf /var/opt/rbt/*.xml
        rm -rf /var/log/memlog*
        rm -rf /var/log/edge.stats*
        touch /var/opt/rbt/.blockstore_clean

        local BS_DEV=`/opt/tms/bin/mddbreq -v /config/mfg/mfdb query get - /rbt/mfd/blockstore_device`
        if [ "x${BS_DEV}" != "x" ]; then
            if [ "x$1" == "xclear-granite" ]; then
                /usr/bin/scrub -p fastold -f "${BS_DEV}"
            fi
            if [ "x$1" == "xclear-granite-fast" ]; then
                /bin/dd if=/dev/zero of=${BS_DEV} bs=1k count=17
            fi
            if [ "x$1" == "xclear-granite-secure" ]; then
                /usr/bin/scrub -p dod -f "${BS_DEV}"
            fi
        fi

        local BC_DEV=`/opt/tms/bin/mddbreq -v /config/mfg/mfdb query get - /rbt/mfd/blockstore_cachedev`
        if [ "x${BC_DEV}" != "x" ]; then
            if [ "x$1" == "xclear-granite" ]; then
                /usr/bin/scrub -p fastold -f "${BC_DEV}"
            fi
            if [ "x$1" == "xclear-granite-fast" ]; then
                /bin/dd if=/dev/zero of=${BC_DEV} bs=1k count=9
            fi
            if [ "x$1" == "xclear-granite-secure" ]; then
                /usr/bin/scrub -p dod -f "${BC_DEV}"
            fi
        fi
    fi
}
