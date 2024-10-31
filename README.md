# cherubim

Simple Python based video recorder. Eventual goal is synchronized multi-camera acquisition. GUI composed using the PySide6 variant of the QT libraries.

## Installing
After cloning the repo, you should be able to `pip install -e .` from the root directory. 

## Python dependencies
+ `pyside6`
+ `numpy`
+ `setproctitle`
+ `pyyaml`
+ `simplejpeg`
+ `pygobject` (this is really only needed for GigE, but it's a lightweight dependency)

## Extra packages for gigabit ethernet cameras
Cherubim uses the Aravis library for gigabit ethernet cameras. Thus, Aravis must be
installed in order for these cameras to work. Aravis uses the GObject framework to
expose cameras and their functionality, including to Python.

+ In Debian variants like Ubuntu, you should be able to `sudo apt install gir1.2-aravis-0.8`.

+ On MacOS, you'll need to `brew install aravis gobject-introspection`

+ Aravis can be compiled from source on Windows, but perhaps there there is a prepackaged version? [TODO]
