import sys
import os

# Resolve imports path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from qt_imports import QWidget, QLineEdit, QPushButton, QGridLayout, QVBoxLayout, pyqtSignal, Qt

class KeypadWidget(QWidget):
    pin_submitted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.entered_pin = ""
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # PIN display box
        self.txtPinDisplay = QLineEdit()
        self.txtPinDisplay.setEchoMode(QLineEdit.Password)
        self.txtPinDisplay.setAlignment(Qt.AlignCenter)
        self.txtPinDisplay.setReadOnly(True)
        self.txtPinDisplay.setPlaceholderText("ENTER PIN")
        self.txtPinDisplay.setStyleSheet("""
            background-color: #f8fafc;
            border: 1px solid #cbd5e1;
            color: #ea580c;
            border-radius: 8px;
            font-size: 28px;
            padding: 10px;
        """)
        main_layout.addWidget(self.txtPinDisplay)

        # Grid layout for keypad
        grid = QGridLayout()
        grid.setSpacing(10)

        buttons = [
            ('1', 0, 0), ('2', 0, 1), ('3', 0, 2),
            ('4', 1, 0), ('5', 1, 1), ('6', 1, 2),
            ('7', 2, 0), ('8', 2, 1), ('9', 2, 2),
            ('Clear', 3, 0), ('0', 3, 1), ('Enter', 3, 2)
        ]

        for text, row, col in buttons:
            btn = QPushButton(text)
            btn.setMinimumHeight(55)
            if text in ['Clear', 'Enter']:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #f1f5f9;
                        border: 1px solid #cbd5e1;
                        color: #475569;
                        border-radius: 8px;
                        font-size: 16px;
                        font-weight: bold;
                    }
                    QPushButton:pressed {
                        background-color: #e2e8f0;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #ffffff;
                        border: 1px solid #e2e8f0;
                        color: #0f172a;
                        border-radius: 8px;
                        font-size: 20px;
                        font-weight: bold;
                    }
                    QPushButton:pressed {
                        background-color: rgba(234, 88, 12, 0.1);
                        border: 1px solid rgba(234, 88, 12, 0.3);
                        color: #ea580c;
                    }
                """)
            
            btn.clicked.connect(self.make_keypad_callback(text))
            grid.addWidget(btn, row, col)

        main_layout.addLayout(grid)

    def make_keypad_callback(self, val):
        return lambda: self.handle_keypad_press(val)

    def handle_keypad_press(self, val):
        if val == 'Clear':
            self.entered_pin = ""
        elif val == 'Enter':
            # Emit signal to parent for validation
            self.pin_submitted.emit(self.entered_pin)
            self.entered_pin = ""
        else:
            if len(self.entered_pin) < 6:
                self.entered_pin += val
        
        self.txtPinDisplay.setText(self.entered_pin)
