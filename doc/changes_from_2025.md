Changes from last year:
=======================
* We moved from AWS Linux to Ubuntu 24.04 Linux. We did this because there are more online tutorials for Ubuntu Linux than for AWS Linux, and because Ubuntu Linux is available on more platforms (e.g. Raspberry PI or [MacOS](https://dev.to/ryfazrin/how-to-run-ubuntu-on-macos-like-wsl-wsl-style-experience-4cd4)).
* We have a script [etc/install-e11](../etc/install-e11) that configures Ubuntu 24.04 for the class
* We created a new command, `e11`, for course VM management.
* We now use [`pipx`](https://pipx.pypa.io/latest/) to manage python commands in the CLI (including e11)
