"""
Bootstrap an ubuntu rootfs.
"""

import argparse
import io
import logging
import sys

import buntstrap
from buntstrap import config

APT_CACHE_HELP = """url of apt-cacher-ng (or other apt proxy). If apt-cacher-ng
is found running on the machine at localhost:3142, then it will be used by
default. If you wish to suppress this behavior, then specify
--apt-cache-url "none://"
"""


def main():
  format_str = '%(levelname)-6s %(filename)s[%(lineno)-3s] : %(message)s'
  logging.basicConfig(level=logging.INFO,
                      format=format_str,
                      datefmt='%Y-%m-%d %H:%M:%S',
                      filemode='w')

  parser = argparse.ArgumentParser(description=__doc__)

  parser.add_argument('-v', '--version', action='version',
                      version=buntstrap.VERSION)
  parser.add_argument('-l', '--log-level', default='info',
                      choices=['debug', 'info', 'warning', 'error'],
                      help='Increase log level to include info/debug')
  parser.add_argument('-c', '--config',
                      help='Configuration file to use')
  parser.add_argument('--dump-config', action='store_true',
                      help='Dump default config')

  default_dict = config.Configuration().serialize()
  for key, value in default_dict.items():
    if key == ['rootfs', 'user_quirks']:
      continue
    config.add_to_argparse(parser, key, value)
  parser.add_argument('rootfs', nargs='?',
                      help='path of the rootfs to bootstrap')
  args = parser.parse_args()
  if args.dump_config:
    config.dump_config(sys.stdout)
    sys.exit(0)

  logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))

  config_dict = {}
  if args.config:
    with io.open(args.config, 'r', encoding='utf8') as infile:
      # pylint: disable=W0122
      exec(infile.read(), config_dict)

  # NOTE(josh): command line arguments override configuration file options,
  # but only if they are actually specified (i.e. not None)
  for key, value in vars(args).items():
    if key in default_dict and value is not None:
      config_dict[key] = value

  configuration = config.Configuration(**config_dict)
  configuration.assert_valid()
  buntstrap.create_rootfs(configuration)


if __name__ == '__main__':
  sys.exit(main())
