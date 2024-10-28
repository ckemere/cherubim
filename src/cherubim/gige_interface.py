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


def start_camera(config, display_queue, stop_signal):
    multiprocessing.current_process().name = "python3 GigE Iface"
    setproctitle.setproctitle(multiprocessing.current_process().name)

    import gi
    gi.require_version ('Aravis', '0.8')
    from gi.repository import Aravis

    class CameraInterface():
        def __init__(self, config, stop_signal, display_queue, write_queue=None):
            self._display_queue = display_queue
            self._stop_signal = stop_signal

            try:
                self._camera = Aravis.Camera.new (None)
            except:
                print ("No camera found")
                exit ()

            self.sy = config['ResY']
            self.sx = config['ResX']
            self.offset_x = config.get('OffsetX',0)
            self.offset_y = config.get('OffsetY',0)

            self.frame_rate = config['FrameRate']

            self._camera.set_region (self.offset_x,self.offset_y,self.sx,self.sy)
            self._camera.set_frame_rate (self.frame_rate)
            self._camera.set_exposure_time(0.95/self.frame_rate * 1e6) # max out exposure by default
            
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
            payload = self._camera.get_payload ()

            [x,y,width,height] = self._camera.get_region ()

            # Initialize two numpy buffers for deBayer'ing
            self._rgb_img = np.zeros((height, width,3))  # converted image data is RGB
            self._conversion_required = False

            self._conversion_required = True # TODO: revisit

            print ("Camera vendor : %s" %(self._camera.get_vendor_name ()))
            print ("Camera model  : %s" %(self._camera.get_model_name ()))
            print ("ROI           : %dx%d at %d,%d" %(width, height, x, y))
            print ("Payload       : %d" %(payload))
            print ("Pixel format  : %s" %(self._camera.get_pixel_format_as_string ()))

            self._stream = self._camera.create_stream (None, None)

            for i in range(0,50): # Is 50 enough?
                self._stream.push_buffer (Aravis.Buffer.new_allocate (payload))

        def debayer(self, img):
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
                    image = self._stream.try_pop_buffer ()

                if self._stop_signal.value:
                    break

                if image:
                    if (image.get_status() != Aravis.BufferStatus.SUCCESS):
                        continue
                    if self._conversion_required:
                        self.debayer(image.get_data())
                        # self._display_queue.put((self._rgb_img, image.get_system_timestamp())) # could be block=False, but then need to wrap with a try/except queue.Full: /continue
                        try:
                            self._display_queue.put(
                                (self._rgb_img, image.get_system_timestamp()), 
                                block=False)
                        except queue.Full:
                            continue

                    self._stream.push_buffer (image)

            self._camera.stop_acquisition ()
            self._camera = None
            self._display_queue.put(None) # Sentinel that we're done!
            print ("Stopped acquisition")

        # def close(self):
        #     if self._camera:
        #         self._camera.stop_acquisition ()


    camera = CameraInterface(config, display_queue=display_queue, stop_signal=stop_signal)
    camera.run()
    print('Ended run')
    print('Done in camera exit.')


    return

