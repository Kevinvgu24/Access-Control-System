import sys
import os

# Resolve imports path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from qt_imports import QWidget, QLineEdit, QPushButton, QVBoxLayout, QLabel, pyqtSignal, Qt

class RegisterWidget(QWidget):
    register_requested = pyqtSignal(str, str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        lbl_title = QLabel("Biometrics Enrollment")
        lbl_title.setStyleSheet("color: #ea580c; font-size: 18px; font-weight: bold;")
        lbl_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_title)

        # Name Field
        self.lbl_name = QLabel("Full Name:")
        self.lbl_name.setStyleSheet("color: #475569; font-size: 13px;")
        self.txtNameInput = QLineEdit()
        self.txtNameInput.setPlaceholderText("e.g. John Doe")
        self.txtNameInput.setStyleSheet("""
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            color: #0f172a;
            border-radius: 8px;
            font-size: 14px;
            padding: 8px;
        """)
        layout.addWidget(self.lbl_name)
        layout.addWidget(self.txtNameInput)

        # Email / Student ID Field
        self.lbl_email = QLabel("Email / Student ID (MSSV):")
        self.lbl_email.setStyleSheet("color: #475569; font-size: 13px;")
        self.txtEmailInput = QLineEdit()
        self.txtEmailInput.setPlaceholderText("e.g. mssv@student.edu.vn")
        self.txtEmailInput.setStyleSheet("""
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            color: #0f172a;
            border-radius: 8px;
            font-size: 14px;
            padding: 8px;
        """)
        layout.addWidget(self.lbl_email)
        layout.addWidget(self.txtEmailInput)

        # Password Field
        self.lbl_password = QLabel("Password:")
        self.lbl_password.setStyleSheet("color: #475569; font-size: 13px;")
        self.txtPasswordInput = QLineEdit()
        self.txtPasswordInput.setEchoMode(QLineEdit.Password)
        self.txtPasswordInput.setPlaceholderText("Enter account password")
        self.txtPasswordInput.setStyleSheet("""
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            color: #0f172a;
            border-radius: 8px;
            font-size: 14px;
            padding: 8px;
        """)
        layout.addWidget(self.lbl_password)
        layout.addWidget(self.txtPasswordInput)

        # Role Field
        self.lbl_role = QLabel("Access Role:")
        self.lbl_role.setStyleSheet("color: #475569; font-size: 13px;")
        self.txtRoleInput = QLineEdit()
        self.txtRoleInput.setPlaceholderText("e.g. student, staff, admin")
        self.txtRoleInput.setStyleSheet("""
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            color: #0f172a;
            border-radius: 8px;
            font-size: 14px;
            padding: 8px;
        """)
        layout.addWidget(self.lbl_role)
        layout.addWidget(self.txtRoleInput)

        # Enrollment status message
        self.lblRegStatus = QLabel("")
        self.lblRegStatus.setAlignment(Qt.AlignCenter)
        self.lblRegStatus.setStyleSheet("font-size: 13px; font-weight: bold;")
        layout.addWidget(self.lblRegStatus)

        # Enroll Button
        self.btnEnroll = QPushButton("📸 CAPTURE & REGISTER")
        self.btnEnroll.setMinimumHeight(45)
        self.btnEnroll.setStyleSheet("""
            QPushButton {
                background-color: #ea580c;
                color: white;
                font-weight: bold;
                font-size: 15px;
                border-radius: 8px;
                border: none;
            }
            QPushButton:pressed {
                background-color: #c2410c;
            }
        """)
        self.btnEnroll.clicked.connect(self.on_enroll_clicked)
        layout.addWidget(self.btnEnroll)
        
        # Spacer
        layout.addStretch()

    def set_capture_mode(self, is_capturing):
        """Hides form controls and scales status/button for easier touch operation during enrollment."""
        self.lbl_name.setVisible(not is_capturing)
        self.txtNameInput.setVisible(not is_capturing)
        
        self.lbl_email.setVisible(not is_capturing)
        self.txtEmailInput.setVisible(not is_capturing)
        
        self.lbl_password.setVisible(not is_capturing)
        self.txtPasswordInput.setVisible(not is_capturing)
        
        self.lbl_role.setVisible(not is_capturing)
        self.txtRoleInput.setVisible(not is_capturing)

        if is_capturing:
            self.lblRegStatus.setStyleSheet("""
                font-size: 18px; 
                font-weight: bold; 
                color: #ea580c; 
                border: 2px dashed #ea580c; 
                padding: 15px; 
                border-radius: 8px; 
                background-color: #fff7ed;
            """)
            self.btnEnroll.setMinimumHeight(80)
            self.btnEnroll.setStyleSheet("""
                QPushButton {
                    background-color: #ea580c;
                    color: white;
                    font-weight: bold;
                    font-size: 22px;
                    border-radius: 12px;
                    border: none;
                }
                QPushButton:disabled {
                    background-color: #cbd5e1;
                    color: #64748b;
                }
                QPushButton:pressed {
                    background-color: #c2410c;
                }
            """)
        else:
            self.lblRegStatus.setStyleSheet("""
                font-size: 13px; 
                font-weight: bold; 
                color: #0f172a; 
                border: none; 
                padding: 0px; 
                background-color: transparent;
            """)
            self.btnEnroll.setMinimumHeight(45)
            self.btnEnroll.setStyleSheet("""
                QPushButton {
                    background-color: #ea580c;
                    color: white;
                    font-weight: bold;
                    font-size: 15px;
                    border-radius: 8px;
                    border: none;
                }
                QPushButton:disabled {
                    background-color: #cbd5e1;
                    color: #64748b;
                }
                QPushButton:pressed {
                    background-color: #c2410c;
                }
            """)

    def on_enroll_clicked(self):
        name = self.txtNameInput.text().strip()
        email = self.txtEmailInput.text().strip()
        password = self.txtPasswordInput.text().strip()
        role = self.txtRoleInput.text().strip()
        self.register_requested.emit(name, email, password, role)

    def clear_inputs(self):
        self.txtNameInput.clear()
        self.txtEmailInput.clear()
        self.txtPasswordInput.clear()
        self.txtRoleInput.clear()
        self.lblRegStatus.setText("")
