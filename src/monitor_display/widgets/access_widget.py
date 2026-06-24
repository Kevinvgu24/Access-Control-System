import sys
import os

# Resolve imports path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from qt_imports import QWidget, QLabel, QPushButton, QVBoxLayout, pyqtSignal, Qt

class AccessWidget(QWidget):
    manual_unlock_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(20)

        # Title
        lbl_section = QLabel("Scan Verification")
        lbl_section.setStyleSheet("color: #ea580c; font-size: 18px; font-weight: bold;")
        lbl_section.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_section)

        # Status alert box
        self.lblScanStatus = QLabel("SCANNING...")
        self.lblScanStatus.setAlignment(Qt.AlignCenter)
        self.lblScanStatus.setWordWrap(True)
        self.lblScanStatus.setStyleSheet("""
            color: #64748b;
            font-size: 24px;
            font-weight: bold;
            padding: 20px;
            background-color: #f8fafc;
            border-radius: 8px;
            border: 1px solid #cbd5e1;
        """)
        layout.addWidget(self.lblScanStatus)

        # Details label
        self.lblScanDetails = QLabel("Please align your face to the camera.")
        self.lblScanDetails.setAlignment(Qt.AlignCenter)
        self.lblScanDetails.setWordWrap(True)
        self.lblScanDetails.setStyleSheet("color: #475569; font-size: 14px;")
        layout.addWidget(self.lblScanDetails)

        layout.addStretch()

        # Touch manual unlock button
        self.btnManualUnlock = QPushButton("🔓 TOUCH TO UNLOCK")
        self.btnManualUnlock.setMinimumHeight(65)
        self.btnManualUnlock.setStyleSheet("""
            QPushButton {
                background-color: #ea580c;
                color: white;
                font-weight: bold;
                font-size: 18px;
                border-radius: 8px;
                border: none;
            }
            QPushButton:pressed {
                background-color: #c2410c;
            }
        """)
        self.btnManualUnlock.clicked.connect(self.manual_unlock_requested.emit)
        layout.addWidget(self.btnManualUnlock)
