=========
buntstrap
=========

an ``uBUNTu bootSTRAP`` utility.

Use ``buntstrap`` to bootstrap an ubuntu (or any debian-based) root filesystem
using ``apt``.

The default configuration is to use ``uchroot`` to enter the rootfs and
configure packages. This requires the ``newuidmap`` setuid helper. On ubuntu
install the ``newuidmap`` package. ``buntstrap`` is also capable of using
posix ``chroot`` (though you'll need to run buntstrap as root) or ``proot``
(which you will need to install).

-------
Example
-------

Create a minimal rootfs capable of running ``nano`` using a linux user
namespace and default uid/gid maps.::

  :~$ buntstrap --apt-include-essential false \
                --apt-include-priorities required \
                --apt-packages dpkg nano \
                -- /tmp/rootfs

  :~$ uchroot /tmp/rootfs
  :/# TERM=xterm nano

Create the same rootfs but make it bootable (i.e. files are really owned by
system users, such as root)::

  :~$ sudo buntstrap --chroot-impl=chroot \
                     --apt-include-essential false \
                     --apt-include-priorities required \
                     --apt-packages dpkg nano \
                     -- /tmp/rootfs

  :~$ sudo chroot /tmp/rootfs
  :/# nano

Create a minimal rootfs with ``ipython``. Note that some of the pip package
dependencies required in the installation of ``ipython`` will build python
extension modules so we have to add ``build-essential`` and ``python-dev`` to
the apt package list::

  :~$ buntstrap --apt-include-essential false \
                --apt-include-priorities required \
                --apt-packages dpkg build-essential python-dev \
                --pip-packages ipython \
                -- /tmp/rootfs

  :~$ uchroot --binds /dev/urandom \
              --exbin /usr/local/bin/ipython \
              -- /tmp/rootfs/


-----
Usage
-----

::

    usage: buntstrap [-h] [-v] [-l {debug,info,warning,error}] [-c CONFIG]
                    [--apt-include-essential [APT_INCLUDE_ESSENTIAL]]
                    [--apt-sources APT_SOURCES] [--pip-wheelhouse PIP_WHEELHOUSE]
                    [--apt-http-proxy APT_HTTP_PROXY]
                    [--apt-size-report APT_SIZE_REPORT]
                    [--external-debs [EXTERNAL_DEBS [EXTERNAL_DEBS ...]]]
                    [--pip-packages [PIP_PACKAGES [PIP_PACKAGES ...]]]
                    [--binds [BINDS [BINDS ...]]] [--apt-clean [APT_CLEAN]]
                    [--apt-skip-update [APT_SKIP_UPDATE]]
                    [--architecture {amd64,arm64,armhf}]
                    [--apt-packages [APT_PACKAGES [APT_PACKAGES ...]]]
                    [--suite {trusty,utopic,vivid,wily,xenial,yakkety,zesty,artful}]
                    [--dpkg-configure-retry-count DPKG_CONFIGURE_RETRY_COUNT]
                    [--qemu-binary QEMU_BINARY]
                    [--apt-include-priorities [APT_INCLUDE_PRIORITIES [APT_INCLUDE_PRIORITIES ...]]]
                    [--rootfs ROOTFS] [--chroot-impl {none,chroot,proot,uchroot}]
                    [rootfs]

    Bootstrap an ubuntu rootfs.

    positional arguments:
      rootfs                path of the rootfs to bootstrap

    optional arguments:
      -h, --help            show this help message and exit
      -v, --version         show program's version number and exit
      -l {debug,info,warning,error}, --log-level {debug,info,warning,error}
                            Increase log level to include info/debug
      -c CONFIG, --config CONFIG
                            Configuration file to use
      --apt-include-essential [APT_INCLUDE_ESSENTIAL]
                            If true, then we will request a list of all
                            "essential" packages from apt and include them in the
                            installation.
      --apt-sources APT_SOURCES
                            This is the string contents of the apt sources list
                            used to bootstrap the system. The file will be written
                            into the target rootfs before executing apt but will
                            be removed afterward.
      --pip-wheelhouse PIP_WHEELHOUSE
                            If installing any packages through pip, you can re-use
                            an existing wheelhouse to cache binary wheels and
                            speed up repeated bootstrapping. Specify the
                            wheelhouse directory here
      --apt-http-proxy APT_HTTP_PROXY
                            If not none, then we'll set the http proxy environment
                            variables for APT using this. If apt-cacher-ng is
                            installed an active it is usually at
                            http://localhost:3142. The function
                            ``config.get_apt_cache_url()`` will check for apt-
                            cacher-ng and return it if found, otherwise None.
      --apt-size-report APT_SIZE_REPORT
                            If you would like buntstrap to write out a package
                            size report then specify here the output path where
                            you would like that report to go.
      --external-debs [EXTERNAL_DEBS [EXTERNAL_DEBS ...]]
                            If you have any plain .deb packages to install inside
                            the rootfs list them here. They will be extracted
                            along with those downloaded by apt and configured with
                            the rest.
      --pip-packages [PIP_PACKAGES [PIP_PACKAGES ...]]
                            List of python package to install using pip. Note that
                            if this list is not empty then `python-pip` will be
                            included in apt_packages (if it is not already) and
                            pip will be installed itself with `pip install
                            --upgrade pip`. If you want to pin a specific version
                            of pip then make sure you list it here.
      --binds [BINDS [BINDS ...]]
                            List of paths to bind-mount to the target rootfs. If a
                            path is a realfile it will be copied into the rootfs
                            and deleted afterward. If it is a directory then it
                            will be bind-mounted (or emulated in the proot case)
      --apt-clean [APT_CLEAN]
                            If true, the apt archive cache and other state files
                            are cleaned up. Use this if you want to reduce the
                            size of your rootfs.
      --apt-skip-update [APT_SKIP_UPDATE]
                            If you already have a rootfs that has been
                            bootstrapped and you wish to (re)-install packages you
                            can set this true to skip the `apt-get` update step.
                            This is mostly useful during debugging/testing
                            iteration.
      --architecture {amd64,arm64,armhf}
                            dpkg architecture of the rootfs to build. If you'd
                            like to know what architecture you're currently on,
                            try running `dpkg --print-architecture`.
      --apt-packages [APT_PACKAGES [APT_PACKAGES ...]]
                            List of packages to install with apt
      --suite {trusty,utopic,vivid,wily,xenial,yakkety,zesty,artful}
                            this is only used to select reasonable defaults if you
                            leave out some configuration parameters, but specify
                            the ubuntu target suite here.
      --dpkg-configure-retry-count DPKG_CONFIGURE_RETRY_COUNT
                            Sometimes a package will fail to configure correctly
                            only because it hasn't correctly declared it's
                            dependencies and it gets configured out of order. An
                            easy work around is to just retry dpkg --configure
                            again. Set here the number of times to try execugind
                            `dpkg --configure`.
      --qemu-binary QEMU_BINARY
                            If you are cross-arch bootstrapping from amd64 to arm
                            then specify here the path to the qemu-static binary
                            that should be copied into the target rootfs during
                            chroot execution. ``config.get_qemu_binary(arch)`` is
                            a convenience function which returns the default path
                            for the qemu-static binary for arm64 or armhf
      --apt-include-priorities [APT_INCLUDE_PRIORITIES [APT_INCLUDE_PRIORITIES ...]]
                            Specify the set of priority package lists to include.
                            'required': dpkg wont function without these
                            'important': standard set of minimal unix programs
                            'standard': reasonably small but not too limited
                            character-mode system
      --rootfs ROOTFS       This is the directory of the rootfs to bootstrap.
      --chroot-impl {none,chroot,proot,uchroot}
                            Use this chroot application


For most executions of ``buntstrap`` you'll probably want to utilize a
configuration file. Most configuration options can be overridden (or primarily
specified) by command line arguments. The command line argument name is the
same as the config file variable with undersore (``_``) replaced by dash
(``-``).

::

    from buntstrap import chroot
    from buntstrap import config

    # dpkg architecture of the rootfs to build. If you'd like to know what
    # architecture you're currently on, try running `dpkg --print-architecture`.
    architecture = u"amd64"

    # this is only used to select reasonable defaults if you leave out some
    # configuration parameters, but specify the ubuntu target suite here.
    suite = u"xenial"

    # Which chroot application to use. There are three builtin options:
    # 1. PosixApp : uses posix ``chroot`` and must be run as root
    # 2. ProotApp : uses ``proot``
    # 3. UchrootApp : uses ``uchroot`` which creats a user namespace. All files
    #    in the target rootfs will have uid/gid ownership with mapped values
    chroot_app = chroot.UchrootApp

    # This is the directory of the rootfs to bootstrap.
    rootfs = '/tmp/rootfs'

    # If not none, then we'll set the http proxy environment variables for APT
    # using this. If apt-cacher-ng is installed an active it is usually at
    # http://localhost:3142. This function will check for apt-cacher-ng and
    # return it if found, otherwise None.
    apt_http_proxy = config.get_apt_cache_url()

    # List of packages to install with apt
    apt_packages = []

    # If true, then we will request a list of all "essential" packages from apt
    # and include them in the installation.
    apt_include_essential = True

    # Specify the set of priority package lists to include.
    apt_include_priorities = [
        'required',  # dpkg wont function without these
        'important',  # standard set of minimal unix programs
        'standard',  # reasonably small but not too limited character-mode system
    ]

    # This is the string contents of the apt sources list used to bootstrap the
    # system. The file will be written into the target rootfs before executing
    # apt but will be removed afterward.
    apt_sources = u"""
    # NOTE(josh): these sources are used to bootstrap the rootfs and should be
    # omitted from after initial package installation. You should not see this
    # file on a live system.

    deb [arch={arch}] {ubuntu_url} {suite} main universe multiverse
    deb [arch={arch}] {ubuntu_url} {suite}-updates main universe multiverse
    deb [arch={arch}] http://ppa.launchpad.net/lttng/stable-2.9/ubuntu {suite} main
    deb [arch={arch}] http://ppa.launchpad.net/nginx/stable/ubuntu {suite} main
    """.format(arch=architecture,
              ubuntu_url=config.get_ubuntu_url(architecture),
              suite=suite)

    # If you already have a rootfs that has been bootstrapped and you wish to
    # (re)-install packages you can set this true to skip the `apt-get` update
    # step. This is mostly useful during debugging/testing iteration.
    apt_skip_update = False

    # If you would like buntstrap to write out a package size report then specify
    # here the output path where you would like that report to go.
    apt_size_report = None

    # If true, the apt archive cache and other state files are cleaned up. Use this
    # if you want to reduce the size of your rootfs.
    apt_clean = True

    # If you have any plain .deb packages to install inside the rootfs list them
    # here. They will be extracted along with those downloaded by apt and configured
    # with the rest.
    external_debs = []

    # If there are any patches that you need to apply or mucking around that you
    # need to do before executing dpkg --configure, then create this hook here.
    # It will be executed inside the chroot so feel free to mess with any
    # files you need.


    def user_quirks():
      pass


    # Sometimes a package will fail to configure correctly only because it hasn't
    # correctly declared it's dependencies and it gets configured out of order.
    # An easy work around is to just retry dpkg --configure again. Set here the
    # number of times to try execugind `dpkg --configure`.
    dpkg_configure_retry_count = 1

    # If installing any packages through pip, you can re-use an existing wheelhouse
    # to cache binary wheels and speed up repeated bootstrapping. Specify the
    # wheelhouse directory here
    pip_wheelhouse = None

    # List of python package to install using pip. Note that if this list is not
    # empty then `python-pip` will be included in apt_packages (if it is not
    # already) and pip will be installed itself with `pip install --upgrade pip`.
    # If you want to pin a specific version of pip then make sure you list it here.
    pip_packages = []

    # If you are cross-arch bootstrapping from amd64 to arm then specify here the
    # path to the qemu-static binary that should be copied into the target rootfs
    # during chroot execution. `get_qemu_binary(arch)` is a convenience function
    # which returns the default path for the qemu-static binary for arm64 or amd64
    qemu_binary = config.get_qemu_binary(architecture)
