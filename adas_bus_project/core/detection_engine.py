import cv2

class DetectionEngine:
    """Manage video capture and prepare frames for display."""

    def __init__(self, source=None):
        self.capture = None
        self.source = source
        self.width = 1280
        self.height = 720
        self.open_source(source)

    def open_source(self, source):
        if self.capture is not None:
            self.capture.release()
            self.capture = None
        if source:
            self.capture = cv2.VideoCapture(source)
        else:
            self.capture = None

    def read_frame(self):
        if self.capture is None:
            return None
        success, frame = self.capture.read()
        if not success:
            return None
        frame = cv2.resize(frame, (self.width, self.height))
        return frame

    def release(self):
        if self.capture is not None:
            self.capture.release()
            self.capture = None
