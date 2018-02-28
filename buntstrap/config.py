"""
Includes definition of the bunstrap configuration class as well as some
convenience utilities for specifying various configuration options.
"""

import httplib
import inspect
import logging
import os
import subprocess

from buntstrap import chroot
from buntstrap import util


def get_host_architecture():
  """
  Return the dpkg host architecture.
  """
  return util.wrap_subprocess(subprocess.check_output,
                              ['dpkg', '--print-architecture']).strip()


def get_host_suite():
  """
  Return the ubuntu host suite
  """
  return util.wrap_subprocess(subprocess.check_output,
                              ['lsb_release', '-cs']).strip()


def get_apt_cache_url():
  """
  Return the URL of apt-cacher-ng if it is running locally, or None if it
  is not.
  """

  # NOTE(josh): check to see if apt-cacher-ng is running locally. If so, use
  # it to cache apt-get.
  for url_attempt in ['localhost:3142']:
    try:
      # NOTE(josh): don't use requests so as to limit dependencies
      http_conn = httplib.HTTPConnection(url_attempt, timeout=1)
      http_conn.request('GET', '/acng-report.html')
      response = http_conn.getresponse()
      if response.status == 200:
        logging.info('apt-cacher-ng running locally, will use')
        return 'http://' + url_attempt
    except Exception:  # pylint: disable=broad-except
      pass

  logging.info('apt-cacher-ng not running locally will not use any apt-cache')
  return None


def get_ubuntu_url(arch):
  """
  Return the ubuntu url for the given suite.
  """
  if arch in ['armhf', 'arm64']:
    return 'http://www.ports.ubuntu.com/ubuntu-ports'
  elif arch == 'amd64':
    return 'http://us.archive.ubuntu.com/ubuntu'


BOOTSTRAP_SOURCES = """
# NOTE(josh): these sources are used to bootstrap the rootfs and should be
# omitted from after initial package installation. You should not see this
# file on a live system.

deb [arch={arch}] {ubuntu_url} {suite} main universe multiverse
deb [arch={arch}] {ubuntu_url} {suite}-updates main universe multiverse
deb [arch={arch}] http://ppa.launchpad.net/lttng/stable-2.9/ubuntu {suite} main
deb [arch={arch}] http://ppa.launchpad.net/nginx/stable/ubuntu {suite} main
"""


def get_bootstrap_sources(arch, suite):
  """
  Return default sources for ubuntu given an architecture and suite
  """
  fmt_args = dict(arch=arch, suite=suite, ubuntu_url=get_ubuntu_url(arch))
  if arch in ['armhf', 'arm64']:
    pass
  elif arch == 'amd64':
    fmt_args['arch'] = 'amd64,i386'
  else:
    raise ValueError('Unexpected arch={}'.format(arch))

  return BOOTSTRAP_SOURCES.format(**fmt_args)


def get_qemu_binary(target_arch):
  """
  Return the path to qemu binary for the target architecture
  """
  if get_host_architecture() != 'amd64':
    return None

  if target_arch == 'amd64':
    return None

  if target_arch == 'arm64':
    return '/usr/bin/qemu-aarch64-static'
  if target_arch == 'armhf':
    return '/usr/bin/qemu-arm-static'

  return None


def directory_is_empty(rootfs_dir):
  """
  Return true if a directory is empty. We consider a directory with exactly
  one entry called 'lost+found' to be empty, such that the mountpoint for an
  empty ext4 filesystem is "empty".
  """
  contents = os.listdir(rootfs_dir)
  if not contents:
    return True
  if len(contents) == 1 and contents[0] == 'lost+found':
    return True
  return False


def get_default(obj, default):
  """
  If obj is not `None` then return it. Otherwise return default.
  """
  if obj is None:
    return default

  return obj


def noop():
  """
  function which does nothing
  """
  logging.info('no-op')


class Configuration(object):
  """
  Aggregates both static-y and runtime-y options from a config file or command
  line options. Basically just a named tuple but with a few additional bits.

  CONFIGURATION PARAMETERS
  static-y things:
    architecture: amd64, armhf, arm64
    bootstrap sources: either a list of package source repositories or one of
                       a set of predefined ones (i.e trusty, xenial)
    apt_packages: list of apt package specifications
    pip_packages: list of pip package specifications
    include_sets:
      Essential: ??
      Priority: important
      Priority: required

  runtime-y things:
    apt_cache_url: apt proxy URL
    rootfs: where to install
    wheelhouse: pip proxy URL

  Strictly runtime things:
    log_stdout_level: log-level for stdout
    log_file_level: log-level for log file
  """

  # pylint: disable=too-many-instance-attributes
  # pylint: disable=too-many-arguments
  def __init__(self,
               architecture=None,
               suite=None,
               chroot_app=None,
               rootfs=None,
               apt_http_proxy=None,
               apt_packages=None,
               apt_include_essential=False,
               apt_include_priorities=None,
               apt_sources=None,
               apt_skip_update=False,
               apt_size_report=None,
               apt_clean=False,
               external_debs=None,
               user_quirks=None,
               dpkg_configure_retry_count=1,
               pip_wheelhouse=None,
               pip_packages=None,
               qemu_binary=None,
               binds=None,
               **_):

    self.architecture = get_default(architecture, get_host_architecture())
    self.suite = get_default(suite, get_host_suite())
    self.chroot_app = get_default(chroot_app, chroot.UchrootApp)
    self.rootfs = get_default(rootfs, '.')
    self.apt_http_proxy = apt_http_proxy
    self.apt_packages = get_default(apt_packages, [])
    self.apt_include_essential = apt_include_essential
    self.apt_include_priorities = get_default(
        apt_include_priorities, ['required', 'important', 'standard'])
    self.apt_sources = get_default(
        apt_sources, get_bootstrap_sources(self.architecture, self.suite))
    self.apt_skip_update = apt_skip_update
    self.apt_size_report = apt_size_report
    self.apt_clean = apt_clean
    self.external_debs = get_default(external_debs, [])
    self.user_quirks = get_default(user_quirks, noop)
    self.dpkg_configure_retry_count = dpkg_configure_retry_count
    self.pip_wheelhouse = pip_wheelhouse
    self.pip_packages = get_default(pip_packages, [])
    self.qemu_binary = qemu_binary

    # NOTE(josh): this is a pretty minimal list. Maybe we should add more by
    # default.
    self.binds = get_default(binds, ['/dev/urandom',
                                     '/etc/resolv.conf'])

  def assert_valid(self):
    if os.path.exists(self.rootfs):
      if not directory_is_empty(self.rootfs):
        logging.warn("target rootfs dir %s exists and is not empty",
                     self.rootfs)

  def serialize(self):
    """
    Return a dictionary describing the configuration.
    """
    argspec = inspect.getargspec(self.__init__)
    return {field: getattr(self, field)
            for field in argspec.args[1:]}
