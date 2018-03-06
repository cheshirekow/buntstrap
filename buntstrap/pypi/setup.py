import io
from setuptools import setup

GITHUB_URL = 'https://github.com/cheshirekow/buntstrap'
VERSION = '0.1.1'

with io.open('README.rst', encoding='utf8') as infile:
  long_description = infile.read()

setup(
    name='buntstrap',
    packages=['buntstrap'],
    version=VERSION,
    description="bootstrap an ubuntu filesystem",
    long_description=long_description,
    author='Josh Bialkowski',
    author_email='josh.bialkowski@gmail.com',
    url=GITHUB_URL,
    download_url='{}/archive/{}.tar.gz'.format(GITHUB_URL, VERSION),
    keywords=['ubuntu', 'linux'],
    classifiers=[],
    entry_points={
        'console_scripts': ['buntstrap=buntstrap.__main__:main'],
    },
    install_requires=[
      'uchroot',
    ]
)
