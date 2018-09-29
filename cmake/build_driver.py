#!/usr/bin/env python
"""
Manage the execution of cmake for different build configurations.
"""

import logging
import os
import subprocess

# Requirements (based on ubuntu 16.04)
# apt-get install
#		python-pip
#		clang
#   clang-format
#   cmake
#   gcc
#   g++
#   gnuradio-dev
#   libcurl4-openssl-dev
#   libfuse-dev
#   libgoogle-glog-dev
#   libmagic-dev
#   libudev-dev
#   libvulkan-dev
#   libx11-xcb-dev
#   ninja-build
#
# pip install --upgrade pip
# pip install --user
# 	cpplint
#   autopep8
#   file-magic
#   flask
#   oauth2client
#   pygerrit2
#   pylint
#   recommonmark
#   sphinx
#   sqlalchemy


class Toolchain(object):
  """
  Stores some aggregate information about compiler suite
  """

  def __init__(self):
    self.name = None
    self.cc = None
    self.cxx = None
    self.tuple = None
    self.version = None

  @staticmethod
  def from_compiler_pair(cc, cxx):
    toolchain = Toolchain()
    toolchain.cc = cc
    toolchain.cxx = cxx

    versionstr = subprocess.check_output([toolchain.cc, '--version']).strip()
    toolchain.name = versionstr.split()[0]

    if toolchain.name == "gcc":
      toolchain.version = subprocess.check_output([cc, "-dumpversion"]).strip()
      toolchain.tuple = subprocess.check_output([cc, '-dumpmachine']).strip()
    elif toolchain.name == "clang":
      lines = versionstr.split('\n')
      toolchain.version = lines[0].split()[2]
      toolchain.tuple = lines[1].split(":", 1)[1].strip()
    else:
      raise ValueError("Unknown compiler {}".format(toolchain.name))

    return toolchain


class BuildSpec(object):
  """
  Named tuple of build type and build spec
  """

  def __init__(self, build_type, build_system, cxx_standard):
    self.type = build_type
    self.system = build_system
    self.cxx_standard = cxx_standard

  @property
  def generator(self):
    return {
        'make': 'Unix Makefiles',
        'ninja': 'Ninja'
    }[self.system]

  @property
  def command(self):
    if self.system == "make":
      return ["make", "-j4"]
    elif self.system == "ninja":
      return ["ninja"]
    else:
      raise ValueError("Invalid build system {}".format(self.system))


def get_builddir(toolchain, build):
  """
  Return the subdirectory of the buildroot designated for a build with the
  given axes.
  """
  return "{}-{}-{}/{}-{}-{}".format(
      toolchain.name, toolchain.tuple, toolchain.version,
      build.type, build.system, build.cxx_standard)


def generate_buildsystem(srcroot, outroot, toolchain, build):
  """
  Call out to cmake to generate the build system.
  """
  builddir = get_builddir(toolchain, build)
  outdir = os.path.join(outroot, builddir)

  if not os.path.exists(outdir):
    os.makedirs(outdir)

  env = os.environ.copy()
  env['CC'] = toolchain.cc
  env['CXX'] = toolchain.cxx

  subprocess.check_call([
      'cmake',
      "-G", build.generator,
      "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
      "-DCMAKE_BUILD_TYPE=" + build.type,
      "-DCXX_STANDARD=" + build.cxx_standard,
      srcroot
  ], env=env, cwd=outdir)


def execute_build(outroot, toolchain, build, target=None):
  """
  Call out to the build system to execute the build
  """
  builddir = get_builddir(toolchain, build)
  outdir = os.path.join(outroot, builddir)

  cmd = build.command
  if target is not None:
    cmd.append(target)
  retcode = subprocess.call(cmd, cwd=outdir)
  if retcode != 0:
    logging.error("Failure while executing in %s", builddir)
    raise subprocess.CalledProcessError(retcode, cmd)


def iter_builds():
  """
  Return a generator that yields toolchain/build-spec pairs for all the
  combinations that we support
  """

  toolchains = [
      Toolchain.from_compiler_pair("/usr/bin/gcc", "/usr/bin/g++"),
      Toolchain.from_compiler_pair("/usr/bin/clang", "/usr/bin/clang++")
  ]

  for toolchain in toolchains:
    for build_system in ['make', 'ninja']:
      for build_type in ['Debug', 'Release', 'RelWithDebInfo']:
        for cxx_standard in ['c++11', 'c++14']:
          yield toolchain, BuildSpec(build_type, build_system, cxx_standard)


def generate_main(srcroot, buildroot):
  for toolchain, build in iter_builds():
    generate_buildsystem(srcroot, buildroot, toolchain, build)


def build_main(buildroot):
  for toolchain, build in iter_builds():
    execute_build(buildroot, toolchain, build)


def main():
  import argparse
  this_dir = os.path.realpath(os.path.dirname(__file__))
  srcroot, _ = this_dir.rsplit(os.sep, 1)

  parser = argparse.ArgumentParser(description=__doc__)
  subparsers = parser.add_subparsers(dest="command")

  generate_parser = subparsers.add_parser("generate",
                                          help=generate_main.__doc__)
  generate_parser.add_argument("--srcroot", default=srcroot)

  build_parser = subparsers.add_parser("build",
                                       help=build_main.__doc__)

  buildroot = os.getcwd()
  if os.path.samefile(srcroot, buildroot):
    buildroot = os.sep.join([buildroot, ".build"])

  for subparser in [generate_parser, build_parser]:
    subparser.add_argument("--buildroot", default=buildroot)

  args = parser.parse_args()

  if args.command == "generate":
    generate_main(args.srcroot, args.buildroot)
  elif args.command == "build":
    build_main(args.buildroot)
  else:
    raise ValueError("unhandled command {}".format(args.command))


if __name__ == '__main__':
  main()
