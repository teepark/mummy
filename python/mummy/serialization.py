import datetime
import decimal
import itertools
import struct
import sys

try:
    import lzf
except ImportError:
    lzf = None


__all__ = ["loads", "dumps", "pure_python_loads", "pure_python_dumps",
        "has_extension"]


if sys.version_info[0] >= 3:
    from functools import reduce
    _str = unicode = str
    class string(bytes):
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
    iterkeys = lambda d: d.keys()
    itervalues = lambda d: d.values()
    xrange = range
    chr = lambda x: bytes([x])
    ord = lambda x: bytes.__getitem__(x, 0)
    bytify = lambda x: x.encode('ascii')
    izip = zip
else:
    iteritems = lambda d: d.iteritems()
    iterkeys = lambda d: d.iterkeys()
    itervalues = lambda d: d.itervalues()
    bytify = lambda x: x
    bytes = string = str
    izip = itertools.izip


MAX_DEPTH = 256

MUMMY_TYPE_NULL = 0x0
MUMMY_TYPE_BOOL = 0x1
MUMMY_TYPE_CHAR = 0x2
MUMMY_TYPE_SHORT = 0x3
MUMMY_TYPE_INT = 0x4
MUMMY_TYPE_LONG = 0x5
MUMMY_TYPE_HUGE = 0x6
MUMMY_TYPE_FLOAT = 0x7
MUMMY_TYPE_SHORTSTR = 0x8
MUMMY_TYPE_LONGSTR = 0x9
MUMMY_TYPE_SHORTUTF8 = 0xA
MUMMY_TYPE_LONGUTF8 = 0xB
MUMMY_TYPE_LONGLIST = 0xC
MUMMY_TYPE_LONGTUPLE = 0xD
MUMMY_TYPE_LONGSET = 0xE
MUMMY_TYPE_LONGHASH = 0xF

MUMMY_TYPE_SHORTLIST = 0x10
MUMMY_TYPE_SHORTTUPLE = 0x11
MUMMY_TYPE_SHORTSET = 0x12
MUMMY_TYPE_SHORTHASH = 0x13

MUMMY_TYPE_MEDLIST = 0x14
MUMMY_TYPE_MEDTUPLE = 0x15
MUMMY_TYPE_MEDSET = 0x16
MUMMY_TYPE_MEDHASH = 0x17
MUMMY_TYPE_MEDSTR = 0x18
MUMMY_TYPE_MEDUTF8 = 0x19

MUMMY_TYPE_DATE = 0x1A
MUMMY_TYPE_TIME = 0x1B
MUMMY_TYPE_DATETIME = 0x1C
MUMMY_TYPE_TIMEDELTA = 0x1D

MUMMY_TYPE_DECIMAL = 0x1E
MUMMY_TYPE_SPECIALNUM = 0x1F

MUMMY_SPECIAL_INFINITY = 0x10
MUMMY_SPECIAL_NAN = 0x20


TYPEMAP = {
    type(None): MUMMY_TYPE_NULL,
    bool: MUMMY_TYPE_BOOL,
    float: MUMMY_TYPE_FLOAT,
}

_BIG_ENDIAN = struct.pack("!h", 1) == struct.pack("h", 1)


def _get_type_code(x):
    mapped = TYPEMAP.get(type(x))
    if mapped is not None:
        return mapped

    if type(x) is list:
        if len(x) < 256:
            return MUMMY_TYPE_SHORTLIST
        if len(x) < 65536:
            return MUMMY_TYPE_MEDLIST
        return MUMMY_TYPE_LONGLIST

    if type(x) is tuple:
        if len(x) < 256:
            return MUMMY_TYPE_SHORTTUPLE
        if len(x) < 65536:
            return MUMMY_TYPE_MEDTUPLE
        return MUMMY_TYPE_LONGTUPLE

    if type(x) in (set, frozenset):
        if len(x) < 256:
            return MUMMY_TYPE_SHORTSET
        if len(x) < 65536:
            return MUMMY_TYPE_MEDSET
        return MUMMY_TYPE_LONGSET

    if type(x) is dict:
        if len(x) < 256:
            return MUMMY_TYPE_SHORTHASH
        if len(x) < 65536:
            return MUMMY_TYPE_MEDHASH
        return MUMMY_TYPE_LONGHASH

    if type(x) is bytes:
        if len(x) < 256:
            return MUMMY_TYPE_SHORTSTR
        if len(x) < 65536:
            return MUMMY_TYPE_MEDSTR
        return MUMMY_TYPE_LONGSTR

    if type(x) is unicode:
        if len(x.encode('utf8')) < 256:
            return MUMMY_TYPE_SHORTUTF8
        if len(x.encode('utf8')) < 65536:
            return MUMMY_TYPE_MEDUTF8
        return MUMMY_TYPE_LONGUTF8

    if type(x) in (int, long):
        if -128 <= x < 128:
            return MUMMY_TYPE_CHAR
        if -32768 <= x < 32768:
            return MUMMY_TYPE_SHORT
        if -2147483648 <= x < 2147483648:
            return MUMMY_TYPE_INT
        if -9223372036854775808 <= x < 9223372036854775808:
            return MUMMY_TYPE_LONG
        return MUMMY_TYPE_HUGE

    if type(x) is datetime.date:
        return MUMMY_TYPE_DATE

    if type(x) is datetime.time:
        return MUMMY_TYPE_TIME

    if type(x) is datetime.datetime:
        return MUMMY_TYPE_DATETIME

    if type(x) is datetime.timedelta:
        return MUMMY_TYPE_TIMEDELTA

    if type(x) is decimal.Decimal:
        if x.is_nan() or x.is_infinite():
            return MUMMY_TYPE_SPECIALNUM
        return MUMMY_TYPE_DECIMAL

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

def _dump_ushort(x, depth=0, default=None):
    return struct.pack("!H", x)

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

def _dump_medstr(x, depth=0, default=None):
    return _dump_ushort(len(x)) + x

def _dump_longstr(x, depth=0, default=None):
    return _dump_uint(len(x)) + x

def _dump_shortutf8(x, depth=0, default=None):
    return _dump_shortstr(x.encode('utf8'))

def _dump_medutf8(x, depth=0, default=None):
    return _dump_medstr(x.encode('utf8'))

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
    return _dump_uchar(len(x)) + bytify("").join(
            pure_python_dumps(item, default, depth + 1, compress=0)
            for item in x)

_dump_shorttuple = _dump_shortset = _dump_shortlist

def _dump_shortdict(x, depth=0, default=None):
    return _dump_uchar(len(x)) + bytify("").join(
            pure_python_dumps(item, default, depth + 1, compress=0) for item in
            reduce(lambda a, b: a.extend(b) or a, iteritems(x), []))

def _dump_medlist(x, depth=0, default=None):
    return _dump_ushort(len(x)) + bytify("").join(
            pure_python_dumps(item, default, depth + 1, compress=0)
            for item in x)

_dump_medtuple = _dump_medset = _dump_medlist

def _dump_meddict(x, depth=0, default=None):
    return _dump_ushort(len(x)) + bytify("").join(
            pure_python_dumps(item, default, depth + 1, compress=0) for item in
            reduce(lambda a, b: a.extend(b) or a, iteritems(x), []))

def _dump_date(x, depth=0, default=None):
    return "".join(
            (_dump_ushort(x.year), _dump_char(x.month), _dump_char(x.day)))

def _dump_time(x, depth=0, default=None):
    if x.tzinfo is not None:
        raise ValueError("can't serialize data objects with tzinfo")
    return "".join((
        _dump_char(x.hour),
        _dump_char(x.minute),
        _dump_char(x.second),
        struct.pack("!I", x.microsecond)[-3:]))

def _dump_datetime(x, depth=0, default=None):
    return _dump_date(x.date()) + _dump_time(x.timetz())

def _dump_timedelta(x, depth=0, default=None):
    return "".join((
        _dump_int(x.days), _dump_int(x.seconds), _dump_int(x.microseconds)))

def _dump_decimal(x, depth=0, default=None):
    sign, digits, expo = x.as_tuple()
    pairs = []
    for i, dig in enumerate(digits):
        if not 0 <= dig <= 9:
            raise ValueError("invalid digit")

        if not (i & 1):
            # even
            pairs.append(0)
        else:
            # odd
            dig <<= 4
        pairs[-1] |= dig

    return (struct.pack("!bhH", sign, expo, len(digits)) +
            "".join(map(_dump_uchar, pairs)))

def _dump_specialnum(x, depth=0, default=None):
    if x.is_snan():
        return _dump_uchar(MUMMY_SPECIAL_NAN | 1)

    if x.is_nan():
        return _dump_uchar(MUMMY_SPECIAL_NAN)

    if x.is_infinite():
        return _dump_uchar(MUMMY_SPECIAL_INFINITY | int(x < 0))


_dumpers = {
    MUMMY_TYPE_NULL: _dump_none,
    MUMMY_TYPE_BOOL: _dump_bool,
    MUMMY_TYPE_CHAR: _dump_char,
    MUMMY_TYPE_SHORT: _dump_short,
    MUMMY_TYPE_INT: _dump_int,
    MUMMY_TYPE_LONG: _dump_long,
    MUMMY_TYPE_HUGE: _dump_huge,
    MUMMY_TYPE_FLOAT: _dump_double,
    MUMMY_TYPE_SHORTSTR: _dump_shortstr,
    MUMMY_TYPE_MEDSTR: _dump_medstr,
    MUMMY_TYPE_LONGSTR: _dump_longstr,
    MUMMY_TYPE_SHORTUTF8: _dump_shortutf8,
    MUMMY_TYPE_MEDUTF8: _dump_medutf8,
    MUMMY_TYPE_LONGUTF8: _dump_longutf8,
    MUMMY_TYPE_LONGLIST: _dump_list,
    MUMMY_TYPE_LONGTUPLE: _dump_tuple,
    MUMMY_TYPE_LONGSET: _dump_set,
    MUMMY_TYPE_LONGHASH: _dump_dict,
    MUMMY_TYPE_SHORTLIST: _dump_shortlist,
    MUMMY_TYPE_MEDLIST: _dump_medlist,
    MUMMY_TYPE_SHORTTUPLE: _dump_shorttuple,
    MUMMY_TYPE_MEDTUPLE: _dump_medtuple,
    MUMMY_TYPE_SHORTSET: _dump_shortset,
    MUMMY_TYPE_MEDSET: _dump_medset,
    MUMMY_TYPE_SHORTHASH: _dump_shortdict,
    MUMMY_TYPE_MEDHASH: _dump_meddict,
    MUMMY_TYPE_DATE: _dump_date,
    MUMMY_TYPE_TIME: _dump_time,
    MUMMY_TYPE_DATETIME: _dump_datetime,
    MUMMY_TYPE_TIMEDELTA: _dump_timedelta,
    MUMMY_TYPE_DECIMAL: _dump_decimal,
    MUMMY_TYPE_SPECIALNUM: _dump_specialnum,
}

def pure_python_dumps(item, default=None, depth=0, compress=True):
    """serialize a native python object into a mummy string
    
    :param object: the python object to serialize
    :param function default:
        If the 'object' parameter is not serializable and this parameter is
        provided, this function will be used to generate a fallback value to
        serialize. It should take one argument (the original object), and
        return something serilizable.
    :param bool compress:
        whether or not to attempt to compress the serialized data (default
        True)

    :returns: the bytestring of the serialized data
    """
    if default and not hasattr(default, "__call__"):
        raise TypeError("default must be callable or None")
    if depth >= MAX_DEPTH:
        raise ValueError("max depth exceeded")
    try:
        kind = _get_type_code(item)
    except ValueError:
        if default is None:
            raise TypeError("unserializable type")
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

def _load_ushort(x):
    return struct.unpack("!H", x[:2])[0], 2

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

def _load_medstr(x):
    width = _load_ushort(x)[0] + 2
    return x[2:width], width

def _load_longstr(x):
    width = _load_uint(x)[0] + 4
    return x[4:width], width

def _load_shortutf8(x):
    str, width = _load_shortstr(x)
    return str.decode('utf8'), width

def _load_medutf8(x):
    str, width = _load_medstr(x)
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
    lst, width = _load_shortlist(x)
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

def _load_medlist(x):
    length, width = _load_ushort(x)
    result = []
    for i in xrange(length):
        item, item_width = _loads(x[width:])
        result.append(item)
        width += item_width + 1
    return result, width

def _load_medtuple(x):
    lst, width = _load_medlist(x)
    return tuple(lst), width

def _load_medset(x):
    lst, width = _load_medlist(x)
    return set(lst), width

def _load_meddict(x):
    length, width = _load_ushort(x)
    result = {}
    for i in xrange(length):
        key, keywidth = _loads(x[width:])
        width += keywidth + 1
        value, valuewidth = _loads(x[width:])
        width += valuewidth + 1
        result[key] = value
    return result, width

def _load_date(x):
    year = struct.unpack("!H", x[:2])[0]
    month = struct.unpack("B", x[2])[0]
    day = struct.unpack("B", x[3])[0]
    return datetime.date(year, month, day), 4

def _load_time(x):
    hour = struct.unpack("B", x[0])[0]
    minute = struct.unpack("B", x[1])[0]
    second = struct.unpack("B", x[2])[0]
    microsecond = struct.unpack("!I", '\x00' + x[3:6])[0]
    return datetime.time(hour, minute, second, microsecond), 6

def _load_datetime(x):
    return datetime.datetime.combine(
            _load_date(x)[0],
            _load_time(x[4:10])[0]), 10

def _load_timedelta(x):
    return (datetime.timedelta(
            _load_int(x)[0], _load_int(x[4:8])[0], _load_int(x[8:12])[0]), 12)

def _load_decimal(x):
    sign = _load_char(x[0])[0]
    expo = _load_short(x[1:3])[0]
    count = _load_ushort(x[3:5])[0]

    width = 5 + (count >> 1) + (count & 1)
    digit_bytes = map(ord, x[5:width])
    digits = []
    for i, b in enumerate(digit_bytes[:-1]):
        digits.append(b & 0x0f)
        digits.append(b >> 4)
    digits.append(digit_bytes[-1] & 0x0f)
    if not count & 1:
        digits.append(digit_bytes[-1] >> 4)

    return decimal.Decimal((sign, digits, expo)), width

def _load_specialnum(x):
    b = _load_uchar(x[0])[0]
    if (b & 0xf0) == MUMMY_SPECIAL_INFINITY:
        if b & 0x01:
            return decimal.Decimal("-Infinity"), 1
        return decimal.Decimal("Infinity"), 1

    if (b & 0xf0) == MUMMY_SPECIAL_NAN:
        if b & 0x01:
            return decimal.Decimal("sNaN"), 1
        return decimal.Decimal("NaN"), 1


_loaders = {
    MUMMY_TYPE_NULL: _load_none,
    MUMMY_TYPE_BOOL: _load_bool,
    MUMMY_TYPE_CHAR: _load_char,
    MUMMY_TYPE_SHORT: _load_short,
    MUMMY_TYPE_INT: _load_int,
    MUMMY_TYPE_LONG: _load_long,
    MUMMY_TYPE_HUGE: _load_huge,
    MUMMY_TYPE_FLOAT: _load_double,
    MUMMY_TYPE_SHORTSTR: _load_shortstr,
    MUMMY_TYPE_MEDSTR: _load_medstr,
    MUMMY_TYPE_LONGSTR: _load_longstr,
    MUMMY_TYPE_SHORTUTF8: _load_shortutf8,
    MUMMY_TYPE_MEDUTF8: _load_medutf8,
    MUMMY_TYPE_LONGUTF8: _load_longutf8,
    MUMMY_TYPE_LONGLIST: _load_list,
    MUMMY_TYPE_LONGTUPLE: _load_tuple,
    MUMMY_TYPE_LONGSET: _load_set,
    MUMMY_TYPE_LONGHASH: _load_dict,
    MUMMY_TYPE_SHORTLIST: _load_shortlist,
    MUMMY_TYPE_MEDLIST: _load_medlist,
    MUMMY_TYPE_SHORTTUPLE: _load_shorttuple,
    MUMMY_TYPE_MEDTUPLE: _load_medtuple,
    MUMMY_TYPE_SHORTSET: _load_shortset,
    MUMMY_TYPE_MEDSET: _load_medset,
    MUMMY_TYPE_SHORTHASH: _load_shortdict,
    MUMMY_TYPE_MEDHASH: _load_meddict,
    MUMMY_TYPE_DATE: _load_date,
    MUMMY_TYPE_TIME: _load_time,
    MUMMY_TYPE_DATETIME: _load_datetime,
    MUMMY_TYPE_TIMEDELTA: _load_timedelta,
    MUMMY_TYPE_DECIMAL: _load_decimal,
    MUMMY_TYPE_SPECIALNUM: _load_specialnum,
}

def _loads(data):
    kind = _load_char(data)[0]
    return _loaders[kind](data[1:])

def pure_python_loads(data):
    """convert a mummy string into the python object it represents
    
    :param bytestring serialized: the serialized string to load

    :returns: the python data
    """
    if not data:
        raise ValueError("no data from which to load")
    if ord(data[0]) >> 7:
        if not lzf:
            raise RuntimeError("can't decompress without python-lzf")
        kind, ucsize, data = (
                chr(ord(data[0]) & 0x7f), _load_int(data[1:5])[0], data[5:])
        data = kind + lzf.decompress(data, ucsize + 1)

    return _loads(string(data))[0]


try:
    from _mummy import dumps, loads
    has_extension = True
except ImportError:
    dumps = pure_python_dumps
    loads = pure_python_loads
    has_extension = False
