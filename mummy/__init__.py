"""
mummy is the codename for a data serialization format and accompanying
(de)serializer.

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

from __future__ import absolute_import

from .serialization import \
        loads, dumps, pure_python_loads, pure_python_dumps, has_extension
from .schemas import schema, OPTIONAL, UNION, ANY


__all__ = ["loads", "dumps", "pure_python_loads", "pure_python_dumps",
        "has_extension", "schema", "OPTIONAL", "UNION", "ANY"]
