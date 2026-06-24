import sys
import os

# Tắt tự động ghi file log hailort.log của SDK để tối ưu bộ nhớ
os.environ["HAILORT_LOGGER_PATH"] = "NONE"

# Add the Newest_Version directory to system path to allow importing core modules
current_dir = os.path.dirname(os.path.abspath(__file__))
newest_version_dir = os.path.abspath(os.path.join(current_dir, "..", "Newest_Version"))
if newest_version_dir not in sys.path:
    sys.path.append(newest_version_dir)

# Add system-level dist-packages to allow importing system-level hailo and gi packages
sys_dist_packages = "/usr/lib/python3/dist-packages"
if os.path.exists(sys_dist_packages) and sys_dist_packages not in sys.path:
    sys.path.append(sys_dist_packages)

# PyQt/PySide fallback import block
try:
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QTimer, QObject
    from PyQt6.QtGui import QImage, QPixmap, QFont, QColor, QPainter, QPen, QBrush, QPainterPath
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QLabel, QPushButton,
        QLineEdit, QVBoxLayout, QHBoxLayout, QGridLayout, QTabWidget,
        QListWidget, QGroupBox, QMessageBox, QFrame, QScroller,
        QGraphicsDropShadowEffect
    )
    # PyQt6 Enum Compatibility Layer
    Qt.AlignCenter = Qt.AlignmentFlag.AlignCenter
    Qt.KeepAspectRatio = Qt.AspectRatioMode.KeepAspectRatio
    Qt.SmoothTransformation = Qt.TransformationMode.SmoothTransformation
    Qt.WaitCursor = Qt.CursorShape.WaitCursor
    QLineEdit.Password = QLineEdit.EchoMode.Password
    QImage.Format_RGB888 = QImage.Format.Format_RGB888
    QFont.Bold = QFont.Weight.Bold
    QScroller.LeftMouseButtonGesture = QScroller.ScrollerGestureType.LeftMouseButtonGesture
except ImportError:
    try:
        from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QTimer, QObject
        from PyQt5.QtGui import QImage, QPixmap, QFont, QColor, QPainter, QPen, QBrush, QPainterPath
        from PyQt5.QtWidgets import (
            QApplication, QMainWindow, QWidget, QLabel, QPushButton,
            QLineEdit, QVBoxLayout, QHBoxLayout, QGridLayout, QTabWidget,
            QListWidget, QGroupBox, QMessageBox, QFrame, QScroller,
            QGraphicsDropShadowEffect
        )
    except ImportError:
        try:
            from PySide2.QtCore import Qt, Signal as pyqtSignal, Slot as pyqtSlot, QTimer, QObject
            from PySide2.QtGui import QImage, QPixmap, QFont, QColor, QPainter, QPen, QBrush, QPainterPath
            from PySide2.QtWidgets import (
                QApplication, QMainWindow, QWidget, QLabel, QPushButton,
                QLineEdit, QVBoxLayout, QHBoxLayout, QGridLayout, QTabWidget,
                QListWidget, QGroupBox, QMessageBox, QFrame,
                QGraphicsDropShadowEffect
            )
            QScroller = None
        except ImportError:
            try:
                from PySide6.QtCore import Qt, Signal as pyqtSignal, Slot as pyqtSlot, QTimer, QObject
                from PySide6.QtGui import QImage, QPixmap, QFont, QColor, QPainter, QPen, QBrush, QPainterPath
                from PySide6.QtWidgets import (
                    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
                    QLineEdit, QVBoxLayout, QHBoxLayout, QGridLayout, QTabWidget,
                    QListWidget, QGroupBox, QMessageBox, QFrame,
                    QGraphicsDropShadowEffect
                )
                QScroller = None
            except ImportError:
                print("[ERROR] Please install PyQt6, PyQt5, PySide2, or PySide6 to run the interface monitor.")
                sys.exit(1)

# GPIO import fallback for Raspberry Pi deployment
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    GPIO = None

RELAY_PIN = 21  # Standard GPIO pin for access control relay on Raspberry Pi

# Initialize GPIO
if GPIO_AVAILABLE:
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(RELAY_PIN, GPIO.OUT)
        GPIO.output(RELAY_PIN, GPIO.LOW)  # LOCKED status
    except Exception as e:
        print(f"[GPIO] Warning: Failed to configure GPIO: {e}")
        GPIO_AVAILABLE = False
