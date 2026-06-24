import sys
import os
import argparse
import time
import cv2
import numpy as np
import gc
from datetime import datetime

# Resolve imports path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from qt_imports import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QTabWidget, QMessageBox, QFrame, Qt, QTimer,
    pyqtSlot, GPIO, GPIO_AVAILABLE, RELAY_PIN, QColor, QGraphicsDropShadowEffect
)
from frame_emitter import FrameEmitter
from widgets.video_widget import VideoWidget
from widgets.access_widget import AccessWidget
from widgets.keypad_widget import KeypadWidget
from widgets.register_widget import RegisterWidget
from widgets.logs_widget import LogsWidget

# Import core smart door system and database synchronization
from app import ProfessionalSmartDoor
# We import register modules dynamically in functions to avoid early driver binding conflicts

# Initialise GStreamer Gst library module
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
Gst.init(None)


class InterfaceMonitorApp(QMainWindow):
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.door_app = None
        self.door_unlocked = False
        
        # Debouncing variables for logging detections
        self.last_logged_name = ""
        self.last_logged_time = 0

        # Face holding state verification
        self.detection_start_time = None
        self.detected_user_name = None
        self.last_detection_time = 0
        self.user_unlocked_this_session = False
        
        # Signal Emitter for thread-safe UI updates
        self.emitter = FrameEmitter()
        self.emitter.new_frame.connect(self.update_video_frame)
        self.emitter.recognition_event.connect(self.handle_recognition_event)

        # Unlock/Lock timer
        self.unlock_timer = QTimer(self)
        self.unlock_timer.setSingleShot(True)
        self.unlock_timer.timeout.connect(self.lock_door)

        # Hardware update timer
        self.hw_timer = QTimer(self)
        self.hw_timer.timeout.connect(self.update_hw_stats)
        self.hw_timer.start(1000)

        # [OPT] Walk-away timeout timer: check 5x/giây thay vì 30x/giây trong frame callback
        self.walkaway_timer = QTimer(self)
        self.walkaway_timer.setInterval(200)
        self.walkaway_timer.timeout.connect(self._check_walkaway_timeout)
        self.walkaway_timer.start()

        # [OPT] Pre-allocate CLAHE object một lần — tránh tạo lại mỗi frame
        self._clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))

        # Multi-angle face enrollment variables
        self.enroll_state = None
        self.enroll_angle_index = 0
        self.enroll_captured_frames = []
        self.enroll_capture_count = 0
        # [MEM] Pending credentials — khởi tạo rỗng để cancel_enrollment an toàn khi gọi sớm
        self.enroll_pending_name = ""
        self.enroll_pending_email = ""
        self.enroll_pending_password = ""
        self.enroll_pending_role = ""
        self.enroll_angles = [
            {"id": "straight", "label": "1/5: Nhìn thẳng (Look Straight)"},
            {"id": "left", "label": "2/5: Quay đầu sang TRÁI (Turn Left)"},
            {"id": "right", "label": "3/5: Quay đầu sang PHẢI (Turn Right)"},
            {"id": "up", "label": "4/5: Ngước đầu LÊN TRÊN (Look Up)"},
            {"id": "down", "label": "5/5: Cúi đầu XUỐNG DƯỚI (Look Down)"}
        ]
        
        # Enrollment workflow timers
        self.enroll_capture_timer = QTimer(self)
        self.enroll_capture_timer.timeout.connect(self.on_enroll_capture_tick)
        
        self.enroll_countdown_seconds = 7
        self.enroll_countdown_timer = QTimer(self)
        self.enroll_countdown_timer.setInterval(1000)
        self.enroll_countdown_timer.timeout.connect(self.on_enroll_countdown_tick)

        # [GUARD] RAM Watchdog: kiểm tra bộ nhớ mỗi 30 giây, cảnh báo và GC nếu vượt ngưỡng
        self._ram_watchdog_timer = QTimer(self)
        self._ram_watchdog_timer.setInterval(30_000)  # 30 giây
        self._ram_watchdog_timer.timeout.connect(self._ram_watchdog_check)
        self._ram_watchdog_timer.start()

        # Initialize GUI Layout and Stylesheet
        self.init_ui()
        self.start_pipeline()

    def init_ui(self):
        self.setWindowTitle("Smart Lab Access Monitor")
        self.resize(1024, 600)  # Standard 7-inch display widescreen resolution
        self.setMinimumSize(800, 480)

        # Apply custom modern light orange and white stylesheet
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f1f5f9;
            }
            QWidget#centralWidget {
                background-color: #f1f5f9;
            }
            QFrame#panelFrame {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 12px;
            }
            QTabWidget::pane {
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                background-color: #ffffff;
                top: -1px;
            }
            QTabBar::tab {
                background-color: #f8fafc;
                color: #64748b;
                border: 1px solid #cbd5e1;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 12px 8px;
                font-size: 12px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #ea580c;
                border-bottom: 3px solid #ea580c;
            }
            QLabel#titleLabel {
                color: #0f172a;
                font-size: 18px;
                font-weight: bold;
            }
        """)

        # Central Widget
        central = QWidget(self)
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        # Main horizontal layout dividing screen into Left and Right
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # =====================================================================
        # LEFT PANEL: Video Stream Feed & Door Lock Status
        # =====================================================================
        self.videoWidget = VideoWidget(self)
        main_layout.addWidget(self.videoWidget, stretch=11)

        # [OPT] Removed QGraphicsDropShadowEffect on VideoWidget — compositing shadow
        # on every repaint (30fps) wastes ~10% CPU on ARM. Border used via stylesheet instead.

        # =====================================================================
        # RIGHT PANEL: Tabbed Touchscreen Navigation & Controls
        # =====================================================================
        right_frame = QFrame()
        right_frame.setObjectName("panelFrame")
        
        # Add beautiful 3D relief drop shadow to Control Panel Card
        shadow_control = QGraphicsDropShadowEffect(self)
        shadow_control.setBlurRadius(15)
        shadow_control.setColor(QColor(0, 0, 0, 40))
        shadow_control.setOffset(0, 4)
        right_frame.setGraphicsEffect(shadow_control)
        right_layout = QVBoxLayout(right_frame)
        right_layout.setContentsMargins(10, 10, 10, 10)

        # Header Title
        lblRightTitle = QLabel("SYSTEM CONTROL")
        lblRightTitle.setObjectName("titleLabel")
        lblRightTitle.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(lblRightTitle)

        # Navigation Tabs
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setExpanding(True)
        
        # Instantiate child modular widgets
        self.tabAccess = AccessWidget()
        self.tabKeypad = KeypadWidget()
        self.tabRegister = RegisterWidget()
        self.tabLogs = LogsWidget()

        # Connect signals
        self.tabAccess.manual_unlock_requested.connect(self.unlock_door)
        self.tabKeypad.pin_submitted.connect(self.handle_pin_submitted)
        self.tabRegister.register_requested.connect(self.handle_register_requested)
        self.tabLogs.sync_requested.connect(self.handle_sync_requested)

        # Add tabs
        self.tabs.addTab(self.tabAccess, "Access")
        self.tabs.addTab(self.tabKeypad, "Keypad")
        self.tabs.addTab(self.tabRegister, "Register")
        self.tabs.addTab(self.tabLogs, "Logs")

        self.tabs.currentChanged.connect(self.handle_tab_changed)

        right_layout.addWidget(self.tabs)
        main_layout.addWidget(right_frame, stretch=9)

        # Add initial log entry
        self.add_log("System", "Monitor UI initialized.")

    # =====================================================================
    # GSTREAMER INTERFACE AND SIGNAL EVENT HANDLERS
    # =====================================================================
    def start_pipeline(self):
        """Initializes and runs the GStreamer Hailo pipeline."""
        print("-> Starting GStreamer Hailo Pipeline from GUI...")
        try:
            self.door_app = ProfessionalSmartDoor(
                yolo_hef=self.args.yolo_hef,
                arcface_hef=self.args.arcface_hef,
                anti_spoofing_hef=self.args.anti_spoofing_hef,
                lbf_model_path=self.args.lbf_model,
                database_dir=self.args.db_dir,
                close_thresh=self.args.close_thresh
            )
            
            # Hook the recognition callback inside the app.py frame probe to emit signals back
            def on_rec_callback(detections_info):
                self.emitter.recognition_event.emit(detections_info)
            self.door_app.recognition_callback = on_rec_callback

            # Hook the appsink callback to emit new video frame buffers back
            def on_frame_callback(rgb_frame):
                self.emitter.new_frame.emit(rgb_frame)

            # Start the GStreamer pipeline without the blocking GLib mainloop
            self.door_app.run(
                width=self.args.cam_width,
                height=self.args.cam_height,
                source=self.args.cam_source,
                appsink_callback=on_frame_callback
            )
            self.update_recognition_state()
            self.add_log("System", "GStreamer pipeline is playing.")
        except Exception as e:
            self.add_log("System", f"Pipeline Init Error: {e}")
            QMessageBox.critical(self, "Pipeline Error", f"Failed to initialize GStreamer: {e}")

    def adjust_frame_brightness_if_dark(self, rgb_frame):
        """
        [CHỨC NĂNG] Tự động tối ưu hóa và tăng cường độ sáng/độ tương phản cho hình ảnh.
        [OPT] Dùng self._clahe được pre-allocated trong __init__ — tránh tạo CLAHE mỗi frame.
        """
        if rgb_frame is None:
            return rgb_frame

        try:
            # [OPT] Đo luminance trên ảnh gốc — tránh copy không cần thiết
            avg_brightness = np.mean(rgb_frame[:, :, 1])  # kênh G ≈ luminance, nhanh hơn cvtColor

            if avg_brightness < 100:
                # Chuyển đổi RGB -> LAB in-place
                lab = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2LAB)
                l, a, b_ch = cv2.split(lab)

                # [OPT] Dùng self._clahe đã pre-allocated — không tạo object mới
                cl = self._clahe.apply(l)

                # Merge và chuyển về RGB
                cv2.merge((cl, a, b_ch), lab)  # merge in-place vào buffer lab
                rgb_enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)

                # Bổ sung tuyến tính nếu cực kỳ tối
                if avg_brightness < 50:
                    cv2.convertScaleAbs(rgb_enhanced, rgb_enhanced, alpha=1.2, beta=15)

                return rgb_enhanced
        except Exception as e:
            print(f"[WARN] Brightness adjustment failed: {e}")

        return rgb_frame

    def _check_walkaway_timeout(self):
        """[OPT] Walk-away check chạy 5x/giây qua QTimer — thay vì 30x/giây trong frame callback."""
        if self.detected_user_name is None:
            return
        now = time.time()
        if now - self.last_detection_time > 1.2:
            self.detection_start_time = None
            self.detected_user_name = None
            self.user_unlocked_this_session = False
            if not self.door_unlocked:
                self.tabAccess.lblScanStatus.setText("SCANNING...")
                self.tabAccess.lblScanStatus.setStyleSheet("""
                    color: #64748b;
                    font-size: 24px;
                    font-weight: bold;
                    padding: 20px;
                    background-color: #f8fafc;
                    border-radius: 8px;
                    border: 1px solid #cbd5e1;
                """)
                self.tabAccess.lblScanDetails.setText("Please align your face to the camera.")

    @pyqtSlot(np.ndarray)
    def update_video_frame(self, rgb_frame):
        """[OPT] Frame callback — walk-away check removed (moved to _check_walkaway_timeout QTimer)."""
        # Bù sáng nếu đang ở tab Register
        if self.tabs.currentIndex() == 2:
            rgb_frame = self.adjust_frame_brightness_if_dark(rgb_frame)

        self.videoWidget.update_frame(rgb_frame)

    @pyqtSlot(list)
    def handle_recognition_event(self, detections_info):
        """Callback triggered when face detection classification events are received in a frame."""
        if not detections_info:
            return
        
        now = time.time()
        num_faces = len(detections_info)
        
        # Check if any face in the frame is unauthorized / unknown
        has_unknown = any(
            d["class_id"] != 0 or "Unknown" in d["label"] 
            for d in detections_info
        )
        
        # SECURITY RULE: If any invalid face is detected, OR if there are more than 2 people
        if has_unknown or num_faces > 2:
            # Immediately lock the door if it was unlocked
            if self.door_unlocked:
                self.lock_door()
            
            # Reset verification timers
            self.detection_start_time = None
            self.detected_user_name = None
            self.user_unlocked_this_session = False
            
            # Show appropriate warning on Access tab
            if num_faces > 2:
                warning_msg = "Cảnh báo: Chỉ cho phép tối đa 1 hoặc 2 người hợp lệ xuất hiện cùng lúc!"
                self.tabAccess.lblScanStatus.setText("⚠️ CẢNH BÁO BẢO MẬT")
                self.tabAccess.lblScanStatus.setStyleSheet("""
                    color: #ef4444;
                    font-size: 20px;
                    font-weight: bold;
                    padding: 20px;
                    background-color: rgba(239, 68, 68, 0.1);
                    border-radius: 8px;
                    border: 2px solid #ef4444;
                """)
                self.tabAccess.lblScanDetails.setText(warning_msg)
                
                # Log to security log
                if "Multi-face warning" != self.last_logged_name or (now - self.last_logged_time > 10):
                    self.add_log("Security", f"Warning: {num_faces} faces detected. Access blocked.")
                    self.last_logged_name = "Multi-face warning"
                    self.last_logged_time = now
            else:
                warning_msg = "Cảnh báo: Phát hiện khuôn mặt không hợp lệ! Cửa đã khóa."
                self.tabAccess.lblScanStatus.setText("🚫 TRUY CẬP BỊ TỪ CHỐI")
                self.tabAccess.lblScanStatus.setStyleSheet("""
                    color: #ef4444;
                    font-size: 20px;
                    font-weight: bold;
                    padding: 20px;
                    background-color: rgba(239, 68, 68, 0.1);
                    border-radius: 8px;
                    border: 2px solid #ef4444;
                """)
                self.tabAccess.lblScanDetails.setText(warning_msg)
                
                # Log only once every 10 seconds to avoid flooding
                if "Unknown" != self.last_logged_name or (now - self.last_logged_time > 10):
                    self.add_log("Security", "Access Denied: Unknown face detected. Door locked.")
                    self.last_logged_name = "Unknown"
                    self.last_logged_time = now
            
            self.last_detection_time = now
            return

        # Normal verification flow if 1 or 2 valid people are detected
        # Pick the first valid person for recognition processing
        valid_user = detections_info[0]
        label = valid_user["label"]
        name = label.split("(")[0].strip()
        
        # If it's a new person, or they walked away and returned
        if self.detected_user_name != name or (now - self.last_detection_time > 1.2):
            self.detection_start_time = now
            self.detected_user_name = name
            self.user_unlocked_this_session = False
            
            self.tabAccess.lblScanStatus.setText("VERIFYING...")
            self.tabAccess.lblScanStatus.setStyleSheet("""
                color: #ea580c;
                font-size: 24px;
                font-weight: bold;
                padding: 20px;
                background-color: rgba(234, 88, 12, 0.08);
                border-radius: 8px;
                border: 1px solid rgba(234, 88, 12, 0.25);
            """)
            self.tabAccess.lblScanDetails.setText(f"Hold face steady for 1s: {name}")
        else:
            # Same person holding their face
            if not self.user_unlocked_this_session:
                duration = now - self.detection_start_time
                if duration >= 1.0:
                    self.tabAccess.lblScanStatus.setText("🔓 ACCESS GRANTED")
                    self.tabAccess.lblScanStatus.setStyleSheet("""
                        color: #10b981;
                        font-size: 24px;
                        font-weight: bold;
                        padding: 20px;
                        background-color: rgba(16, 185, 129, 0.08);
                        border-radius: 8px;
                        border: 1px solid rgba(16, 185, 129, 0.25);
                    """)
                    self.tabAccess.lblScanDetails.setText(f"Welcome back, {label}!")
                    
                    # Automatically unlock the door (only once per session)
                    self.unlock_door()
                    self.user_unlocked_this_session = True
                    
                    # Log the event exactly once
                    self.add_log("Scan", f"Granted: {label}")
                    self.last_logged_name = name
                    self.last_logged_time = now
                else:
                    # Show remaining progress countdown
                    remaining = max(0.0, 1.0 - duration)
                    self.tabAccess.lblScanDetails.setText(f"Keep holding: {name} ({remaining:.1f}s)")
        
        self.last_detection_time = now

    # =====================================================================
    # DOOR LOCK CONTROL & HARDWARE VITAL MONITORING
    # =====================================================================
    def unlock_door(self):
        """Triggers the relay state to UNLOCKED and sets an automatic re-lock timer."""
        if self.door_unlocked:
            # Refresh countdown if already unlocked
            self.unlock_timer.start(5000)
            return
 
        self.door_unlocked = True
        self.videoWidget.update_lock_status(True)
        
        # Physical GPIO trigger
        if GPIO_AVAILABLE:
            try:
                GPIO.output(RELAY_PIN, GPIO.HIGH)
            except Exception as e:
                self.add_log("GPIO Error", str(e))
                
        self.add_log("Hardware", "Access lock relay opened.")
        self.unlock_timer.start(5000)  # Automatically re-locks after 5 seconds

    def lock_door(self):
        """Sets the door relay state back to LOCKED."""
        self.door_unlocked = False
        self.videoWidget.update_lock_status(False)
        
        # Physical GPIO trigger
        if GPIO_AVAILABLE:
            try:
                GPIO.output(RELAY_PIN, GPIO.LOW)
            except Exception as e:
                pass
                
        self.add_log("Hardware", "Access lock relay closed.")
        
        # Reset access tab UI
        self.tabAccess.lblScanStatus.setText("SCANNING...")
        self.tabAccess.lblScanStatus.setStyleSheet("""
            color: #64748b;
            font-size: 24px;
            font-weight: bold;
            padding: 20px;
            background-color: #f8fafc;
            border-radius: 8px;
            border: 1px solid #cbd5e1;
        """)
        self.tabAccess.lblScanDetails.setText("Please align your face to the camera.")

    def update_hw_stats(self):
        """Timer callback updating the hardware vitals stats labels on the HUD."""
        if self.door_app and self.door_app.hw_monitor:
            cpu_t = self.door_app.hw_monitor.cpu_temp
            hailo_t = self.door_app.hw_monitor.hailo_temp
            ram = self.door_app.hw_monitor.ram_mb
            fps = self.door_app._fps
            
            stats_text = (
                f"LIVE STREAM STATUS\n"
                f"FPS: {fps:.1f} frames/s\n"
                f"CPU Temp: {cpu_t:.1f}°C\n"
                f"Hailo-8L Temp: {hailo_t:.1f}°C\n"
                f"RAM RSS Usage: {ram:.1f} MB"
            )
            self.videoWidget.update_vitals(stats_text)

    def handle_tab_changed(self, index):
        self.update_recognition_state()
        # If we exited the Register tab (index 2), make sure guides are cleared and any active enrollment is cancelled
        if index != 2:
            if self.enroll_state is not None:
                self.cancel_enrollment()
            else:
                self.videoWidget.draw_oval = False
                self.videoWidget.guide_text = ""

    def update_recognition_state(self):
        if not self.door_app:
            return
        # Disable recognition if we are on the Register tab (index 2) OR if we are currently enrolling
        is_registering = (self.tabs.currentIndex() == 2) or (self.enroll_state is not None)
        self.door_app.recognition_enabled = not is_registering

    def cancel_enrollment(self):
        """[MEM FIX] Dừng tất cả timer và giải phóng toàn bộ bộ nhớ enrollment."""
        # Dừng các timer người dùng trước
        self.enroll_capture_timer.stop()
        self.enroll_countdown_timer.stop()

        # [MEM] Xóa từng frame numpy riêng lẻnh trước khi reset list
        # chỉ gán [] thì CPython GC mới xử lý sau — không đảm bảo giải phóng ngay
        for _frame in self.enroll_captured_frames:
            del _frame
        self.enroll_captured_frames.clear()

        # [MEM] Xóa dữ liệu cá nhân nhạy cảm khỏi RAM
        self.enroll_pending_name = ""
        self.enroll_pending_email = ""
        self.enroll_pending_password = ""
        self.enroll_pending_role = ""

        self.enroll_state = None
        self.enroll_angle_index = 0
        self.enroll_capture_count = 0
        self.tabRegister.set_capture_mode(False)
        self.videoWidget.draw_oval = False
        self.videoWidget.guide_text = ""
        self.tabRegister.btnEnroll.setText("📸 CAPTURE & REGISTER")
        self.tabRegister.btnEnroll.setEnabled(True)
        self.tabRegister.lblRegStatus.setText("Enrollment cancelled.")
        self.tabRegister.lblRegStatus.setStyleSheet("color: #ef4444; font-weight: bold;")
        if self.door_app:
            self.door_app.pipeline.set_state(Gst.State.PLAYING)
        QApplication.restoreOverrideCursor()

        # [MEM] Buộc CPython giải phóng ngay lập tức thay vì đợi vòng GC tiếp theo
        gc.collect()

    def handle_pin_submitted(self, pin):
        """Validates touch-pad PIN entries and grants access upon verification."""
        if pin == "1234":  # Default demo master PIN code
            self.add_log("Keypad", "Correct PIN entered.")
            self.unlock_door()
            self.tabs.setCurrentIndex(0)  # Navigate back to Access Home
        else:
            self.add_log("Keypad", "Warning: Incorrect PIN attempt.")
            QMessageBox.warning(self, "Invalid PIN", "The PIN code entered is incorrect.")

    def handle_register_requested(self, name, email, password, role):
        """Starts or continues the multi-angle manual-trigger face capture sequence."""
        if self.enroll_state == "waiting_user_capture":
            # User clicked capture for the current angle!
            self.start_capturing_current_angle()
            return

        if self.enroll_state in ["capturing_angle", "waiting_countdown", "processing"]:
            # Ignore clicks while busy
            return

        if not name or not email or not password:
            QMessageBox.warning(self, "Input Error", "Please fill in Name, Email/MSSV, and Password.")
            return

        if self.videoWidget.last_frame is None:
            QMessageBox.warning(self, "Camera Error", "No video frame captured. Please wait for camera stream.")
            return

        # Store details for submission after capture sequence completes
        self.enroll_pending_name = name
        self.enroll_pending_email = email
        self.enroll_pending_password = password
        self.enroll_pending_role = role if role else "student"

        self.add_log("Register", f"Started manual-trigger enrollment for {email}")

        # Start state machine
        self.enroll_captured_frames = []
        self.enroll_angle_index = 0
        self.enroll_state = "waiting_user_capture"
        
        # Turn on capture mode UI
        self.tabRegister.set_capture_mode(True)
        
        # Turn on oval guide on VideoWidget
        self.videoWidget.draw_oval = True
        self.videoWidget.guide_text = self.enroll_angles[0]["label"]
        
        self.tabRegister.lblRegStatus.setText("Align face. Click capture button below when ready!")
        self.tabRegister.lblRegStatus.setStyleSheet("color: #ea580c; font-weight: bold;")
        self.tabRegister.btnEnroll.setEnabled(True)
        self.tabRegister.btnEnroll.setText("📸 CAPTURE: STRAIGHT")

    def start_capturing_current_angle(self):
        angle_info = self.enroll_angles[self.enroll_angle_index]
        self.enroll_state = "capturing_angle"
        self.enroll_capture_count = 0
        
        self.tabRegister.lblRegStatus.setText(f"Capturing {angle_info['id'].upper()}...")
        self.tabRegister.lblRegStatus.setStyleSheet("color: #eab308; font-weight: bold;")
        self.tabRegister.btnEnroll.setEnabled(False)
        self.tabRegister.btnEnroll.setText("CAPTURING...")
        
        # Capture 5 frames at 150ms intervals
        self.enroll_capture_timer.start(150)

    def on_enroll_capture_tick(self):
        """Tick of fast capture timer. Grabs frames from live feed."""
        # [GUARD] Phòng thủ tràn bộ nhớ: không cho phép tích lũy quá 30 frame
        # (5 góc × 5 frame = 25 tối đa, buffer 5 frame dự phòng)
        if len(self.enroll_captured_frames) >= 30:
            print(f"[WARN] enroll_captured_frames overflow guard triggered: {len(self.enroll_captured_frames)} frames")
            self.enroll_capture_timer.stop()
            return

        if self.videoWidget.last_frame is not None:
            # Capture frame and apply low-light enhancement for dark lab conditions
            frame = self.videoWidget.last_frame.copy()
            frame = self.adjust_frame_brightness_if_dark(frame)
            self.enroll_captured_frames.append(frame)
            self.enroll_capture_count += 1
            
            angle_info = self.enroll_angles[self.enroll_angle_index]
            self.videoWidget.guide_text = f"{angle_info['label']} - Capture {self.enroll_capture_count}/5"
            
            if self.enroll_capture_count >= 5:
                # Stop capture timer
                self.enroll_capture_timer.stop()
                
                # Move to next angle
                self.enroll_angle_index += 1
                if self.enroll_angle_index < len(self.enroll_angles):
                    # Transition to 7-second countdown wait
                    self.enroll_state = "waiting_countdown"
                    self.enroll_countdown_seconds = 7
                    
                    next_angle = self.enroll_angles[self.enroll_angle_index]
                    self.videoWidget.guide_text = f"Chuẩn bị: {next_angle['label']} ({self.enroll_countdown_seconds}s)"
                    self.tabRegister.lblRegStatus.setText(f"Prepare next angle: {next_angle['id'].upper()} ({self.enroll_countdown_seconds}s)...")
                    self.tabRegister.lblRegStatus.setStyleSheet("color: #ea580c; font-weight: bold;")
                    self.tabRegister.btnEnroll.setEnabled(False)
                    self.tabRegister.btnEnroll.setText(f"WAITING... ({self.enroll_countdown_seconds}s)")
                    
                    # Start 7-second countdown
                    self.enroll_countdown_timer.start(1000)
                else:
                    # All angles completed!
                    self.enroll_state = "processing"
                    self.videoWidget.draw_oval = False
                    self.videoWidget.guide_text = ""
                    self.enroll_capture_timer.stop()
                    self.enroll_countdown_timer.stop()
                    
                    # Run the final NPU processing and upload
                    self.process_enroll_captured_data()

    def on_enroll_countdown_tick(self):
        self.enroll_countdown_seconds -= 1
        
        next_angle = self.enroll_angles[self.enroll_angle_index]
        self.videoWidget.guide_text = f"Chuẩn bị: {next_angle['label']} ({self.enroll_countdown_seconds}s)"
        self.tabRegister.lblRegStatus.setText(f"Prepare next angle: {next_angle['id'].upper()} ({self.enroll_countdown_seconds}s)...")
        self.tabRegister.btnEnroll.setText(f"WAITING... ({self.enroll_countdown_seconds}s)")
        
        if self.enroll_countdown_seconds <= 0:
            self.enroll_countdown_timer.stop()
            self.enroll_state = "waiting_user_capture"
            self.videoWidget.guide_text = next_angle["label"]
            self.tabRegister.lblRegStatus.setText(f"Ready! Align face and click capture.")
            self.tabRegister.lblRegStatus.setStyleSheet("color: #10b981; font-weight: bold;")
            self.tabRegister.btnEnroll.setEnabled(True)
            self.tabRegister.btnEnroll.setText(f"📸 CAPTURE: {next_angle['id'].upper()}")

    def process_enroll_captured_data(self):
        """Processes all collected multi-angle frames, extracts embeddings, and uploads to Firebase."""
        name = self.enroll_pending_name
        email = self.enroll_pending_email
        password = self.enroll_pending_password
        role = self.enroll_pending_role

        self.tabRegister.lblRegStatus.setText("Processing biometric images, pausing GStreamer...")
        self.tabRegister.lblRegStatus.setStyleSheet("color: #eab308; font-weight: bold;")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()

        # Stop GStreamer completely (NULL state) to release all GStreamer elements' NPU memory allocations
        self.door_app.pipeline.set_state(Gst.State.NULL)
        time.sleep(0.8)

        try:
            self.tabRegister.lblRegStatus.setText(f"Analyzing {len(self.enroll_captured_frames)} frames on NPU...")
            QApplication.processEvents()

            # Process all captured frames
            from hailo_platform import VDevice 
            from common import HailoPythonInferenceEngine, letterbox_image, scale_detections_to_original
            from face_engine import FaceAligner
            from register import get_face_embedding
            
            # [MEM] Lưu tất cả handle NPU/dữ liệu lớn thành instance attributes
            # để finally block có thể xóa chúng an toàn dù exception xảy ra bất kỳ đâu.
            # del locals()[var] KHÔNG hoạt động trong Python — locals() là bản sao read-only.
            self._enroll_shared_vdevice = VDevice()
            self._enroll_yolo_engine = HailoPythonInferenceEngine(self.args.yolo_hef, target=self._enroll_shared_vdevice)
            self._enroll_aligner = FaceAligner(self.args.lbf_model)
            self._enroll_embeddings = []
            self._enroll_representative_face = None
            self._enroll_face_crops = []

            for idx, rgb_frame in enumerate(self.enroll_captured_frames):
                self.tabRegister.lblRegStatus.setText(f"Detecting faces: {idx+1}/{len(self.enroll_captured_frames)}...")
                QApplication.processEvents()

                # Convert RGB array to OpenCV BGR for correct alignment pipeline
                bgr_img = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)
                orig_h, orig_w = bgr_img.shape[:2]
                padded, scale, pad_w, pad_h = letterbox_image(rgb_frame, target_size=640) # letterbox expects RGB

                detections, _ = self._enroll_yolo_engine.infer(np.expand_dims(padded, axis=0).astype(np.uint8), verbose=False, conf_threshold=0.4)
                if not detections:
                    continue

                detections = scale_detections_to_original(detections, orig_h, orig_w, scale, pad_w, pad_h)
                best_det = max(detections, key=lambda x: x['conf'])

                ymin, xmin, ymax, xmax = int(best_det['y1']), int(best_det['x1']), int(best_det['y2']), int(best_det['x2'])
                my, mx = int((ymax - ymin) * 0.1), int((xmax - xmin) * 0.1)

                raw_face = bgr_img[max(0, ymin - my):min(orig_h, ymax + my), max(0, xmin - mx):min(orig_w, xmax + mx)]
                if raw_face.size == 0:
                    continue

                # Align face
                if best_det.get('landmarks') and len(best_det['landmarks']) >= 5:
                    processed_face = self._enroll_aligner.align_with_landmarks(bgr_img, best_det['landmarks'])
                    if processed_face is None:
                        processed_face = self._enroll_aligner.align(raw_face)
                else:
                    processed_face = self._enroll_aligner.align(raw_face)

                if processed_face is not None:
                    self._enroll_face_crops.append(processed_face)
                    if self._enroll_representative_face is None and idx < 5:
                        self._enroll_representative_face = processed_face

            # [MEM] Giải phóng YOLO engine ngay khi dùng xong để lấy lại NPU RAM
            del self._enroll_yolo_engine
            self._enroll_yolo_engine = None
            del self._enroll_aligner
            self._enroll_aligner = None

            if not self._enroll_face_crops:
                raise ValueError("Could not detect face in any of the captured frames. Please align face correctly.")

            # Step 2: Initialize ArcFace to extract embeddings from cropped faces
            self.tabRegister.lblRegStatus.setText("Extracting features on NPU...")
            QApplication.processEvents()

            self._enroll_arcface_engine = HailoPythonInferenceEngine(self.args.arcface_hef, target=self._enroll_shared_vdevice)
            
            for cropped_face in self._enroll_face_crops:
                emb = get_face_embedding(self._enroll_arcface_engine, cropped_face)
                self._enroll_embeddings.append(emb)

            # [MEM] Giải phóng ArcFace và VDevice ngay khi dùng xong
            del self._enroll_arcface_engine
            self._enroll_arcface_engine = None
            del self._enroll_shared_vdevice
            self._enroll_shared_vdevice = None

            if not self._enroll_embeddings:
                raise ValueError("Could not extract embeddings from any of the detected faces.")

            # Average all valid embeddings to create a single robust multi-angle template
            avg_embedding = np.mean(self._enroll_embeddings, axis=0)
            final_embedding = avg_embedding / np.linalg.norm(avg_embedding)

            # Use first face or a fallback
            if self._enroll_representative_face is None:
                self._enroll_representative_face = cv2.resize(
                    cv2.cvtColor(self.enroll_captured_frames[0], cv2.COLOR_RGB2BGR), (112, 112)
                )

            self.tabRegister.lblRegStatus.setText("Connecting to Firebase Cloud...")
            QApplication.processEvents()

            # Initialize Firebase Admin SDK
            import firebase_admin
            from firebase_admin import credentials, firestore, storage
            import json

            SERVICE_ACCOUNT_PATH = "/home/kevinvgu/Access-Control-System/serviceAccountKey.json"
            if not os.path.exists(SERVICE_ACCOUNT_PATH):
                raise FileNotFoundError(f"Firebase Service Account Key not found at {SERVICE_ACCOUNT_PATH}")

            if not firebase_admin._apps:
                with open(SERVICE_ACCOUNT_PATH) as f:
                    cred_data = json.load(f)
                project_id = cred_data.get("project_id")
                bucket_name = f"{project_id}.appspot.com"
                cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
                firebase_admin.initialize_app(cred, {
                    'storageBucket': bucket_name
                })

            db_client = firestore.client()
            bucket = storage.bucket()

            self.tabRegister.lblRegStatus.setText("Uploading representative face image...")
            QApplication.processEvents()

            # Save representative face image to scratch path
            scratch_dir = "/home/kevinvgu/Access-Control-System/scratch"
            os.makedirs(scratch_dir, exist_ok=True)
            temp_img_path = os.path.join(scratch_dir, "temp_aligned.jpg")
            
            # Save aligned representative face (which is RGB, convert to BGR)
            cv2.imwrite(temp_img_path, cv2.cvtColor(self._enroll_representative_face, cv2.COLOR_RGB2BGR))

            # Upload to Firebase Storage
            blob = bucket.blob(f"users/{self.enroll_pending_email}/face_0.jpg")
            blob.upload_from_filename(temp_img_path, content_type="image/jpeg")
            blob.make_public()
            public_url = blob.public_url

            self.tabRegister.lblRegStatus.setText("Registering user on Firestore...")
            QApplication.processEvents()

            # Write Firestore user document with averaged multi-angle embedding
            doc_ref = db_client.collection("users").document(self.enroll_pending_email)
            doc_ref.set({
                "fullName": self.enroll_pending_name,
                "emailOrMssv": self.enroll_pending_email,
                "password": self.enroll_pending_password,
                "role": self.enroll_pending_role,
                "status": "pending",
                "embedding": final_embedding.tolist(),
                "createdAt": firestore.SERVER_TIMESTAMP
            })

            # Create faceImages subcollection document
            doc_ref.collection("faceImages").document("face_0").set({
                "storagePath": public_url
            })

            # Cleanup temp file
            if os.path.exists(temp_img_path):
                os.remove(temp_img_path)

            self.add_log("Register", f"Pending registration uploaded: {self.enroll_pending_email} (Robust multi-angle template)")
            self.tabRegister.lblRegStatus.setText("Upload successful! Pending admin approval.")
            self.tabRegister.lblRegStatus.setStyleSheet("color: #10b981; font-weight: bold;")

            QMessageBox.information(
                self, 
                "Registration Success", 
                f"Successfully completed multi-angle enrollment for '{self.enroll_pending_name}'!\n"
                f"Processed {len(self._enroll_embeddings)}/{len(self.enroll_captured_frames)} valid face frames.\n"
                f"Robust biometric profile uploaded to server, waiting for approval."
            )
            self.tabRegister.clear_inputs()

        except Exception as e:
            self.tabRegister.lblRegStatus.setText("Enrollment failed.")
            self.tabRegister.lblRegStatus.setStyleSheet("color: #ef4444; font-weight: bold;")
            self.add_log("Register", f"Failed registration: {e}")
            QMessageBox.critical(self, "Registration Error", f"Failed to register biometric face: {e}")

        finally:
            # ================================================================
            # [MEM] GIẢI PHÓNG BỘ NHỚ TOÀN DIỆN — chạy dù try thành công hay lỗi
            # ================================================================

            # 1. Xóa handle NPU engines (nếu chưa xóa trong try — trường hợp exception sớm)
            for _attr in ('_enroll_yolo_engine', '_enroll_arcface_engine',
                          '_enroll_shared_vdevice', '_enroll_aligner'):
                obj = getattr(self, _attr, None)
                if obj is not None:
                    del obj
                    setattr(self, _attr, None)

            # 2. Xóa từng face crop numpy array
            for _crop in getattr(self, '_enroll_face_crops', []):
                del _crop
            if hasattr(self, '_enroll_face_crops'):
                self._enroll_face_crops.clear()
                self._enroll_face_crops = None

            # 3. Xóa embedding list
            for _emb in getattr(self, '_enroll_embeddings', []):
                del _emb
            if hasattr(self, '_enroll_embeddings'):
                self._enroll_embeddings.clear()
                self._enroll_embeddings = None

            # 4. Xóa representative face image
            if hasattr(self, '_enroll_representative_face'):
                del self._enroll_representative_face
                self._enroll_representative_face = None

            # 5. Xóa từng frame numpy đã chụp khỏi RAM
            for _f in self.enroll_captured_frames:
                del _f
            self.enroll_captured_frames.clear()

            # 6. Xóa thông tin cá nhân nhạy cảm khỏi RAM
            self.enroll_pending_name = ""
            self.enroll_pending_email = ""
            self.enroll_pending_password = ""
            self.enroll_pending_role = ""

            # 7. Reset trạng thái enrollment
            self.enroll_state = None
            self.enroll_angle_index = 0
            self.enroll_capture_count = 0
            self.tabRegister.set_capture_mode(False)
            self.tabRegister.btnEnroll.setText("📸 CAPTURE & REGISTER")
            self.tabRegister.btnEnroll.setEnabled(True)

            # 8. Resume GStreamer pipeline và cập nhật nhận diện
            if self.door_app:
                self.door_app.pipeline.set_state(Gst.State.PLAYING)
            self.update_recognition_state()
            QApplication.restoreOverrideCursor()

            # 9. Buộc CPython GC chạy ngay — giải phóng tất cả numpy/NPU objects còn lại
            gc.collect()

    def handle_sync_requested(self):
        """Forces manual sync check on database folder files to re-initialize SQLite matrix."""
        self.add_log("Admin", "Triggered manual weight compilation.")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        # Stop GStreamer
        self.door_app.pipeline.set_state(Gst.State.READY)
        time.sleep(0.5)

        try:
            from register import auto_sync_database
            auto_sync_database(
                yolo_hef=self.args.yolo_hef,
                arcface_hef=self.args.arcface_hef,
                lbf_model_path=self.args.lbf_model,
                database_dir=self.args.db_dir
            )
            self.add_log("Admin", "Database weights compiled successfully.")
            QMessageBox.information(self, "Sync Complete", "SQLite database and binary vector cache synced successfully.")
        except Exception as e:
            self.add_log("Admin", f"Manual Sync Error: {e}")
            QMessageBox.critical(self, "Sync Error", f"Failed to sync database weights: {e}")
        finally:
            self.door_app.pipeline.set_state(Gst.State.PLAYING)
            QApplication.restoreOverrideCursor()

    # =====================================================================
    # LOGGING AND OS EVENT UTILITIES
    # =====================================================================
    def add_log(self, tag, message):
        """Appends a new timestamped log record to the list view tab."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{tag.upper()}] {message}"
        self.tabLogs.add_log_entry(log_entry)

    def _ram_watchdog_check(self):
        """[GUARD] Kiểm tra RAM mỗi 30 giây. Kích hoạt GC và cảnh báo nếu vượt ngưỡng."""
        try:
            import resource
            usage_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            usage_mb = usage_kb / 1024.0

            # Ngưỡng cảnh báo: 350MB
            if usage_mb > 350:
                print(f"[WARN] RAM Watchdog: RSS = {usage_mb:.1f}MB — forcing gc.collect()")
                gc.collect()
                # Hủy enrollment nếu đang chạy để giải phóng frame buffers
                if self.enroll_state is not None:
                    print("[WARN] RAM Watchdog: cancelling active enrollment to free frame buffers")
                    self.cancel_enrollment()
                    self.add_log("System", f"⚠️ RAM watchdog cancelled enrollment: {usage_mb:.0f}MB used")
        except Exception:
            pass  # Watchdog không được crash chương trình chính

    def keyPressEvent(self, event):
        """Allow pressing Esc key to exit the application."""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """[MEM FIX] Dừng toàn bộ timer, giải phóng bộ nhớ, và tắt GStreamer pipeline an toàn."""
        # 1. Dừng tất cả QTimers trước khi cleanup
        self.hw_timer.stop()
        self.unlock_timer.stop()
        self.walkaway_timer.stop()
        self._ram_watchdog_timer.stop()
        self.enroll_capture_timer.stop()
        self.enroll_countdown_timer.stop()

        # 2. Hủy enrollment đang chạy (giải phóng frame buffers + NPU handles)
        if self.enroll_state is not None:
            self.cancel_enrollment()

        # 3. Dừng GStreamer pipeline
        if self.door_app:
            try:
                self.door_app.stop()
            except Exception:
                pass

        # 4. GPIO cleanup
        if GPIO_AVAILABLE:
            try:
                GPIO.cleanup()
            except Exception:
                pass

        # 5. Giải phóng frame cuối cùng trong VideoWidget
        if self.videoWidget.last_frame is not None:
            del self.videoWidget.last_frame
            self.videoWidget.last_frame = None

        # 6. Buộc GC chạy lần cuối
        gc.collect()

        event.accept()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart Lab 7-inch touchscreen UI Monitor")
    parser.add_argument("--yolo_hef", type=str, required=True, help="Path to YOLO Face detector HEF")
    parser.add_argument("--arcface_hef", type=str, required=True, help="Path to ArcFace recognizer HEF")
    parser.add_argument("--anti_spoofing_hef", type=str, default="/home/kevinvgu/Access-Control-System/models/mobilenet_v3.hef", help="Path to Anti-Spoofing NPU HEF")
    parser.add_argument("--db_dir", type=str, required=True, help="Database folder directory containing SQLite database and photos")
    parser.add_argument("--lbf_model", type=str, required=True, help="Path to LBF Facemark configuration YAML")
    parser.add_argument("--close_thresh", type=int, default=130, help="Minimum face size close distance threshold")
    parser.add_argument("--cam_width", type=int, default=640, help="Camera resolution width")
    parser.add_argument("--cam_height", type=int, default=480, help="Camera resolution height")
    parser.add_argument("--cam_source", type=str, default="0", help="Camera source dev number or path")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    monitor = InterfaceMonitorApp(args)
    monitor.show()
    sys.exit(app.exec())
