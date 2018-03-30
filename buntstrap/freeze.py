"""
print a version-pinned package specification from a rootfs construction, using
either the json apt report, or using dpkg from within the chroot
"""

import argparse
import io
import os
import json
import re
import subprocess
import sys

import buntstrap
from buntstrap import chroot
from buntstrap import util

VERSION = '0.1.3'


def freeze_report(report_path):
  with open(report_path, 'r') as infile:
    report_data = json.load(infile)

  return sorted(util.PackageMeta(item).sub('name', 'version')
                for item in report_data)


def freeze_dpkg(chroot_app):
  dpkg_proc = chroot_app.popen(['dpkg', '--list'],
                               stdout=subprocess.PIPE)

  out = []
  with dpkg_proc.stdout:
    for line in dpkg_proc.stdout:
      if line.startswith('ii'):
        _, name, version, _ = re.split(r'\s+', line, 3)
        if ':' in name:
          name, _ = name.split(':')
        out.append({'name': name, 'version': version})

  dpkg_proc.wait()
  return sorted(out)


def dump_python(outfile, sorted_items):
  outfile.write(u'apt_packages=[\n')
  for item in sorted_items:
    outfile.write(u'    "{name}={version}",\n'
                  .format(**item))
  outfile.write(u']\n')


def dump_text(outfile, sorted_items):
  for item in sorted_items:
    outfile.write(u'{name}={version}\n'
                  .format(**item))


def main():
  parser = argparse.ArgumentParser('buntstrap.freeze', description=__doc__)
  parser.add_argument('-v', '--version', action='version',
                      version=buntstrap.VERSION)
  parser.add_argument('-l', '--log-level', default='info',
                      choices=['debug', 'info', 'warning', 'error'],
                      help='Increase log level to include info/debug')
  parser.add_argument('--chroot-impl', default='uchroot',
                      choices=['chroot', 'uchroot', 'proot'])
  parser.add_argument('--qemu-binary',
                      help='path to qemu to bind to the rootfs')
  parser.add_argument('inpath',
                      help='json report file or rootfs directory')
  parser.add_argument('out_path', nargs='?', default='-',
                      help='write the report to this file')
  parser.add_argument('--format', default=None, choices=['python'],
                      help='output requirements in this format')
  args = parser.parse_args()

  if args.out_path == '-':
    outfile = io.open(sys.stdout.fileno(), 'w', encoding='utf-8')
  else:
    outfile = io.open(args.out_path, 'w', encoding='utf-8')

  if os.path.isdir(args.inpath):
    chroot_class = {
        'chroot': chroot.PosixApp,
        'uchroot': chroot.UchrootApp,
        'proot': chroot.ProotApp,
    }.get(args.chroot_impl)

    assert chroot_class is not None, \
        "Unrecognized chroot_class: '{}'".format(args.chroot_impl)

    chroot_app = chroot_class(args.inpath, [], args.qemu_binary, None)
    sorted_items = freeze_dpkg(chroot_app)
  else:
    sorted_items = freeze_report(args.inpath)

  if args.format == 'python':
    dump_python(outfile, sorted_items)
  else:
    dump_text(outfile, sorted_items)
  outfile.flush()


if __name__ == '__main__':
  main()
