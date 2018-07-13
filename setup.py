from setuptools import find_packages, setup

import os
import re


def get_version():
    with open(os.path.join(os.path.dirname(__file__), 'phxd', '__init__.py')) as fp:
        return re.match(r".*__version__ = '(.*?)'", fp.read(), re.S).group(1)


def get_requirements():
    with open(os.path.join(os.path.dirname(__file__), 'requirements.txt')) as fp:
        return [line.strip() for line in fp.read().splitlines() if line.strip()]


setup(
    name='phxd',
    version=get_version(),
    description='A Hotline server written in Python using Twisted.',
    author='Dan Watson',
    author_email='dcwatson@gmail.com',
    url='https://github.com/dcwatson/phxd',
    license='BSD',
    packages=find_packages(),
    install_requires=get_requirements(),
    scripts=[
        'scripts/phxd',
        'scripts/phx',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
    ]
)
