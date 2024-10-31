from multiprocessing.sharedctypes import Value
import os, setproctitle, time

# import skvideo.io # scikit-video
import simplejpeg

import multiprocessing
import queue
import csv

class VideoWriter():
    def __init__(self, config, frame_queue, done_signal, filename):
        self._done_signal = done_signal

        self._frame_queue = frame_queue

        log_directory = config.get('LogDirectory', os.getcwd())
        if not os.path.isdir(log_directory):
            raise(ValueError('VideoWriter LogDirectory [{}] not found.'.format(log_directory)))

        self.sx = config['ResX'] 
        self.sy = config['ResY']
        self.framerate = config.get('FrameRate', 30) # TODO: sync defaults across processes
        mode = config.get('Mode', 'Mono8') 
        quality = config.get('CompressionQuality', 85)
        self._compressed = None
        if config.get('Compress',True):
            self._compressed = True
            video_filename = os.path.join(log_directory, '{}.mjpeg'.format(filename))
            self._writer = open(video_filename, 'wb')
            if mode == 'Mono8':
                self.write = lambda img: self._writer.write(
                        simplejpeg.encode_jpeg(img, quality=quality,
                            colorspace='Gray', colorsubsampling='Gray'))
            elif mode == 'Bayer_RG8':
                self.write = lambda img: self._writer.write(
                        simplejpeg.encode_jpeg(img, quality=quality,
                        colorspace='BGR', colorsubsampling='444'))
            elif mode == 'RGB8':
                self.write = lambda img: self._writer.write(
                        simplejpeg.encode_jpeg(img, quality=quality,
                        colorspace='RGB', colorsubsampling='444'))
            else:
                raise ValueError('Unsupported video mode. ({})'.format(mode))

            # self._writer = skvideo.io.FFmpegWriter(video_filename, outputdict={
            #     #'-vcodec': 'libx264', '-b': '300000000'
            #     # '-vcodec': 'libx264', '-crf': '27', '-preset': 'veryfast'
            #     '-vcodec': 'mjpeg'
            # })
        else:
            self._compressed = False
            video_filename = os.path.join(log_directory, '{}.raw'.format(filename))
            self._writer = open(video_filename, 'wb')
            self.write = self._writer.write

        timestamps_filename = os.path.join(log_directory, '{}_timestamps.csv'.format(filename))
        self._ts_file = open(timestamps_filename, 'w')
        self._ts_writer = csv.writer(self._ts_file, delimiter=',')

    def run(self):
        t_write = 0
        print ("Writing")

        while True:
            queued_value = self._frame_queue.get(0.02)

            if queued_value is None: # our camera interface is finished
                print('Got a None in writer')
                break

            (img, timestamp) = queued_value
            self.write(img)
            self._ts_writer.writerow([timestamp, time.clock_gettime_ns(time.CLOCK_MONOTONIC)])
            # t_write = time.time() - t0

        self.close()

    def close(self):
        if (self._writer):
            self._writer.close()
            self._writer = None
        if (self._ts_file):
            self._ts_file.close()
            self._ts_file = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.close()
        self._done_signal = True
        print('Video writer exited')


def start_writer(config, frame_queue, done_flag, filename):
    multiprocessing.current_process().name = "python3 VideoWriter"
    setproctitle.setproctitle(multiprocessing.current_process().name)
    with VideoWriter(config, frame_queue, done_flag, filename) as vwriter:
        done_flag.value = False #  change our done state to False
        vwriter.run()
    done_flag.value = True
    return
