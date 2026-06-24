import sys
import os

# Resolve imports path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from qt_imports import QWidget, QListWidget, QPushButton, QVBoxLayout, pyqtSignal, QScroller

class LogsWidget(QWidget):
    sync_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # Log ledger
        self.listLogs = QListWidget()
        self.listLogs.setStyleSheet("""
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                color: #334155;
                border-radius: 8px;
                padding: 5px;
                font-family: monospace;
                font-size: 11px;
            }
        """)
        
        # Configure touch scroller for Raspberry Pi 7" capacitive display
        if QScroller is not None:
            QScroller.grabGesture(self.listLogs.viewport(), QScroller.LeftMouseButtonGesture)
            
        layout.addWidget(self.listLogs)

        # Database Compile/Sync button
        self.btnSync = QPushButton("🔄 COMPILE DB WEIGHTS")
        self.btnSync.setMinimumHeight(45)
        self.btnSync.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                color: #ea580c;
                font-weight: bold;
                border-radius: 8px;
                font-size: 14px;
            }
            QPushButton:pressed {
                background-color: rgba(234, 88, 12, 0.1);
            }
        """)
        self.btnSync.clicked.connect(self.sync_requested.emit)
        layout.addWidget(self.btnSync)

    def add_log_entry(self, log_entry):
        self.listLogs.insertItem(0, log_entry)
        if self.listLogs.count() > 100:
            self.listLogs.takeItem(self.listLogs.count() - 1)
