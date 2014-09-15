from distutils.core import setup
from setuptools import setup, find_packages

setup( name='siptest',
    version='0.1',
    description='Sipp test tool',
    author='Stas Kridzanovskiy',
    author_email='slaviann@gmail.com',
    packages=find_packages(),
      install_requires=[
          'twisted',
          'dpkt-fix',
      ],
    scripts=['bin/siptest'],

    )
