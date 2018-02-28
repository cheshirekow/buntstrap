from __future__ import print_function

import enum
import hashlib
import httplib
import logging
import math
import pipes
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types

from buntstrap import chroot
from buntstrap import util

VERSION = '0.1.0'


def install_apt_key(root_dir, keyring_filename, gpg_key):
  """
  Add a public signing key to the apt keyring named `keyring_filename`.
  """

  keyring_dir = os.path.join(root_dir, 'etc/apt/trusted.gpg.d')
  keyring_path = os.path.join(keyring_dir, keyring_filename)
  apt_key_cmd = ['apt-key', '--keyring', keyring_path, 'add', '-']

  try:
    os.makedirs(keyring_dir)
  except OSError:
    pass

  # If we are not running as root, then append fakeroot to the command,
  # because the command is stupid and checks that we are root before doing
  # anything.
  if os.getuid() != 0:
    apt_key_cmd = ['fakeroot'] + apt_key_cmd

  apt_key_proc = subprocess.Popen(apt_key_cmd, stdin=subprocess.PIPE)
  apt_key_proc.communicate(gpg_key)
  apt_key_proc.wait()
  assert apt_key_proc.returncode == 0, \
      "Failed to add gpg key {}".format(gpg_key)


def install_local_repo_key(repo_dir, root_dir, keyring_filename):
  """
  Add public signing keys from a local (i.e. file://) debian repository to the
  apt keyring so that apt will trust packages from the local repository.
  """

  key_path = os.path.join(repo_dir, 'GPGKEY')
  with open(key_path, 'r') as keyfile:
    install_apt_key(root_dir, keyring_filename, keyfile.read())


def force_symlink(target_path, link_location):
  """
  create the symlink if needed, if it already exists but points somewhere
  else, then remove it and replace it.
  """

  if os.path.lexists(link_location):
    assert os.path.islink(link_location), \
        "The path {} exists but is not a symlink".format(link_location)
    if os.readlink(link_location) != target_path:
      os.remove(link_location)
      os.symlink(target_path, link_location)
  else:
    os.symlink(target_path, link_location)


def get_deb_item(deb_path, field):
  """Return the value of a control field for a package"""

  dpkg_cmd = ['dpkg', '--field', deb_path, field]
  return util.wrap_subprocess(subprocess.check_output,
                              dpkg_cmd, env={'LC_ALL': 'C'}).strip()


def get_deb_info(deb_path, *args):
  """
  Return a tuple of control fields for a package. Control field keys are the
  positional arguments. For exeample:

  get_deb_info('Version', 'Package', 'Source', 'Multi-Arch')
  """
  return (get_deb_item(deb_path, arg) for arg in args)


def md5sum_file(filepath):
  """return md5sum of a file."""
  hasher = hashlib.md5()
  with open(filepath, 'rb') as infile:
    for chunk in util.chunk_reader(infile):
      hasher.update(chunk)
  return hasher.hexdigest()


def extract_deb(deb_path, rootfs):
  """
  Extract a debian package into rootfs. Replicates dpkg --install up to the
  point of running post-instalation scripts. Extracted packages must be
  configured later with dpkg --configure.

  Implementors note: logic was copied from multistrap as a reference, not dpkg,
  so there may be some subtle differences.

  `deb_pat`: path to XXX.deb file to extract
  `rootfs`: root directory of the filesystem to extract to
  """

  package = get_deb_item(deb_path, 'Package')
  info_dir = os.path.join(rootfs, 'var/lib/dpkg/info')
  list_path = os.path.join(info_dir, '{}.list'.format(package))
  available_path = os.path.join(rootfs, 'var/lib/dpkg/available')
  status_path = os.path.join(rootfs, 'var/lib/dpkg/status')

  try:
    os.makedirs(info_dir)
  except OSError:
    pass

  with open(list_path, 'w') as listfile:
    dpkg_cmd = ['dpkg', '-x', deb_path, rootfs]
    dpkg_proc = util.wrap_subprocess(subprocess.Popen, dpkg_cmd,
                                     env={'LC_ALL': 'C'},
                                     stdout=subprocess.PIPE)
    for line in dpkg_proc.stdout:
      listfile.write(line)
    dpkg_proc.stdout.close()
    dpkg_proc.wait()
    assert dpkg_proc.returncode == 0, \
        "command exited with {}: {}".format(dpkg_proc.returncode,
                                            util.quote_args(dpkg_cmd))

  control_dir = tempfile.mkdtemp()
  util.wrap_subprocess(subprocess.check_call,
                       ['dpkg', '-e', deb_path, control_dir],
                       env={'LC_ALL': 'C'})

  with open(available_path, 'a') as available:
    with open(status_path, 'a') as status:
      conflines = []
      for mscript in os.listdir(control_dir):
        mscript_path = os.path.join(control_dir, mscript)
        if mscript == 'control':
          with open(mscript_path, 'r') as control:
            for line in control:
              if line.strip():
                available.write(line)
                status.write(line)
          available.write('\n\n')
          status.write('Status: install ok unpacked\n')
        else:
          filename = '{}.{}'.format(package, mscript)
          shutil.copy2(mscript_path, os.path.join(info_dir, filename))
          if mscript == 'conffiles':
            with open(mscript_path, 'r') as infile:
              for filepath in infile:
                filepath = filepath.strip()
                if filepath:
                  confile_path = os.path.join(rootfs, filepath.lstrip('/'))
                  conflines.append((filepath, md5sum_file(confile_path)))

      if conflines:
        status.write('Conffiles:\n')
      for filepath, md5sum in conflines:
        status.write(' {} {}\n'.format(filepath, md5sum))
      status.write('\n')

  shutil.rmtree(control_dir)


def filter_obsolete_packages(deb_list):
  """
  Given a list of paths to debian package files, find any package in the list
  that would replace another package in the list, and then remove the older
  one from the list.
  """

  # NOTE(josh): maps unique package name to a path of the debian package
  # file providing it
  package_map = {}

  for deb in deb_list:
    package, version = get_deb_info(deb, 'Package', 'Version')
    _, version_in_map = package_map.get(package, (None, None))
    if version_in_map is None:
      package_map[package] = (deb, version)
    else:
      dpkg_cmd = ['dpkg', '--compare-versions', version, 'gt', version_in_map]
      if subprocess.call(dpkg_cmd):
        package_map[package] = (deb, version)
        logging.warn('Skipping obsolete %s %s, superceded by %s\n', package,
                     version_in_map, version)
      else:
        logging.warn('Skipping obsolete %s %s, superceded by %s\n', package,
                     version, version_in_map)

  return sorted(deb for deb, _ in package_map.values())


def get_file_size(file_path):
  """
  Get the size, in bytes of a file. Note that this size includes 'holes' as
  if they were filled. Specifically it is equal to the file offset of the
  last byte addressable in the file.
  """
  with open(file_path, 'rb') as infile:
    infile.seek(0, 2)
    return infile.tell()


def unpack_archives(rootfs, deb_list):
  """
  Extract a debian package into rootfs the same way that multistrap would.
  According to the documentation this is the same set of steps dpkg would do
  up to the point of running configure scripts.

  `rootfs`: path to the root filesystem where we want to install packages
  `deb_list`: list of paths to `.deb` files that are to be installed in the
              `rootfs`.

  Returns a size report: a list of tuples in the form of
  (package_name, packaged_size, installed_size, description)
  """

  unfiltered_len = len(deb_list)
  logging.info('I have %s archives to unpackage', unfiltered_len)
  deb_list = filter_obsolete_packages(deb_list)
  if len(deb_list) != unfiltered_len:
    logging.info('Filtered down to %s', len(deb_list))

  dpkg_dir = os.path.join(rootfs, 'var/lib/dpkg')
  try:
    os.makedirs(dpkg_dir)
  except OSError:
    pass

  report = []
  prev_msg_len = 0
  for idx, deb_path in enumerate(deb_list):
    msg = '\rUnpacking [{:6.2f}%]:{:20s}'.format(
        100.0 * (idx + 1) / len(deb_list),
        get_deb_item(deb_path, 'Package'))
    sys.stdout.write('\r')
    sys.stdout.write(' ' * prev_msg_len)
    sys.stdout.write(msg)
    sys.stdout.flush()
    prev_msg_len = len(msg)

    package_name = get_deb_item(deb_path, 'Package')
    package_size = get_file_size(deb_path)
    try:
      installed_size = int(get_deb_item(deb_path, 'Installed-Size'))
    except (subprocess.CalledProcessError, ValueError):
      installed_size = 0

    try:
      description = get_deb_item(deb_path, 'Description-en')
    except subprocess.CalledProcessError:
      description = None
    report.append((package_name, package_size, installed_size, description))
    extract_deb(deb_path, rootfs)

  sys.stdout.write('\rUnpacking [100.00%]\n')
  return report


def unpack_apt_archives_plus(rootfs, external_debs=None):
  """
  Unpack all of the archives in the primed apt-cache on `rootfs`, as well as
  thos in the list `external_debs`.
  """

  cache_dir = os.path.join(rootfs, 'var/cache/apt/archives')
  deb_list = [os.path.join(cache_dir, filename)
              for filename in os.listdir(cache_dir)
              if filename.endswith('.deb')]

  if external_debs is not None:
    deb_list.extend(external_debs)

  return unpack_archives(rootfs, deb_list)


def apply_patch_text(patch_text, apply_dir):
  """
  Attempt to apply the patch to the specified directory. Fail if the patch
  doesn't apply cleanly.
  """
  patch_proc = subprocess.Popen(['patch', '-d', apply_dir, '-p0', '--forward',
                                 '--reject-file=/dev/null'],
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
  stdout_text, stderr_text = patch_proc.communicate(patch_text)
  if stdout_text:
    logging.info(stdout_text)
  if stderr_text:
    logging.warn(stderr_text)
  if patch_proc.returncode != 0:
    raise RuntimeError('Failed to apply patch [{}]'
                       .format(patch_proc.returncode))


# NOTE(josh):
# Sometimes (i.e. consistently as of lately, though used to be fine) the
# base-packages post-install hook failes to remove /var/run when running dpkg
# --configure -a. This appears to be an issue that multistrap should be
# providing some mechanism to work-around (i.e. evidently debootstrap does
# this). There's an old bug report at
# https://bugs.launchpad.net/ubuntu/+source/base-files/+bug/874505
#
# This is a patch which has never been merged:
# https://launchpadlibrarian.net/90834174/base-files-6.5-postint.diff
BASE_FILES_PATCH = """
--- var/lib/dpkg/info/base-files.postinst   2016-09-07 11:48:24.997337549 -0700
+++ var/lib/dpkg/info/base-files.postinst   2016-09-07 11:50:09.641334627 -0700
@@ -23,6 +23,13 @@

 migrate_directory() {
   if [ ! -L $1 ]; then
+    if [ ! -z "`ls -A $1/`" ]; then
+      for x in $1/* $1/.[!.]* $1/..?*; do
+        if [ -e "$x" ]; then
+          mv -- "$x" $2/
+        fi
+      done
+    fi
     rmdir $1
     ln -s $2 $1
   fi
"""


def tweak_new_filesystem(root_dir):
  """
  Apply various tweaks/edits to the root filesystem after packages have been
  collected but before dpkg has been run to configure the system
  """

  # create a symlink for insserv
  force_symlink('../usr/lib/insserv/insserv',
                os.path.join(root_dir, 'sbin/insserv'))

  # create a symlink for awk
  force_symlink('mawk', os.path.join(root_dir, 'usr/bin/awk'))

  # Nvidia keeps packaging up a broken post-install script for their cudnn
  # deb. Freaking nvidia
  cudnn_postinst_path = 'var/lib/dpkg/info/libcudnn6-dev.postinst'
  cudnn_postinst_path = os.path.join(root_dir, cudnn_postinst_path)

  if os.path.exists(cudnn_postinst_path):
    with open(cudnn_postinst_path, 'r') as infile:
      content = infile.read()
    if not content.startswith("#!"):
      with open(cudnn_postinst_path, 'w') as outfile:
        outfile.write('#! /bin/sh\n')
        outfile.write(content)

  # NOTE(josh): patch the base-packages post-install hook so it doesn't
  # complain about files in /var/run
  basefiles_path = os.path.join(root_dir,
                                'var/lib/dpkg/info/base-files.postinst')
  if os.path.exists(basefiles_path):
    apply_patch_text(BASE_FILES_PATCH, root_dir)

  # NOTE(josh): ifupdown should depend on initscripts, but it doesn't
  status_path = os.path.join(root_dir, 'var/lib/dpkg/status')
  tempfile_path = status_path + '.tmp'
  with open(tempfile_path, 'wb') as outfile:
    with open(status_path, 'rb') as infile:
      for line in infile:
        outfile.write(line)
        if line.strip() == 'Package: ifupdown':
          break

      for line in infile:
        if line.startswith('Depends: '):
          line = ', '.join(line.strip().split(', ') + ['initscripts']) + '\n'
          outfile.write(line)
          break
        else:
          outfile.write(line)

      for line in infile:
        outfile.write(line)
    os.rename(tempfile_path, status_path)

  # NOTE(josh): resolvconf tries to a write a file in this directory
  try:
    target_path = os.path.join(root_dir, 'run/resolvconf/interface')
    os.makedirs(target_path)
  except OSError:
    if not os.path.isdir(target_path):
      raise

  # NOTE(josh): Can't postinst makedev without CAP_MKNOD
  if os.getuid() != 0:
    makedev_postinst = os.path.join(root_dir,
                                    'var/lib/dpkg/info/makedev.postinst')
    if os.path.exists(makedev_postinst):
      os.rename(makedev_postinst, makedev_postinst + '.bak')

  # remove temporary/boostrap files
  files_to_remove = ['etc/apt/sources.list.d/bootstrap.list']

  for filename in files_to_remove:
    file_path = os.path.join(root_dir, filename)
    if os.path.exists(file_path):
      os.remove(file_path)


MEGABYTE = 1024 * 1024

POLICY_SCRIPT = """#!/bin/sh
echo "All runlevel operations denied by policy" >&2
exit 101
"""


def configure_dpkgs(chroot_app, rootfs, retry_count):
  """
  Attempt to use qemu-arm-static to finish configuration, without moving the
  rootfs to an actual arm system.
  """

  if os.path.exists(os.path.join(rootfs, 'var/lib/dpkg/info/dash.preinst')):
    chroot_app.check_call(['/var/lib/dpkg/info/dash.preinst', 'install'])

  # NOTE(josh): prevent interactive question of whether or not to use dash as
  # default system shell
  if os.path.exists(os.path.join(rootfs, 'usr/bin/debconf-set-selections')):
    debconf_proc = chroot_app.popen(['debconf-set-selections'],
                                    stdin=subprocess.PIPE)
    debconf_proc.communicate('dash dash/sh boolean true\n')
    debconf_proc.wait()
    assert debconf_proc.returncode == 0, \
        "Failed to set dash as the default shell"

  # NOTE(josh): prevent interactive question for timezone
  # TODO(josh): move to config / command line
  logging.info('setting timezone')
  with open(os.path.join(rootfs, 'etc/timezone'), 'w') as timezone:
    timezone.write('America/Los_Angeles\n')

  # NOTE(josh): try to disable any daemons from starting
  policy_path = os.path.join(rootfs, 'usr/sbin/policy-rc.d')
  with open(policy_path, 'w') as policy:
    policy.write(POLICY_SCRIPT)
  os.chmod(policy_path, 0o755)

  # configure everything except nginx
  configure_success = False
  for _ in range(1 + retry_count):
    try:
      chroot_app.check_call(['dpkg', '--configure', '-a'])
      configure_success = True
      break
    except subprocess.CalledProcessError:
      pass

  assert configure_success, \
      "'dpkg --configure -a' failed after {} tries".format(1 + retry_count)

  os.remove(policy_path)


def install_pip_packages(chroot_app, rootfs, package_list):
  wheelhouse = os.path.join(rootfs, 'opt/wheelhouse')
  if not os.path.exists(wheelhouse):
    os.makedirs(wheelhouse)

  chroot_app.check_call(['pip', 'install', '--upgrade', 'pip'])
  chroot_app.check_call(['pip', 'install', '--upgrade', 'wheel', 'setuptools'])

  logging.info('Installing pip packages:\n  %s',
               '\n  '.join(package_list))

  chroot_app.check_call(['pip', 'wheel',
                         '--find-links=/opt/wheelhouse',
                         '--wheel-dir=/opt/wheelhouse']
                        + package_list)
  chroot_app.check_call(['pip', 'install', '--upgrade', '--no-index',
                         '--find-links=/opt/wheelhouse'] + package_list)

  paths_to_remove = ['root/.cache/pip']
  for path in paths_to_remove:
    subprocess.check_call(['rm', '-rf', os.path.join(rootfs, path)])


def initialize_rootfs(rootfs_dir, apt_sources):
  """
  Write initial apt configuration files so that we can call apt.
  """

  lib64_path = os.path.join(rootfs_dir, 'lib64')
  if not os.path.exists(lib64_path):
    force_symlink('lib', lib64_path)

  for mkdir in ['etc/apt',
                'etc/apt/sources.list.d',
                'etc/apt/preferences.d',
                'var/cache/apt/archives/partial',
                'var/cache/debconf',
                'var/lib/dpkg',
                'var/lib/dpkg/alternatives',
                'var/lib/dpkg/info',
                'var/lib/dpkg/parts',
                'var/lib/dpkg/updates', ]:
    try:
      os.makedirs(os.path.join(rootfs_dir, mkdir))
    except OSError:
      pass

  bootstrap_list_path = os.path.join(rootfs_dir,
                                     'etc/apt/sources.list.d/bootstrap.list')
  with open(bootstrap_list_path, 'w') as bootstrap_list:
    bootstrap_list.write(apt_sources)

  for touch_path in ['var/lib/dpkg/arch',
                     'var/lib/dpkg/diversions',
                     'var/lib/dpkg/lock',
                     'var/lib/dpkg/statoverride',
                     'var/lib/dpkg/status', ]:
    with open(os.path.join(rootfs_dir, touch_path), 'w') as _:
      pass


def rfc822_parse(infile):
  """
  Parse rfc822 style dictionaries used in debian package list files. Returns a
  generator over dictionaries of package information.

  https://www.w3.org/Protocols/rfc822/
  """

  result = {}
  current_key = None
  current_content = []

  for idx, line in enumerate(infile):
    line = line.rstrip()
    if not line.strip():
      if result:
        yield result
      result = {}
      current_key = None
      current_content = None
      continue

    if current_key:
      if line.startswith(' ') or line.startswith('\t'):
        current_content.append(line.strip())
        continue
      else:
        result[current_key] = '\n'.join(current_content).strip()

    try:
      current_key, content = line.split(':', 1)
    except ValueError:
      logging.warn('malformed rfc822 format on %s:%d\n',
                   getattr(infile, 'name', '?'), idx)
      raise

    current_content = [content]

  if current_key:
    result[current_key] = '\n'.join(current_content)

  if result:
    yield result


def get_default_packages(rootfs, include_essential=False,
                         include_priorities=None):
  """
  Read source lists to get a list of essential or high priority packages.
  """
  if include_priorities is None:
    include_priorities = []

  package_list = set()

  list_dir = os.path.join(rootfs, 'var/lib/apt/lists')
  for filename in os.listdir(list_dir):
    if not filename.endswith('_Packages'):
      continue

    with open(os.path.join(list_dir, filename)) as infile:
      for pkg in rfc822_parse(infile):
        if 'Essential' in pkg and include_essential:
          package_list.add(pkg['Package'])
          continue
        if 'Priority' not in pkg:
          continue

        if pkg['Priority'] in include_priorities:
          package_list.add(pkg['Package'])

  return list(sorted(package_list))


APT_GET_FMT = """
apt-get
  -o Apt::Architecture={arch}
  -o Dir::Etc::TrustedParts={rootfs}/etc/apt/trusted.gpg.d
  -o Dir::Etc::Trusted={rootfs}/etc/apt/trusted.gpg
  -o Apt::Get::Download-Only=true
  -o Apt::Install-Recommends=false
  -o Dir={rootfs}/
  -o Dir::Etc={rootfs}/etc/apt/
  -o Dir::Etc::Parts={rootfs}/etc/apt/apt.conf.d/
  -o Dir::Etc::PreferencesParts={rootfs}/etc/apt/preferences.d/
  -o APT::Default-Release=*
  -o Dir::State={rootfs}/var/lib/apt/
  -o Dir::State::Status={rootfs}/var/lib/dpkg/status
  -o Dir::Cache={rootfs}/var/cache/apt/
  -o Acquire::Source-Symlinks=false
"""

APT_PROXY_FMT = """
  -o Acquire::http::Proxy={proxy}
  -o Acquire::http::Proxy::download.oracle.com=DIRECT
  -o Acquire::https::Proxy=false
"""


def get_apt_command(arch, rootfs, apt_cacher):
  """
  Return base apt-get command with all configuration options.
  """

  base_cmd = APT_GET_FMT.format(arch=arch, rootfs=rootfs).strip().split()
  if apt_cacher:
    base_cmd += APT_PROXY_FMT.format(proxy=apt_cacher).strip().split()
  return base_cmd


def print_size_report(report_path, include_packed_size=True,
                      include_size_on_disk=True,
                      include_description=True,
                      human_readable=True,
                      sort_column=0):
  """
  Pretty-print a sorted size report from a json package report
  """

  with open(report_path, 'r') as infile:
    report_data = json.load(infile)

  sorted_items = sorted(((item[1], int(item[2]) * 1024, item[0], item[3])
                         for item in report_data), key=lambda x: x[sort_column])

  fmt_parts = []
  if include_packed_size:
    if human_readable:
      fmt_parts.append('{:10s}')
    else:
      fmt_parts.append('{:12d}')
  if include_size_on_disk:
    if human_readable:
      fmt_parts.append('{:10s}')
    else:
      fmt_parts.append('{:12d}')
  fmt_parts.append('{:20s}')

  if include_description:
    fmt_parts.append('{:30s}')

  format_str = ' '.join(fmt_parts) + '\n'

  for package_size, installed_size, package, description in sorted_items:
    description_lines = description.splitlines()
    if description_lines:
      description_str = description_lines[0][:30]
    else:
      description_str = description

    args = []
    if include_packed_size:
      if human_readable:
        args.append(util.get_human_readable_size(package_size))
      else:
        args.append(package_size)
    if include_size_on_disk:
      if human_readable:
        args.append(util.get_human_readable_size(installed_size))
      else:
        args.append(installed_size)
    args.append(package)
    if include_description:
      args.append(description_str)

    logging.info(format_str.format(*args))
  sys.stdout.flush()


def iter_mounts():
  """
  Return a generator that iterates over split lines in /proc/mounts. The format
  of each entry is a tuple of the form (device, mountpoint, filesystem,
  options).
  """
  with open('/proc/mounts', 'r') as mounts:
    for line in mounts.readlines():
      (device, mountpoint, filesystem,
       options, _, _) = line.decode('UTF-8').split()
      yield (device, mountpoint, filesystem, options)


def get_device_mounted_at(query_path):
  """Return the device file mounted at the given path if it is a mount point."""

  # pylint: disable=unused-variable
  for device, mountpoint, filesystem, options in iter_mounts():
    try:
      if os.path.samefile(mountpoint, query_path):
        return device
    except OSError:
      continue

  return None


def get_apt_version():
  """
  Execute ``apt-get --version`` and parse the result to get a list of integers
  used to identify the apt version number.
  """
  version_output = util.print_and(subprocess.check_output,
                                  ['apt-get', '--version']).strip()
  firstline = version_output.splitlines()[0]
  version_number = firstline.split()[1]
  return [int(part) for part in version_number.split('.')]


def create_rootfs(config):

  try:
    os.makedirs(config.rootfs)
  except OSError:
    if not os.path.isdir(config.rootfs):
      raise

  initialize_rootfs(config.rootfs, config.apt_sources)

  apt_cmd = get_apt_command(config.architecture, config.rootfs,
                            config.apt_http_proxy)
  if not config.apt_skip_update:
    util.print_and(subprocess.check_call, apt_cmd + ['update'])

  default_packages = get_default_packages(config.rootfs,
                                          config.apt_include_essential,
                                          config.apt_include_priorities)
  if config.pip_packages:
    default_packages.append('python-pip')
  apt_package_list = list(sorted(set(config.apt_packages
                                     + default_packages)))

  apt_version = get_apt_version()
  if apt_version >= [1, 2, 24]:
    util.print_and(subprocess.check_call,
                   apt_cmd + ['-y',
                              '--allow-downgrades',
                              '--allow-remove-essential',
                              '--allow-change-held-packages',
                              'install'] + apt_package_list)
  else:
    util.print_and(subprocess.check_call,
                   apt_cmd
                   + ['-y', '--force-yes', 'install']
                   + apt_package_list)

  report = unpack_apt_archives_plus(config.rootfs, config.external_debs)
  if config.apt_size_report is not None:
    parent_dir = os.path.dirname(config.apt_size_report)
    try:
      os.makedirs(parent_dir)
    except OSError:
      pass
    with open(config.apt_size_report, 'w') as reportfile:
      json.dump(report, reportfile, indent=2, separators=(',', ': '))

  logging.info('tweaking new filesystem')
  tweak_new_filesystem(config.rootfs)

  logging.info('applying user quirks')
  config.user_quirks()

  if config.chroot_app is None:
    logging.info('Skipping dpkg configure step')
  else:
    chroot_app = config.chroot_app(config.rootfs, config.binds,
                                   config.qemu_binary,
                                   config.pip_wheelhouse)
    with chroot_app:
      logging.info('Executing dpkg --configure')
      configure_dpkgs(chroot_app, config.rootfs,
                      config.dpkg_configure_retry_count)

      if config.pip_packages:
        logging.info('Installing pip packages')
        install_pip_packages(chroot_app, config.rootfs, config.pip_packages)

  if config.apt_clean:
    # TODO(josh): document what this actually cleans up
    util.print_and(subprocess.check_call, apt_cmd + ['clean'])

    cache_dir = os.path.join(config.rootfs, 'var/cache/apt/archives')
    for filename in os.listdir(cache_dir):
      os.remove(os.path.join(cache_dir, filename))
