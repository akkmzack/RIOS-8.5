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

import sys
import os
import os.path
import traceback
import re
import shlex
from xml.dom import minidom
import subprocess
from optparse import OptionParser
from string import capwords, ascii_lowercase, ascii_uppercase, digits
import math
import logging

DNS_SERVER = "updates.riverbed.com"
DNS_TEST_SERVER = "updtest.riverbed.com"

class DNSError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def log():
    return logging.getLogger(__name__)

def get_command_output(cmd, check_exit=False, use_shell=False, silent=False):
    """
    Execute a command and return its output or None, forwarding any
    error output to the logging stream and catching any exceptions.
    (why is this so hard?)

    If cmd is a list, cmd[0] is executed directly.

    If cmd is a string and use_shell is not set, then shlex() splits
    cmd into a list, and cmd[0] is executed directly, as above.

    If cmd is a string and use_shell is set, /bin/sh -c 'cmd' is used,
    thus allowing shell expansions. This is not encouraged.

    Return the shell output as a byte string, stripped of extra spaces.

    if check_exit=True and there's a nonzero exit code, log an error
    and return None. It defaults to False because so many exec scripts
    are sloppy about letting nonzero error codes come back.

    if silent=True, don't log error output.
    """
    text = None
    try:
        if type(cmd) != list:
            cmd = shlex.split(cmd)
        log().debug("cmd = %s" % repr(cmd))
        if not os.path.exists(cmd[0]): # avoid popen leaking fds on error
            raise Exception("no such executable %s" % cmd[0])
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, 
                             stderr=subprocess.PIPE)
        (text,err) = p.communicate()
        if check_exit and p.returncode:
            raise Exception("exit code %s, output: %s" % (
                    p.returncode, str(text)+str(err)))
        if err:
            raise Exception(err)
        text = text.strip()
    except Exception, e:
        if not silent:
            log().error("error running %s: %s" % (repr(cmd), e))
            log().debug(traceback.format_exc())
    return text
    
def query_mfdb(path):
    """
    shell out to query the given path in the mfdb on the appliance,
    return its text value.
    """
    return get_command_output(['/opt/tms/bin/mddbreq', '-v', '/config/mfg/mfdb', 
                         'query', 'get', '-', path])

def xml_to_spec(prod, xml_text):
    """
    parse the xml and extract the spec for the named product abbrev.
    """
    try:
        xml_nodes = xml_text and minidom.parseString(xml_text)
        return xml_nodes and get_spec(xml_nodes, "heartbeat", prod)
    except Exception, e:
        log().error("Parsing xml specification: %s" % str(e))
    return None

def to_int(s, default=''):
    """
    parse a decimal or hexidecimal int string, or truncate a float.
    if s is an empty string or None, process the supplied default.
    raise ValueError if something goes wrong (note that you must override
    default if you want an unexceptional default)

    >>> to_int("12") == 12
    True
    >>> to_int(0xFFFF) == 65535
    True
    >>> to_int("0xFFFF") == 65535
    True
    >>> to_int(23.4) == 23
    True
    >>> to_int("", "0") == 0
    True
    >>> to_int(0) == 0
    True
    >>> to_int("")
    Traceback (most recent call last):
        ...
    ValueError: to_int: expecting an integer value:  is empty or None
    """
    if s == '' or s == None:
        s = default
    if s == '' or s == None:
        raise ValueError("to_int: expecting an integer value: %s is empty or None" % s)
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
    ValueError: to_bool: expecting an integer, or 'true' or 'false', input '' is empty or None
    >>> to_bool("")
    Traceback (most recent call last):
        ...
    ValueError: to_bool: expecting an integer, or 'true' or 'false', input '' is empty or None
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
        raise ValueError("to_bool: expecting an integer, or 'true' or 'false', input '%s' is empty or None" % s)
    if isinstance(s,basestring) and s.isdigit():
        return bool(to_int(s))
    elif isinstance(s,basestring):
        return s.lower()!="false"
    else:
        return bool(s)

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

def get_item_stype(spec, dotname):
    """
    Return the 'stype' for the item, a string in ('int', 'bool',
    'char', 'enum') or None if dotname is not in this spec.
    """
    item = get_item(spec, dotname)
    if not item:
        return None
    return item.getAttribute('type')

def get_item_type(spec, dotname):
    """
    Return a native python item value types (bool/int/str),
    from the given spec for the named node. These are the 
    return types of items after decoding: 1-bit ints are 
    type bool, and enums are type str.
    """
    stype = get_item_stype(spec, dotname)
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

def get_item_description(spec, dotname):
    """
    Return the description for this dotname
    """
    item = get_item(spec, dotname)
    if not item:
        return None
    return item.getAttribute('description')

def get_item_email(spec, dotname):
    """
    Return the email for this dotname
    """
    item = get_item(spec, dotname)
    if not item:
        return None
    return item.getAttribute('email')

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

def execute(spec, verbose=False, check_exit=False):
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
                value = get_command_output(str(execstr % value),
                                   check_exit=check_exit) 
                if verbose:
                    log().info( "  ==> %s" % value)
            values[key] = value
    return values

def values_to_bits(values, spec, verbose=False):
    """
    given a dictionary of string or native values corresponding to
    item nodes in the status spec, transform them and then pack their
    bits as indicated by the spec into a boolean array. 
    Throw an exception if there are unused values. 
    """
    values = values and values.copy() # we're gonna destroy this thing
    status_bits = [False] * to_int(spec.getAttribute('nbits'))
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
        ...
    KeyError: "unknown enum value 'min' and unknown default '', will be transmitted as 'none'"
    >>> encode_enum("", "0:none 1:one 2:two 3:three 255:max",8)
    Traceback (most recent call last):
        ...
    KeyError: "unknown enum value '' and unknown default '', will be transmitted as 'none'"
    >>> encode_enum("", "0:none 1:one 2:two 3:three 255:max",8, "none")
    [False, False, False, False, False, False, False, False]
    >>> encode_enum("bleat", "0:none 1:one 2:two 3:error ", 2, "my_default")
    Traceback (most recent call last):
        ...
    KeyError: "unknown enum value 'bleat' and unknown default 'my_default', will be transmitted as 'none'"
    >>> encode_enum("bleat", "0:none 1:one 2:two 3:unknown ", 2, "unknown")
    [True, True]
    >>> encode_enum("", "0:none 1:one 2:two 3:unknown ", 2, "unknown")
    [True, True]
    >>> encode_enum('1', "0:0 1:100 2:101 3:102 4:200 5:201 6:202 7: ", 3)
    [True, True, True]
    >>> encode_enum('1', "0:0 1:100 2:101 3:102 4:200 5:201 6:202 7:invalid", 3,"invalid" )
    [True, True, True]
    """
    enumidxs = parse_enum_dict(enum_def_str)
    #
    # three possibilities: 
    # 1. value is not in enumidxs, nor is default, log an error and send 0
    # 2. value is not in enumidxs, but default is, send default
    # 3. value is in the enumidxs, send value
    #
    if value not in enumidxs and default not in enumidxs:
        idx_names = parse_enum_dict(enum_def_str, idx_to_string=True)
        msg = "unknown enum value '%s' and unknown default '%s', " % (
            value, default)
        msg += "will be transmitted as '%s'" % idx_names[0]
        raise KeyError(msg)
    elif value not in enumidxs:
        value = default 
    assert value in enumidxs
    idx = to_int(enumidxs[value])
    bits = [bool(idx&(1<<i)) for i in range(nbits)]
    return bits

def bits_to_values(status_bits, spec):
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

    >>> decode_int_bits(encode_int(0, nbits=8)) == 0
    True
    >>> decode_int_bits(encode_int(1, nbits=8)) == 1
    True
    >>> decode_int_bits(encode_int(254, nbits=8)) == 254
    True
    >>> decode_int_bits(encode_int(255, nbits=8)) == 255
    True
    >>> decode_int_bits(encode_int(256, nbits=8)) == 255
    True
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
    ...                 sigbits=3, scale=10) == 0
    True
    >>> decode_int_bits(encode_int(10, nbits=5, sigbits=3, scale=10),
    ...                 sigbits=3, scale=10) == 10
    True
    >>> decode_int_bits(encode_int(11, nbits=5, sigbits=3, scale=10),
    ...                 sigbits=3, scale=10) == 20
    True
    >>> decode_int_bits(encode_int(80, nbits=5, sigbits=3, scale=10),
    ...                 sigbits=3, scale=10) == 80
    True
    >>> decode_int_bits(encode_int(90, nbits=5, sigbits=3, scale=10),
    ...                 sigbits=3, scale=10) == 80
    True
    >>> decode_int_bits(encode_int(550, nbits=5, sigbits=3, scale=10),
    ...                 sigbits=3, scale=10) == 480
    True
    >>> decode_int_bits(encode_int(560, nbits=5, sigbits=3, scale=10),
    ...                 sigbits=3, scale=10) == 560
    True
    >>> decode_int_bits(encode_int(570, nbits=5, sigbits=3, scale=10),
    ...                 sigbits=3, scale=10) == 560
    True
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
    CHR is a list of characters, and the index of each is its integer value
    in the encoding.
    NBITS is the number of bits we expect to encode in a single character

    Only use this for charsets whose lengths are powers of 2

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
    ORD is a dictionary mapping characters to integers.
    NBITS is the number of bits in each of ORD's integers.
    
    Only use this for charsets whose lengths are powers of 2

    >>> from_charset('bcdaaada', {'a':0,'b':1,'c':2,'d':3}, 2) == [
    ... True, False, False, True, True, True, False, False, False, False, 
    ... False, False, True, True, False, False]
    True
    >>> decode_int_bits(from_charset(to_charset(encode_int(12345, nbits=16), 
    ...                                         'abcd', 2), 
    ...                              {'a':0,'b':1,'c':2,'d':3}, 2)) == 12345
    True
    """
    return [bool(ORD[c]&(1<<i)) for c in str for i in range(NBITS)]

def to_binary(bits):
    return to_charset(bits, "01", 1)

def from_binary(str):
    return from_charset(str, {'0':0, '1':1}, 1)

HEX_CHR = digits+'abcdef'
HEX_ORD = dict([(HEX_CHR[i],i) for i in range(16)])

def to_hex(bits):
    return to_charset(bits, HEX_CHR, 4)

def from_hex(str):
    return from_charset(str.lower(), HEX_ORD, 4)

# DNS encoding is clumsier...
V0_CHR = digits + ascii_uppercase + ascii_lowercase
V0_ORD = dict([(V0_CHR[i],i) for i in range(len(V0_CHR))])

V1_CHR = digits + ascii_lowercase # reserving '-' because it seems so useful
V1_ORD = dict([(V1_CHR[i],i) for i in range(len(V1_CHR))])

def splitn(seq, size):
    """
    split the sequence into a list of subsequences of length size,
    with any extra as the last item in the list
    """
    return (seq[pos:pos + size] for pos in xrange(0, len(seq), size))

def dns_checkchr(s):
    """
    compute the 1-character checksum for the given string.
    used in the V0 dns status word encoding.
    >>> dns_checkchr("")
    '0'
    >>> dns_checkchr("a")
    'a'
    >>> dns_checkchr("aa")
    'k'
    >>> dns_checkchr("3KmAxYxZ1jxTF2LSEOvpkQNTyB8714B16H9cldUb2p09626n")
    'K'
    """
    checksum = sum([(i+1)*V0_ORD[char] for (i,char) in enumerate(s[::-1])])
    return V0_CHR[checksum % len(V0_CHR)]

def bits_to_body(bits, DNS_CHR):
    """
    convert the given bits into our DNS status string using the given charset.
    returns a string of the form abcdefghijklmnop (the "body" part of the 
    status word, no dots or checksums). 
    >>> bits_to_body([False], V0_CHR)
    '0'
    >>> bits_to_body([True,False,True], 'abcd')
    'bb'
    >>> bits_to_body([True,False,True], V0_CHR)
    '5'
    >>> bits_to_body([True,False,True], V1_CHR)
    '5'
    >>> bits_to_body([True]*32, V0_CHR)
    '4gfFC3'
    >>> bits_to_body([True]*32, V1_CHR)
    '1z141z3'
    """
    #
    # this is just a conversion of a base-2 representation to a base-n
    # representation using a given character set for the base-n digits
    #
    status_int = 0
    base = len(DNS_CHR)
    for i,s in enumerate(bits):
        status_int += (1L<<i)*to_int(s or 0)
    status = ""
    while status_int != 0:
        (status_int, cord) = divmod(status_int, base)
        status = DNS_CHR[cord] + status
    return status or '0'


def body_to_bits(body, DNS_ORD, spec_nbits):
    """
    decode the body of the status string into an array of status
    bits using the specified character ordering. spec_nbits is the
    length of the resulting status bit array, from the heartbeat.xml
    spec associated with this status word, and is needed to do
    zero-padding for short strings.  status is of the form 'abcdefg'
    (the "body" part of the status word, no dots or checksum)

    >>> body_to_bits('4gfFC3', V0_ORD, 32) == [True]*32
    True
    >>> body_to_bits('1z141z3', V1_ORD, 32) == [True]*32
    True
    """
    base = len(DNS_ORD)
    status_int = 0
    for i,s in enumerate(body):
        status_int = status_int * base + DNS_ORD[s]
    return [bool(status_int&(1L<<i)) for i in range(spec_nbits)]

def parsed_status_to_values(parsed_status, spec):
    """
    convert the parsed prod_status dictionary to bits and then decode the bits
    into status item values based on the spec. 
    """
    nbits = to_int(spec.getAttribute('nbits') or 0)
    bits = body_to_bits(parsed_status['dns_body'], parsed_status['dns_ord'], 
                        nbits)
    return bits_to_values(bits, spec)

def parse_prod_status(prod_status):
    """
    parse out the dns_version and dns_prod from the provided
    prod_status, return as a dictionary.
    prod_status should be as returned by parse_fqdn, containing 
    no 'packaging' characters, eg, 1SHA-blargityblargh,
    complains about illegal characters, but ignores any trailing
    '-0' on a v1 status string, though it should not be there.

    >>> parse_prod_status("FOO-abcdefghijklmnop-Z") == dict(
    ... dns_version=0, dns_prod='FOO', dns_body='abcdefghijklmnop',
    ... status_word="FOO-abcdefghijklmnop-Z", dns_ord=V0_ORD)
    True
    >>> parse_prod_status("FOO-abcdefghijklmnop") == dict(
    ... dns_version=0, dns_prod='FOO', dns_body='abcdefghijklmnop',
    ... status_word="FOO-abcdefghijklmnop", dns_ord=V0_ORD)
    True
    >>> parse_prod_status("1FOO-abcdefghijklmnop") == dict(
    ... dns_version=1, dns_prod='FOO', dns_body='abcdefghijklmnop',
    ... status_word="1FOO-abcdefghijklmnop", dns_ord=V1_ORD)
    True
    >>> parse_prod_status("1FOO-ABCDEFGHIJKLMNOP") == dict(
    ... dns_version=1, dns_prod='FOO', dns_body='abcdefghijklmnop',
    ... status_word="1FOO-ABCDEFGHIJKLMNOP", dns_ord=V1_ORD)
    True
    >>> parse_prod_status("1FOO-abcdefg/hijklmnop")
    Traceback (most recent call last):
        ...
    DNSError: 'illegal characters in status body abcdefg/hijklmnop'
    >>> parse_prod_status("1FOO-abcdefg-hijklmnop")
    Traceback (most recent call last):
        ...
    DNSError: 'illegal characters in status body abcdefg-hijklmnop'
    >>> parse_prod_status("1FOO-abcdefghijklmnop-0") == dict(
    ... dns_version=1, dns_prod='FOO', dns_body='abcdefghijklmnop',
    ... status_word="1FOO-abcdefghijklmnop-0", dns_ord=V1_ORD)
    True
    >>> parse_prod_status("1FOO-abcdefg/hijklmnop")
    Traceback (most recent call last):
        ...
    DNSError: 'illegal characters in status body abcdefg/hijklmnop'
    """
    if prod_status.count('-') == 0:
        raise DNSError("status should have a dash after PROD: %s" % prod_status)
    if not prod_status[0].isdigit(): # v0
        dns_version = 0
        dns_ord = V0_ORD
        (dns_prod,dns_body) = prod_status.split('-',1)
        dns_body = dns_body.split('-')[0] # dns_body will not have the checksum
        if dns_prod.upper() != dns_prod:
            # We always send these in all uppper case. Someone's havin a go.
            raise DNSError("case-squashed V0 status word: %s" % prod_status)
    else: # v > 0
        dns_version = int(prod_status[0])
        dns_ord = V1_ORD
        (dns_prod,dns_body) = prod_status[1:].split('-',1)
        if dns_body.endswith('-0'):
            dns_body = dns_body[:-2]  # quietly throw away any '-0'
        dns_body = dns_body.lower()
    if sum([not dns_ord.has_key(c) for c in dns_body]) > 0:
        raise DNSError("illegal characters in status body %s" % dns_body)
    return dict(status_word=prod_status,
                dns_prod=dns_prod,
                dns_ord=dns_ord,
                dns_version=dns_version,
                dns_body=dns_body)

def parse_fqdn(fqdn, dns_server=DNS_SERVER):
    """
    break a fqdn into heartbeat fields, for writing into the raw
    heartbeats database.  fqdn is the sequence of dotted components we
    read from a line in the DNS request log:

        serial.model.uptime.svcuptime.status...word.version.updates.riverbed.com

    It may be a V0 or V1 format (the uptime info and status word are
    formatted differently for V0 and V1).  status_word is not further
    decoded here (a spec needs to be looked up in the release
    database), but it is reformatted to remove any characters not
    related to the bits_to_body/body_to_bits encoding. The returned
    status word will be either a V0 form:
        SHA-abcdefg-X
    or a V1 form:
        1SHA-abcdefg
    or a degenerate '0' if no status was included in the dns fqdn.

    Version 0 tests:
    >>> parse_fqdn('A16GG00012345.100.0.0.0.6.5.0.updates.riverbed.com'
    ... ) == { 'uptime': 0, 'status_word': '0', 'version': '6.5.0', 
    ... 'serial': 'A16GG00012345', 'model': '100', 'service_uptime': 0, 
    ... 'dns_version': 0, 'dns_prod':'0'}
    True
    >>> parse_fqdn(
    ... 'A16GG00012345.100.123.456.SHA-0-0.6.5.0.updates.riverbed.com') == {
    ... 'uptime': 123, 'status_word': 'SHA-0-0', 'version': '6.5.0', 
    ... 'serial': 'A16GG00012345', 'model': '100', 'service_uptime': 456, 
    ... 'dns_version': 0, 'dns_prod':'SHA'}
    True

    Version 1 tests:
    >>> parse_fqdn(
    ... 'A16GG00012345.100.0.0.1SHA-0-0.6.5.0.updates.riverbed.com')=={
    ... 'serial': 'A16GG00012345', 'status_word': '1SHA-0', 'model': '100', 
    ... 'version': '6.5.0', 'dns_version': 1, 'uptime':0, 'service_uptime':0, 
    ... 'dns_prod':'SHA'}
    True
    >>> parse_fqdn(
    ... 'A16GG00012345.100.qglj.4k241.1SHA-1.2-0.6.5.0.updates.riverbed.com'
    ... ) == {'serial': 'A16GG00012345', 'status_word': '1SHA-12', 
    ... 'model': '100', 'version': '6.5.0', 'dns_version': 1,
    ... 'uptime':1234567, 'service_uptime':7654321, 'dns_prod':'SHA'}
    True
    
    """
    if not fqdn.lower().endswith("."+dns_server):
        raise DNSError("Malformed DNS fqdn '%s' (incorrect DNS suffix " \
                        "- does not match %s)" % (fqdn, dns_server))
    components = fqdn.split('.')
    if len(components) < 7:
        raise DNSError("Malformed DNS fqdn '%s' (too few components)" % fqdn)
    rc = {}
    rc['serial'] = components[0]
    rc['model'] = components[1]
    rc['uptime'] = components[2]
    rc['service_uptime'] = components[3]
    header = components[4]
    if header[0]=='0' or not header[0].isdigit():
        #
        # v0:
        # serial.model.up.svcup.status.version.updates.riverbed.com
        # 
        rc['dns_version'] = 0
        rc['dns_prod'] = components[4].split('-')[0]
        if len(components) < 9:
            raise DNSError("Malformed DNS '%s' (too few components)" % fqdn)
        rc['uptime'] = int(rc['uptime'])
        rc['service_uptime'] = int(rc['service_uptime'])
        rc['status_word'] = components[4]
        rc['version'] = '.'.join(components[5:len(components)-3])
    elif header[0] == '1': 
        #
        # v1: 
        # serial.model.up.svcup.1nPROD-c1...cn.version.updates.riverbed.com
        # where uptimes are encoded as 32-bit ints with leading 0,
        # and header is 1nPROD, n is component count (digit),
        # and PROD is the three-letter product abbreviation for
        # looking up the status spec in heartbeat.xml (though we
        # tolerate abbrevs with different lengths in this
        # decoder). Component count is the number of body components
        # including the header before the software version starts. 0
        # means there is no status word, and the next component
        # begins the software version.
        #
        (prod, body, therest) = ''.join(components[4:]).split('-',2)
        #
        # uptime and service uptime are encoded as a 64 bit in the V1
        # character encoding to be split into 2 32-bit ints
        #
        rc['dns_version'] = 1
        rc['dns_prod'] = prod[1:]
        try:
            rc['uptime'] = decode_int_bits(body_to_bits(rc['uptime'], V1_ORD, 32))
        except:
            raise DNSError("Malformed DNS uptime '%s' in '%s'" % (
                    rc['uptime'], fqdn))
        try:
            rc['service_uptime'] = decode_int_bits(
                body_to_bits(rc['service_uptime'], V1_ORD, 32))
        except:
            raise DNSError("Malformed DNS service uptime '%s' in '%s'" % (
                    rc['service_uptime'], fqdn))
        rc['status_word'] = "1%s-%s" % (rc['dns_prod'], body.lower())
        (dprod, dbody, dversion) = '.'.join(components[4:-3]).split('-',2)
        rc['version'] = dversion[2:] # skip the leftover leading dot
    else:
        raise DNSError("Malformed DNS status header '%s' in '%s'" % (
                header, fqdn))
    return rc

def bits_to_prod_status(bits, dns_prod, dns_version):
    """
    format the bits into a prod_status word like the output of
    parse_fqdn() (no uptimes or extra dots).
    dns_prod is the 2,3-letter product abbreviation that identifies the
    spec to use within a heartbeat.xml file (eg, SHA, EX).
    dns_version is the dns encoding vesion integer (0, 1)
    """
    if dns_version == 0:
        body = bits_to_body(bits, V0_CHR)
        prod_status = "%s-%s-%s" % (dns_prod, body, dns_checkchr(body))
    elif dns_version == 1:
        body = bits_to_body(bits, V1_CHR)
        prod_status = "1%s-%s" % (dns_prod, body)
    else:
        raise DNSError("Bad dns_version: %s. Not gonna encode it" % dns_version)
    return prod_status

def prod_status_to_fqdn_status(prod_status, octet_len=62):
    """
    format the prod_status (eg, 1SHA-blargityblarg) into the status
    part of a fqdn status word, by adding dots to break up long spans
    and placing a trailing '-' at the end of the status word if needed.
    the default octet_len of 62 is the maxuimum length allowed for
    a dotted dns segment. Shorter values are useful for testing.

    we don't pass in a dns_version because it's already implicit in
    how the prod_status is encoded.

    >>> prod_status_to_fqdn_status('SHA-blargityblargityblargit-k')
    'SHA-blargityblargityblargit-k'
    >>> prod_status_to_fqdn_status('SHA-blargityblargityblargit-k', 
    ... octet_len=10)
    Traceback (most recent call last):
        ...
    DNSError: 'v0 status word is too long: SHA-blargityblargityblargit-k'
    >>> prod_status_to_fqdn_status('1SHA-0', octet_len=10)
    '1SHA-0-0'
    >>> prod_status_to_fqdn_status('1SHA-01', octet_len=10)
    '1SHA-01-0'
    >>> prod_status_to_fqdn_status('1SHA-012', octet_len=10)
    '1SHA-012-0'
    >>> prod_status_to_fqdn_status('1SHA-0123', octet_len=10)
    '1SHA-012.3-0'
    >>> prod_status_to_fqdn_status('1SHA-01234', octet_len=10)
    '1SHA-0123.4-0'
    >>> prod_status_to_fqdn_status('1SHA-012345', octet_len=10)
    '1SHA-01234.5-0'
    >>> prod_status_to_fqdn_status('1SHA-0123456789', octet_len=10)
    '1SHA-01234.56789-0'
    >>> prod_status_to_fqdn_status('1SHA-012345678901234', octet_len=10)
    '1SHA-01234.567890123.4-0'
    >>> prod_status_to_fqdn_status('1SHA-blargityblargityblargit', octet_len=10)
    '1SHA-blarg.ityblargit.yblargit-0'
    >>> prod_status_to_fqdn_status('2SHA-blargityblargityblargit', octet_len=10)
    Traceback (most recent call last):
        ...
    DNSError: 'Bad version: 2. Not gonna encode it'
    """
    (prod, body) = prod_status.split('-',1)
    if prod[0].isalpha():
        # V0
        fqdn_status = prod_status
        if len(fqdn_status) > octet_len:
            raise DNSError("v0 status word is too long: %s" % fqdn_status)
    elif prod[0] == '1':
        # V1
        if len(prod_status) <= octet_len - 2:
            fqdn_status = prod_status + '-0' 
        else:
            #
            # break up a long one with dots. we do tricks with the
            # suffix that would not work on a very short one.
            #
            suffix = body[-1] + '-0'
            head = body[:-1] # important to do this before getting prefix!
            prefix_len = octet_len-len(prod)-1 # leave room for PROD-
            prefix = head[:prefix_len]
            middle = head[prefix_len:] 
            if middle == '':
                fqdn_status = "%s-%s.%s" % (prod, prefix, suffix)
            else:
                octets = list(splitn(middle, octet_len))
                if len(octets[-1]) + len(suffix) <= octet_len:
                    octets[-1] = octets[-1] + suffix
                else:
                    octets.append(suffix)
                fqdn_status = "%s-%s.%s" % (prod, prefix, '.'.join(octets))
    else:
        raise DNSError("Bad version: %s. Not gonna encode it" % prod[0])
    return fqdn_status

def compute_dns_length(spec, dns_version):
    """
    compute the relevant max length of a status string under the given spec.
    this includes dns_prod and checksum, but not other fqdn cruft
    like uptimes or component dots.
    """
    nbits = to_int(spec.getAttribute('nbits') or 0)
    bits = [True]*nbits
    chars = bits_to_prod_status(bits, spec.getAttribute('product'), dns_version)
    return len(chars)

def check_wordlengths(heartbeat_xml_text, dns_version, verbose=False):
    """
    compute the maximum wordlength for each spec in the xml file and 
    check against limits. Note this processes the entire heartbeat.xml
    file.
    """
    nodes = minidom.parseString(heartbeat_xml_text)
    for node in nodes.getElementsByTagName('status'):
        attrs = dict(node.attributes.items())
        if (attrs.get('type') == 'heartbeat'):
            prod = attrs.get('product')
            compute_defaults(node, False)
            nc = compute_dns_length(node, dns_version)
            nb = to_int(node.getAttribute('nbits') or 0)
            if dns_version == 0 and nc > 63:
                print "Fail: product %s is length %d (%d bits), " % (
                    prod, nc, nb)
            # http://bugzilla.nbttech.com/show_bug.cgi?id=92058#c7
            elif dns_version > 0 and nc > 191:
                print "Fail: product %s is length %d (%d bits), " % (
                    prod, nc, nb)
            if verbose:
                print "product %s is length %d (%d bits), " % (prod, nc, nb)
    if verbose:
        if dns_version == 0:
            print "(maximum status length is 63 characters, 338 1/3 bits)"
        elif dns_version > 0:
            print "(maximum allowed total length is 191 characters, 995 bits)"

def get_dns_prod(mobo=None):
    """
    query the appliance environment for the dns_prod.
    """
    prod_id = os.environ.get('BUILD_PROD_ID')
    mobo = mobo or get_command_output(['/opt/hal/bin/hal', 'get_motherboard'])
    if mobo == 'VM': 
        prod_id = 'V' + prod_id
    dns_prod = { 'SH':   'SHA',
                 'GW':   'SMC',
                 'VGW':  'SVE',
                 'VCMC': 'CMC',
                 'VCB':  'CB' }.get(prod_id, prod_id)
    return dns_prod

def format_fqdn(dns_version, status_bits, 
                version=None, model=None, serial=None, 
                uptime=None, serviceup=None, dns_prod=None,
                mobo=None, dns_server=DNS_SERVER):
    """
    construct full DNS lookup name. Status bits have already been
    computed, here we encode them into a dns-compatible string and
    marry them up to the additional information we place in a FQDN
    (serial, product, version, etc). That additional information can
    be specified as optional parameters, but if not specified it will
    be looked up in the shell environment or procfs (typical in an
    appliance uptime_ping invocation). 
    >>> format_fqdn(0, [True, False, True, False, True, False, True, False],
    ... version="6.5.0a", model="100", serial="AB9000ABCDE", uptime=123,
    ... serviceup = 456, dns_prod="XXX")
    'AB9000ABCDE.100.123.456.XXX-1N-P.6.5.0a.updates.riverbed.com'
    >>> format_fqdn(1, [],
    ... version="6.5.0a", model="100", serial="AB9000ABCDE", uptime=123,
    ... serviceup = 456, dns_prod="XXX")
    'AB9000ABCDE.100.3f.co.1XXX-0-0.6.5.0a.updates.riverbed.com'
    >>> format_fqdn(1, [True, False, True, False, True, False, True, False],
    ... version="6.5.0a", model="100", serial="AB9000ABCDE", uptime=123,
    ... serviceup = 456, dns_prod="XXX")
    'AB9000ABCDE.100.3f.co.1XXX-2d-0.6.5.0a.updates.riverbed.com'
    """
    version = version or os.environ.get('BUILD_PROD_RELEASE') or "UNKNOWN"
    model = (model or query_mfdb('/rbt/mfd/flex/model') or 
             query_mfdb('/rbt/mfd/model') or "UNKNOWN")
    serial = serial or query_mfdb('/rbt/mfd/serialnum')
    if (serial is None or serial == '0' or serial == 'NA' or 
        serial == 'V70KY00000000'):
        serial = get_command_output(['/opt/tms/bin/mdreq', '-v', 'query', 'get', '-',
                             '/rbt/manufacture/serialnum'])
    if uptime is None:
        uptime = 0
        try:
            uptime = int(open('/proc/uptime').read().split('.')[0])
        except Exception, e:
            log().error("error getting uptime: %s" % e)
    if serviceup is None:
        serviceup = 0
        service = os.environ.get('BUILD_PROD_UPTIME_BINARY')
        servicepid = service and get_command_output(['/sbin/pidof',service])
        if servicepid:
            try:
                serviceup_s = open('/proc/'+servicepid+'/stat').read().split()
                serviceup = int(serviceup_s[21]) / 100
            except Exception, e:
                log().error("error computing serviceuptime: %s" % e)
    if dns_version == 0:
        (fqdn_uptime, fqdn_serviceup) = (str(uptime), str(serviceup))
    else:
        # encode the integers, and signal a V1 encoding by having a leading 0
        fqdn_uptime = bits_to_body(encode_int(uptime, nbits=32),V1_CHR)
        fqdn_serviceup = bits_to_body(encode_int(serviceup,nbits=32),V1_CHR)
    if dns_prod is None:
        dns_prod = get_dns_prod(mobo=mobo)
    prod_status = bits_to_prod_status(status_bits, dns_prod, dns_version)
    fqdn_status = prod_status_to_fqdn_status(prod_status)
    octets = [serial, model, fqdn_uptime, fqdn_serviceup, fqdn_status, 
              version, dns_server]
    if None in octets:
        log().error("Null heartbeat components: %s" % repr(octets))
        return None
    else:
        return '.'.join(octets)

def main():
    parser = OptionParser(usage="""
    %prog [options] [heartbeat.xml|svn url] [dns.word | status.word]

    Decode or fetch heartbeat status values according to the spec
    provided in heartbeat.xml or svn url, or the xml looked up for
    the specified --version (if not on an appliance).
    
    If status is given on the cmdline, decode it to extract its
    values. Status is assumed to be in our DNS ASCII encoding. The
    product in the status string will be used rather than any --product arg.

    If no status is given to decode, get values by executing the
    queries and shell commands in heartbeat.xml.  Write the values to
    stdout in ASCII dns encoding, unless a different encoding is
    specified with -v, -b, or -x
    """)
    parser.add_option("--serial", default="",
                      help="encode this serial number")
    parser.add_option("--model", default="",
                      help="encode this model number")
    parser.add_option("--uptime", default=None, type="int",
                      help="encode this system uptime")
    parser.add_option("--serviceup", default=None, type="int",
                      help="encode this service uptime")
    parser.add_option("--version", default=None,
                      help="encode this device version")
    parser.add_option("--mobo", default=None,
                      help="mobojobo, set to VM or none (default)")
    parser.add_option("-x", "--hex", action="store_true",
                      help="output status as ascii hex ('0xABCD')")
    parser.add_option("-b", "--binary", action="store_true",
                      help="output status as ascii binary ('0b01101')")
    parser.add_option("-v", "--verbose", action="store_true",
                      help="output in human-readable name=value form")
    parser.add_option("--debug", action="store_true",
                      help="debug-level logging")
    parser.add_option("--dnsversion", default=0, type="int", dest='dns_version',
                      help="encode using this DNS version (default=%default)")
    parser.add_option("--product","-p", dest='dns_prod', 
                      # do not define a default for this, you break appliance!
                      help="encode this product status")
    parser.add_option("--fqdn", action='store_true',
                      help="encode/decode FQDN instead of just status word")
    parser.add_option("--fqdntest", action='store_true',
                      help="encode/decode FQDN using riverbed test address")
    parser.add_option("--url", action='store_true',
                      help="show svn url for xml for this heartbeat product and version")
    parser.add_option("--test", action="store_true", help="run doctests")

    (opts, args) = parser.parse_args()

    if opts.debug:
        level = logging.DEBUG
    elif opts.verbose:
        level = logging.INFO
    elif opts.test:
        level = logging.ERROR
    else:
        level = logging.WARN
    logging.basicConfig(stream=sys.stderr, level=level,
                        format='%(asctime)s %(levelname)s %(message)s',
                        datefmt='%b-%d %H:%M:%S')
    dns_version = opts.dns_version
    dns_server = (opts.fqdntest and DNS_TEST_SERVER or DNS_SERVER )
    if opts.url:
        #
        # report which archived heartbeat.xml would be used to encode/decode
        #
        if opts.dns_prod is None or opts.version is None:
            parser.error("you must specify --product and --version")
        url = release_to_heartbeat_url(opts.dns_prod, opts.version,
                                       no_tags=False, try_point=True)
        if url:
            print url
            print "last updated ",get_svn_datestring(url)
        else:
            print "No heartbeat.xml for %s-%s" % (opts.dns_prod, opts.version)
        sys.exit(0)
    #
    # If a heartbeat.xml was specified on the commandline, get it, either
    # from a filepath ending in .xml, a subversion url
    # beginning svn://
    #
    xml_text = None
    xml_source = None
    if args:
        for i,path in enumerate(args):
            if path.startswith("svn://"):
                xml_source = path
                xml_text = get_svn_url(path)
                args.pop(i) # consume argument
                break
            elif path.endswith(".xml"):
                xml_source = path
                xml_text = open(args[0]).read()
                args.pop(i) # consume argument
                break
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
        check_wordlengths(xml_text, dns_version, verbose=opts.verbose)
        return 0 # success!
    if args:
        #
        # decode cmdline status to get status item values.
        # This overrides any cmdline options for product or dns version.
        #
        status = args.pop()
        if opts.fqdn or opts.fqdntest:
            components = parse_fqdn(status, dns_server=dns_server)
            parsed_status = parse_prod_status(components['status_word'])
        else:
            parsed_status = parse_prod_status(status)
        prod_status = parsed_status['status_word']
        dns_version = parsed_status['dns_version']
        dns_prod = parsed_status['dns_prod']
        if xml_text is None:
            xml_source = release_to_heartbeat_url(dns_prod,opts.version)
            xml_text = get_svn_url(xml_source)
        spec = xml_to_spec(dns_prod, xml_text)
        assert spec, "No matching spec for %s found in %s"% (
            dns_prod, xml_source)
        values = parsed_status_to_values(parsed_status, spec)
    elif xml_text is not None:
        #
        # execute the spec on the appliance to get the values
        #
        dns_prod = opts.dns_prod or get_dns_prod() 
        spec = xml_to_spec(dns_prod, xml_text)
        assert spec, "No matching spec for %s found in %s"% (
            dns_prod, xml_source)
        values = execute(spec, opts.verbose, check_exit=opts.verbose)
    else:
        parser.error("Cannot encode heartbeat: need heartbeat.xml")
    #
    # encode and output status values using the specified encoding
    #
    status_bits = values_to_bits(values, spec, opts.verbose)
    if opts.hex:
        print "0x"+to_hex(status_bits)
    elif opts.binary:
        print "0b"+to_binary(status_bits)
    elif opts.verbose:
        #
        # print human-readable name/value pairs
        # do a full encode/decode to capture truncation effects
        #
        values = bits_to_values(status_bits, spec)
        pairs = ["%s=%s" % name_value for name_value in values.items()]
        pairs.sort()
        print "\n".join(pairs)
    elif opts.fqdn or opts.fqdntest:
        #
        # output a FQDN suitable for nslookup
        #
        try:
            fqdn = format_fqdn(dns_version, status_bits, dns_prod=dns_prod,
                               version=opts.version, model=opts.model, 
                               serial=opts.serial, uptime=opts.uptime, 
                               serviceup=opts.serviceup, mobo=opts.mobo,
                               dns_server=dns_server)
            if fqdn:
                print fqdn
            else:
                log().error("Not emitting FQDN because of errors")
        except Exception, e:
            log().error(str(e))
            log().debug(traceback.format_exc())
    else:
        #
        # output just the status word. 
        # 
        print bits_to_prod_status(status_bits, dns_prod, dns_version)

 
if __name__ == "__main__":
    sys.exit(main())

