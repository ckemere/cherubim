import setproctitle
import multiprocessing
import queue
import numpy as np
import cv2
import time


def check_camera(config):
    sy = config['ResY']
    sx = config['ResX']
    offset_x = config.get('OffsetX',0)
    offset_y = config.get('OffsetY',0)

    camera_index = config.get('CameraIndex', 0)

    try:
        capture = cv2.VideoCapture(camera_index)
    except:
         print('Failure acquiring camera ', camera_index)
         return None

    capture.set(cv2.CAP_PROP_FRAME_WIDTH, sx)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, sy)

    # camera.set_region (offset_x,offset_y,sx,sy)

    frame_rate = config['FrameRate']
    capture.set(cv2.CAP_PROP_FPS,frame_rate) 
    # camera.set_exposure_time(0.95/frame_rate * 1e6) # max out exposure by default
    
    # mode = config.get('Mode', 'Mono8')
    # if mode not in ['Mono8', 'YUV422', 'Bayer_RG8']:
    #    raise ValueError('Unsupported video mode.')

    ret, frame = capture.read()

    capture.release()

    if ret:
        print('Successfully configured for ', frame.shape)
        return frame.shape
    else:
        print('Failed to capture')
        return None


def start_camera(config, display_queue, stop_signal):
    multiprocessing.current_process().name = "python3 Webcam Iface"
    setproctitle.setproctitle(multiprocessing.current_process().name)

    class CameraInterface():
        def __init__(self, config, stop_signal, display_queue, write_queue=None):
            self._display_queue = display_queue
            self._stop_signal = stop_signal

            try:
                self._capture = cv2.VideoCapture(config.get('CameraIndex', 0))
            except:
                print ("No web camera found for index ", config.get('CameraIndex', 0))
                return None
            
            self.sy = config['ResY']
            self.sx = config['ResX']
            self.offset_x = config.get('OffsetX',0)
            self.offset_y = config.get('OffsetY',0)

            self.frame_rate = config['FrameRate']
            
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.sx)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.sy)
            self._capture.set(cv2.CAP_PROP_FPS,self.frame_rate) 

            ret, frame = self._capture.read()
            if ret is None:
                print('Failure to acquire frames from camera.')
                return None

            self.sy = frame.shape[0]
            self.sx = frame.shape[1]

            self._rgb_img = np.zeros((self.sy, self.sx,3))  # converted image data is RGB
            self._conversion_required = True

            # print ("Camera vendor : %s" %(self._camera.get_vendor_name ()))
            # print ("Camera model  : %s" %(self._camera.get_model_name ()))
            # print ("ROI           : %dx%d at %d,%d" %(width, height, x, y))
            # print ("Payload       : %d" %(payload))
            # print ("Pixel format  : %s" %(self._camera.get_pixel_format_as_string ()))

        def run(self):
            print ("Acquisition")

            while not self._stop_signal.value:
                ret, frame = self._capture.read()

                if self._stop_signal.value:
                    break

                if ret is None:
                    print('Error in capture. Returned None.')
                    break
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # self._display_queue.put((self._rgb_img, image.get_system_timestamp())) # could be block=False, but then need to wrap with a try/except queue.Full: /continue
                try:
                    self._display_queue.put((frame, time.monotonic()), block=False)
                except queue.Full:
                    print('full')
                    continue

            self._capture.release()
            self._display_queue.put(None) # Sentinel that we're done!
            print ("Stopped acquisition")


    camera = CameraInterface(config, display_queue=display_queue, stop_signal=stop_signal)
    camera.run()
    print('Ended run')
    print('Done in camera exit.')


    return

