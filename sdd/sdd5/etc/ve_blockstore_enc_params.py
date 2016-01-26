#!/usr/bin/env python

from xml.dom import minidom
import xml

# CONSTANTS
edge_config_file = "/var/opt/rbt/edge-cfg.xml"

# DEFAULTS
encryption_type = "NONE"
encryption_key_file="/var/opt/rbt/decrypted/blockstore_key"

try:
    # fist find blockstore element
    xml_tree = minidom.parse(edge_config_file)
    bs = None
    vas = xml_tree.getElementsByTagName('va')
    for va in vas:
        blockstores = xml_tree.getElementsByTagName('blockstore')
        for blockstore in blockstores:
            bs = blockstore
            break

    if bs != None:
        # valid blockstore find encryption_type and encryption_key_file
        encryption_type = bs.getAttribute('encryption_type')
        encryption_key_file = bs.getAttribute('encryption_key_file')

except xml.parsers.expat.ExpatError, e:
    pass

if encryption_type == "NONE":
    print ''
else:
    print '--encryption-type %s --encryption-key %s' % (encryption_type, encryption_key_file)
