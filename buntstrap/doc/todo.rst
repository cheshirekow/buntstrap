====
TODO
====

1. Figure out how to excalate CAP_MKNOD for the container so that makedev can
   work. You'll probably need to sudo it.

http://man7.org/linux/man-pages/man7/capabilities.7.html
http://man7.org/linux/man-pages/man3/cap_set_proc.3.html

2. Apparently missing /etc/passwd and /etc/groups will cause various packages
   to fail installation on trusty. On xenial, these files seem to be provided
   in their own packages and will install OK. We might need to deploy some stubs
   on trusty to get things going.
3. Finish implementing ``chroot_binds`` as a configuration option. Add
   ``qemu_binary`` and ``wheelhouse`` if those options are set.
