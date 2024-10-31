import numpy as np
import cv2

try:
    from cherubim.generic_camera_interface import GenericCameraInterface
except ModuleNotFoundError:
    from generic_camera_interface import GenericCameraInterface

import gi
gi.require_version ('Aravis', '0.8')
from gi.repository import Aravis


def checkcamera(config):  
    camera = Aravis.Camera.new (None)

    sy = config['ResY']
    sx = config['ResX']
    offset_x = config.get('OffsetX',0)
    offset_y = config.get('OffsetY',0)

    frame_rate = config['FrameRate']

    camera.set_region (offset_x,offset_y,sx,sy)
    camera.set_frame_rate (frame_rate)
    camera.set_exposure_time(0.95/frame_rate * 1e6) # max out exposure by default
    
    mode = config.get('Mode', 'Mono8')
    if mode not in ['Mono8', 'YUV422', 'Bayer_RG8']:
       raise ValueError('Unsupported video mode.')

    if mode == 'Mono8':
        camera.set_pixel_format (Aravis.PIXEL_FORMAT_MONO_8)
    elif mode == 'Bayer_RG8':
        camera.set_pixel_format (Aravis.PIXEL_FORMAT_BAYER_RG_8)
    else:
        raise ValueError('Unsupported video mode.')

    payload = camera.get_payload ()

    [x,y,width,height] = camera.get_region ()

    camera.stop_acquisition ()
    del camera

    print('Successfully configured for ', width, height)

    return (width, height)


class OpenCVCameraInterface(GenericCameraInterface):
    def __init__(self, config, display_queue, write_queue, stop_signal, write_queue_signal):
        super().__init__(config, display_queue, write_queue, stop_signal, write_queue_signal)

        try:
            self.camera = Aravis.Camera.new (config.get('CameraID', None))
        except:
            print ("No camera found")
            exit ()

        self.sy = config['ResY']
        self.sx = config['ResX']
        self.offset_x = config.get('OffsetX',0)
        self.offset_y = config.get('OffsetY',0)

        self.binning = config.get('Binning', 1)

        self.frame_rate = config['FrameRate']

        self.camera.set_binning(self.binning, self.binning)
        self.camera.set_region (self.offset_x,self.offset_y,self.sx,self.sy)
        self.camera.set_frame_rate (self.frame_rate)
        self.camera.set_exposure_time_auto(False)
        self.camera.set_exposure_time(
            config.get('ExposureTime', 0.5/self.frame_rate * 1e6) # default 50% of frame rate
        )
        
        self.mode = config.get('Mode', 'Bayer_RG8')
        if self.mode not in ['Mono8', 'YUV422', 'Bayer_RG8']:
            raise ValueError('Unsupported video mode.')

        if self.mode == 'Mono8':
            self.camera.set_pixel_format (Aravis.PIXEL_FORMAT_MONO_8)
            self._bytes_per_pixel = 1
        elif self.mode == 'YUV422': # TODO: Support this!!!
            self.camera.set_pixel_format (Aravis.PIXEL_FORMAT_YUV_422_PACKED)
            self._bytes_per_pixel = 2
        elif self.mode == 'Bayer_RG8':
            self.camera.set_pixel_format (Aravis.PIXEL_FORMAT_BAYER_RG_8)
            self._bytes_per_pixel = 1
        else:
            raise ValueError('Unsupported video mode.')

        self.camera.gv_set_packet_size(9000) # Assumes we have set the MTU on the GigE Interface
        # self.camera.gv_auto_packet_size() # This will set packet size to max. Very important

        [x,y,width,height] = self.camera.get_region ()

        # Initialize numpy buffer for deBayer'ing
        # self.rgb_img = np.zeros((height, width,3))  # converted image data is RGB
        self.frame = None # will be for data from camera

        payload = self.camera.get_payload ()

        print ("Camera vendor : %s" %(self.camera.get_vendor_name ()))
        print ("Camera model  : %s" %(self.camera.get_model_name ()))
        print ("Camera device  : %s" %(self.camera.get_device_id ()))
        print ("ROI           : %dx%d at %d,%d" %(width, height, x, y))
        print ("Payload       : %d" %(payload))
        print ("Pixel format  : %s" %(self.camera.get_pixel_format_as_string ()))

        self._stream = self.camera.create_stream (None, None)

        for i in range(0,50): # Is 50 enough?
            self._stream.push_buffer (Aravis.Buffer.new_allocate (payload))

        self.image_buffer = None
        

    def start_acquisition(self):
        print('Acquisiton')
        return

    def stop_acquisiton(self):
        self.camera.stop_acquisition ()
        self.camera = None
        return
    
    def get_frame(self):
        self.image_buffer = None
        while not self._stop_signal.value:
            self.image_buffer = self._stream.timeout_pop_buffer (500) # timeout is us
            if self.image_buffer:
                if (self.image_buffer.get_status() != Aravis.BufferStatus.SUCCESS):
                    print(self.image_buffer.get_status())
                    continue # If we get a frame error, we'll print out and keep going
                else:
                    break

        if self._stop_signal.value:
            return False
        else:
            self.frame = self.image_buffer.get_data()
            self.current_frame_timestamp = self.image_buffer.get_system_timestamp()

            # De-Bayer / convert as needed
            if self.mode == 'Mono8': # no need!
                self.current_frame_data = np.frombuffer(self.frame, np.uint8).reshape(self.sy, self.sx,1) # this is a cast!
            elif self.mode == 'Bayer_RG8':
                img_np = np.frombuffer(self.frame, np.uint8).reshape(self.sy, self.sx) # this is a cast
                self.current_frame_data = cv2.cvtColor(img_np, cv2.COLOR_BayerRG2BGR)

            return True

    def post_queue(self):
        self._stream.push_buffer(self.image_buffer)
        return



