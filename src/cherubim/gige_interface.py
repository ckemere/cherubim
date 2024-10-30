import setproctitle
import multiprocessing
import queue
import numpy as np
import cv2
import time


def check_camera(config):  
    import gi
    gi.require_version ('Aravis', '0.8')
    from gi.repository import Aravis

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


def start_camera(config, display_queue, write_queue, stop_signal, write_queue_signal):
    multiprocessing.current_process().name = "python3 GigE Iface"
    setproctitle.setproctitle(multiprocessing.current_process().name)

    import gi
    gi.require_version ('Aravis', '0.8')
    from gi.repository import Aravis

    class CameraInterface():
        def __init__(self, config, display_queue, write_queue, stop_signal, write_queue_signal):
            self._display_queue = display_queue
            self._write_queue = write_queue
            self._stop_signal = stop_signal
            self._write_queue_signal = write_queue_signal

            try:
                self._camera = Aravis.Camera.new (config.get('CameraID', None))
            except:
                print ("No camera found")
                exit ()

            self.sy = config['ResY']
            self.sx = config['ResX']
            self.offset_x = config.get('OffsetX',0)
            self.offset_y = config.get('OffsetY',0)

            self.binning = config.get('Binning', 1)

            self.frame_rate = config['FrameRate']

            self._camera.set_binning(self.binning, self.binning)
            self._camera.set_region (self.offset_x,self.offset_y,self.sx,self.sy)
            self._camera.set_frame_rate (self.frame_rate)
            self._camera.set_exposure_time_auto(False)
            self._camera.set_exposure_time(
                config.get('ExposureTime', 0.5/self.frame_rate * 1e6) # default 50% of frame rate
            )
            
            self.mode = config.get('Mode', 'Bayer_RG8')
            if self.mode not in ['Mono8', 'YUV422', 'Bayer_RG8']:
                raise ValueError('Unsupported video mode.')

            if self.mode == 'Mono8':
                self._camera.set_pixel_format (Aravis.PIXEL_FORMAT_MONO_8)
                self._bytes_per_pixel = 1
            elif self.mode == 'YUV422':
                self._camera.set_pixel_format (Aravis.PIXEL_FORMAT_YUV_422_PACKED)
                self._bytes_per_pixel = 2
            elif self.mode == 'Bayer_RG8':
                self._camera.set_pixel_format (Aravis.PIXEL_FORMAT_BAYER_RG_8)
                self._bytes_per_pixel = 1
            else:
                raise ValueError('Unsupported video mode.')


            print('Initial packet size: ', self._camera.gv_get_packet_size())
            self._camera.gv_set_packet_size(9000) # Assumes we have set the MTU on the GigE Interface
            # self._camera.gv_auto_packet_size() # This will set packet size to max. Very important
            print('After autoset packet size: ', self._camera.gv_get_packet_size())

            [x,y,width,height] = self._camera.get_region ()

            # Initialize two numpy buffers for deBayer'ing
            self._rgb_img = np.zeros((height, width,3))  # converted image data is RGB

            payload = self._camera.get_payload ()

            print ("Camera vendor : %s" %(self._camera.get_vendor_name ()))
            print ("Camera model  : %s" %(self._camera.get_model_name ()))
            print ("Camera device  : %s" %(self._camera.get_device_id ()))
            print ("ROI           : %dx%d at %d,%d" %(width, height, x, y))
            print ("Payload       : %d" %(payload))
            print ("Pixel format  : %s" %(self._camera.get_pixel_format_as_string ()))

            self._stream = self._camera.create_stream (None, None)

            for i in range(0,50): # Is 50 enough?
                self._stream.push_buffer (Aravis.Buffer.new_allocate (payload))

            self._write_queue_is_active = False

        def convert(self, img):
            if self.mode == 'Mono8': # no need!
                self._rgb_img = np.frombuffer(img, np.uint8).reshape(self.sy, self.sx,1) # this is a cast!
            elif self.mode == 'Bayer_RG8':
                img_np = np.frombuffer(img, np.uint8).reshape(self.sy, self.sx) # this is a cast
                self._rgb_img = cv2.cvtColor(img_np, cv2.COLOR_BayerRG2BGR)

        def run(self):
            self._camera.start_acquisition ()
            print ("Acquisition")

            while not self._stop_signal.value:
                image = None
                while image is None and not self._stop_signal.value:
                    image = self._stream.timeout_pop_buffer (500) # timeout is us

                if self._stop_signal.value:
                    break

                if image:
                    if (image.get_status() != Aravis.BufferStatus.SUCCESS):
                        print(image.get_status())
                        continue

                    self.convert(image.get_data())

                    if self._write_queue_signal.value:
                        self._write_queue.put((self._rgb_img, image.get_system_timestamp())) # needs to block because we want every frame saved!
                        self._write_queue_is_active = True
                    elif self._write_queue_is_active: # We've recently toggled recording off
                        self._write_queue.put(None)
                        self._write_queue_is_active = False

                    try:
                        self._display_queue.put(
                            (self._rgb_img, image.get_system_timestamp()), 
                            block=False) # doesn't need to block because we don't care about dropping frames
                    except queue.Full:
                        continue
                        
                    self._stream.push_buffer (image)

            self._camera.stop_acquisition ()
            self._camera = None
            if self._write_queue_is_active:
                self._write_queue.put(None) # Sentinel that we're done!
                print('Pushed a None onto write queue')

            self._display_queue.put(None) # Sentinel that we're done!

            print ("Stopped acquisition")

        # def close(self):
        #     if self._camera:
        #         self._camera.stop_acquisition ()


    camera = CameraInterface(config, display_queue=display_queue, 
                             stop_signal=stop_signal, 
                             write_queue=write_queue,
                             write_queue_signal=write_queue_signal)
    camera.run()
    print('Ended run')
    print('Done in camera exit.')


    return

