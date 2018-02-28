import logging
import math
import pipes


class ChunkReader(object):
  """A wrapper around a file obj for use in iter(reader.read, b'')."""

  def __init__(self, fileobj, chunk_size):
    self.fileobj = fileobj
    self.chunk_size = chunk_size

  def read(self):
    return self.fileobj.read(self.chunk_size)


def chunk_reader(fileobj, chunk_size=4096):
  """Return a chunk generator for reading files."""
  reader = ChunkReader(fileobj, chunk_size)
  for chunk in iter(reader.read, b''):
    yield chunk


def get_human_readable_size(size_in_bytes):
  """
  Convert a number of bytes into a human readable string.
  """
  if size_in_bytes == 0:
    return '0B'

  exponent = int(math.log(size_in_bytes, 1024))
  unit = ['B', 'KB', 'MB', 'GB', 'PB', 'EB'][exponent]
  size_in_units = float(size_in_bytes) / (1024 ** exponent)
  return '{:6.2f}{}'.format(size_in_units, unit)


def quote_args(args):
  """
  Opposite of shlex.split(). Will quote any argument that contains whitespace
  in it.
  """
  return ' '.join(pipes.quote(arg) for arg in args)


def wrap_subprocess(spfn, cmd, *args, **kwargs):
  """
  call subproces.<fn> but print the command in a helpful way on error.
  """

  try:
    return spfn(cmd, *args, **kwargs)
  except SystemExit as ex:
    # WTF is wrong with the subprocess module... raises SystemExit in the
    # parent if raised in the child... geeze.
    logging.error('%s failure:\n  %s', spfn.__name__, quote_args(cmd),
                  exc_info=True)
    if hasattr(ex, 'child_traceback'):
      logging.error(getattr(ex, 'child_traceback'))
    raise
  except:  # pylint:disable=bare-except
    logging.error('%s failure:\n  %s', spfn.__name__, quote_args(cmd),
                  exc_info=True)
    raise


def print_and(spfn, cmd, *args, **kwargs):
  """
  Call one of the subprocess.<fn> functions but print the command first and
  print it in a helpful way on error.
  """

  # NOTE(josh): want to word-wrap?
  # wrapper = textwrap.TextWrapper(
  #     width=80, subsequent_indent='  ', break_long_words=False)
  # wrapped_cmd = wrapper.fill(quote_args(cmd))
  logging.debug('%s: %s', spfn.__name__, quote_args(cmd))
  return wrap_subprocess(spfn, cmd, *args, **kwargs)
