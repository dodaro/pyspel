from setuptools import setup, find_packages

VERSION = '1.0.0'
NAME = 'pyspel'
DESCRIPTION = 'Python Specification Language (Pyspel)'
LONG_DESCRIPTION = 'Pyspel is a python-based specification language that combines python programs with Answer Set Programming'

setup(
  name=NAME,
  packages=find_packages(),
  version='1.0.0',
  license='Apache 2.0',
  description=DESCRIPTION,
  long_description=LONG_DESCRIPTION,
  author='Carmine Dodaro',
  author_email='carmine.dodaro@unical.it',
  url='https://github.com/dodaro/pyspel',
  download_url='https://github.com/dodaro/pyspel/archive/refs/tags/v1.0.0.tar.gz',
  keywords=['answer set programming', 'specification language', 'combinatorial problems'],
  install_requires=['decorator'],
  classifiers=[
    'Development Status :: 4 - Beta',
    'Intended Audience :: Developers',
    'Topic :: Software Development :: Build Tools',
    'License :: OSI Approved :: Apache Software License',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.7',
    'Programming Language :: Python :: 3.8',
    'Programming Language :: Python :: 3.9',
  ],
)
