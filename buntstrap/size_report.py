"""
Pretty-print a sorted size report from a json package report
"""

import argparse
import io
import json
import sys

from buntstrap import util


def print_size_report(report_data, outfile, columns=None,
                      human_readable=True, sort_column=None,
                      sort_descending=False):

  if columns is None:
    columns = [u'packed_size', u'size_on_disk', u'name', u'description']

  if sort_column is None:
    sort_column = columns[0]

  sorted_items = sorted(
      (util.PackageMeta(item)
       for item in report_data),
      key=lambda x: x.get(sort_column), reverse=sort_descending)

  colsize = {key: 1 for key in columns}

  for item in sorted_items:
    for key in columns:
      value = item.get(key)
      if isinstance(value, int):
        if human_readable:
          value = util.get_human_readable_size(value)
        else:
          value = str(value)
      vlen = len(value)
      if vlen > colsize[key]:
        colsize[key] = vlen

  fmt_parts = []
  for key in columns:
    if 'size' in key and not human_readable:
      fmt_parts.append(u'{' + key + u':' + str(colsize[key]) + u'd}')
    else:
      fmt_parts.append(u'{' + key + u':' + str(colsize[key]) + u's}')

  format_str = u'  '.join(fmt_parts) + '\n'

  for item in sorted_items:
    outfile.write(format_str.format(**item.sub(columns, human_readable)))


def main():
  parser = argparse.ArgumentParser('buntstrap.size_report', description=__doc__)
  parser.add_argument('report_path',
                      help='json report file')
  parser.add_argument('out_path', nargs='?', default='-',
                      help='write the report to this file')
  parser.add_argument('--columns', default=None, nargs='*',
                      choices=['name', 'packed_size', 'size_on_disk',
                               'description', 'version'])
  parser.add_argument('--sort-column',
                      choices=['name', 'packed_size', 'size_on_disk',
                               'description', 'version'])
  parser.add_argument('--human-readable', action='store_true')
  parser.add_argument('--sort-descending', action='store_true')
  args = parser.parse_args()

  if args.out_path == '-':
    outfile = io.open(sys.stdout.fileno(), 'w', encoding='utf-8')
  else:
    outfile = io.open(args.out_path, 'w', encoding='utf-8')

  with open(args.report_path, 'r') as infile:
    report_data = json.load(infile)

  print_size_report(report_data, outfile,
                    columns=args.columns,
                    sort_column=args.sort_column,
                    sort_descending=args.sort_descending,
                    human_readable=args.human_readable)
  outfile.flush()


if __name__ == '__main__':
  main()
