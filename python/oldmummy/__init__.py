"""
mummy is a data serialization format and accompanying (de)serializer.

the format is designed to be first fast, and second compact, willing to
sacrifice human-readability in the name of those two values.

the main implementation is in C, but there is a pure-python version it falls
back to if the extension is unavailable. the module-global `has_extension` is a
boolean indicating whether the C extension is in use.
"""

from __future__ import absolute_import

from .serialization import \
        loads, dumps, pure_python_loads, pure_python_dumps, has_extension
from .schemas import Message, OPTIONAL, UNION, ANY


__all__ = ["loads", "dumps", "pure_python_loads", "pure_python_dumps",
        "has_extension", "Message", "OPTIONAL", "UNION", "ANY"]
