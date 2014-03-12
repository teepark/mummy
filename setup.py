import errno
import os
import sys

from setuptools import setup, Extension


VERSION = (1, 0, 3, "")

info = {
    'name': 'mummy',
    'description': 'fast, efficient serialization',
    'packages': ['mummy', 'oldmummy'],
    'package_dir': {'': 'python'},
    'version': '.'.join(filter(None, map(str, VERSION))),
    'author': 'Travis Parker',
    'author_email': 'travis.parker@gmail.com',
    'url': 'http://github.com/teepark/mummy',
    'license': 'BSD',
    'classifiers': [
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Natural Language :: English",
        "Programming Language :: C",
        "Programming Language :: Python",
    ],
}

if sys.subversion[0].lower() != 'pypy':
    info['ext_modules'] = [
        Extension(
            '_mummy',
            ['python/dump.c', 'python/load.c', 'python/mummymodule.c',
                'lzf/lzf_c.c', 'lzf/lzf_d.c',
                'lib/mummy_string.c', 'lib/dump.c', 'lib/load.c'],
            include_dirs=('python', 'lzf', 'include'),
            extra_compile_args=['-Wall']),
        Extension(
            '_oldmummy',
            ['python/_old_mummy.c', 'lzf/lzf_c.c', 'lzf/lzf_d.c'],
            include_dirs=('python', 'lzf'),
            extra_compile_args=['-Wall']),
        ]

setup(**info)
