"""
print a version-pinned package specification from an apt-report
"""

import argparse
import io
import json
import sys

from buntstrap import util


def freeze(report_data, outfile):
  sorted_items = sorted(util.PackageMeta(item) for item in report_data)
  outfile.write(u'apt_packages=[\n')

  for item in sorted_items:
    outfile.write(u'    "{name}={version}",\n'
                  .format(**item.sub(['name', 'version'])))
  outfile.write(u']\n')


def main():
  parser = argparse.ArgumentParser('buntstrap.freeze', description=__doc__)
  parser.add_argument('report_path',
                      help='json report file')
  parser.add_argument('out_path', nargs='?', default='-',
                      help='write the report to this file')
  args = parser.parse_args()

  if args.out_path == '-':
    outfile = io.open(sys.stdout.fileno(), 'w', encoding='utf-8')
  else:
    outfile = io.open(args.out_path, 'w', encoding='utf-8')

  with open(args.report_path, 'r') as infile:
    report_data = json.load(infile)

  freeze(report_data, outfile)
  outfile.flush()


if __name__ == '__main__':
  main()
