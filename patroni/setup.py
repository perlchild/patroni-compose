#!/usr/bin/env python

"""
    Setup file for patroni
"""

import sys
import os
import inspect

import setuptools
from setuptools.command.test import test as TestCommand
from setuptools import setup

if sys.version_info < (2, 7, 0):
    sys.stderr.write('FATAL: patroni needs to be run with Python 2.7+\n')
    sys.exit(1)

__location__ = os.path.join(os.getcwd(), os.path.dirname(inspect.getfile(inspect.currentframe())))


def read_version(package):
    data = {}
    with open(os.path.join(package, 'version.py'), 'r') as fd:
        exec(fd.read(), data)
    return data['__version__']

NAME = 'patroni'
MAIN_PACKAGE = NAME
SCRIPTS = 'scripts'
VERSION = read_version(MAIN_PACKAGE)
DESCRIPTION = 'PostgreSQL High-Available orchestrator and CLI'
LICENSE = 'The MIT License'
URL = 'https://github.com/zalando/patroni'
AUTHOR = 'Alexander Kukushkin, Oleksii Kliukin, Feike Steenbergen'
AUTHOR_EMAIL = 'alexander.kukushkin@zalando.de, oleksii.kliukin@zalando.de, feike.steenbergen@zalando.de'
KEYWORDS = 'etcd governor patroni postgresql postgres ha zookeeper streaming replication'

COVERAGE_XML = True
COVERAGE_HTML = False
JUNIT_XML = True

# Add here all kinds of additional classifiers as defined under
# https://pypi.python.org/pypi?%3Aaction=list_classifiers
CLASSIFIERS = [
    'Development Status :: 4 - Beta',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'Intended Audience :: System Administrators',
    'License :: OSI Approved :: MIT License',
    'Operating System :: POSIX :: Linux',
    'Programming Language :: Python',
    'Programming Language :: Python :: 2.7',
    'Programming Language :: Python :: 3.3',
    'Programming Language :: Python :: 3.4',
    'Programming Language :: Python :: Implementation :: CPython',
]

CONSOLE_SCRIPTS = ['patroni = patroni:main',
                   'patronictl = patroni.ctl:ctl',
                   "patroni_wale_restore = patroni.scripts.wale_restore:main",
                   "patroni_aws = patroni.scripts.aws:main"]


class PyTest(TestCommand):

    user_options = [('cov=', None, 'Run coverage'), ('cov-xml=', None, 'Generate junit xml report'), ('cov-html=',
                    None, 'Generate junit html report'), ('junitxml=', None, 'Generate xml of test results')]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.cov_xml = False
        self.cov_html = False
        self.junitxml = None

    def finalize_options(self):
        TestCommand.finalize_options(self)
        if self.cov_xml or self.cov_html:
            self.cov = ['--cov', MAIN_PACKAGE, '--cov', MAIN_PACKAGE, '--cov-report', 'term-missing']
            if self.cov_xml:
                self.cov.extend(['--cov-report', 'xml'])
            if self.cov_html:
                self.cov.extend(['--cov-report', 'html'])
        if self.junitxml is not None:
            self.junitxml = ['--junitxml', self.junitxml]

    def run_tests(self):
        try:
            import pytest
        except:
            raise RuntimeError('py.test is not installed, run: pip install pytest')
        params = {'args': self.test_args}
        if self.cov:
            params['args'] += self.cov
        if self.junitxml:
            params['args'] += self.junitxml
        params['args'] += ['--doctest-modules', MAIN_PACKAGE, '-s', '-vv']
        errno = pytest.main(**params)
        sys.exit(errno)


def get_install_requirements(path):
    content = open(os.path.join(__location__, path)).read()
    return [req for req in content.split('\n') if req != '']


def read(fname):
    return open(os.path.join(__location__, fname)).read()


def setup_package():
    # Assemble additional setup commands
    cmdclass = {}
    cmdclass['test'] = PyTest

    # Some helper variables
    version = os.getenv('GO_PIPELINE_LABEL', VERSION)

    requirements = 'requirements-py2.txt' if sys.version_info[0] == 2 else 'requirements-py3.txt'
    install_reqs = get_install_requirements(requirements)

    command_options = {'test': {'test_suite': ('setup.py', 'tests')}}
    if JUNIT_XML:
        command_options['test']['junitxml'] = 'setup.py', 'junit.xml'
    if COVERAGE_XML:
        command_options['test']['cov_xml'] = 'setup.py', True
    if COVERAGE_HTML:
        command_options['test']['cov_html'] = 'setup.py', True

    setup(
        name=NAME,
        version=version,
        url=URL,
        author=AUTHOR,
        author_email=AUTHOR_EMAIL,
        description=DESCRIPTION,
        license=LICENSE,
        keywords=KEYWORDS,
        long_description=read('README.rst'),
        classifiers=CLASSIFIERS,
        test_suite='tests',
        packages=setuptools.find_packages(exclude=['tests', 'tests.*']),
        package_data={MAIN_PACKAGE: ["*.json"]},
        install_requires=install_reqs,
        setup_requires=['six', 'flake8'],
        cmdclass=cmdclass,
        tests_require=['pytest-cov', 'pytest'],
        command_options=command_options,
        entry_points={'console_scripts': CONSOLE_SCRIPTS},
    )


if __name__ == '__main__':
    setup_package()
