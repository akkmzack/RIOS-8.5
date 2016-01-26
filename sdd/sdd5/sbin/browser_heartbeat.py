#!/usr/bin/python
#
# Tally the contents of the browser log, select one to be reported via the DNS
# heartbeat mechanism, and empty the browser log.

import os, random, sys, heartbeat_status
from optparse import OptionParser

# Constants
BROWSER_LOG = '/var/opt/tms/browser_log'
HEARTBEAT_XML = '/opt/rbt/etc/heartbeat.xml'

## Get the set of legal browser types from the heartbeat XML spec.
## product specifies the product type being queried (products as defined in the
## XML spec, e.g. SHA, CMC, CVE, etc)
#
# @return A dictionary containing the legal browser types as keys.
def getBrowserTypes(product):
    return heartbeat_status.read_enum_dict(
               'webui.browser', HEARTBEAT_XML, 'heartbeat', product)

## Tally the number of times each browser appears in the logfile.
#
# @param browserTypes A dictionary containing the legal browser types as keys.
# @return A dictionary containing the browser counts.
def tallyBrowsers(browserTypes):
    browserCounts = {}

    try:
        logFile = open(BROWSER_LOG)
    except IOError:
        return browserCounts

    for line in logFile:
        browser = line.rstrip('\n')

        # Skip blank lines.
        if not browser:
            continue

        if browser not in browserTypes:
            sys.stderr.write("Unknown browser found: '%s'\n" % browser)
            continue

        browserCounts[browser] = browserCounts.get(browser, 0) + 1

    logFile.close()

    return browserCounts

## Select a browser at random, following the distribution of browser totals.
#
# @param browserCounts A dictionary containing the browser counts.
# @return The browser we wish to report.
def selectBrowser(browserCounts):
    total = sum(browserCounts.values())
    rand = random.random() * total
    boundary = 0

    if total == 0:
        return 'none'

    for browser, count in browserCounts.iteritems():
        boundary += count
        if rand < boundary:
            return browser

## Empty the browser log.
def emptyLogfile():
    try:
        os.remove(BROWSER_LOG)
    except OSError:
        return

def main():
    parser = OptionParser(
        usage="Need product"
    )
    parser.add_option("--product", default="SHA",
                      help="Browser data for this product")

    (opts, args) = parser.parse_args()
    product = opts.product or 'SHA'

    browserTypes = getBrowserTypes(product)
    browserCounts = tallyBrowsers(browserTypes)
    print selectBrowser(browserCounts)
    emptyLogfile()

if __name__ == "__main__":
    main()
