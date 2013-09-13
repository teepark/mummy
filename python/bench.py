#!/usr/bin/env python

import random
import sys
import time

import mummy
import oldmummy

try:
    import cPickle
except ImportError:
    import pickle as cPickle
import string

try:
    import bson
except ImportError:
    bson = None
try:
    import yajl
except ImportError:
    yajl = None
try:
    import cjson
except ImportError:
    cjson = None
try:
    import simplejson
except ImportError:
    simplejson = None
try:
	import wbin
except ImportError:
	wbin = None
try:
    import msgpack
except ImportError:
    msgpack = None


test_data = [
"'this is a test'",
'''[{
    "name": "foo",
    "type": "bar",
    "count": 1,
    "info": {
        "x": 203,
        "y": 102,
        "z": list(range(5))
    }
}] * 100''',
"{'x': 203, 'y': 102, 'z': list(range(5))}",
"[0, 1, 2, 3, 4]", 
"{'a': {}}",
#"[]",
#"[[]] * 500",
#"[random.random() for i in xrange(1000)]",
#"[None] * 5000",
#"[dict.fromkeys(map(str, range(20)), 14.3)] * 100",
]


def ttt(f, data=None, x=10*1000):
    start = time.time()
    while x:
        x -= 1
        foo = f(data)
    return time.time()-start


def profile(serial, deserial, data, x=10*1000):
    squashed = serial(data)
    return (ttt(serial, data, x), ttt(deserial, squashed, x), len(squashed))


def equalish(a, b):
    if isinstance(a, (tuple, list)) and isinstance(b, (tuple, list)):
        a, b = tuple(a), tuple(b)
        for suba, subb in zip(a, b):
            if not equalish(suba, subb):
                return False
        return True
    if isinstance(a, dict) and isinstance(b, dict):
        return equalish(a.items(), b.items())
    return a == b


def test(serial, deserial, data):
    assert equalish(deserial(serial(data)), data)


def format(flt, prec=3):
    s = str(round(flt, prec))
    return padright(s, s.index(".") + 4, "0")


def padright(s, upto, padchar=" "):
    return s + (padchar * (upto - len(s)))


contenders = [
        ('mummy', (lambda s: mummy.dumps(s), mummy.loads)),
        ('oldmummy', (lambda s: oldmummy.dumps(s), oldmummy.loads))]
if wbin:
	contenders.append(('wirebin', (wbin.serialize, wbin.deserialize)))
if msgpack:
    contenders.append(('msgpack', (msgpack.dumps, msgpack.loads)))
if yajl:
    contenders.append(('py-yajl', (yajl.dumps, yajl.loads)))
if cjson:
    contenders.append(('cjson', (cjson.encode, cjson.decode)))
if bson:
    contenders.append(('bson', (bson.BSON.encode, lambda s: bson.BSON(s).decode())))
#contenders.append(('cPickle (protocol 2)',
#    (lambda x: cPickle.dumps(x, 2), cPickle.loads)))
#contenders.append(('cPickle (protocol 1)',
#    (lambda x: cPickle.dumps(x, 1), cPickle.loads)))
#contenders.append(('cPickle (protocol 0)', (cPickle.dumps, cPickle.loads)))
#if simplejson:
#    contenders.append(('simplejson', (simplejson.dumps, simplejson.loads)))
#contenders.append(('repr/eval', (repr, eval)))
#contenders.append(('mummy pure-python',
#	(mummy.pure_python_dumps, mummy.pure_python_loads)))

if __name__ == '__main__':
    tmpl = string.Template(
        "$name serialize: $ser  deserialize: $des  total: $tot  size: $size")
    for sdata in test_data:
        print sdata
        data = eval(sdata)
        for name, (serial, deserial) in contenders:
            test(serial, deserial, data)
            x, y, size = profile(serial, deserial, data)
            print(tmpl.substitute(
                name=padright(name, 20),
                ser=format(x, 6),
                des=format(y, 6),
                tot=format(x + y, 6),
                size=size,
            ))
        print
