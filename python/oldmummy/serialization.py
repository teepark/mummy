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

TYPE_MEDLIST = 0x14
TYPE_MEDTUPLE = 0x15
TYPE_MEDSET = 0x16
TYPE_MEDDICT = 0x17
TYPE_MEDSTR = 0x18
TYPE_MEDUTF8 = 0x19

TYPE_DATE = 0x1A
TYPE_TIME = 0x1B
TYPE_DATETIME = 0x1C
TYPE_TIMEDELTA = 0x1D

TYPE_DECIMAL = 0x1E


TYPEMAP = {
    type(None): TYPE_NONE,
    bool: TYPE_BOOL,
    float: TYPE_DOUBLE,
}

_BIG_ENDIAN = struct.pack("!h", 1) == struct.pack("h", 1)


def _get_type_code(x):
    mapped = TYPEMAP.get(type(x))
    if mapped is not None:
        return mapped

    if type(x) is list:
        if len(x) < 256:
            return TYPE_SHORTLIST
        if len(x) < 65536:
            return TYPE_MEDLIST
        return TYPE_LIST

    if type(x) is tuple:
        if len(x) < 256:
            return TYPE_SHORTTUPLE
        if len(x) < 65536:
            return TYPE_MEDTUPLE
        return TYPE_TUPLE

    if type(x) in (set, frozenset):
        if len(x) < 256:
            return TYPE_SHORTSET
        if len(x) < 65536:
            return TYPE_MEDSET
        return TYPE_SET

    if type(x) is dict:
        if len(x) < 256:
            return TYPE_SHORTDICT
        if len(x) < 65536:
            return TYPE_MEDDICT
        return TYPE_DICT

    if type(x) is bytes:
        if len(x) < 256:
            return TYPE_SHORTSTR
        if len(x) < 65536:
            return TYPE_MEDSTR
        return TYPE_LONGSTR

    if type(x) is unicode:
        if len(x.encode('utf8')) < 256:
            return TYPE_SHORTUTF8
        if len(x.encode('utf8')) < 65536:
            return TYPE_MEDUTF8
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

    if type(x) is datetime.date:
        return TYPE_DATE

    if type(x) is datetime.time:
        return TYPE_TIME

    if type(x) is datetime.datetime:
        return TYPE_DATETIME

    if type(x) is datetime.timedelta:
        return TYPE_TIMEDELTA

    if type(x) is decimal.Decimal:
        return TYPE_DECIMAL

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
    flags = 0

    flags |= expo in ("n", "N", "F")
    flags |= sign << 1
    if flags & 1:
        if expo == "F":
            flags |= 4
        else:
            flags |= (expo == "N") << 3

        return _dump_char(flags)

    digitpairs = []
    for i, dig in enumerate(digits):
        if not 0 <= dig <= 9:
            raise ValueError("invalid digit")

        if not (i & 1):
            digitpairs.append(0)
            dig <<= 4

        digitpairs[-1] |= dig

    return (struct.pack("!BhH", flags, expo, len(digits)) +
            "".join(map(chr, digitpairs)))


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
    TYPE_MEDSTR: _dump_medstr,
    TYPE_LONGSTR: _dump_longstr,
    TYPE_SHORTUTF8: _dump_shortutf8,
    TYPE_MEDUTF8: _dump_medutf8,
    TYPE_LONGUTF8: _dump_longutf8,
    TYPE_LIST: _dump_list,
    TYPE_TUPLE: _dump_tuple,
    TYPE_SET: _dump_set,
    TYPE_DICT: _dump_dict,
    TYPE_SHORTLIST: _dump_shortlist,
    TYPE_MEDLIST: _dump_medlist,
    TYPE_SHORTTUPLE: _dump_shorttuple,
    TYPE_MEDTUPLE: _dump_medtuple,
    TYPE_SHORTSET: _dump_shortset,
    TYPE_MEDSET: _dump_medset,
    TYPE_SHORTDICT: _dump_shortdict,
    TYPE_MEDDICT: _dump_meddict,
    TYPE_DATE: _dump_date,
    TYPE_TIME: _dump_time,
    TYPE_DATETIME: _dump_datetime,
    TYPE_TIMEDELTA: _dump_timedelta,
    TYPE_DECIMAL: _dump_decimal,
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
    flags = struct.unpack("B", x[0])[0]

    if flags & 1:
        width = 1
        if flags & 4:
            # (+ or -) Infinity
            triple = ((flags & 2) >> 1, (0,), "F")
        else:
            # [s]NaN
            triple = (0, (), flags & 8 and "N" or "n")
    else:
        sign = (flags & 2) >> 1
        exponent, length = struct.unpack("!hH", x[1:5])
        width = 5 + (length // 2) + (length & 1)

        digitbytes = map(ord, x[5:width])
        digits = []
        for i, b in enumerate(digitbytes):
            digits.append((b & 0xf0) >> 4)
            digits.append(b & 0xf)

        if not digits[-1]:
            digits.pop()

        triple = (sign, digits, exponent)

    return decimal.Decimal(triple), width


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
    TYPE_MEDSTR: _load_medstr,
    TYPE_LONGSTR: _load_longstr,
    TYPE_SHORTUTF8: _load_shortutf8,
    TYPE_MEDUTF8: _load_medutf8,
    TYPE_LONGUTF8: _load_longutf8,
    TYPE_LIST: _load_list,
    TYPE_TUPLE: _load_tuple,
    TYPE_SET: _load_set,
    TYPE_DICT: _load_dict,
    TYPE_SHORTLIST: _load_shortlist,
    TYPE_MEDLIST: _load_medlist,
    TYPE_SHORTTUPLE: _load_shorttuple,
    TYPE_MEDTUPLE: _load_medtuple,
    TYPE_SHORTSET: _load_shortset,
    TYPE_MEDSET: _load_medset,
    TYPE_SHORTDICT: _load_shortdict,
    TYPE_MEDDICT: _load_meddict,
    TYPE_DATE: _load_date,
    TYPE_TIME: _load_time,
    TYPE_DATETIME: _load_datetime,
    TYPE_TIMEDELTA: _load_timedelta,
    TYPE_DECIMAL: _load_decimal,
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

    return _loads(string(data))[0]


try:
    from _oldmummy import dumps, loads
    has_extension = True
except ImportError:
    dumps = pure_python_dumps
    loads = pure_python_loads
    has_extension = False
