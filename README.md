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

## Running

Run cherubim from the command line: `cherubim config_file.yaml`

To run cherubim, you need a config file. This specifies the information
needed to access the camera and selects resolution, frame rate, etc.

An example for a gigabit ethernet camera can be found in
`example_gige_config.yaml`. 

Here are the contents:
```
# Config file for LUCID PHX016S-CC
'Interface': 'GigE' # 'WebCam' to use a WebCam with the OpenCV interface
'CameraID': 'Lucid Vision Labs-PHX016S-C-221501060' # Find this out from arv-tool. 
          # If you don't specify a parameter, it will default to None, 
          # which will look for cameras and pick the first one. 
          # (For WebCam interface, we use integers starting from 0)
'Mode': 'Bayer_RG8' # Alternatively 'Mono8' works! For webcam, use 'RGB8'
'RecordVideo': True # Whether we should start recording immediately at startup
'Compress': True # Otherwise Raw!
'LogDirectory': '/home/me/Data' # If this is not specified, use the current directory
'Binning': 2 # Some (larger) sensors allow for combining the 
             # information across adjacent pixels. This is useful
             # to reduce bandwidth. We set the same value for X and Y.
'ResX': 720 # Horizontal resolution (Note that this is after binning, assumes a 1440 pixel wide sensor)
'ResY': 540 # Vertical resolution (This is after binning with a 1080 line sensor.)
'OffsetX': 0 # If the resolutions are not maxmium, the offset parameters 
             # enable locating the cropped image from the larger sensor field of view
'OffsetY': 0
'FrameRate': 30
'ExposureTime': 5000.0 # In us. Autoexposure can be dangerous because it may mess with
                       # automated data analysis pipelines. So you should specify
                       # it manually. Default is half of the frame period.
```

