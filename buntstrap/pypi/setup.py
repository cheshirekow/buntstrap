import io
from setuptools import setup

GITHUB_URL = 'https://github.com/cheshirekow/buntstrap'

VERSION = None
with io.open('buntstrap/__init__.py', encoding='utf-8') as infile:
  for line in infile:
    line = line.strip()
    if line.startswith('VERSION ='):
      VERSION = line.split('=', 1)[1].strip().strip("'")

assert VERSION is not None


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
        'console_scripts': [
            'buntstrap=buntstrap.__main__:main',
            'buntstrap.size_report=buntstrap.size_report:main',
            'buntstrap.freeze=buntstrap.freeze:main'
        ],
    },
    install_requires=[
        'uchroot',
    ]
)
