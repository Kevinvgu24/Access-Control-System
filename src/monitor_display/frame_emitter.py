from qt_imports import QObject, pyqtSignal
import numpy as np

class FrameEmitter(QObject):
    """Thread-safe signal emitter to forward GStreamer frame buffers and recognition events to the Qt UI thread."""
    new_frame = pyqtSignal(np.ndarray)
    recognition_event = pyqtSignal(list)
