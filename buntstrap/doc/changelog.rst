=========
Changelog
=========

-----------
v0.1 series
-----------

v0.1.4
------

* doc edits
* sort help
* add support for "none" in --apt-include-priorities
* make a general --phases and --skip instead of invidiual flags
* add missing apt config options and sort them
* fix version mechanism

v0.1.3
------

* bunstrap.freeze can work with a report json or dpkg in a chroot
* move user quirks after chroot app construction
* user quirks takes a chroot app as input
* add java webupd8team ppa to default bunstrap
* fix default user quirks noop()
* downsample some stdout progress messages

v0.1.2
------

* add command line help
* add warning if unused config file option
* add --dump-config
* split size report and package extraction into two separate steps
* added --terminate-after config/command-line option
* Add buntstrap.size_report command line utility
* Add buntstrap.freeze command line utility

v0.1.1
------

* fix dictionary in setup.py should be list

v0.1.0
------

Initial public release.

* Executes apt from parent rootfs, then chroot and execute dpkg --configure
* Support for installation of pip packages after dpkg --configure
* Support for ``uchroot``, ``chroot``, or ``proot`` as the changeroot
  application
* Support for http proxy as apt cache
* Support for pip wheelhouse cache

