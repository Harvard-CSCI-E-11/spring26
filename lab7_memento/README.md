# Lab 7
Welcome to Lab 7

First, read this:

https://learn.adafruit.com/adafruit-memento-camera-board/basic-camera

Be sure to format your SD card:

https://learn.adafruit.com/adafruit-memento-camera-board/formatting-notes

Do not rely on the file system that it came with!

The files in this folder are not a substitute for the excellent
tutorials on the CircuitPython.org website. Instead, they are designed
to provide you the minimum amount of information you need to be
successful with Lab 7.

## Getting Started
Plug in the Circuit Python device. Find its serial port. If you are using a Mac, use the `ls` command and look at devices being `/dev/cu*`:

```
% ls -l /dev/cu*
crw-rw-rw-  1 root  wheel  0x9000003 Dec 16 17:57 /dev/cu.Bluetooth-Incoming-Port
crw-rw-rw-  1 root  wheel  0x9000001 Dec 16 17:54 /dev/cu.debug-console
crw-rw-rw-  1 root  wheel  0x9000005 Dec 16 17:57 /dev/cu.DockingK10C
crw-rw-rw-  1 root  wheel  0x9000007 Dec 16 17:57 /dev/cu.Shokz
crw-rw-rw-  1 root  wheel  0x9000009 Dec 22 19:55 /dev/cu.usbmodem468E3347B6091
%
```

Here's what they mean:

`/dev/cu.Bluetooth-Incoming-Port`   --- Handles incomming Bluetooth connections.

`/dev/cu.debug-console`   --- An internal MacOS Bluetooth port

`/dev/cu.DockingK10C`   --- Simson's K10C Bluetooth headphone

`/dev/cu.Shokz`   --- Simson's Shokz Bluetooth Headphones

`/dev/cu.usbmodem468E3347B6091`   --- The MEMENTO!


You should also see the CIRCUITPY folder mounted:

```
% ls -l /Volumes/CIRCUITPY
total 15
-rwx------  1 simsong  staff   150 Jan  1  2000 boot_out.txt
-rwx------@ 1 simsong  staff  3235 Dec 22 19:09 code.py
drwx------  1 simsong  staff  2560 Dec 12 22:13 lib
drwx------  1 simsong  staff   512 Jan  1  2000 sd
-rwx------@ 1 simsong  staff   252 Dec 22 19:48 settings.toml
%
```

Use the `circup` command to install software:
```
simsong@Seasons-2 lab8 % poetry run circup --help
Usage: circup [OPTIONS] COMMAND [ARGS]...

  A tool to manage and update libraries on a CircuitPython device.

Options:
  --verbose              Comprehensive logging is sent to stdout.
  --path DIRECTORY       Path to CircuitPython directory. Overrides automatic
                         path detection.
  --host TEXT            Hostname or IP address of a device. Overrides
                         automatic path detection.
  --port INTEGER         Port to contact. Overrides automatic path detection.
  --password TEXT        Password to use for authentication when --host is
                         used. You can optionally set an environment variable
                         CIRCUP_WEBWORKFLOW_PASSWORD instead of passing this
                         argument. If both exist the CLI arg takes precedent.
  --timeout INTEGER      Specify the timeout in seconds for any network
                         operations.
  --board-id TEXT        Manual Board ID of the CircuitPython device. If
                         provided in combination with --cpy-version, it
                         overrides the detected board ID.
  --cpy-version TEXT     Manual CircuitPython version. If provided in
                         combination with --board-id, it overrides the
                         detected CPy version.
  --bundle-version TEXT  Specify the version to use for a bundle. Include the
                         bundle name and the version separated by '=', similar
                         to the format of requirements.txt. This option can be
                         used multiple times for different bundles. Bundle
                         version values provided here will override any pinned
                         values from the pyproject.toml.
  --version              Show the version and exit.
  --help                 Show this message and exit.

Commands:
  bundle-add     Add bundles to the local bundles list, by "user/repo"...
  bundle-freeze  Output details of all the bundles for modules found on...
  bundle-remove  Remove one or more bundles from the local bundles list.
  bundle-show    Show the list of bundles, default and local, with URL,...
  example        Copy named example(s) from a bundle onto the device.
  freeze         Output details of all the modules found on the connected...
  install        Install a named module(s) onto the device.
  list           Lists all out of date modules found on the connected...
  show           Show a list of available modules in the bundle.
  uninstall      Uninstall a named module(s) from the connected device.
  update         Update modules on the device. Use --all to automatically
                 update all modules without Major Version warnings.
```

Install what you need with:

```
% poetry install
% poetry run circup install $(cat requirements_circuit.txt)
```

In the `demos/` directory you will find several self-contained circuit python files that you can copy and paste into the Thonny editor and save on to your MEMENTO. You can also send them to the MEMENTO using the `ampy` command line program. Remember - when the computer starts up, it runs the python program called `code.py`.

Be sure to add your wifi settings to `/settings.toml` for the demos that require internet access!

Two programs you should look at include:

`code_bounce.py` - Draw a bouncing ball.

`code_leaderboard_client.py` - The client for the leaderboard. This is what you need to complete lab7.

Now go to the lab at https://csci-e-11.org/lab7
