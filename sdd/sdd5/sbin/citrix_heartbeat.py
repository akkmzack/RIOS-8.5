#!/usr/bin/python
#

import optparse
import subprocess

MDREQ = "/opt/tms/bin/mdreq"

FILE_BUFFER_SIZE_PATH = "/rbt/citrix/config/cdm/file_buffer_size"
SMALL_PKTS_THRESHOLD_PATH = "/rbt/citrix/config/small_pkts_threshold"

def get_value(path):
    mdreq_cmd = "%s -v query get - %s" % (MDREQ, path)
    return subprocess.Popen(mdreq_cmd, shell=True,
        stdout=subprocess.PIPE).communicate()[0]

def get_interpreted_file_buffer_size(mdreq_output):
    """
    >>> get_interpreted_file_buffer_size("4")
    '4_blocks'
    >>> get_interpreted_file_buffer_size("5")
    '5-8_blocks'
    >>> get_interpreted_file_buffer_size("8")
    '5-8_blocks'
    >>> get_interpreted_file_buffer_size("9")
    '9-32_blocks'
    >>> get_interpreted_file_buffer_size("31")
    '9-32_blocks'
    >>> get_interpreted_file_buffer_size("32")
    '9-32_blocks'
    >>> get_interpreted_file_buffer_size("64")
    '33+_blocks'
    """
    file_buffer_size = int(mdreq_output)
    if file_buffer_size == 4:
        return "4_blocks"
    elif file_buffer_size > 32:
        return "33+_blocks"
    elif file_buffer_size > 8:
        return "9-32_blocks"
    else:
        return "5-8_blocks"

def get_interpreted_small_pkts_threshold(mdreq_output):
    """
    >>> get_interpreted_small_pkts_threshold("60")
    '0-63_bytes'
    >>> get_interpreted_small_pkts_threshold("63")
    '0-63_bytes'
    >>> get_interpreted_small_pkts_threshold("64")
    '64_bytes'
    >>> get_interpreted_small_pkts_threshold("65")
    '65-128_bytes'
    >>> get_interpreted_small_pkts_threshold("127")
    '65-128_bytes'
    >>> get_interpreted_small_pkts_threshold("128")
    '65-128_bytes'
    >>> get_interpreted_small_pkts_threshold("129")
    '129+_bytes'
    >>> get_interpreted_small_pkts_threshold("200")
    '129+_bytes'
    """
    threshold = int(mdreq_output)
    if threshold < 64:
        return "0-63_bytes"
    elif threshold == 64:
        return "64_bytes"
    elif threshold > 128:
        return "129+_bytes"
    else:
        return "65-128_bytes"

def get_node_data(node):
    raw_value = get_value(node).strip()
    if node == FILE_BUFFER_SIZE_PATH:
        return get_interpreted_file_buffer_size(raw_value)
    elif node == SMALL_PKTS_THRESHOLD_PATH:
        return get_interpreted_small_pkts_threshold(raw_value)

def parse_options():
    parser = optparse.OptionParser()
    parser.add_option(
        "-n", "--node",
        action="store", type="string", dest="node",
        help="The name of the node to get the information for.")

    return parser.parse_args()

def main():
    (options, args) = parse_options()

    print get_node_data(options.node)

if __name__ == "__main__":
    #import doctest
    #doctest.testmod()
    main()
