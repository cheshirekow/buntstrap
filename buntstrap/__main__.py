"""
Bootstrap an ubuntu rootfs.
"""

import argparse
import io
import logging
import sys

import buntstrap
from buntstrap import config
from buntstrap import chroot

APT_CACHE_HELP = """url of apt-cacher-ng (or other apt proxy). If apt-cacher-ng
is found running on the machine at localhost:3142, then it will be used by
default. If you wish to suppress this behavior, then specify
--apt-cache-url "none://"
"""

VERSION = '0.1.2'


def parse_bool(string):
  if string.lower() in ('y', 'yes', 't', 'true', '1', 'yup', 'yeah', 'yada'):
    return True
  elif string.lower() in ('n', 'no', 'f', 'false', '0', 'nope', 'nah', 'nada'):
    return False

  logging.warn("Ambiguous truthiness of string '%s' evalutes to 'FALSE'",
               string)
  return False


def main():
  format_str = '%(levelname)-6s %(filename)s[%(lineno)-3s] : %(message)s'
  logging.basicConfig(level=logging.INFO,
                      format=format_str,
                      datefmt='%Y-%m-%d %H:%M:%S',
                      filemode='w')

  parser = argparse.ArgumentParser(description=__doc__)

  parser.add_argument('-v', '--version', action='version', version=VERSION)
  parser.add_argument('-l', '--log-level', default='info',
                      choices=['debug', 'info', 'warning', 'error'],
                      help='Increase log level to include info/debug')
  parser.add_argument('-c', '--config',
                      help='Configuration file to use')
  parser.add_argument('--dump-config', action='store_true',
                      help='Dump default config')

  default_dict = config.Configuration().serialize()
  for key, value in default_dict.items():
    helpstr = config.VARDOCS.get(key, None)
    if key == ['rootfs', 'chroot_app', 'user_quirks']:
      continue
    # NOTE(josh): argparse store_true isn't what we want here because we want
    # to distinguish between "not specified" = "default" and "specified"
    elif isinstance(value, bool):
      parser.add_argument('--' + key.replace('_', '-'), nargs='?', default=None,
                          const=True, type=parse_bool, help=helpstr)
    elif isinstance(value, (str, unicode, int, float)) or value is None:
      if key in config.VARCHOICES:
        parser.add_argument('--' + key.replace('_', '-'), type=type(value),
                            choices=config.VARCHOICES[key], help=helpstr)
      else:
        parser.add_argument('--' + key.replace('_', '-'), type=type(value),
                            help=helpstr)
    # NOTE(josh): argparse behavior is that if the flag is not specified on
    # the command line the value will be None, whereas if it's specified with
    # no arguments then the value will be an empty list. This exactly what we
    # want since we can ignore `None` values.
    elif isinstance(value, (list, tuple)):
      parser.add_argument('--' + key.replace('_', '-'), nargs='*', help=helpstr)

  parser.add_argument('--chroot-impl', default=None,
                      choices=['none', 'chroot', 'proot', 'uchroot'],
                      help='Use this chroot application')
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
  if args.chroot_impl is not None:
    if args.chroot_impl == 'chroot':
      config_dict['chroot_app'] = chroot.PosixApp
    elif args.chroot_impl == 'proot':
      config_dict['chroot_app'] = chroot.ProotApp
    elif args.chroot_impl == 'uchroot':
      config_dict['chroot_app'] = chroot.UchrootApp
    else:
      config_dict['chroot_app'] = None

  configuration = config.Configuration(**config_dict)
  configuration.assert_valid()
  buntstrap.create_rootfs(configuration)


if __name__ == '__main__':
  sys.exit(main())
