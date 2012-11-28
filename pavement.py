import errno
import os
import sys

from setuptools import Extension

from paver.easy import *
from paver.path import path
from paver.setuputils import setup


VERSION = (1, 0, 1, "")

info = dict(
    name="mummy",
    description="fast, efficient serialization",
    packages=["mummy", "oldmummy"],
    package_dir={'': 'python'},
    version=".".join(filter(None, map(str, VERSION))),
    author="Travis Parker",
    author_email="travis.parker@gmail.com",
    url="http://github.com/teepark/mummy",
    license="BSD",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Natural Language :: English",
        "Programming Language :: C",
        "Programming Language :: Python",
    ],
)

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

MANIFEST = (
    "setup.py",
    "paver-minilib.zip",
    "include/mummy.h",
    "python/mummypy.h",
    "lzf/lzf.h",
    "lzf/lzfP.h",
)

@task
def manifest():
    path('MANIFEST.in').write_lines('include %s' % x for x in MANIFEST)

@task
@needs('generate_setup', 'minilib', 'manifest', 'setuptools.command.sdist')
def sdist():
    pass

@task
def clean():
    for p in map(path, ('mummy.egg-info', 'dist', 'build', 'MANIFEST.in')):
        if p.exists():
            if p.isdir():
                p.rmtree()
            else:
                p.remove()
    for p in path(__file__).abspath().parent.walkfiles():
        if p.endswith(".pyc") or p.endswith(".pyo"):
            try:
                p.remove()
            except OSError, exc:
                if exc.args[0] == errno.EACCES:
                    continue
                raise

@task
def test():
    sh("cd python; nosetests")

@task
def docs():
    sh("find docs/source/mummy -name *.rst | xargs touch")
    sh("cd docs; make html")
