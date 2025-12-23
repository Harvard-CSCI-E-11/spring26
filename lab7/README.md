# Lab 7
Welcome to Lab 67

The files in this folder are not a substitute for the excellent
tutorials on the CircuitPython.org website. Instead, they are designed
to provide you the minimum amount of information you need to be
successful with Lab 7.

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
% ampy -p /dev/cu.usbmodem487F303F2B261 ls
/boot_out.txt
/code.py
/lib
/sd
/settings.toml
```

(You may see additional files if you are running on a Macintosh. These files are used by the MacOS Trash and indexing system.)

In the `demos/` directory you will find several self-contained circuit python files that you can copy and paste into the Thonny editor and save on to your MEMENTO. You can also send them to the MEMENTO using the `ampy` command line program. Remember - when the computer starts up, it runs the python program called `code.py`.

Be sure to add your wifi settings to `/settings.toml` for the demos that require internet access!

Two programs you should look at include:

`code_bounce.py` - Draw a bouncing ball.

`code_leaderboard_client.py` - The client for the leaderboard. This is what you need to complete lab7.
