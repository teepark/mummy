#!/usr/bin/env python

"""
mummy is the current (ridiculous) codename for a data serialization format and
accompanying (de)serializer.

the format is designed to be first fast, and second compact, completely
sacrificing human-readability in the name of those two values.

it's prefix-encoded. that means the first byte is the type, and that is
followed by the content. depending on the type, the content may begin with more
meta-data.

first byte is the type:
    0x00 null (python None)
    0x01 boolean
    0x02 char (fits in a 8 bit signed int)
    0x03 short (fits in a 16 bit signed int)
    0x04 integer (fits in a 32 bit signed int)
    0x05 long (fits in a 64 bit signed int)
    0x06 huge (signed integer in a big-endian byte array)
    0x07 double
    0x08 shortstring(bytes, any encoding, up to 255 chars)
    0x09 longstring (bytes, any encoding)
    0x0A short utf8 string
    0x0B long utf8 string
    0x0C list
    0x0D tuple
    0x0E set
    0x0F dictionary

    0x10 short list (<256 items)
    0x11 short tuple (<256 items)
    0x12 short set (<256 items)
    0x13 short dict (<256 items)

* null: no body
* boolean: one byte body (null or 1)
* char: 1 byte body
* short: 2 byte body
* integer: 4 byte body
* long: 8 byte body
* huge: 4 byte header holding the length of the body in bytes, the body is a
        base-256 integer
* double: a C double
* short string: 1 byte header holding the length of the body in bytes
* long string: 4 byte header holding the length of the body in bytes
* short utf8: 1 byte header holding the length of the body in bytes, mummy
        encodes on serialization and decodes on deserialization
* long utf8: 4 byte header holding the length of the body in bytes, mummy
        encodes on serialization and decodes on deserialization
* list: 4 byte header contains the number of objects contained, the body is
        just the mummified contents with no separators
* tuple: same as list, only difference is the type
* set: same as list, only difference is the type
* dictionary: flatten the .items(), then same as list except for the type

all the number types are signed and stored big-endian, except that all header
numbers are unsigned.

the main implementation is in C, but there is a pure-python version it falls
back to if the extension is unavailable. the module-global `has_extension` is a
boolean indicating whether the C extension is in use.
"""

import struct
import sys

try:
    import lzf
except ImportError:
    lzf = None


if sys.version_info[0] >= 3:
    from functools import reduce
    _str = unicode = str
    class str(bytes):
        def __getitem__(self, index):
            if isinstance(index, int):
                return type(self)(super().__getitem__(
                    slice(index, index + 1, None)))
            return type(self)(super().__getitem__(index))

        def __iter__(self):
            i, l = 0, len(self)
            while i < l:
                yield self[i]
                i += 1

    long = int
    map = lambda *a: list(__builtins__['map'](*a))
    iteritems = lambda d: d.items()
    xrange = range
    chr = lambda x: bytes([x])
    ord = lambda x: bytes.__getitem__(x, 0)
    bytify = lambda x: x.encode('ascii')
else:
    iteritems = lambda d: d.iteritems()
    bytify = lambda x: x
    bytes = str


__all__ = ["loads", "dumps", "pure_python_loads", "pure_python_dumps",
        "has_extension"]


MAX_DEPTH = 256

TYPE_NONE = 0x0
TYPE_BOOL = 0x1
TYPE_CHAR = 0x2
TYPE_SHORT = 0x3
TYPE_INT = 0x4
TYPE_LONG = 0x5
TYPE_HUGE = 0x6
TYPE_DOUBLE = 0x7
TYPE_SHORTSTR = 0x8
TYPE_LONGSTR = 0x9
TYPE_SHORTUTF8 = 0xA
TYPE_LONGUTF8 = 0xB
TYPE_LIST = 0xC
TYPE_TUPLE = 0xD
TYPE_SET = 0xE
TYPE_DICT = 0xF

TYPE_SHORTLIST = 0x10
TYPE_SHORTTUPLE = 0x11
TYPE_SHORTSET = 0x12
TYPE_SHORTDICT = 0x13


TYPEMAP = {
    type(None): TYPE_NONE,
    bool: TYPE_BOOL,
    # skipping the integer types here
    float: TYPE_DOUBLE,
    # skipping strings, unicodes, list, tuples, sets and dicts
}

_BIG_ENDIAN = struct.pack("!h", 1) == struct.pack("h", 1)


def _get_type_code(x):
    mapped = TYPEMAP.get(type(x))
    if mapped is not None:
        return mapped

    if type(x) is list:
        if len(x) < 256:
            return TYPE_SHORTLIST
        return TYPE_LIST

    if type(x) is tuple:
        if len(x) < 256:
            return TYPE_SHORTTUPLE
        return TYPE_TUPLE

    if type(x) is set:
        if len(x) < 256:
            return TYPE_SHORTSET
        return TYPE_SET

    if type(x) is dict:
        if len(x) < 256:
            return TYPE_SHORTDICT
        return TYPE_DICT

    if type(x) is bytes:
        if len(x) < 256:
            return TYPE_SHORTSTR
        return TYPE_LONGSTR

    if type(x) is unicode:
        if len(x.encode('utf8')) < 256:
            return TYPE_SHORTUTF8
        return TYPE_LONGUTF8

    if type(x) in (int, long):
        if -128 <= x < 128:
            return TYPE_CHAR
        if -32768 <= x < 32768:
            return TYPE_SHORT
        if -2147483648 <= x < 2147483648:
            return TYPE_INT
        if -9223372036854775808 <= x < 9223372036854775808:
            return TYPE_LONG
        return TYPE_HUGE

    raise ValueError("%r cannot be serialized" % type(x))


##
## DUMPERS
##

def _dump_none(x, depth=0, default=None):
    return bytify("")

def _dump_bool(x, depth=0, default=None):
    return bytify(x and '\x01' or '\x00')

def _dump_char(x, depth=0, default=None):
    if x < 0:
        x += 256
    return chr(x)

def _dump_uchar(x, depth=0, default=None):
    return chr(x)

def _dump_short(x, depth=0, default=None):
    return struct.pack("!h", x)

def _dump_int(x, depth=0, default=None):
    return struct.pack("!i", x)

def _dump_uint(x, depth=0, default=None):
    return struct.pack("!I", x)

def _dump_long(x, depth=0, default=None):
    return struct.pack("!q", x)

def _dump_huge(x, depth=0, default=None):
    data = []
    neg = x < 0
    if neg:
        x = ~x
    while x:
        data.append(x & 0xff)
        x >>= 8
    if neg:
        data = map(lambda byte: byte ^ 0xff, data)
    if not _BIG_ENDIAN:
        data = data[::-1]
    if neg and not data[0] & 0x80:
        data = [255] + data
    if not neg and data[0] & 0x80:
        data = [0] + data
    data = map(chr, data)
    return _dump_uint(len(data)) + bytify("").join(data)

def _dump_double(x, depth=0, default=None):
    return struct.pack("!d", x)

def _dump_shortstr(x, depth=0, default=None):
    return _dump_uchar(len(x)) + x

def _dump_longstr(x, depth=0, default=None):
    return _dump_uint(len(x)) + x

def _dump_shortutf8(x, depth=0, default=None):
    return _dump_shortstr(x.encode('utf8'))

def _dump_longutf8(x, depth=0, default=None):
    return _dump_longstr(x.encode('utf8'))

def _dump_list(x, depth=0, default=None):
    return _dump_uint(len(x)) + bytify("").join(
            pure_python_dumps(item, default, depth + 1, compress=0)
            for item in x)

_dump_set = _dump_tuple = _dump_list

def _dump_dict(x, depth=0, default=None):
    return _dump_uint(len(x)) + bytify("").join(
            pure_python_dumps(item, default, depth + 1, compress=0) for item in
            reduce(lambda a, b: a.extend(b) or a, iteritems(x), []))

def _dump_shortlist(x, depth=0, default=None):
    return _dump_uchar(len(x)) + "".join(
            pure_python_dumps(item, default, depth + 1, compress=0)
            for item in x)

_dump_shorttuple = _dump_shortset = _dump_shortlist

def _dump_shortdict(x, depth=0, default=None):
    return _dump_uchar(len(x)) + "".join(
            pure_python_dumps(item, default, depth + 1, compress=0) for item in
            reduce(lambda a, b: a.extend(b) or a, iteritems(x), []))

_dumpers = {
    TYPE_NONE: _dump_none,
    TYPE_BOOL: _dump_bool,
    TYPE_CHAR: _dump_char,
    TYPE_SHORT: _dump_short,
    TYPE_INT: _dump_int,
    TYPE_LONG: _dump_long,
    TYPE_HUGE: _dump_huge,
    TYPE_DOUBLE: _dump_double,
    TYPE_SHORTSTR: _dump_shortstr,
    TYPE_LONGSTR: _dump_longstr,
    TYPE_SHORTUTF8: _dump_shortutf8,
    TYPE_LONGUTF8: _dump_longutf8,
    TYPE_LIST: _dump_list,
    TYPE_TUPLE: _dump_tuple,
    TYPE_SET: _dump_set,
    TYPE_DICT: _dump_dict,
    TYPE_SHORTLIST: _dump_shortlist,
    TYPE_SHORTTUPLE: _dump_shorttuple,
    TYPE_SHORTSET: _dump_shortset,
    TYPE_SHORTDICT: _dump_shortdict,
}

def pure_python_dumps(item, default=None, depth=0, compress=True):
    "serialize a native python object into a mummy string"
    if default and not hasattr(default, "__call__"):
        raise TypeError("default must be callable or None")
    if depth >= MAX_DEPTH:
        raise ValueError("max depth exceeded")
    try:
        kind = _get_type_code(item)
    except ValueError:
        item = default(item)
        kind = _get_type_code(item)
    data = _dumpers[kind](item, depth, default)
    datalen = len(data)
    if compress and lzf and datalen > 5:
        compressed = lzf.compress(data, datalen - 5)
        if compressed:
            data = struct.pack("!i", datalen) + compressed
            kind = kind | 0x80
    kind = _dump_char(kind)

    return kind + data


##
## LOADERS
##

def _load_none(x):
    return None, 0

def _load_bool(x):
    return bool(ord(x[0])), 1

def _load_char(x):
    num = ord(x[0])
    if num >= 128:
        num -= 256
    return num, 1

def _load_uchar(x):
    return ord(x[0]), 1

def _load_short(x):
    return struct.unpack("!h", x[:2])[0], 2

def _load_int(x):
    return struct.unpack("!i", x[:4])[0], 4

def _load_uint(x):
    return struct.unpack("!I", x[:4])[0], 4

def _load_long(x):
    return struct.unpack("!q", x[:8])[0], 8

def _load_huge(x):
    width = _load_uint(x)[0] + 4
    num = 0
    x = x[4:]
    neg = ord(x[0]) & 0x80
    data = map(ord, x[:width])
    if neg:
        data = map(lambda byte: byte ^ 0xff, data)
    for c in data:
        num = (num << 8) | c
    if neg:
        return -num - 1, width
    return num, width

def _load_double(x):
    return struct.unpack("!d", x[:8])[0], 8

def _load_shortstr(x):
    width = _load_uchar(x)[0] + 1
    return x[1:width], width

def _load_longstr(x):
    width = _load_uint(x)[0] + 4
    return x[4:width], width

def _load_shortutf8(x):
    str, width = _load_shortstr(x)
    return str.decode('utf8'), width

def _load_longutf8(x):
    str, width = _load_longstr(x)
    return str.decode('utf8'), width

def _load_list(x):
    length, width = _load_uint(x)
    result = []
    for i in xrange(length):
        item, item_width = _loads(x[width:])
        result.append(item)
        width += item_width + 1
    return result, width

def _load_set(x):
    lst, width = _load_list(x)
    return set(lst), width

def _load_tuple(x):
    lst, width = _load_list(x)
    return tuple(lst), width

def _load_dict(x):
    length, width = _load_uint(x)
    result = {}
    for i in xrange(length):
        key, keywidth = _loads(x[width:])
        width += keywidth + 1
        value, valuewidth = _loads(x[width:])
        width += valuewidth + 1
        result[key] = value
    return result, width

def _load_shortlist(x):
    length, width = _load_uchar(x)
    result = []
    for i in xrange(length):
        item, item_width = _loads(x[width:])
        result.append(item)
        width += item_width + 1
    return result, width

def _load_shorttuple(x):
    lst, width = _load_shortlist(x)
    return tuple(lst), width

def _load_shortset(x):
    lst, width = _load_list(x)
    return set(lst), width

def _load_shortdict(x):
    length, width = _load_uchar(x)
    result = {}
    for i in xrange(length):
        key, keywidth = _loads(x[width:])
        width += keywidth + 1
        value, valuewidth = _loads(x[width:])
        width += valuewidth + 1
        result[key] = value
    return result, width

_loaders = {
    TYPE_NONE: _load_none,
    TYPE_BOOL: _load_bool,
    TYPE_CHAR: _load_char,
    TYPE_SHORT: _load_short,
    TYPE_INT: _load_int,
    TYPE_LONG: _load_long,
    TYPE_HUGE: _load_huge,
    TYPE_DOUBLE: _load_double,
    TYPE_SHORTSTR: _load_shortstr,
    TYPE_LONGSTR: _load_longstr,
    TYPE_SHORTUTF8: _load_shortutf8,
    TYPE_LONGUTF8: _load_longutf8,
    TYPE_LIST: _load_list,
    TYPE_TUPLE: _load_tuple,
    TYPE_SET: _load_set,
    TYPE_DICT: _load_dict,
    TYPE_SHORTLIST: _load_shortlist,
    TYPE_SHORTTUPLE: _load_shorttuple,
    TYPE_SHORTSET: _load_shortset,
    TYPE_SHORTDICT: _load_shortdict,
}

def _loads(data):
    kind = _load_char(data)[0]
    return _loaders[kind](data[1:])

def pure_python_loads(data):
    "convert a mummy string into the python object it represents"
    if not data:
        raise ValueError("no data from which to load")
    if ord(data[0]) >> 7:
        if not lzf:
            raise RuntimeError("can't decompress without python-lzf")
        kind, ucsize, data = (
                chr(ord(data[0]) & 0x7f), _load_int(data[1:5])[0], data[5:])
        data = kind + lzf.decompress(data, ucsize + 1)

    return _loads(str(data))[0]


try:
    from _mummy import dumps, loads
    has_extension = True
except ImportError:
    dumps = pure_python_dumps
    loads = pure_python_loads
    has_extension = False
