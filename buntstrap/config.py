"""
Includes definition of the bunstrap configuration class as well as some
convenience utilities for specifying various configuration options.
"""

import httplib
import inspect
import json
import logging
import os
import pprint
import subprocess
import textwrap

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
               terminate_after=None,
               **extra):
    extra_keys = [key for key in extra if not key.startswith('_')]
    if extra_keys:
      logging.warn("Unused config file options: %s",
                   ', '.join(sorted(extra_keys)))

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
    self.terminate_after = terminate_after

  def assert_valid(self):
    if os.path.exists(self.rootfs):
      if not directory_is_empty(self.rootfs):
        logging.warn("target rootfs dir %s exists and is not empty",
                     self.rootfs)

  def get_field_names(self):
    """
    Return a list of field names, extracted from kwargs to __init__().
    """
    return inspect.getargspec(self.__init__).args[1:]

  def serialize(self):
    """
    Return a dictionary describing the configuration.
    """
    return {field: getattr(self, field)
            for field in self.get_field_names()}


VARCHOICES = {
    'architecture': ['amd64', 'arm64', 'armhf'],
    'suite': ['trusty', 'utopic', 'vivid', 'wily', 'xenial', 'yakkety',
              'zesty', 'artful'],
    'apt_include_priorities': ['required', 'important', 'standard'],
    'terminate_after': ['apt-update', 'apt-download',
                        'size-report', 'dpkg-extract', 'dpkg-configure']
}

VARDOCS = {
    "architecture":
    """
dpkg architecture of the rootfs to build. If you'd like to know what
architecture you're currently on, try running `dpkg --print-architecture`.
""",
    "suite":
    """\
this is only used to select reasonable defaults if you leave out some
configuration parameters, but specify the ubuntu target suite here.
""",
    "chroot_app":
    """\
Which chroot application to use. There are three builtin options:
1. PosixApp : uses posix ``chroot`` and must be run as root
2. ProotApp : uses ``proot``
3. UchrootApp : uses ``uchroot`` which creats a user namespace. All files
   in the target rootfs will have uid/gid ownership with mapped values
""",
    "rootfs":
    """\
This is the directory of the rootfs to bootstrap.
""",
    "apt_http_proxy":
    """\
If not none, then we'll set the http proxy environment variables for APT
using this. If apt-cacher-ng is installed an active it is usually at
http://localhost:3142. The function ``config.get_apt_cache_url()`` will
check for  apt-cacher-ng and return it if found, otherwise None.
""",
    "apt_packages":
    """\
List of packages to install with apt
""",
    "apt_include_essential":
    """\
If true, then we will request a list of all "essential" packages from apt
and include them in the installation.
""",
    "apt_include_priorities":
    """\
Specify the set of priority package lists to include.
'required': dpkg wont function without these
'important': standard set of minimal unix programs
'standard':  reasonably small but not too limited character-mode system
""",
    "apt_sources":
    """\
This is the string contents of the apt sources list used to bootstrap the
system. The file will be written into the target rootfs before executing
apt but will be removed afterward.
""",
    "apt_skip_update":
    """\
If you already have a rootfs that has been bootstrapped and you wish to
(re)-install packages you can set this true to skip the `apt-get` update
step. This is mostly useful during debugging/testing iteration.
""",
    "apt_size_report":
    """\
If you would like buntstrap to write out a package size report then specify
here the output path where you would like that report to go.
""",
    "apt_clean":
    """\
If true, the apt archive cache and other state files are cleaned up. Use this
if you want to reduce the size of your rootfs.
""",
    "external_debs":
    """\
If you have any plain .deb packages to install inside the rootfs list them
here. They will be extracted along with those downloaded by apt and configured
with the rest.
""",
    "dpkg_configure_retry_count":
    """\
Sometimes a package will fail to configure correctly only because it hasn't
correctly declared it's dependencies and it gets configured out of order.
An easy work around is to just retry dpkg --configure again. Set here the
number of times to try execugind `dpkg --configure`.
""",
    "pip_wheelhouse":
    """\
If installing any packages through pip, you can re-use an existing wheelhouse
to cache binary wheels and speed up repeated bootstrapping. Specify the
wheelhouse directory here
""",
    "pip_packages":
    """\
List of python package to install using pip. Note that if this list is not
empty then `python-pip` will be included in apt_packages (if it is not
already) and pip will be installed itself with `pip install --upgrade pip`.
If you want to pin a specific version of pip then make sure you list it here.
""",
    "qemu_binary":
    """\
If you are cross-arch bootstrapping from amd64 to arm then specify here the
path to the qemu-static binary that should be copied into the target rootfs
during chroot execution. ``config.get_qemu_binary(arch)`` is a convenience
function which returns the default path for the qemu-static binary for arm64
or armhf
""",
    "binds":
    """\
List of paths to bind-mount to the target rootfs. If a path is a realfile
it will be copied into the rootfs and deleted afterward. If it is a
directory then it will be bind-mounted (or emulated in the proot case)
""",
    "terminate_after":
    """\
Terminate early after performing the specified step.
"""
}


def dump_config(outfile):
  """
  Dump the default configuration to ``outfile``.
  """

  cfg = Configuration()
  ppr = pprint.PrettyPrinter(indent=2)
  for key in cfg.get_field_names():
    helptext = VARDOCS.get(key, None)
    if helptext:
      for line in textwrap.wrap(helptext, 78):
        outfile.write('# ' + line + '\n')
    value = getattr(cfg, key)
    if isinstance(value, dict):
      outfile.write('{} = {}\n\n'.format(key, json.dumps(value, indent=2)))
    else:
      outfile.write('{} = {}\n\n'.format(key, ppr.pformat(value)))
