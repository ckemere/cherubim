#!/usr/bin/env python3

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QWidget, QLabel, \
  QPushButton, QVBoxLayout, QHBoxLayout, QSizePolicy, QStatusBar

import multiprocessing.queues
import numpy as np

import setproctitle
import multiprocessing
import queue
import numpy as np

import sys
import shutil
import os.path

import datetime

import yaml

from videowriter import start_writer


# https://stackoverflow.com/questions/72188903/pyside6-how-do-i-resize-a-qlabel-without-loosing-the-size-aspect-ratio
class ScaledLabel(QLabel):
    def __init__(self, *args, **kwargs):
        QLabel.__init__(self)
        self._pixmap = self.pixmap()
    
    def resizeEvent(self, event):
        self.setPixmap(self._pixmap)
        print(self.frameSize())

    def setPixmap(self, pixmap): #overiding setPixmap
        if not pixmap:return 
        self._pixmap = pixmap
        # return QLabel.setPixmap(self,self._pixmap)
        return QLabel.setPixmap(self,self._pixmap.scaled(
            self.frameSize(),
            Qt.KeepAspectRatio))


class MainApp(QWidget):

    def __init__(self, config):
        QWidget.__init__(self)
        self.video_size = QSize(config.get('ResX'), config.get('ResY'))

        # Initialization related to file saving
        self.recording_directory = config.get('LogDirectory', os.getcwd())
        if not os.path.isdir(self.recording_directory):
            raise(ValueError('VideoWriter LogDirectory [{}] not found.'.format(self.recording_directory)))
        self.filename_header = config.get('FilenameHeader', None)
        self.writer_filename = None
        self.recording_active = False
    
        # stuff specifically to help with quitting
        self.display_queue_empty = False # This only is set when quitting
        self.writer_finalizing_counter = 0

        self.setup_ui()
        self.setGeometry(0, 0, 640, 480)
        self.setup_camera(config)

    def update_free_space(self):
        total, used, free = shutil.disk_usage(self.recording_directory)
        self.disk_space_label.setText("Free: {:7.2f}G".format(free/(1024**3)))

        if self.recording_active:
            self.filename_label.setText("{}".format(self.recording_directory))
            self.filename_label.setStyleSheet("QLabel { background-color : pink; color : blue; }");
        else:
            self.filename_label.setText("{}".format(self.recording_directory))
            self.filename_label.setStyleSheet("QLabel { background-color : white; color : black; }");


    def setup_ui(self):
        """Initialize widgets.
        """
        self.image_label = ScaledLabel()
        self.image_label.setSizePolicy( QSizePolicy.Ignored, QSizePolicy.Ignored )
        # self.image_label.setScaledContents(True)

        # Top Row
        self.record_button = QPushButton("⏺ REC")
        self.record_button.setSizePolicy( QSizePolicy.Fixed, QSizePolicy.Fixed )
        self.record_button.setCheckable(True)  # Make the button checkable
        self.record_button.clicked.connect(self.handle_record_button)

        self.filename_label = QLabel("{}".format(self.recording_directory))
        self.disk_space_label = QLabel("") # This will show available disk space
        self.update_free_space()
        self.disk_space_timer = QTimer()
        self.disk_space_timer.timeout.connect(self.update_free_space)
        self.disk_space_timer.start(1000) # Update disk space every second

        # self.quit_button = QPushButton("Quit")
        # self.quit_button.clicked.connect(self.close)

        self.top_row_layout = QHBoxLayout()
        self.top_row_layout.addWidget(self.record_button)
        self.top_row_layout.addWidget(self.filename_label)
        self.top_row_layout.addWidget(self.disk_space_label)
        # self.top_row_layout.addWidget(self.quit_button)

        self.main_layout = QVBoxLayout()
        self.main_layout.addLayout(self.top_row_layout, stretch=0)
        self.main_layout.addWidget(self.image_label, stretch=1)

        self.status_bar = QStatusBar()
        self.main_layout.addWidget(self.status_bar, stretch=0)

        self.main_layout.setSpacing(5)
        self.main_layout.setContentsMargins(5,5,5,5)
        self.top_row_layout.setSpacing(5)

        self.setLayout(self.main_layout)
        # self.setFrameShape(QFrame.NoFrame)


    def setup_camera(self, config):
        """Initialize camera.
        """
        self.display_queue = multiprocessing.Queue()
        self.writer_queue = multiprocessing.Queue()
        self.acqusition_stop_signal = multiprocessing.Value('b', False)
        self.writer_stop_signal = multiprocessing.Value('b', False)
        self.writer_done_signal = multiprocessing.Value('b', False)
        self.writer_queue_active_signal = multiprocessing.Value('b', False)

        self.recording_active = False

        self.interface_style = config.get('Interface', 'WebCam')
        if self.interface_style == 'GigE':
            from gige_interface import start_camera
        elif self.interface_style == 'WebCam':
            from opencv_interface import start_camera
        else:
            print('Unsupported Interface')

        self.camera_process = multiprocessing.Process(target=start_camera, 
            args=(config, self.display_queue, self.writer_queue, 
                    self.acqusition_stop_signal, self.writer_queue_active_signal))
        self.camera_process.start()

        self.writer_process = None

        if config['RecordVideo']:
            self.record_button.click()
                
        self.video_timer = QTimer()
        self.video_timer.timeout.connect(self.display_video_stream)
        self.video_timer.start(10)


    def handle_record_button(self):
        if self.recording_active: # stop writing
            self.writer_queue_active_signal.value = False # triggers end of write by sending None on queue
            self.writer_finalizing_counter += 1
            self.status_bar.showMessage("Finalizing writing." + '.' * (self.writer_finalizing_counter % 5))
            if not self.writer_done_signal.value: 
                QTimer.singleShot(10, self.handle_record_button) # Come back to this close event again in a 10 ms!
                return
            else:
                self.writer_process.join()
                self.recording_active = False
                self.writer_finalizing_counter = 0
                self.status_bar.showMessage("Stopped recording.")
                self.record_button.setText("⏺ REC")


        else:
            self.start_record()
            self.status_bar.showMessage("Recording to {}.".format(self.writer_filename))
            self.record_button.setText("⏸︎ STOP")


    def start_record(self):
        self.writer_done_signal.value = False
        now = datetime.datetime.now()
        if self.filename_header is None:
            self.writer_filename = 'ExperimentVideo_{}'.format(now.strftime("%Y-%m-%d_%H%M"))
        else:
            self.writer_filename = '{}_{}'.format(self.filename_header, now.strftime("%Y-%m-%d_%H%M"))

        self.writer_process = multiprocessing.Process(target=start_writer,
            args=(config, self.writer_queue, self.writer_done_signal, self.writer_filename))
        self.writer_process.start()
        self.writer_queue_active_signal.value = True
        self.recording_active = True


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
            self.display_queue_empty = True
            return

        (img, timestamp) = queued_data
        image = QImage(img, img.shape[1], img.shape[0], 
                       img.strides[0], QImage.Format_RGB888)
        self.image_label.setPixmap(QPixmap.fromImage(image))

    def closeEvent(self, event):
        self.acqusition_stop_signal.value = True # This should trigger a None, causing writer to exit
        if self.recording_active:  # stop writing
            self.writer_finalizing_counter += 1
            self.status_bar.showMessage("Finalizing writing." + '.' * (self.writer_finalizing_counter % 5))
            if not self.writer_done_signal.value: 
                QTimer.singleShot(10, self.close) # Come back to this close event again in a 10 ms!
                event.ignore()
                return
            else:
                self.writer_process.join()
                self.recording_active = False

        if not self.display_queue_empty:
            while True:
                queued_data = self.display_queue.get(block=True) #(block=True, timeout=0.1)
                if queued_data is None:
                    print('Cleared display queue to None')
                    break

        if self.camera_process is not None:
            self.camera_process.join()
        
        event.accept()


def read_config_file(file_path):
    with open(file_path, 'r') as file:
        try:
            data = yaml.safe_load(file)
            return data
        except yaml.YAMLError as e:
            print(f"Error reading YAML file: {e}")
            return None

if __name__ == "__main__":
    app = QApplication(sys.argv)

    default_config = {
        'CameraIndex': 0,
        'Interface': 'GigE', # 'WebCam'
        'Mode': 'Bayer_RG8', # For webcam, use 'RGB8'
        'RecordVideo': True,
        'Compress': True, # Otherwise Raw!
        'LogDirectory': os.getcwd(),
        'Binning': 2, 
        'ResX': 720, 'ResY': 540, # This is after binning!
        'OffsetX': 0,
        'OffsetY': 0,
        'FrameRate': 15,
        'ExposureTime': 1000.0, # In us
    }


    if len(sys.argv) >= 2:
        config = read_config_file(sys.argv[1])
        if config is None:
            sys.exit(1)
    else:            
        print('Using default config: ')
        for key, value in default_config.items():
            print(key, ":", value)
        config = default_config



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
