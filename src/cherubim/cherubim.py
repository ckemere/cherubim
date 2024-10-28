#!/usr/bin/env python

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QWidget, QLabel, \
  QPushButton, QVBoxLayout, QHBoxLayout, QSizePolicy, QFrame

import multiprocessing.queues
import numpy as np

import setproctitle
import multiprocessing
import queue
import numpy as np

import sys
import shutil
import os.path

# https://stackoverflow.com/questions/72188903/pyside6-how-do-i-resize-a-qlabel-without-loosing-the-size-aspect-ratio
class ScaledLabel(QLabel):
    def __init__(self, *args, **kwargs):
        QLabel.__init__(self)
        self._pixmap = self.pixmap()
    
    def resizeEvent(self, event):
        self.setPixmap(self._pixmap)

    def setPixmap(self, pixmap): #overiding setPixmap
        if not pixmap:return 
        self._pixmap = pixmap
        return QLabel.setPixmap(self,self._pixmap.scaled(
                self.frameSize(),
                Qt.KeepAspectRatio))

class MainApp(QWidget):

    def __init__(self, config):
        QWidget.__init__(self)
        self.video_size = QSize(config.get('ResX'), config.get('ResY'))
        self._recording_directory = os.path.dirname(__file__)
        total, used, free = shutil.disk_usage(self._recording_directory)
        print(self._recording_directory, free/(1024 **3))

        self.setup_ui()
        self.setGeometry(0, 0, 640, 480)
        self.setup_camera(config)

    def update_free_space(self):
        total, used, free = shutil.disk_usage(self._recording_directory)
        self.disk_space_label.setText("Free: {:7.2f}G".format(free/(1024**3)))

    def setup_ui(self):
        """Initialize widgets.
        """
        self.image_label = ScaledLabel()
        self.image_label.setSizePolicy( QSizePolicy.Ignored, QSizePolicy.Ignored )
        # self.image_label.setScaledContents(True)

        # Top Row
        self.record_button = QPushButton("⏺ REC")
        self.filename_label = QLabel("{}".format(self._recording_directory))
        self.disk_space_label = QLabel("Diskspace")
        self.quit_button = QPushButton("Quit")
        self.quit_button.clicked.connect(self.close)
        self.top_row_layout = QHBoxLayout()
        self.top_row_layout.addWidget(self.record_button)
        self.top_row_layout.addWidget(self.filename_label)
        self.top_row_layout.addWidget(self.disk_space_label)
        self.update_free_space()
        self.disk_space_timer = QTimer()
        self.disk_space_timer.timeout.connect(self.update_free_space)
        self.disk_space_timer.start(1000)


        self.top_row_layout.addWidget(self.quit_button)

        self.main_layout = QVBoxLayout()
        self.main_layout.addLayout(self.top_row_layout)
        self.main_layout.addWidget(self.image_label)
        self.main_layout.setSpacing(5)
        self.main_layout.setContentsMargins(5,5,5,5)
        self.top_row_layout.setSpacing(5)


        self.setLayout(self.main_layout)
        # self.setFrameShape(QFrame.NoFrame)

        self.interface_style = None


    def setup_camera(self, config):
        """Initialize camera.
        """
        self.display_queue = multiprocessing.Queue()
        self.stop_signal = multiprocessing.Value('b', False)

        self.interface_style = config.get('Interface', 'WebCam')
        if self.interface_style == 'GigE':
            from gige_interface import start_camera
        elif self.interface_style == 'WebCam':
            from opencv_interface import start_camera
        else:
            print('Unsupported Interface')

        self.camera_process = multiprocessing.Process(target=start_camera, 
            args=(config, self.display_queue, self.stop_signal))
        self.camera_process.start()

        print('Started Camera Process.')

        self.video_timer = QTimer()
        self.video_timer.timeout.connect(self.display_video_stream)
        self.video_timer.start(10)


    def display_video_stream(self):
        """Read frame from camera and repaint QLabel widget.
        """
        queued_data_recevied = False
        while True: # always drain queue
            try:
                queued_data = self.display_queue.get(block=False) #(block=True, timeout=0.1)
                queued_data_recevied = True
            except queue.Empty:
                break

        # 3 options here - (1) we got some data, (2) we got a None, or (3) we got no data
        if not queued_data_recevied:
            return
        
        if queued_data is None: # If we pushed a None onto the queue, that means the camera process has finished
            self.close()
            return

        (img, timestamp) = queued_data
        image = QImage(img, img.shape[1], img.shape[0], 
                       img.strides[0], QImage.Format_RGB888)
        self.image_label.setPixmap(QPixmap.fromImage(image))

    def closeEvent(self, event):
        print('Setting stop signal')
        self.stop_signal.value = True
        while True:
            queued_data = self.display_queue.get(block=True)
            if queued_data is None:
                break
        
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    config = {
        'Interface': 'GigE',
        'RecordVideo': True,
        'Mode': 'Bayer_RG8',
        'FilenameHeader': 'videodata',
        'Compress': False,
        # 'LogDirectory': os.getcwd(),
        'CameraIndex': 0,
        'Binning': 2, 
        'ResX': 720, 'ResY': 540, 'FrameRate': 15,
        'CameraParams': {
            'Power Line frequency': 2, # 60 Hz
            'Gain': 10
        }

    }

    interface_style = config.get('Interface', 'WebCam')
    if interface_style == 'GigE':
        from gige_interface import check_camera
        pass
    elif interface_style == 'WebCam':
        from opencv_interface import check_camera
        retval = check_camera(config)
        if retval:
            frame_width, frame_height = retval[1], retval[0]
            print(frame_width, frame_height)
            config['ResX'] = frame_width
            config['ResY'] = frame_height
        else:
            print('Looking for a camera but no web camera found.')
            sys.exit(app.exec())
    else:
        print('Unsupported Interface')    
        sys.exit(app.exec())

    win = MainApp(config)
    win.show()
    sys.exit(app.exec())
