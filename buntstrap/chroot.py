
import enum
import logging
import os
import shutil
import stat
import subprocess

from buntstrap import util


class Type(enum.Enum):
  """
  Enumerates options for calling dpkg-configure
  """
  NONE = 1,
  CHROOT = 2,
  PROOT = 3,
  UCHROOT = 4


class AppBase(object):
  """
  Base class for chroot implementations
  """

  def __init__(self, rootfs, binds, qemu_binary, wheelhouse):
    self.cmd = []
    self.env = dict(DEBIAN_FRONTEND='noninteractive',
                    LANG='en_US.UTF-8',
                    LANGUAGE='en_US',
                    LC_ALL='C',
                    PATH=':'.join(['/usr/local/sbin',
                                   '/usr/local/bin',
                                   '/usr/sbin',
                                   '/usr/bin',
                                   '/sbin',
                                   '/bin']))
    self.preexec_fn = None
    self.rootfs = rootfs
    self.binds = binds
    self.qemu_binary = qemu_binary
    self.wheelhouse = wheelhouse

  def _update_kwargs(self, kwargs):
    """
    Merge the requested environment with the base environment, and set
    the preexec_fn if base class requested it
    """
    if 'env' in kwargs:
      env = dict(kwargs['env'])
      env.update(self.env)
    else:
      env = dict(self.env)
    kwargs['env'] = env

    if self.preexec_fn is not None:
      kwargs['preexec_fn'] = self.preexec_fn

  def popen(self, cmd, *args, **kwargs):
    self._update_kwargs(kwargs)
    return util.print_and(subprocess.Popen, self.cmd + cmd, *args, **kwargs)

  def call(self, cmd, *args, **kwargs):
    self._update_kwargs(kwargs)
    return util.print_and(subprocess.call, self.cmd + cmd, *args, **kwargs)

  def check_call(self, cmd, *args, **kwargs):
    self._update_kwargs(kwargs)
    return util.print_and(subprocess.check_call, self.cmd + cmd,
                          *args, **kwargs)

  def check_output(self, cmd, *args, **kwargs):
    self._update_kwargs(kwargs)
    return util.print_and(subprocess.check_output, self.cmd + cmd,
                          *args, **kwargs)

  def iterbinds(self):
    """
    Given a list of bind specifications, return a generator that iterates over
    (source, dest) pairs where ``source`` is an absolute path on the host
    filesystem and ``dest`` is a relative path within the target filesystem.
    """
    for bind in self.binds:
      if isinstance(bind, (tuple, list)):
        source, dest = bind
      elif ':' in bind:
        source, dest = bind.split(':')
      else:
        source = dest = bind

      yield (os.path.realpath(source), dest.lstrip('/'))

    if self.wheelhouse:
      yield (os.path.realpath(source), 'opt/wheelhouse')

  def __enter__(self):
    for source, dest in self.iterbinds():
      dest = os.path.join(self.rootfs, dest)

      if stat.S_ISREG(os.stat(source).st_mode):
        logging.debug('cp %s -> %s', source, dest)
        shutil.copy2(source, dest)
      elif os.path.isdir(source):
        if not os.path.exists(dest):
          logging.debug('mkdir %s', dest)
          os.makedirs(dest)
      else:
        pardir = os.path.dirname(dest)
        if not os.path.exists(pardir):
          logging.debug('mkdir %s', pardir)
          os.makedirs(pardir)
        with open(dest, 'w') as _:
          pass

  def __exit__(self, exc_type, exc_value, traceback):
    for source, dest in self.iterbinds():
      dest = os.path.join(self.rootfs, dest)
      if stat.S_ISREG(os.stat(source).st_mode):
        os.remove(dest)


class PosixApp(AppBase):

  def __init__(self, rootfs, binds, qemu_binary, wheelhouse):
    super(PosixApp, self).__init__(rootfs, binds, qemu_binary, wheelhouse)
    self.cmd = ['chroot', rootfs]

    assert os.getuid() == 0, "PosixApp will only work as root!"

  def __enter__(self):
    for source, dest in self.iterbinds():
      dest = os.path.join(self.rootfs, dest)

      if stat.S_ISREG(os.stat(source).st_mode):
        shutil.copy2(source, dest)
      elif os.path.isdir(source):
        if not os.path.exists(dest):
          os.makedirs(dest)
        util.print_and(subprocess.check_call,
                       ['mount', '-o', 'bind', source, dest])
      else:
        pardir = os.path.dirname(dest)
        if not os.path.exists(pardir):
          logging.debug('mkdir %s', pardir)
          os.makedirs(pardir)
        with open(dest, 'w') as _:
          pass
        util.print_and(subprocess.check_call,
                       ['mount', '-o', 'bind', source, dest])

  def __exit__(self, exc_type, exc_value, traceback):
    for source, dest in self.iterbinds():
      dest = os.path.join(self.rootfs, dest)
      if stat.S_ISREG(os.stat(source).st_mode):
        os.remove(dest)
      else:
        util.print_and(subprocess.check_call, ['umount', dest])

    return False


class ProotApp(AppBase):

  def __init__(self, rootfs, binds, qemu_binary, wheelhouse):
    super(ProotApp, self).__init__(rootfs, binds, qemu_binary, wheelhouse)

    self.cmd = ['proot',
                '--rootfs={}'.format(rootfs),
                '--cwd=/']
    if qemu_binary:
      self.cmd.append('--qemu={}'.format(qemu_binary))
    if wheelhouse:
      self.cmd.append('--bind={}:/opt/wheelhouse'.format(wheelhouse))

    for source, dest in self.iterbinds():
      if os.path.isdir(source):
        self.cmd.append('-bind={}:/{}'.format(source, dest))

    # If I am not root, then emulate root
    if os.getuid() != 0:
      self.cmd.append('-0')

    # Extra environment variables
    self.env.update({
        'PROOT_NO_SECCOMP': '1',
    })


class UchrootApp(AppBase):

  def __init__(self, rootfs, binds, qemu_binary, wheelhouse):
    super(UchrootApp, self).__init__(rootfs, binds, qemu_binary, wheelhouse)
    config = {
        'rootfs': rootfs,
        'binds': binds,
        'qemu': qemu_binary,
        'identity': (0, 0),
        "uid_range": (100000, 65536),
        "gid_range": (100000, 65536),
        "cwd": "/",
    }
    if wheelhouse:
      config['binds'] += [(wheelhouse, '/opt/wheelhouse')]

    import uchroot
    self.preexec_fn = uchroot.Main(**config)


def get_class(enum_value):
  return {
      Type.CHROOT: PosixApp,
      Type.PROOT: ProotApp,
      Type.UCHROOT: UchrootApp,
  }[enum_value]
