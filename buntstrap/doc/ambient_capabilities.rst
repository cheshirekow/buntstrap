
-----
Notes
-----

http://man7.org/linux/man-pages/man7/capabilities.7.html
https://lwn.net/Articles/632520/
https://lwn.net/Articles/632113/
http://man7.org/linux/man-pages/man2/prctl.2.html
http://man7.org/linux/man-pages/man3/cap_from_text.3.html


ambient_test::

    ------------------------------ ambient_test.c
    #include <stdlib.h>
    #include <stdio.h>
    #include <errno.h>
    #include <sys/capability.h>
    #include <sys/prctl.h>
    #include <linux/capability.h>
    #include <linux/securebits.h>
    #include <unistd.h>

    int main(int argc, char **argv)
    {
      int rc;

      int secbits = prctl(PR_GET_SECUREBITS);
      cap_t cap_p = cap_get_proc();
      cap_flag_value_t value_p = 0;
      cap_get_flag(cap_p, CAP_NET_RAW, CAP_EFFECTIVE, &value_p);
      printf("CAP_NET_RAW(effective): %d\n", value_p);
      cap_get_flag(cap_p, CAP_NET_RAW, CAP_INHERITABLE, &value_p);
      printf("CAP_NET_RAW(inheritable): %d\n", value_p);
      cap_get_flag(cap_p, CAP_NET_RAW, CAP_PERMITTED, &value_p);
      printf("CAP_NET_RAW(permitted): %d\n", value_p);

      value_p = 1;
      cap_value_t caps[] = {CAP_NET_RAW, CAP_NET_ADMIN, CAP_SYS_NICE};
      if(cap_set_flag(cap_p, CAP_INHERITABLE, 3, caps, 1))
        perror("Cannot set CAP_INHERITABLE");

      if(cap_set_proc(cap_p))
        perror("Cannot set_proc");

      cap_free(cap_p);

      if(secbits & SECBIT_NO_CAP_AMBIENT_RAISE)
        printf("SECBIT_NO_CAP_AMBIENT_RAISE");

      if (prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_RAISE, CAP_NET_RAW, 0, 0))
        perror("Cannot set CAP_NET_RAW");

      if (prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_RAISE, CAP_NET_ADMIN, 0, 0))
        perror("Cannot set CAP_NET_ADMIN");

      if (prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_RAISE, CAP_SYS_NICE, 0, 0))
        perror("Cannot set CAP_SYS_NICE");

      printf("Ambient_test forking shell\n");
      if (execv(argv[1], argv + 1))
        perror("Cannot exec");

      return 0;
    }
    -------------------------------- ambient_test.c

Allows the inheritance of CAP_SYS_NICE, CAP_NET_RAW and CAP_NET_ADMIN.
With that device raw access is possible and also real time priorities
can be set from user space. This is a frequently needed set of
priviledged operations in HPC and HFT applications. User space
processes need to be able to directly access devices as well as
have full control over scheduling.

::

    josh@donut:~/Codes/buntstrap$ gcc -o /tmp/ambient_test /tmp/ambient_test.c -lcap
    josh@donut:~/Codes/buntstrap$ sudo setcap cap_mknod,cap_setpcap,cap_net_raw,cap_net_admin,cap_sys_nice+eip /tmp/ambient_test
    josh@donut:~/Codes/buntstrap$ /tmp/ambient_test /bin/bash


    #include <stdlib.h>
    #include <stdio.h>
    #include <errno.h>
    #include <sys/prctl.h>
    #include <linux/capability.h>
    #include <unistd.h>

    int main(int argc, char **argv)
    {
      int rc;

      if (prctl(PR_CAP_AMBIENT, CAP_MKNOD))
        perror("Cannot set CAP_MKNOD");

      printf("Ambient test\n");
      if (execv(argv[1], argv + 1))
        perror("Cannot exec");

      return 0;
    }
