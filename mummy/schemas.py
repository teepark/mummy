"""
SCHEMAS:

simple schemas:
    - just a basic atomic python type (the type object itself)
        - bool
        - int (also validates longs in python 2.x)
        - float
        - str
    - asserts that the validated object is an instance

simple instance schemas:
    - an instance of any of the atomic python types (bool, int, float, str)
    - asserts that the validated object is equal

tuple schemas:
    - assert that the validated object is a tuple
    - assets that the validated tuple is the same length (with a caveat related
      to OPTIONALs, see below)
    - pairs up the items of the validated tuple with the sub-schemas in the
      schema tuple and asserts that they all match
    - sub-schemas may be OPTIONALs, in which case they don't have to be present
      at all in the validated tuple
        - all OPTIONALs must come after all non-OPTIONALs so that it is
          possible to match everything up
        - the n objects in the validated tuple after all non-OPTIONALs will be
          matched up with the *first* n OPTIONALs in the schema tuple in order
          (so for example the second OPTIONAL may be be present unless the
          first one is)

list schemas:
    - assert that the validated object is itself a list
    - only homogeneous lists may be validated, so the schema list must be of
      length 0 or 1 (although "homogeneous" is in terms of the sub-schema,
      which may actually be a UNION)
    - if the schema list is empty it will only match an empty list
    - the item in the list schema is a schema which is used to match all the
      contents of the validated list
    - if the item in the schema list is an OPTIONAL, the list is allowed to be
      empty

dict schemas:
    - assert that the validated object is a dict
    - values are schemas used to validate the validated dict's values
    - keys are used to match up the sub-schemas to their values
    - keys may be instances of simple types (bool, int, float, str)
        - asserts that the exact key is present, and matches the corresponding
          value to the sub-schema
    - keys may be simple type objects (the types, not instances)
        - matches any key of that type that is not matched by a simple type
          instance or tuple
        - by extension, allows any keys of this type in the validated dict (as
          long as their values match the paired sub-schema)
    - if a value is an OPTIONAL, specifies that the corresponding key doesn't
      necessarily have to match anything in the validated object

UNION schemas:
    - instances of UNION, the constructor of which accepts any number of
      sub-schemas as arguments
    - attempts matching the message against each of the sub-schemas, validates
      if any of them match

OPTIONAL schemas:
    - only usable inside compound schema types (tuple, list, dict)
    - specifies that a particular slot in the compound schema is optional

ANY schemas:
    - ANY is a singleton that can be used as a schema simply to consider
      anything as valid


A schema definition can be any of the above schema types and any allowed
sub-schemas.

>>> address_book_schema = [{
...     'first_name': str,
...     'last_name': str,
...     'is_male': bool,
...     'birthday': int, #unix timestamp
...     'address': {
...         'street_name': str,
...         'street_number': int,
...         'sub_number': OPTIONAL(str), #apt number or similar (the B in 345B)
...         'zip_code': int,
...         'city': str,
...         'state': OPTIONAL(str), #optional for countries without states
...         'country': str,
...     },
...     'hobbies': [OPTIONAL(str)],
...     'properties': ANY,
... }]


The API for schemas is just 4 names: OPTIONAL, UNION, ANY. and schema. The
first 3 were explained above, and schema is a metaclass whose constructor takes
a schema (like address_book_schema above), and which produces a message class
that can be used to validate, serialize, and deserialize messages which conform
to the schema.

>>> AddressBookMessage = mummy.schema(address_book_schema)
>>> abm = AddressBookMessage([{
...     'first_name': 'Travis',
...     'last_name': 'Parker',
...     'is_male': True,
...     'birthday': 442224000,
...     'address': {
...         'street_number': 11,
...         'zip_code': 12345,
...         'street_name': 'None',
...         'city': 'Of',
...         'state': 'Your',
...         'country': 'Business',
...     },
...     'hobbies': [],
...     'properties': None,
... }])
>>> abm.validate()
>>> abm.message
[{'first_name': 'Travis', 'last_name': 'Parker', 'is_male': True, 'hobbies': [], 'birthday': 442224000, 'address': {'city': 'Of', 'street_number': 11, 'country': 'Business', 'street_name': 'None', 'state': 'Your', 'zip_code': 12345}, 'properties': None}]
>>> len(abm.dumps())
64
>>> len(mummy.dumps(abm.message))
190
>>> AddressBookMessage.loads(abm.dumps()).message == abm.message
True

"""

from __future__ import absolute_import

import itertools
import sys

from .serialization import loads, dumps


__all__ = ["schema", "OPTIONAL", "UNION", "ANY"]


# python 2/3 compat stuff
if sys.version_info[0] >= 3:
    izip = zip
    imap = map
    ifilter = filter
    def iteritems(d):
        return d.items()
    def iterkeys(d):
        return d.keys()
    def itervalues(d):
        return d.values()
    long = int
else:
    izip = itertools.izip
    imap = itertools.imap
    ifilter = itertools.ifilter
    def iteritems(d):
        return d.iteritems()
    def iterkeys(d):
        return d.iterkeys()
    def itervalues(d):
        return d.itervalues()


_primitives = (bool, int, float, str)
_type_validations = {
    bool: bool,
    int: (int, long),
    float: float,
    str: str,
}

class OPTIONAL(object):
    "wraps a schema dictionary key to specify that it is optional"
    def __init__(self, schema):
        self.schema = schema

    def __repr__(self):
        return "OPTIONAL(%r)" % (self.schema,)

def _optional(x):
    return isinstance(x, OPTIONAL)

def _required(x):
    return not isinstance(x, OPTIONAL)

class UNION(object):
    "specify that a message may match any of the sub-schemas"
    def __init__(self, *options):
        self.options = options

    def __repr__(self):
        return "UNION(%r)" % (list(self.options),)

class ANY(object):
    "validates any object successfully"
    def __call__(self):
        return self

    def __repr__(self):
        return "<ANY>"
ANY = ANY()


##
## Validation
##

def _validate_simple(schema, message):
    if isinstance(message, _type_validations[schema]):
        return True, None
    return False, (message, schema)

def _validate_simple_instance(schema, message):
    if schema == message:
        return True, None
    return False, (message, schema)

def _validate_tuple(schema, message):
    if not isinstance(message, tuple):
        return False, (message, schema)

    if len(message) > len(schema):
        return False, (message, schema)

    required = izip(
            itertools.takewhile(_required, schema),
            message)

    for i, (sub_schema, sub_message) in enumerate(required):
        matched, info = _validate(sub_schema, sub_message)
        if not matched:
            return False, info

    optional = itertools.islice(izip(schema, message), i + 1, None)

    for sub_schema, sub_message in optional:
        matched, info = _validate(sub_schema, sub_message)
        if not matched:
            return False, info

    return True, None

def _validate_list(schema, message):
    if not isinstance(message, list):
        return False, (message, schema)

    if not schema:
        if message:
            return False, (message, schema)
        return True, None

    sub_schema = schema[0]
    if isinstance(sub_schema, OPTIONAL):
        if not message:
            return True, None
        sub_schema = sub_schema.schema
    elif not message:
        return False, (message, schema)

    for sub_message in message:
        matched, info = _validate(sub_schema, sub_message)
        if not matched:
            return False, info

    return True, None

def _validate_dict(schema, message):
    if not isinstance(message, dict):
        return False, (message, schema)

    required_keys = set(
            k for k, v in iteritems(schema)
            if not isinstance(v, OPTIONAL))
    required_wildcards = required_keys.intersection(_primitives)
    required_keys.difference_update(_primitives)

    msg_keys = set(message)

    # missing required keys
    if required_keys - msg_keys:
        return False, (message, schema)

    # missing required wildcards
    if required_wildcards - set(imap(type, message)):
        return False, (message, schema)

    wildcards = set(_primitives)
    wildcards.intersection_update(schema)

    # extra non-allowed keys
    msg_keys.difference_update(schema)
    if set(imap(type, msg_keys)) - wildcards:
        return False, (message, schema)

    # now validate sub_schemas/sub_messages
    for key, sub_message in iteritems(message):
        if key in schema:
            sub_schema = schema[key]
        else:
            sub_schema = schema[type(key)]

        if isinstance(sub_schema, OPTIONAL):
            sub_schema = sub_schema.schema

        matched, info = _validate(sub_schema, sub_message)
        if not matched:
            return False, info

    return True, None

def _validate_union(schema, message):
    for sub_schema in schema.options:
        matched, info = _validate(sub_schema, message)
        if matched:
            return True, None
    return False, (message, schema)

def _validate_any(schema, message):
    return True, None

_validators = {
    bool: _validate_simple_instance,
    int: _validate_simple_instance,
    long: _validate_simple_instance,
    float: _validate_simple_instance,
    str: _validate_simple_instance,
    type: _validate_simple,
    tuple: _validate_tuple,
    list: _validate_list,
    dict: _validate_dict,
    UNION: _validate_union,
    type(ANY): _validate_any,
}

def _validate(schema, message):
    return _validators[type(schema)](schema, message)


##
## Validation of the Schema itself
##

def _validate_simple_instance_schema(schema):
    return True, None

def _validate_simple_schema(schema):
    if schema in _type_validations:
        return True, None
    return False, schema

def _validate_tuple_schema(schema):
    for sub_schema in schema:
        if isinstance(sub_schema, OPTIONAL):
            sub_schema = sub_schema.schema
        valid, info = _validate_schema(sub_schema)
        if not valid:
            return False, info
    return True, None

def _validate_list_schema(schema):
    if not schema:
        return True, None

    if len(schema) != 1:
        return False, schema

    sub_schema = schema[0]
    if isinstance(sub_schema, OPTIONAL):
        sub_schema = sub_schema.schema

    return _validate_schema(sub_schema)

def _validate_dict_schema(schema):
    for key in iterkeys(schema):
        if isinstance(key, _primitives + (long,)):
            continue

        if key in _primitives:
            continue

        return False, schema

    for sub_schema in itervalues(schema):
        if isinstance(sub_schema, OPTIONAL):
            sub_schema = sub_schema.schema
        valid, info = _validate_schema(sub_schema)
        if not valid:
            return False, info

    return True, None

def _validate_union_schema(schema):
    for sub_schema in schema.options:
        valid, info = _validate_schema(sub_schema)
        if not valid:
            return False, info
    return True, None

def _validate_any_schema(schema):
    return True, None

_schema_validators = {
    bool: _validate_simple_instance_schema,
    int: _validate_simple_instance_schema,
    long: _validate_simple_instance_schema,
    float: _validate_simple_instance_schema,
    str: _validate_simple_instance_schema,
    type: _validate_simple_schema,
    tuple: _validate_tuple_schema,
    list: _validate_list_schema,
    dict: _validate_dict_schema,
    UNION: _validate_union_schema,
    type(ANY): _validate_any_schema,
}

def _validate_schema(schema):
    schema_type = type(schema)
    if schema_type not in _schema_validators:
        return False, schema
    return _schema_validators[schema_type](schema)


##
## [un]transforming messages based on a schema
##

def _group_schema_keys(schema):
    key_set = set(schema)

    key_set.difference_update(_type_validations)

    optional = [k for k, v in iteritems(schema) if isinstance(v, OPTIONAL)]
    key_set.difference_update(optional)
    optional.sort()

    required = list(key_set)
    required.sort()

    return required, optional

def _transform(schema, message):
    if isinstance(schema, list):
        return [_transform(s, m) for s, m in izip(schema, message)]

    if isinstance(schema, tuple):
        return tuple(_transform(s, m) for s, m in izip(schema, message))

    if not isinstance(schema, dict):
        return message

    required, optional = _group_schema_keys(schema)

    msgkeys = set(message)

    result = []
    for key in required:
        result.append(_transform(schema[key], message[key]))
    for key in optional:
        if key in message:
            result.append(_transform(schema[key], message[key]))
        else:
            result.append(None)
    msgkeys.difference_update(required)
    msgkeys.difference_update(optional)

    for key in msgkeys:
        result.append(key)
        result.append(_transform(schema[type(message[key])], message[key]))

    return result

def _untransform(schema, message):
    if isinstance(schema, list):
        return [_untransform(s, m) for s, m in izip(schema, message)]

    if isinstance(schema, tuple):
        return tuple(_untransform(s, m) for s, m in izip(schema, message))

    if not isinstance(schema, dict):
        return message

    required, optional = _group_schema_keys(schema)
    result = {}

    for key, value in izip(required, message):
        result[key] = _untransform(schema[key], value)

    for key, value in izip(optional, itertools.islice(
            message, len(required), None)):
        if value is not None:
            result[key] = _untransform(schema[key], value)

    is_key = True
    for item in itertools.islice(
            message, len(required) + len(optional), None):
        if is_key:
            key = item
        else:
            result[key] = _untransform(schema[type(item)], item)
        is_key = not is_key

    return result


##
## the schema metaclass
##

class _Invalid(Exception):
    pass

class InvalidSchema(_Invalid):
    pass

class _BaseMessage(object):
    def __init__(self, message):
        self.message = message
        self._validation = None
        self._transformation = None

    def validate(self):
        if self._validation is None:
            self._validation = _validate(self.SCHEMA, self.message)
        if not self._validation[0]:
            raise self.InvalidMessage(self._validation[1])

    def transform(self):
        self.validate()
        if self._transformation is None:
            self._transformation = _transform(self.SCHEMA, self.message)
        return self._transformation

    def dumps(self):
        self.validate()
        return dumps(self.transform())

    @classmethod
    def untransform(cls, message):
        return _untransform(cls.SCHEMA, message)

    @classmethod
    def loads(cls, message):
        return cls(cls.untransform(loads(message)))

class schema(type):
    def __new__(metacls, schema):
        valid, info = _validate_schema(schema)
        if not valid:
            raise InvalidSchema(info)

        return type.__new__(metacls, 'Message', (_BaseMessage,), {
            'SCHEMA': schema,
            'InvalidMessage': type('InvalidMessage', (_Invalid,), {})})
