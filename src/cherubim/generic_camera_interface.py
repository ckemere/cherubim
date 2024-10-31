import queue

class GenericCameraInterface():
    def __init__(self, config, display_queue, write_queue, stop_signal, write_queue_signal):
        self._display_queue = display_queue
        self._write_queue = write_queue
        self._stop_signal = stop_signal
        self._write_queue_signal = write_queue_signal
        self._write_queue_is_active = False

        self.current_frame_data = None
        self.current_frame_timestamp = None

    def start_acquisition(self):
        print('Acquisiton')

    def stop_acquisition(self):
        return

    def get_frame(self):
        return False # Should return true if frame is captured into self.frame or false
    
    def post_queue(self):
        return

    def run(self):
        self.start_acquisition()

        while not self._stop_signal.value:
            capture_success = self.get_frame() # This should get an convert a video frame

            if not capture_success  or self._stop_signal.value:
                break

            if self._write_queue_signal.value:
                self._write_queue.put((self.current_frame_data, 
                                       self.current_frame_timestamp)) # needs to block because we want every frame saved!
                self._write_queue_is_active = True
            elif self._write_queue_is_active: # We've recently toggled recording off
                self._write_queue.put(None)
                self._write_queue_is_active = False

            try:
                self._display_queue.put((self.current_frame_data, 
                                         self.current_frame_timestamp),
                                         block=False) # doesn't need to block because we don't care about dropping frames
            except queue.Full:
                continue
                
            self.post_queue() # This might, for example allow for a buffer to be reallocated

        self.stop_acquisition()

        if self._write_queue_is_active:
            self._write_queue.put(None) # Sentinel that we're done!
            print('Pushed a None onto write queue')

        self._display_queue.put(None) # Sentinel that we're done!

        print ("Stopped acquisition")

