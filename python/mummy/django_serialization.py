import mummy
from StringIO import StringIO

from django.core.serializers.python import Serializer as PythonSerializer
from django.core.serializers.python import Deserializer as PythonDeserializer
from django.utils import datetime_safe
try:
    import decimal
except ImportError:
    from django.utils import _decimal as decimal # Python 2.3 fallback


class Serializer(PythonSerializer):
    internal_use_only = False

    DATE_FORMAT = "%Y-%m-%d"
    TIME_FORMAT = "%H:%M:%S"

    def end_serialization(self):
        self.options.pop('stream', None)
        self.options.pop('fields', None)
        self.stream.write(mummy.dumps(self.objects))

    def getvalue(self):
        if callable(getattr(self.stream, 'getvalue', None)):
            return self.stream.getvalue()


def Deserializer(stream_or_string, **options):
    if isinstance(stream_or_string, basestring):
        stream = StringIO(stream_or_string)
    else:
        stream = stream_or_string
    for obj in PythonDeserializer(mummy.loads(stream.read())):
        yield obj
