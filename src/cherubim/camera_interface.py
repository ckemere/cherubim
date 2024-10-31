import setproctitle
import multiprocessing

def start_camera(config, display_queue, write_queue, stop_signal, write_queue_signal):
    multiprocessing.current_process().name = "python3 Camera Iface"
    setproctitle.setproctitle(multiprocessing.current_process().name)

    if config.get('Interface', 'WebCam') == 'GigE':
        try:
            from cherubim.gige_interface import GigECameraInterface as CameraInterface
        except ModuleNotFoundError:
            from gige_interface import GigECameraInterface as CameraInterface
    elif config.get('Interface', 'WebCam') == 'WebCam':
        try:
            from cherubim.opencv_interface import OpenCVCameraInterface as CameraInterface
        except ModuleNotFoundError:
            from opencv_interface import OpenCVCameraInterface as CameraInterface
    else:
        print('Unsupported Interface')

    camera = CameraInterface(config, display_queue=display_queue, 
                             stop_signal=stop_signal, 
                             write_queue=write_queue,
                             write_queue_signal=write_queue_signal)
    camera.run()
    print('Ended run')
    print('Done in camera exit.')

    return

