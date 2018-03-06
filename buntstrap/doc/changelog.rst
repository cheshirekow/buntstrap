=========
Changelog
=========

------
v0.1.0
------

Initial public release.

* Executes apt from parent rootfs, then chroot and execute dpkg --configure
* Support for installation of pip packages after dpkg --configure
* Support for ``uchroot``, ``chroot``, or ``proot`` as the changeroot
  application
* Support for http proxy as apt cache
* Support for pip wheelhouse cache

v0.1.1
------

* fix dictionary in setup.py should be list
