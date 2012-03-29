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
      length 0 or 1 (although "homogeneous" is in terms of the sub-schemata,
      which may actually be UNIONs)
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

RULE schemas:
    - the RULE constructor accepts a function as an argument; the function
      should take one argument and return a boolean. the schema requires that
      the function, when called on the matched message, returns True


A schema definition can be any of the above schema types and any allowed
sub-schemas.

>>> address_book_schema = [{
...     'first_name': str,
...     'last_name': str,
...     'is_male': bool,
...     'birthday': datetime.date,
...     'address': {
...         'street_name': str,
...         'street_number': int,
...         OPTIONAL('sub_number'): str, # apt # or similar (eg the B in 345B)
...         'zip_code': int,
...         'city': str,
...         OPTIONAL('state'): str, # optional for countries without states
...         'country': str,
...     },
...     'hobbies': [OPTIONAL(str)],
...     'properties': ANY,
... }]


The API for schemas is just 5 names: OPTIONAL, UNION, ANY, RULE, and Message.
The first 4 were explained above. Message is a base class you can use to create
message classes; just give them a SCHEMA attribute of a valid schema and they
can be used to validate, shorten, and serialize their instances.

>>> import mummy
>>> class AddressBookMessage(mummy.Message):
...     SCHEMA = address_book_schema
...

abm = AddressBookMessage([{
    'first_name': 'Travis',
    'last_name': 'Parker',
    'is_male': True,
    'birthday': datetime.date(1984, 1, 6),
    'address': {
        'street_number': 11,
        'zip_code': 12345,
        'street_name': 'None',
        'city': 'Of',
        'state': 'Your',
        'country': 'Business',
    },
    'hobbies': [],
    'properties': None,
}])

>>> abm.validate()

>>> abm.message
[{'first_name': 'Travis', 'last_name': 'Parker', 'is_male': True, 'hobbies': [], 'birthday': datetime.date(1984, 1, 6), 'address': {'city': 'Of', 'street_number': 11, 'country': 'Business', 'street_name': 'None', 'state': 'Your', 'zip_code': 12345}, 'properties': None}]


Instances of the message class are able to shorten the serialized data by
removing information that is already present in the schema itself, and the
message class itself is able to undo that transformation.

>>> abm.transform()
[[['Of', 'Business', 'None', 11, 12345, 'Your', None], datetime.date(1984, 1, 6), 'Travis', [], True, 'Parker', None]]
>>> AddressBookMessage.untransform(abm.transform()) == abm.message
True


The result is that messages serialized through a Message class are much shorter
than if the same data were serialized via basic mummy.dumps, but as long as the
message receiver has the schema as well, no information is lost.

>>> len(abm.dumps())
64
>>> len(mummy.dumps(abm.message))
195
>>> AddressBookMessage.loads(abm.dumps()).message == abm.message
True

"""

from __future__ import absolute_import

import datetime
import decimal
import itertools
import sys

from .serialization import loads, dumps


__all__ = ["Message", "OPTIONAL", "UNION", "ANY"]


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


_primitives = (
        bool, int, float, str,
        datetime.date, datetime.time, datetime.datetime, datetime.timedelta,
        decimal.Decimal)
_type_validations = {
    bool: bool,
    int: (int, long),
    float: float,
    str: str,
    datetime.date: datetime.date,
    datetime.time: datetime.time,
    datetime.datetime: datetime.datetime,
    datetime.timedelta: datetime.timedelta,
    decimal.Decimal: decimal.Decimal,
}

class OPTIONAL(object):
    """specifies that a piece of a schema is optional in some specific contexts

    - as a dictionary key, allows that key to be left out
    - as a member of a tuple schema, allows the message tuple to be left out
    - as the only member of a list schema, allows the message list to be empty
    """
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

class RULE(object):
    "require that a message passes a given boolean predicate"
    def __init__(self, pred):
        self.pred = pred

    def __repr__(self):
        return "<RULE (%r)>" % self.pred


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

    required_keys = set(k for k in schema if not isinstance(k, OPTIONAL))
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
    msg_keys.difference_update(
            k.schema for k in schema if isinstance(k, OPTIONAL))
    if set(imap(type, msg_keys)) - wildcards:
        return False, (message, schema)

    schema = schema.copy()
    schema.update(
        dict((k.schema, v) for k, v in iteritems(schema)
            if isinstance(k, OPTIONAL)))

    # now validate sub_schemas/sub_messages
    for key, sub_message in iteritems(message):
        if key in schema:
            sub_schema = schema[key]
        else:
            sub_schema = schema[type(key)]

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

def _validate_rule(schema, message):
    if schema.pred(message):
        return True, None
    return False, (message, schema)

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
    RULE: _validate_rule,
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
        if isinstance(key, OPTIONAL):
            key = key.schema

        if isinstance(key, _primitives + (long,)):
            continue

        if key in _primitives:
            continue

        return False, schema

    for sub_schema in itervalues(schema):
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

def _validate_rule_schema(schema):
    if callable(getattr(schema, "pred", None)):
        return True, None
    return False, schema

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
    RULE: _validate_rule_schema,
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

    optional = [k for k in schema if isinstance(k, OPTIONAL)]
    key_set.difference_update(optional)
    optional = [k.schema for k in optional]
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

    schema = schema.copy()
    schema.update(
            dict((k.schema, v) for k, v in iteritems(schema)
                if isinstance(k, OPTIONAL)))

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

    schema = schema.copy()
    schema.update(
            dict((k.schema, v) for k, v in iteritems(schema)
                if isinstance(k, OPTIONAL)))

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


class _validated_schema(type):
    def __init__(cls, *args, **kwargs):
        super(_validated_schema, cls).__init__(*args, **kwargs)
        if hasattr(cls, "SCHEMA"):
            valid, info = _validate_schema(cls.SCHEMA)
            if not valid:
                raise InvalidSchema(info)

        cls.InvalidMessage = type('InvalidMessage', (_Invalid,), {})

class Message(object):
    __metaclass__ = _validated_schema

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
