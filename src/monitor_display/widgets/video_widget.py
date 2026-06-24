import sys
import os
import numpy as np

# Resolve imports path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from qt_imports import QFrame, QLabel, QVBoxLayout, QHBoxLayout, Qt, QImage, QPixmap, QPainter, QPen, QColor, QBrush, QPainterPath, QFont

class VideoWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panelFrame")
        self.last_frame = None
        self.draw_oval = False
        self.guide_text = ""
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)

        # Video stream viewport QLabel
        self.lblVideo = QLabel()
        self.lblVideo.setAlignment(Qt.AlignCenter)
        self.lblVideo.setText("Waking up camera stream...")
        self.lblVideo.setStyleSheet("color: #64748b; font-size: 16px; background-color: #020617; border-radius: 8px;")
        self.lblVideo.setScaledContents(False)
        layout.addWidget(self.lblVideo, stretch=4)

        # Bottom row HUD (Lock Status and Vitals info)
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(10)

        self.lblLockStatus = QLabel("🔒 LOCKED")
        self.lblLockStatus.setAlignment(Qt.AlignCenter)
        self.lblLockStatus.setStyleSheet("background-color: #ef4444; color: white; font-weight: bold; border-radius: 8px; padding: 10px; font-size: 18px;")
        bottom_row.addWidget(self.lblLockStatus, stretch=1)

        self.lblVitals = QLabel("Initializing vitals...")
        self.lblVitals.setStyleSheet("background-color: #f8fafc; color: #475569; border: 1px solid #cbd5e1; border-radius: 8px; padding: 10px; font-size: 12px;")
        bottom_row.addWidget(self.lblVitals, stretch=2)

        layout.addLayout(bottom_row, stretch=1)

    def update_frame(self, rgb_frame):
        self.last_frame = rgb_frame
        
        # Calculate viewport dimensions
        w = self.lblVideo.width()
        h = self.lblVideo.height()
        if w < 100 or h < 100:
            w, h = 640, 640

        im_height, im_width, _ = rgb_frame.shape
        qimg = QImage(rgb_frame.data, im_width, im_height, im_width * 3, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg)
        
        # [OPT] FastTransformation: thay bicubic bằng bilinear — không phân biệt được ở 50-80cm
        # nhưng giảm ~20% CPU render frame trên ARM Cortex-A76
        scaled_pix = pix.scaled(w, h, Qt.KeepAspectRatio, Qt.FastTransformation)
        
        # Draw 3D oval alignment guide overlay if enrollment is active
        if self.draw_oval:
            painter = QPainter(scaled_pix)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Create full-screen path
            path = QPainterPath()
            path.addRect(0, 0, scaled_pix.width(), scaled_pix.height())

            # Define center oval bounds
            oval_w = int(scaled_pix.width() * 0.45)
            oval_h = int(scaled_pix.height() * 0.60)
            oval_x = int((scaled_pix.width() - oval_w) / 2)
            oval_y = int((scaled_pix.height() - oval_h) / 2)

            oval_path = QPainterPath()
            oval_path.addEllipse(oval_x, oval_y, oval_w, oval_h)

            # Mask out the center oval to darken the rest of the stream
            mask_path = path.subtracted(oval_path)
            painter.fillPath(mask_path, QBrush(QColor(0, 0, 0, 160)))

            # Draw a beautiful bright orange dashed oval border
            pen = QPen(QColor("#ea580c"))
            pen.setWidth(3)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawEllipse(oval_x, oval_y, oval_w, oval_h)

            # Draw bottom guide text bar
            if self.guide_text:
                painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))
                
                banner_h = 35
                painter.fillRect(0, scaled_pix.height() - banner_h, scaled_pix.width(), banner_h, QColor(0, 0, 0, 200))
                
                painter.setPen(QColor("#ffffff"))
                painter.drawText(
                    0, scaled_pix.height() - banner_h, scaled_pix.width(), banner_h,
                    Qt.AlignCenter, self.guide_text
                )
            
            painter.end()

        self.lblVideo.setPixmap(scaled_pix)

    def update_vitals(self, text):
        self.lblVitals.setText(text)

    def update_lock_status(self, is_unlocked):
        if is_unlocked:
            self.lblLockStatus.setText("🔓 UNLOCKED")
            self.lblLockStatus.setStyleSheet("background-color: #10b981; color: white; font-weight: bold; border-radius: 8px; padding: 10px; font-size: 18px;")
        else:
            self.lblLockStatus.setText("🔒 LOCKED")
            self.lblLockStatus.setStyleSheet("background-color: #ef4444; color: white; font-weight: bold; border-radius: 8px; padding: 10px; font-size: 18px;")
