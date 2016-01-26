#!/usr/bin/python
"""
Encode/decode appliance heartbeat status vectors.

Executed on an appliance, this program executes mgmt queries and shell
commands from a heartbeat.xml schema file to compute values for each
of its status items.  It then transforms these values into bitfields
and assembles them into a status word according to the schema. The
staus word can be output in a variety of encodings -- ascii binary,
ascii hex, DNS heartbeat format, or human-readable name=value form.

See the comments in the heartbeat-example.xml file for details on how things
are specified there.

If a status word is provided as a command-line argument (in any of the
understood output formats), the word is decoded according to the rules
above and its values are used instead of querying the appliance
values. By combining status word input arguments and output format
flags, this program can be thus used as a standalone
encoder/decoder/translator for status bit patterns.

"""

import sys, os, traceback
import re
from xml.dom import minidom
from subprocess import Popen, PIPE
from optparse import OptionParser
from string import capwords, ascii_lowercase, ascii_uppercase, digits
import math
import logging

def log():
    return logging.getLogger(__name__)

def to_rbt_product(status_product):
    """
    Translate yet another product abbreviation scheme (the prefixes of
    our status words) into the familiar rbt_foo form for interoperating
    with other product-related code and data. Return empty string for unknown
    product or empty status.
    """
    return {
        'SHA':'rbt_sh',
        'CMC':'rbt_cmc',
        'CVE':'rbt_cmc',
        'SMC':'rbt_gw',
        'SVE':'rbt_gw',
        'IB':'rbt_ib',
        'CAP':'cas_prof',
        'CAG':'cas_gw',
        'CAS':'cas_sens',
        'CAX':'cas_expr'
        }.get(status_product.upper(),status_product)

def release_to_build(product, release):
    """
    find the svn tag for the release. 
    product is like SHA, CMC, etc
    """
    if release == '' or (release and release.find("flamebox") >= 0):
        return None # these are never tagged.
    rbt_product = to_rbt_product(product)
    try:
        text = Popen(["/mnt/builds/tools/release-to-build.pl", 
                      "-product", rbt_product, release],
                     stdout=PIPE).communicate()[0]
        m = re.search("svn co (svn://svn/mgmt(-fwk)?/tags/\S+)", text)
        return m and m.groups()[0]
    except Exception, e:
        log().error(str(e))
        return None

def build_to_heartbeat_url(product, tag, user=None, passwd=None):
    """
    find the svn url for the tag's heartbeat.xml.
    """
    if not tag:
        return None
    rbt_product = to_rbt_product(product)
    try:
        #
        # modern heartbeat.xml lives in framework
        #
        fwk_url = "/framework/src/base_os/common/script_files/heartbeat.xml"
        cmd = ["/usr/bin/svn", "ls", tag+fwk_url]
        if user:
            cmd.extend(["--username", user, "--password", passwd, 
                        "--no-auth-cache"])
        (out,err) = Popen(cmd, stdout=PIPE, stderr=PIPE).communicate()
        if err:
            log().error(err)
        if out:
            return tag+fwk_url
        #
        # early heartbeat.xml lived in products
        #
        prod_url = "/products/%s/src/base_os/common/script_files/heartbeat.xml"\
                   % rbt_product
        cmd = ["/usr/bin/svn", "ls", tag+prod_url]
        if user:
            cmd.extend(["--username", user, "--password", passwd, 
                        "--no-auth-cache"])
        (out,err) = Popen(cmd, stdout=PIPE, stderr=PIPE).communicate()
        if err:
            log().error(err)
        if out:
            return tag+prod_url
        return None
    except Exception, e:
        log().error(str(e))
        return None
    

def release_to_heartbeat_url(product, release, user=None, passwd=None):
    """
    find the svn url for the release's heartbeat.xml.
    """
    return build_to_heartbeat_url(product,release_to_build(product, release),
                                  user, passwd)

def release_to_heartbeat_xml(product, release, user=None, passwd=None):
    """
    return the heartbeat xml for the given product and release string
    """
    url = release_to_heartbeat_url(product,release, user, passwd)
    if not url:
        log().error("No heartbeat.xml found for release %s %s" % (
                to_rbt_product(product),release))
        return None
    devnull = open("/dev/null","w")
    cmd = ["/usr/bin/svn", "cat", url]
    if user:
        cmd.extend(["--username", user, "--password", passwd, 
                    "--no-auth-cache"])
    (xml_text, err) = Popen(cmd, stdout=PIPE, stderr=PIPE).communicate()
    if err:
        log().error(err)
    if not xml_text:
        log().error("Empty heartbeat.xml found for release %s %s at %s" % (
                to_rbt_product(product),release, url))
    return xml_text

def to_int(s, default=''):
    """
    parse a decimal or hexidecimal int string, or truncate a float.
    if s is an empty string or None, process the supplied default.
    raise ValueError if something goes wrong (note that you must override
    default if you want an unexceptional default)

    >>> to_int("12")
    12
    >>> to_int(0xFFFF)
    65535
    >>> to_int("0xFFFF")
    65535
    >>> to_int(23.4)
    23
    >>> to_int("", "0")
    0
    >>> to_int(0)
    0
    >>> to_int("")
    Traceback (most recent call last):
        ...
    ValueError: to_int: empty or None
    """
    if s == '' or s == None:
        s = default
    if s == '' or s == None:
        raise ValueError("to_int: empty or None")
    if isinstance(s,basestring) and s.startswith("0x"):
        return int(s, 16)
    else:
        return int(s)

def to_bool(s, default=''):
    """
    convert a native, int, or string to a boolean.
    if s is an empty string or None, process the supplied default.
    Unlike the python bool(), "0" and "False" evaluate to False; and 
    in the absense of a default, "" and None raise ValueError.

    >>> to_bool(None)
    Traceback (most recent call last):
        ...
    ValueError: to_bool: empty or None
    >>> to_bool("")
    Traceback (most recent call last):
        ...
    ValueError: to_bool: empty or None
    >>> to_bool("", False)
    False
    >>> to_bool(False)
    False
    >>> to_bool(True)
    True
    >>> to_bool("True")
    True
    >>> to_bool("false")
    False
    >>> to_bool("true")
    True
    >>> to_bool("False")
    False
    >>> to_bool("True")
    True
    >>> to_bool("0")
    False
    >>> to_bool("1")
    True
    >>> to_bool(0)
    False
    >>> to_bool(1)
    True
    """
    if s == '' or s == None:
        s = default
    if s == '' or s == None:
        raise ValueError("to_bool: empty or None")
    if isinstance(s,basestring) and s.isdigit():
        return bool(to_int(s))
    elif isinstance(s,basestring):
        return s.lower()!="false"
    else:
        return bool(s)

def xml_to_spec(xml_text, stype="heartbeat", product="SHA"):
    """
    extract the specified xml snippet (matching type/prod)
    from the xml_text, which may contain many specs, parse it into a DOM
    and return the root node.
    """
    xml_nodes = minidom.parseString(xml_text)
    return get_spec(xml_nodes, stype, product)

def get_spec(nodes, stype=None, product=None, verbose=False):
    """
    parse the xml to find the element matching the
    specified type/product. Return a DOM node or None.
    """
    spec = None
    for node in nodes.getElementsByTagName('status'):
        attrs = dict(node.attributes.items())
        if (attrs.get('type') == stype and
            attrs.get('product') == product):
            spec = node
            break
    if spec:
        compute_defaults(spec, verbose)
    return spec

def get_product(spec):
    """
    return the version for this spec
    """
    attrs = dict(spec.attributes.items())
    return attrs.get('product')
    
def get_canonical_xml(spec):
    """
    return canonical xml string (any CDATA deleted to be immune from
    whitespace and comments).  This modifies spec in place by deleting
    CDATA, but that should not matter to you.
    """
    for child in spec.childNodes[:]:
        if child.nodeType==spec.TEXT_NODE:
            spec.removeChild(child)
    return spec.toxml()

def get_item(spec, dotname):
    """
    fetch the item node in the spec having the given dotname.
    """
    for item in spec.getElementsByTagName('item'):
        if item.getAttribute('dotname') == dotname:
            return item

def get_item_type(spec, dotname):
    """
    Return a native python item value types (bool/int/str),
    from the given spec for the named node. These are the 
    return types of items after decoding: 1-bit ints are 
    type bool, and enums are type str.
    """
    item = get_item(spec, dotname)
    if not item:
        return None
    stype = item.getAttribute('type')
    if stype == 'bool':
        return bool
    elif stype == 'int':
        return int
    elif stype == 'char' or stype == 'enum':
        return str
    else:
        return None

def get_item_nicename(spec, dotname):
    """
    Return the nicename for this dotname
    """
    item = get_item(spec, dotname)
    if not item:
        return None
    return item.getAttribute('nicename')

def parse_enum_dict(values, idx_to_string=False):
    """
    parse the 'values' string from the xml spec into a dictionary
    mapping enum strings to integers, unless unless idx_to_string is
    True, in which case the reverse mapping is returned.

    >>> d = parse_enum_dict("0:none 1:one 2:two 3:three 255:max")
    >>> d == {"none":0, "one":1, "two":2, "three":3, "max":255}
    True
    >>> d = parse_enum_dict("0:none 1:one 2:two 3:three 255:max", 
    ...                     idx_to_string=True)
    >>> d == {0:"none", 1:"one", 2:"two", 3:"three", 255:"max"}
    True
    >>> d = parse_enum_dict("0: 1:one 2:two 3:three 255:max")
    >>> d == {"":0, "one":1, "two":2, "three":3, "max":255}
    True
    """
    items = re.split(r"(?<!\\)\s+", values.strip()) # split on unescaped spaces
    d = dict([item.replace(r'\ ', ' ').strip().split(":",1) for item in items])
    d = dict([(to_int(item[0]), item[1]) for item in d.items()])
    if idx_to_string:
        return d
    else:
        return dict([(value, key) for (key, value) in d.items()])

def get_enum_dict(spec, dotname):
    """
    return a dictionary mapping enum names to integer values
    for the enum item having dotname
    """
    item = get_item(spec, dotname)
    return parse_enum_dict(item.getAttribute("values"))

def read_enum_dict(dotname, fname, stype, product, verbose=False):
    """
    load the spec from the given xml fname, and return the enum dict
    for the node named dotname
    """
    xml_nodes = minidom.parse(fname)
    spec = get_spec(xml_nodes, stype, product, verbose)
    return get_enum_dict(spec, dotname)

def get_item_names(spec):
    """
    Return a list of "dotnames" from the given spec node. This requires
    that compute_defaults has been called on the spec.
    """
    names = [item.getAttribute('dotname')
             for group in spec.getElementsByTagName('group')
             for item in group.getElementsByTagName('item')]
    return names

def compute_defaults(spec, verbose=False):
    """
    annotate the nodes with computed default values and absolute bit
    positions for each item.
    """
    if verbose:
        log().info("Bit posistions for status items:")
    bit = to_int(spec.getAttribute('bit') or 0)
    for group in spec.getElementsByTagName('group'):
        assert group.hasAttribute('name'), "Every group needs a name!"
        if not group.hasAttribute('exec'):
            group.setAttribute('exec', spec.getAttribute('exec'))
        nicename = group.getAttribute('nicename') or \
                   capwords(group.getAttribute('name').replace("_"," "))
        group.setAttribute('nicename', nicename)
        newbit = to_int(group.getAttribute('bit') or  bit)
        assert newbit >= bit, "group %s has a bad bit attribute %d > %d" % \
              (group.getAttribute('name'), newbit, bit)
        group.setAttribute('bit', str(newbit))
        bit = newbit
        for item in group.getElementsByTagName('item'):
            assert item.hasAttribute('name'), "Every item needs a name!"
            if not item.hasAttribute('exec'):
                item.setAttribute('exec', group.getAttribute('exec'))
            nicename = item.getAttribute('nicename') or \
                       capwords(item.getAttribute('name').replace("_"," "))
            item.setAttribute('nicename', nicename)
            item.setAttribute('dotname', group.getAttribute('name') + "."+ \
                              item.getAttribute('name'))
            item.setAttribute('nbits',item.getAttribute('nbits') or '1')
            item.setAttribute('offset',item.getAttribute('offset') or '0')
            item.setAttribute('scale',item.getAttribute('scale') or '1')
            item.setAttribute('sigbits',item.getAttribute('sigbits') or '0')
            item.setAttribute('default',item.getAttribute('default') or '')
            if not item.getAttribute('type'):
                item.setAttribute('type',
                                  item.getAttribute('nbits')=='1' and 'bool' or
                                  'int')
            newbit = to_int(item.getAttribute('bit') or bit)
            assert newbit >= bit, "item %s has a bad bit attribute %d > %d" % \
                  (item.getAttribute('name'), newbit, bit)
            item.setAttribute('bit', str(newbit))
            if verbose:
                log().info( item.getAttribute('dotname')+'='+ \
                                item.getAttribute('bit'))
            bit = newbit + to_int(item.getAttribute('nbits'))
    spec.setAttribute('nbits', str(bit))
    if verbose:
        log().info( "%d status bits" % bit )

def execute(spec, verbose=False):
    """
    given a spec containing items with exec and value attributes,
    produce a dictionary of string values by execing each of the items.
    This does no conversion or sanity-checking of exec output.
    """
    values = {}
    for group in spec.getElementsByTagName('group'):
        for item in group.getElementsByTagName('item'):
            key = item.getAttribute('dotname')
            execstr = item.getAttribute('exec')
            value = item.getAttribute('value')
            stype = item.getAttribute('type')
            if execstr:
                if verbose:
                    log().info( execstr % value)
                try:
                    p = os.popen(execstr % value)
                    value = p.read().strip()
                    if verbose:
                        log().info( "  ==> %s" % value)
                except Exception, e:
                    log().error( "exec failure for %s: %s" % (execstr % value,e))
            values[key] = value
    return values

def encode(values, spec, status_bits, verbose=False):
    """
    given a dictionary of string or native values corresponding to
    item nodes in the status spec, transform them and then pack their
    bits as indicated by the spec into the status_bits boolean
    array. Throw an exception if there are unused values. 
    """
    values = values and values.copy() # we're gonna destroy this thing
    for group in spec.getElementsByTagName('group'):
        for item in group.getElementsByTagName('item'):
            stype = item.getAttribute('type')
            name = item.getAttribute('dotname')
            nodename = item.getAttribute('value')
            default = item.getAttribute('default')
            bit = to_int(item.getAttribute('bit'))
            nbits = to_int(item.getAttribute('nbits'))
            bits = [False] * nbits 
            if values and values.has_key(name):
                try:
                    if stype == 'bool':
                        bits[0] = to_bool(values[name], default)
                    elif stype == 'int':
                        value = to_int(values[name], default)
                        offset = to_int(item.getAttribute('offset'))
                        scale = to_int(item.getAttribute('scale'))
                        sigbits = to_int(item.getAttribute('sigbits'))
                        bits = encode_int(value,offset,scale,sigbits,nbits)
                    elif stype == 'char':
                        bits = encode_str(values[name], nbits, default)
                    elif stype == 'enum':
                        enum_def = item.getAttribute("values")
                        bits = encode_enum(values[name],enum_def, 
                                           nbits, default)
                    else:
                        assert False, "unknown item type %s" % stype
                except Exception, e:
                    log().error("while encoding %s: %s" % (name, str(e)))
                del(values[name])
            else:
                log().warn( "No value for %s" % name)
            status_bits[bit:bit+nbits] = bits
    assert not values, "No matching item in spec for: %s" % str(values.keys())
    return status_bits

def encode_int(value,offset=0,scale=1,sigbits=0,nbits=1):
    """
    given an integer value and bit-reduction modifiers, compute a bit
    representation. optional operations are applied to value if
    specified, in order: subtract offset; divide by scale; retain
    sigbits significant bits and compute an nbits-sigbits base 2
    exponent; return an n-bit array of booleans representing the
    reduced int.  Regarding sigbits: a value of 0 signals a regular
    int (specifying sigbits=nbits would do that as well). For other
    nonzero sigbits, a scaled/offset nonzero value is bit-shifted down
    until it fits in sigbits bits, and the number of shifts becomes
    the exponent. In particular, for sigbits=1 it's all exponent, and
    you're encoding your value as log2(n). Overflows peg at the
    maximum value. We don't do negative values or negative exponents
    (non-integer values).

    >>> encode_int(0, nbits=8)
    [False, False, False, False, False, False, False, False]
    >>> encode_int(1, nbits=8)
    [True, False, False, False, False, False, False, False]
    >>> encode_int(-1, nbits=8)
    [False, False, False, False, False, False, False, False]
    >>> encode_int(254, nbits=8)
    [False, True, True, True, True, True, True, True]
    >>> encode_int(255, nbits=8)
    [True, True, True, True, True, True, True, True]
    >>> encode_int(256, nbits=8)
    [True, True, True, True, True, True, True, True]
    >>> encode_int(0, scale=100, nbits=3)
    [False, False, False]
    >>> encode_int(1, scale=100, nbits=3)
    [True, False, False]
    >>> encode_int(100, scale=100, nbits=3)
    [True, False, False]
    >>> encode_int(101, scale=100, nbits=3)
    [False, True, False]
    >>> encode_int(200, scale=100, nbits=3)
    [False, True, False]
    >>> encode_int(201, scale=100, nbits=3)
    [True, True, False]
    >>> encode_int(300, scale=100, nbits=3)
    [True, True, False]
    >>> encode_int(800, scale=100, nbits=3)
    [True, True, True]
    >>> encode_int(700, scale=100, nbits=3)
    [True, True, True]
    """
    
    value = int(math.ceil((value - offset)/float(scale)))
    if value < 0:
        value = 0
    if sigbits:
        maxval = (1<<sigbits) - 1
        maxexp = (1<<(nbits-sigbits)) - 1
        exp = 0
        while value > maxval:
            value /= 2
            exp += 1
        if exp > maxexp:
            exp = maxexp
            value = maxval
        valbits = [bool(value&(1<<i)) for i in range(sigbits)]
        expbits = [bool(exp&(1<<i)) for i in range(nbits-sigbits)]
        bits = valbits + expbits
    else:
        maxval = (1<<nbits) - 1 # max out with all 1's
        if value > maxval:
            value = maxval
        bits = [bool(value&(1<<i)) for i in range(nbits)]
    return bits

def encode_str(value, nbits, default=''):
    """
    expand the ascii string into an array of n booleans. If empty,
    use any supplied default value.

    >>> encode_str("0",8)
    [False, False, False, False, True, True, False, False]
    >>> encode_str("",8,"0")
    [False, False, False, False, True, True, False, False]
    >>> encode_str("01",16)
    [False, False, False, False, True, True, False, False, True, False, False, False, True, True, False, False]
    >>> encode_str("01",24)
    [False, False, False, False, True, True, False, False, True, False, False, False, True, True, False, False, False, False, False, False, False, False, False, False]
    """
    if value == '' or value == None:
        value = default
    if len(value)*8 > nbits:
        log().warn("Truncating string %s to %d bits" % (
                value,nbits))
        value = value[:nbits/8]
    bits = [False] * nbits 
    for i, char in enumerate(value):
        bits[i*8:(i+1)*8] = [bool(ord(char)&(1<<j))
                             for j in range(8)]
    return bits


def encode_enum(value, enum_def_str, nbits, default=''):
    """
    parse the enum_values into a dictionary mapping enum names to ints,
    then encode the int named by value as an array of bools.

    >>> encode_enum("one", "0:none 1:one 2:two 3:three 255:max",8)
    [True, False, False, False, False, False, False, False]
    >>> encode_enum("two", "0:none 1:one 2:two 3:three 255:max",8)
    [False, True, False, False, False, False, False, False]
    >>> encode_enum("three", "0:none 1:one 2:two 3:three 255:max",8)
    [True, True, False, False, False, False, False, False]
    >>> encode_enum("max", "0:none 1:one 2:two 3:three 255:max",8)
    [True, True, True, True, True, True, True, True]
    >>> encode_enum("min", "0:none 1:one 2:two 3:three 255:max",8)
    Traceback (most recent call last):
    KeyError: 'unknown enum value min'
    >>> encode_enum("", "0:none 1:one 2:two 3:three 255:max",8)
    Traceback (most recent call last):
    KeyError: 'unknown enum value '
    >>> encode_enum("", "0:none 1:one 2:two 3:three 255:max",8, "none")
    [False, False, False, False, False, False, False, False]
    """
    if value == '' or value == None:
        value = default
    enumidxs = parse_enum_dict(enum_def_str)
    if value in enumidxs:
        idx = to_int(enumidxs[value])
        bits = [bool(idx&(1<<i)) for i in range(nbits)]
        return bits
    else:
        raise KeyError("unknown enum value %s" % value)

def decode(status_bits, spec):
    """
    given an array of booleans representing an encoded status word, unpack
    it to produce a dictionary of native type values as defined by the
    item types in the spec.
    """
    values = {}
    for group in spec.getElementsByTagName('group'):
        for item in group.getElementsByTagName('item'):
            stype = item.getAttribute('type')
            name = item.getAttribute('dotname')
            bit = to_int(item.getAttribute('bit'))
            nbits = to_int(item.getAttribute('nbits'))
            bits = status_bits[bit:bit+nbits]
            if stype == 'bool':
                values[name] = bits[0]
            elif stype == 'int':
                offset = to_int(item.getAttribute('offset'))
                scale = to_int(item.getAttribute('scale'))
                sigbits = to_int(item.getAttribute('sigbits'))
                values[name] = decode_int_bits(bits,offset,scale,sigbits)
            elif stype == 'char':
                values[name] = decode_str_bits(bits)
            elif stype == 'enum':
                enum_def = item.getAttribute("values")
                values[name] = decode_enum_bits(bits, enum_def)
            else:
                assert False, "unknown item type %s" % stype
    return values

def decode_int_bits(bits,offset=0,scale=1,sigbits=0):
    """
    reverse the operations performed in encode_int to transform
    the bits into an int.

    >>> decode_int_bits(encode_int(0, nbits=8))
    0
    >>> decode_int_bits(encode_int(1, nbits=8))
    1
    >>> decode_int_bits(encode_int(254, nbits=8))
    254
    >>> decode_int_bits(encode_int(255, nbits=8))
    255
    >>> decode_int_bits(encode_int(256, nbits=8))
    255
    >>> decode_int_bits(encode_int(4294967294, nbits=32)) == 4294967294
    True
    >>> decode_int_bits(encode_int(4294967295, nbits=32)) == 4294967295
    True
    >>> decode_int_bits(encode_int(4294967296, nbits=32)) == 4294967295
    True
    >>> decode_int_bits(encode_int(0xFFFFFFFE, nbits=32)) == 4294967294
    True
    >>> decode_int_bits(encode_int(0xFFFFFFFF, nbits=32)) == 4294967295
    True
    >>> decode_int_bits(encode_int(0x100000000, nbits=32)) == 4294967295
    True
    >>> decode_int_bits(encode_int(0, nbits=5, sigbits=3, scale=10),
    ...                 sigbits=3, scale=10)
    0
    >>> decode_int_bits(encode_int(10, nbits=5, sigbits=3, scale=10),
    ...                 sigbits=3, scale=10)
    10
    >>> decode_int_bits(encode_int(11, nbits=5, sigbits=3, scale=10),
    ...                 sigbits=3, scale=10)
    20
    >>> decode_int_bits(encode_int(80, nbits=5, sigbits=3, scale=10),
    ...                 sigbits=3, scale=10)
    80
    >>> decode_int_bits(encode_int(90, nbits=5, sigbits=3, scale=10),
    ...                 sigbits=3, scale=10)
    80
    >>> decode_int_bits(encode_int(550, nbits=5, sigbits=3, scale=10),
    ...                 sigbits=3, scale=10)
    480
    >>> decode_int_bits(encode_int(560, nbits=5, sigbits=3, scale=10),
    ...                 sigbits=3, scale=10)
    560
    >>> decode_int_bits(encode_int(570, nbits=5, sigbits=3, scale=10),
    ...                 sigbits=3, scale=10)
    560
    """
    nbits = len(bits)
    if sigbits:
        expbits = bits[sigbits:nbits]
        exp = sum([to_int(expbits[i])<<i for i in range(nbits-sigbits)])
        valbits = bits[0:sigbits]
        value = sum([to_int(valbits[i])<<(i+exp) for i in range(sigbits)])
    else:
        value = sum([to_int(bits[i])<<(i) for i in range(nbits)])
    ivalue = int(value*scale + offset)
    if ivalue > 0:
        return ivalue
    else:
        return 0

def decode_str_bits(bits):
    """
    convert the bool array into a string of 8-bit characters

    >>> decode_str_bits([False, False, False, False, True, True, False, False])
    '0'
    >>> decode_str_bits([False, False, False, False, True, True, False, False,
    ... True, False, False, False, True, True, False, False])
    '01'
    """
    nbits = len(bits)
    chars = [chr(sum([to_int(bits[i+j*8])<<i
                      for i in range(8)]))
             for j in range(nbits/8)]
    return "".join(chars)

def decode_enum_bits(bits, enum_def_str):
    """
    find the string value that goes with the index encoded in bits
    for the given enum definition.

    >>> decode_enum_bits([True, False, False, False, False, False,False,False],
    ... '0:none 1:one 2:two 3:three 255:max')
    'one'
    >>> decode_enum_bits([False, True, False, False, False, False,False,False],
    ... '0:none 1:one 2:two 3:three 255:max')
    'two'
    >>> decode_enum_bits([True, True, False, False, False, False,False,False],
    ... '0:none 1:one 2:two 3:three 255:max')
    'three'
    >>> decode_enum_bits([True, True, True, True, True, True, True, True],
    ... '0:none 1:one 2:two 3:three 255:max')
    'max'
    >>> decode_enum_bits([True, True, True, True, False, False, False, False],
    ... '0:none 1:one 2:two 3:three 255:max')
    Traceback (most recent call last):
    IndexError: unknown enum index 15
    """
    nbits = len(bits)
    enumvals = parse_enum_dict(enum_def_str, idx_to_string=True)
    idx = sum([to_int(bits[i])<<i for i in range(nbits)])
    if idx in enumvals:
        return enumvals[idx]
    else:
        raise IndexError("unknown enum index %d" % idx)

def to_charset(bits, CHR, NBITS):
    """
    given an array of booleans representing a bit vector, encode it as
    a sequence of chars from the given charmap.

    >>> to_charset([0], 'abcd', 2)
    'a'
    >>> to_charset([0,0], 'abcd', 2)
    'a'
    >>> to_charset([0,0,0], 'abcd', 2)
    'aa'
    >>> to_charset([0,0,0,0], 'abcd', 2)
    'aa'
    >>> to_charset([1], 'abcd', 2)
    'b'
    >>> to_charset([1,1], 'abcd', 2)
    'd'
    >>> to_charset([1,1,1], 'abcd', 2)
    'db'
    >>> to_charset([1,1,1,1], 'abcd', 2)
    'dd'
    >>> to_charset(encode_int(12345, nbits=16), 'abcd', 2)
    'bcdaaada'
    """
    nchars = (len(bits)+NBITS-1)/NBITS
    bits = bits + [False]*(nchars*NBITS - len(bits)) # pad to even char width
    chars = [CHR[sum([bits[i+j*NBITS]<<i for i in range(NBITS)])]
             for j in range(nchars)]
    return "".join(chars)

def from_charset(str, ORD, NBITS):
    """
    given a string of chars, and a mapping from those chars to bits,
    decode the string into a boolean array bit vector.

    >>> from_charset('bcdaaada', {'a':0,'b':1,'c':2,'d':3}, 2)
    [True, False, False, True, True, True, False, False, False, False, False, False, True, True, False, False]
    >>> decode_int_bits(from_charset(to_charset(encode_int(12345, nbits=16), 
    ...                                         'abcd', 2), 
    ...                              {'a':0,'b':1,'c':2,'d':3}, 2))
    12345
    """
    return [bool(ORD[c]&(1<<i)) for c in str for i in range(NBITS)]

def to_binary(str):
    return to_charset(str, "01", 1)

def from_binary(bits):
    return from_charset(bits, {'0':0, '1':1}, 1)

HEX_CHR = digits+'abcdef'
HEX_ORD = dict([(HEX_CHR[i],i) for i in range(16)])

def to_hex(bits):
    return to_charset(bits, HEX_CHR, 4)

def from_hex(str):
    return from_charset(str.lower(), HEX_ORD, 4)

# DNS encoding is clumsier, it uses the 62 alphanumeric chars
DNS_CHR = digits + ascii_uppercase + ascii_lowercase
DNS_ORD = dict([(DNS_CHR[i],i) for i in range(len(DNS_CHR))])

def to_dns(product, bits):
    """
    convert the bits into the base 62 DNS status string with product prefix
    
    >>> to_dns("SHA", [1])
    'SHA-1-1'
    >>> to_dns("SHA", [1,1,1,1,0,0,0,0,1,1,1,1])
    'SHA-10B-E'
    """
    status_int = 0
    for i,s in enumerate(bits):
        status_int += (1L<<i)*to_int(s or 0)
    (i, status, checkdigit) = (0, "", 0)
    while status_int != 0:
        (status_int, ord) = divmod(status_int, 62)
        status += DNS_CHR[ord]
        checkdigit += (i+1)*ord
        i += 1
    checkchr = DNS_CHR[checkdigit % 62]
    return product + "-" + status[::-1] + "-" + checkchr

def from_dns(status, nbits):
    """
    decode the base-62 dns status string, return array of status bits
    and product string.
    
    >>> from_dns('SHA-1-1',1)
    ('SHA', [True])
    >>> from_dns('SHA-10B-E', 12)
    ('SHA', [True, True, True, True, False, False, False, False, True, True, True, True])
    """
    base = len(DNS_CHR)
    try:
        (product,statstr,check) = status.split("-")
    except:
        raise Exception("Malformed status word '%s'" % status)
    status_int, check_digit = 0,0
    for i,s in enumerate(statstr):
        status_int = status_int * base + DNS_ORD[s]
    for i,s in enumerate(statstr[::-1]):
        check_digit += (i+1)*DNS_ORD[s]
    check_chr = DNS_CHR[check_digit % 62]
    assert check_chr == status[-1], "bad checksum, got %s, computed %s" % \
           (status[-1], check_chr)
    return product, [bool(status_int&(1L<<i)) for i in range(nbits)]

def decode_ascii(ascii, spec):
    """
    decode an ascii representation of a status word and return
    its values in a dictionary (keyed by the node names in the spec)
    """
    #
    # decode entire string according to the spec
    #
    (product,statstr,check) = ascii.split("-")
    if statstr.startswith("0x"):
        status_bits = from_hex(statstr[2:])
    elif ascii.startswith("0b"):
        status_bits = from_binary(statstr[2:])
    else:
        nbits = to_int(spec.getAttribute("nbits"))
        (product, status_bits) = from_dns(ascii, nbits)
    return decode(status_bits, spec)


def compute_dns_length(spec):
    """
    compute the max length of a status string under the given spec.
    this includes product and checksum characters.
    spec must have had compute_defaults called already.
    """
    nbits = to_int(spec.getAttribute('nbits') or 0)
    bits = [True]*nbits
    chars = to_dns(spec.getAttribute('product'), bits)
    return len(chars)
    
def check_wordlengths(xml_text, verbose=False):
    """
    compute the maximum wordlength for each spec in the xml file and 
    check against limits.
    """
    xml_nodes = minidom.parseString(xml_text)
    for node in xml_nodes.getElementsByTagName('status'):
        attrs = dict(node.attributes.items())
        if (attrs.get('type') == 'heartbeat'):
            prod = attrs.get('product')
            compute_defaults(node, False)
            nc = compute_dns_length(node)
            nb = to_int(node.getAttribute('nbits') or 0)
            if nc > 63:
                print "Fail: product %s is length %d (%d bits), " % (
                    prod, nc, nb), "cannot exceed 63 (338 bits)"
            elif verbose:
                print "product %s is length %d (%d bits), " % (prod, nc, nb)

def main():

    parser = OptionParser(usage="""
    %prog [options] heartbeat.xml|release [status]

    Decode or fetch heartbeat status values according to the spec
    in heartbeat.xml or the spec associated with the named release. 
    
    If status is given as the second argment, decode it to extract its
    values. Status is assumed to be in our DNS ASCII encoding. The
    product in the status string will be used rather than any --product arg.

    If no status is given to decode, get values by executing the
    queries and shell commands in heartbeat.xml.  Write the values to
    stdout in ASCII dns encoding, unless a different encoding is
    specified with -v, -b, or -x
    """)
    parser.add_option("-n", "--dryrun", action="store_true",
                      help="read name=value pairs from stdin instead of "
                      "executing queries from heartbeat.xml")
    parser.add_option("-x", "--hex", action="store_true",
                      help="output status as ascii hex ('0xABCD')")
    parser.add_option("-b", "--binary", action="store_true",
                      help="output status as ascii binary ('0b01101')")
    parser.add_option("-v", "--verbose", action="store_true",
                      help="output in human-readble name=value form")
    parser.add_option("-#", "--showbits", action="store_true",
                      help="output absolute bit position for each item (implies dryrun)")
    parser.add_option("--product","-p", default="SHA",
                      help="encode this product status (default=%default)")
    parser.add_option("--type", default="heartbeat",
                      help="encode this status type (default=%default)")
    parser.add_option("--test", action="store_true", help="run doctests")
    parser.add_option("--svn", action="store_true", 
                      help="print svn url for the specified release")
    parser.add_option("--xml", action="store_true", 
                      help="print xml for the specified release")

    (opts, args) = parser.parse_args()

    if opts.verbose:
        level = logging.INFO
    elif opts.test:
        level = logging.ERROR
    else:
        level = logging.WARN
    logging.basicConfig(stream=sys.stderr, level=level,
                        format='%(asctime)s %(levelname)s %(message)s',
                        datefmt='%b-%d %H:%M:%S')
    if not len(args):
        parser.error("You must give a heartbeat.xml file or a release string")

    if len(args)==2:
        #
        # get the product from the status word
        #
        try:
            (opts.product,statstr,check) = args[1].split("-")
        except:
            parser.error("Malformed status string %s" % args[1])
    #
    # get XML for the heartbeat specification
    #
    if os.path.exists(args[0]):
        xml_text = open(args[0]).read()
    elif opts.svn:
        print release_to_heartbeat_url(opts.product,args[0])
        sys.exit()
    else:
        xml_text = release_to_heartbeat_xml(opts.product,args[0])
    if opts.xml:
        print xml_text
        sys.exit()

    if opts.test:
        #
        # run the doctests. These are intentionally limited to tests
        # that can be run with no external resources (eg, on an
        # appliance without access to /mnt/builds). Grander tests live
        # over in heartbeat-unittest.py
        # This also checks the status word lengths of each spec in
        # the specified heartbeat.xml
        #
        import doctest
        doctest.testmod()
        check_wordlengths(xml_text, opts.verbose)
        sys.exit()
    
    try:
        xml_nodes = minidom.parseString(xml_text)
    except Exception, e:
        parser.error("Parsing xml specification for %s: %s" % \
                         (args[0], str(e)))
    spec = get_spec(xml_nodes, opts.type, opts.product, opts.showbits)
    assert spec, "No matching spec for %s found in %s"% (opts.product, args[0])
    #
    # get status, either by querying mgmt or decoding a command-line arg
    #
    if len(args) > 1:
        values = decode_ascii(args[1], spec)
        opts.product = spec.getAttribute('product')
    elif opts.dryrun or opts.showbits:
        items = sys.stdin.read().strip().split('\n')
        values = dict([item.split('=') for item in items])
    else:
        values = execute(spec, opts.verbose)
    assert values, "No values decoded for %s using %s"% (opts.product, args[0])
    #
    # encode and output status values
    #
    status_bits = [False] * to_int(spec.getAttribute('nbits'))
    status_bits = encode(values, spec, status_bits, opts.verbose)
    if opts.hex:
        print "0x"+to_hex(status_bits)
    elif opts.binary:
        print "0b"+to_binary(status_bits)
    elif opts.verbose:
        # do a full encode/decode to capture truncation effects
        values = decode(status_bits, spec)
        pairs = ["%s=%s" % name_value for name_value in values.items()]
        pairs.sort()
        print "\n".join(pairs)
    else:
        print to_dns(opts.product, status_bits)

if __name__ == "__main__":
    sys.exit(main())
