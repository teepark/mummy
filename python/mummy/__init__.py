"""
mummy is the name for a data serialization format and accompanying
(de)serializer.

the format is designed to be first fast and second compact, sacrificing
human-readability in the name of those two values.

it's prefix-encoded. that means the first byte is the type, and that is
followed by the content. depending on the type, the content may begin with more
meta-data.

first byte is the type:
    0x00 null
    0x01 boolean
    0x02 char
    0x03 short
    0x04 integer
    0x05 long
    0x06 huge
    0x07 float
    0x08 shortstring
    0x18 medstring
    0x09 longstring
    0x0A short utf8 string
    0x19 medium utf8
    0x0B long utf8 string
    0x10 short list
    0x14 medium list
    0x0C long list
    0x11 short tuple
    0x15 medium tuple
    0x0D long tuple
    0x12 short set
    0x16 mediumset
    0x0E long set
    0x13 short hash
    0x17 medium hash
    0x0F long hash
    0x1A date
    0x1B time
    0x1C date & time
    0x1D time difference
    0x1E decimal
    0x1F special number

* null: no body, decodes to python None
* boolean: one byte body (0 or 1), python bool
* char, short, integer, long: 1, 2, 4, 8 byte bodies respectively, containing
        big-endian signed integers. comes out as a python int (on 32 bit
        pythons the mummy 'long' type will be a python long)
* huge: 4 byte prefix holding the length of the rest of the body, which is a
        big-endian signed integer of arbitrary size. decodes to a python long.
* float: 64-bit IEEE floating point. python float type.
* strings: 1, 2 or 4 byte prefix for (short, med, long) strings. prefix
        contains the length of the body, which is just the input bytes. decodes
        to python bytestring (python2 string, python3 bytes).
* utf8: same as strings but encodes from/decodes to python unicode strings via
        UTF-8. the length prefix is encoded length, not unicode char count.
* lists: 1, 2 or 4 byte length prefix for (short, med, long) lists. prefix in
        this case is # of contained elements, not body byte length. the body
        simply holds the mummified contents.
* tuples: same as lists, only difference is the python type
* sets: same as lists, only difference is the python type
* hashes: 1, 2 or 4 byte length prefix holds # of contained key value pairs.
        the body is mummified alternating keys and values with no separators.
        encodes from/decodes to python dict.
* date: no header, then 2 byte unsigned big-endian year, one byte month, one
        byte day. python type datetime.date
* time: no header, then one byte each for (hour, minute, second), then unsigned
        3-byte big-endian microsecond. python type is datetime.time
* date & time: after the single type byte it holds the bodies of a date and
        time mashed together. python type is datetime.datetime
* time difference: signed 4 big-endian bytes for each of days, seconds,
        microseconds. python type is datetime.timedelta.
* decimal: single byte of sign (0 or 1), 2 byte signed big-endian for decimal
        point position, 2 byte unsigned big-endian for number of digits, then
        4-bit unsigned numbers for digits alternating low 4, high 4 (always
        low 4 first). python type is decimal.Decimal.
* special numbers: single byte body, the high 4 bits value can be 1 for
        infinity or 2 for NaN, and the low 4 bits value being 1 (instead of 0)
        turns Infinity into -Infinity, or NaN into sNaN. the python class is
        decimal.Decimal, which supports all 4 of these special numbers.

the main implementation is in C, but there is a pure-python version it falls
back to if the extension is unavailable. the module-global `has_extension` is a
boolean indicating whether the C extension is in use.
"""

from __future__ import absolute_import

from .serialization import \
        loads, dumps, pure_python_loads, pure_python_dumps, has_extension
from .schemas import Message, OPTIONAL, UNION, ANY


VERSION = (1, 0, 1, "")
__version__ = ".".join(filter(None, map(str, VERSION)))


__all__ = ["loads", "dumps", "pure_python_loads", "pure_python_dumps",
        "has_extension", "Message", "OPTIONAL", "UNION", "ANY"]
