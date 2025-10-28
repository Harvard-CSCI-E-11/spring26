# Lab 6
Welcome to Lab 6.

The files in this folder are not a substitute for the excellent
tutorials on the CircuitPython.org website. Instead, they are designed
to provide you the minimum amount of information you need to be
successful with Lab 6.

## Getting Started
Plug in the Circuit Python device. Find its serial port. If you are using a Mac, use the `ls` command and look at devices being `/dev/cu*`:

```
simsong@Seasons ~ % ls -l /dev/cu*
crw-rw-rw-  1 root  wheel  0x900000b Dec 14 10:39 /dev/cu.Bluetooth-Incoming-Port
crw-rw-rw-  1 root  wheel  0x9000005 Dec 14 10:39 /dev/cu.ETYMOTION-BT
crw-rw-rw-  1 root  wheel  0x9000003 Dec 14 10:39 /dev/cu.K10C
crw-rw-rw-  1 root  wheel  0x9000009 Dec 14 10:39 /dev/cu.K21
crw-rw-rw-  1 root  wheel  0x9000007 Dec 21 19:29 /dev/cu.Shokz
crw-rw-rw-  1 root  wheel  0x9000001 Dec 21 20:45 /dev/cu.debug-console
crw-rw-rw-  1 root  wheel  0x900000d Dec 25 11:41 /dev/cu.usbmodem487F303F2B261
simsong@Seasons ~ %
```

In    this   case,    the   `/dev/cu.ETYMOTION-BT`,    `/dev/cu.K10C`,
`/dev/cu.K21` and  `/dev/cu.Shokz` are  all BlueTooth  headsets, while
`/dev/cu.debug-console` is another  CircuitPython device.  The device
we want is `/dev/cu.usbmodem487F303F2B261`.

I verify this with the `ampy` `ls` command:

```
(venv) simsong@Seasons lab6 % ampy -p /dev/cu.usbmodem487F303F2B261 ls                                                                                                               (main)csci_e-11
/.Trash-1000
/.Trashes
/._code.py
/.fseventsd
/.metadata_never_index
/boot_out.txt
/code.py
/lib
/sd
/settings.toml
```

1. Several files begin with `demo_`. These are self-contained circuit python files that you can copy and paste into the Mu editor and save on to your Circuit Python computer. You can also send them to the computer using the `ampy` command line program. Remember - when the computer starts up, it runs the python program called `code.py`.

2. For ease of maintaining these demos, we store wifi configuration in a file called config.py. This file is not included in the git repo for security reasons, but there is a file called `config_dist.py` that you can copy to `config.py` and edit. Once you do that, send it to your device with:
