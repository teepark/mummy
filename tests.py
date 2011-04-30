#!/usr/bin/env python

import datetime
import decimal
try:
    import fractions
except ImportError:
    fractions = None
from random import randrange
import string
import sys
import unittest

import mummy


if sys.version_info[0] >= 3:
    def unicodify(s):
        return s
    def bytify(s):
        return s.encode("utf8")
    def iteritems(d):
        return d.items()
else:
    def unicodify(s):
        return s.decode("utf8")
    def bytify(s):
        return s
    def iteritems(d):
        return d.iteritems()


class BasicMummyTests(unittest.TestCase):
    def assertEqual(self, a, b):
        if isinstance(a, decimal.Decimal) and a.is_nan():
            self.assert_(isinstance(b, decimal.Decimal) and b.is_nan(), (a, b))
        else:
            super(BasicMummyTests, self).assertEqual(a, b)

    def encoding_reference(self, val, default=None):
        c = mummy.dumps(val, default)
        py = mummy.pure_python_dumps(val, default)
        self.assertEqual(c, py)

    def decoding_reference(self, data):
        c = mummy.loads(data)
        py = mummy.pure_python_loads(data)
        self.assertEqual(c, py)

    def roundtrip(self, val, default=None):
        encoded = mummy.dumps(val, default)
        finished = mummy.loads(encoded)
        self.assertEqual(val, finished)

    def pure_python_roundtrip(self, val, default=None):
        encoded = mummy.pure_python_dumps(val, default)
        finished = mummy.pure_python_loads(encoded)

        if isinstance(val, decimal.Decimal) and val.is_nan():
            self.assert_(isinstance(finished, decimal.Decimal) and
                    finished.is_nan(), finished)
        else:
            self.assertEqual(val, finished)


def _make_test(name, target):
    def test_encoding_reference(self):
        self.encoding_reference(target)

    def test_decoding_reference(self):
        self.decoding_reference(mummy.dumps(target))

    def test_roundtrip(self):
        self.roundtrip(target)

    def test_pure_python_roundtrip(self):
        self.pure_python_roundtrip(target)

    return type(name + 'Test', (BasicMummyTests,), locals())


def generate(targets):
    globals()['tests'] = targets
    for title, target in iteritems(targets):
        globals()[title + 'Test'] = _make_test(title, target)


generate({
    'None': None,
    'True': True,
    'False': False,
    'LotsOfBools': [True, False] * 5000,

    'NegativeOneChar': -1,
    'ZeroChar': 0,
    'PositiveOneChar': 1,
    'MinChar': -1 << 7,
    'MaxChar': (1 << 7) - 1,

    'MaxNegativeShort': (-1 << 7) - 1,
    'MinPositiveShort': 1 << 7,
    'MinShort': -1 << 15,
    'MaxShort': (1 << 15) - 1,

    'MaxNegativeInt': (-1 << 15) - 1,
    'MinPositiveInt': 1 << 15,
    'MinInt': -1 << 31,
    'MaxInt': (1 << 31) - 1,

    'MaxNegativeLong': (-1 << 31) - 1,
    'MinPositiveLong': 1 << 31,
    'MinLong': -1 << 63,
    'MaxLong': (1 << 63) - 1,

    'MaxNegativeHuge': (-1 << 63) - 1,
    'MinPositiveHuge': 1 << 63,
    'BigNegativeHuge': -0x10deb23ab8184340de1e6337,
    'BigPositiveHuge': 0x10deb23ab8184340de1e6337,

    'ZeroFloat': 0.0,
    'PositiveFloat': 632.345,
    'NegativeFloat': -928.346,
    'BigPositiveFloat': 9.4182e100,
    'BigNegativeFloat': 5.2734e100,

    'ShortString': bytify("hello"),
    'LongString': bytify('this is a test,') * 20,
    'ShortUnicode': unicodify("hiya"),
    'LongUnicode': unicodify("this is still a test") * 20,

    'OverflowingHuge': (1 << 33000) - 1,
    'OverflowingHuge2': 1 << 33000,
    'OverflowingLongString': bytify("oh") * 4096,
    'OverflowingLongUnicode': unicodify("oh") * 4096,

    'StringList': list(bytify(string.ascii_letters)),
    'CharList': list(range(-128, 128)),
    #'HugeList': [randrange(1 << 64, 1 << 3000) for i in range(30)],

    'StringTuple': tuple(bytify(string.ascii_letters)),
    'CharTuple': tuple(list(range(-128, 128))),
    #'HugeTuple': tuple(randrange(1 << 64, 1 << 3000) for i in range(30)),

    'DateToday': datetime.date.today(),
    'TimeNow': datetime.datetime.now().time(),
    'DateTimeNow': datetime.datetime.now(),
    'TimeDelta': datetime.timedelta(3, 11, 12345),

    'DecimalNaN': decimal.Decimal('NaN'),
    'DecimalSNaN': decimal.Decimal('sNaN'),
    'DecimalInfinity': decimal.Decimal('Infinity'),
    'DecimalNegInfinity': decimal.Decimal('-Infinity'),
    'DecimalPositiveOdd': decimal.Decimal('106.1984'),
    'DecimalNegaviteOdd': decimal.Decimal('-106.1984'),
    'DecimalPositiveEven': decimal.Decimal('1106.1984'),
    'DecimalNegativeEven': decimal.Decimal('-1106.1984'),
})


class ExtensionExistsTest(unittest.TestCase):
    def runTest(self):
        assert mummy.has_extension


class RecursionDepthTest(unittest.TestCase):

    # python prints out an extra warning even when the recursion
    # depth exception is caught. this is expected, so silence it
    def setUp(self):
        self._stderr = sys.stderr
        sys.stderr = open("/dev/null", "w")

    def tearDown(self):
        sys.stderr.close()
        sys.stderr = self._stderr

    def test_c_version(self):
        l = []
        l.append(l)
        self.assertRaises(ValueError, mummy.dumps, l)

    def test_pure_python_version(self):
        l = []
        l.append(l)
        self.assertRaises(ValueError, mummy.pure_python_dumps, l)


class DefaultFormatterTest(BasicMummyTests):
    if fractions:
        def fraction_formatter(self, f):
            if isinstance(f, fractions.Fraction):
                return (f.numerator, f.denominator)
            raise TypeError("unserializable")

        def test_fractions(self):
            f = fractions.Fraction(5, 7)
            d = self.fraction_formatter
            self.encoding_reference(f, d)
            self.decoding_reference(mummy.dumps(f, d))


if __name__ == '__main__':
    unittest.main()
