import cv2
import time
try:
    from cherubim.generic_camera_interface import GenericCameraInterface
except ModuleNotFoundError:
    from generic_camera_interface import GenericCameraInterface

def check_camera(config):
    sy = config['ResY']
    sx = config['ResX']
    offset_x = config.get('OffsetX',0)
    offset_y = config.get('OffsetY',0)

    camera_index = config.get('CameraID', 0)

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


class OpenCVCameraInterface(GenericCameraInterface):
    def __init__(self, config, display_queue, write_queue, stop_signal, write_queue_signal):
        super().__init__(config, display_queue, write_queue, stop_signal, write_queue_signal)

        try:
            self._capture = cv2.VideoCapture(config.get('CameraID', 0))
        except:
            print ("No web camera found for index ", config.get('CameraID', 0))
            return None
        
        self.frame_rate = config['FrameRate']
        self._capture.set(cv2.CAP_PROP_FPS,self.frame_rate) 

        self.sy = config['ResY']
        self.sx = config['ResX']
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.sx)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.sy)
        # self.offset_x = config.get('OffsetX',0)
        # self.offset_y = config.get('OffsetY',0)        

        # NOTE THIS MAY NOT ACTUALLY BE WHAT WE GET!
        # NEED TO TEST PARAMETERS BEFORE STARTING INTERFACE

        self.frame = None

    def start_acquisition(self):
        print('Acquisiton')
        return

    def stop_acquisiton(self):
        self._capture.release()
        return
    
    def get_frame(self):
        ret, self.frame = self._capture.read() # blocking
        self.current_frame_data = cv2.cvtColor(self.frame, cv2.COLOR_BGR2RGB)
        self.current_frame_timestamp = time.monotonic()
        if not ret: #
            print('Error in OpenCV capture.')
            return False
        else:
            return True




