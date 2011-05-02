#!/usr/bin/env python

import sys
import time

import mummy
try:
    import cPickle
except ImportError:
    import pickle as cPickle
import string

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

default_data = {
    "name": "Foo",
    "type": "Bar",
    "count": 1,
    "info": {
        "x": 203,
        "y": 102,
        "z": list(range(5)),},}


def ttt(f, data=None, x=100*1000):
    start = time.time()
    while x:
        x -= 1
        foo = f(data)
    return time.time()-start


def profile(serial, deserial, data=None, x=100*1000):
    if not data:
        data = default_data
    squashed = serial(data)
    return (ttt(serial, data, x), ttt(deserial, squashed, x), len(squashed))


def test(serial, deserial, data=None):
    if not data:
        data = default_data
    assert deserial(serial(data)) == data


def format(flt, prec=3):
    s = str(round(flt, prec))
    return padright(s, s.index(".") + 4, "0")


def padright(s, upto, padchar=" "):
    return s + (padchar * (upto - len(s)))


contenders = [('mummy', (mummy.dumps, mummy.loads))]
if wbin:
	contenders.append(('wirebin', (wbin.serialize, wbin.deserialize)))
if yajl:
    contenders.append(('py-yajl', (yajl.dumps, yajl.loads)))
if cjson:
    contenders.append(('cjson', (cjson.encode, cjson.decode)))
contenders.append(('cPickle (protocol 2)',
    (lambda x: cPickle.dumps(x, 2), cPickle.loads)))
contenders.append(('cPickle (protocol 1)',
    (lambda x: cPickle.dumps(x, 1), cPickle.loads)))
contenders.append(('cPickle (protocol 0)', (cPickle.dumps, cPickle.loads)))
if simplejson:
    contenders.append(('simplejson', (simplejson.dumps, simplejson.loads)))
contenders.append(('repr/eval', (repr, eval)))
contenders.append(('mummy pure-python',
	(mummy.pure_python_dumps, mummy.pure_python_loads)))

if __name__ == '__main__':
    tmpl = string.Template(
        "$name serialize: $ser  deserialize: $des  total: $tot  size: $size")
    for name, args in contenders:
        test(*args)
        x, y, size = profile(*args)
        print(tmpl.substitute(
            name=padright(name, 20),
            ser=format(x),
            des=format(y),
            tot=format(x + y),
            size=size,
        ))
