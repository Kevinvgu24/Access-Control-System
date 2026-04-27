import cv2
import time
import numpy as np
import os
import threading

from hailo_platform import VDevice 
from common import HailoPythonInferenceEngine, letterbox_image, scale_detections_to_original

from utils import calculate_cosine_similarity, cosine_to_percentage
from hardware import HardwareMonitor
from camera import CameraStream
from face_engine import FaceAligner, FaceTracker, get_face_embedding
from database import FaceDatabase
from ui_drawer import UIDrawer
from auto_sync_service import AutoSyncManager 

class ProfessionalSmartDoor:
    def __init__(self, yolo_hef, arcface_hef, lbf_model_path, database_dir, rec_thresh=0.45):
        self.rec_thresh = rec_thresh
        
        db_path = os.path.join(database_dir, "smart_door.db")
        self.db = FaceDatabase(db_path)
        self.known_users = self.db.load_all_users()
        print(f"-> Đã nạp {len(self.known_users)} người dùng từ SQLite.")
        
        self.shared_vdevice = VDevice()
        self.yolo_engine = HailoPythonInferenceEngine(yolo_hef, target=self.shared_vdevice)
        self.arcface_engine = HailoPythonInferenceEngine(arcface_hef, target=self.shared_vdevice)
        self.aligner = FaceAligner(lbf_model_path)
        
        self.npu_lock = threading.Lock()
        
        # --- [BẢN VÁ]: KHAI BÁO CỜ BÁO HIỆU ---
        self.db_updated_flag = False 
        
        # Truyền hàm báo hiệu vào luồng ngầm
        self.sync_manager = AutoSyncManager(self.yolo_engine, self.arcface_engine, self.aligner, database_dir, self.npu_lock, self.trigger_db_update)
        self.sync_manager.start()
        
        self.tracker = FaceTracker(dist_threshold=150, max_missed=5, history_len=5)
        self.fps_history = []
        self.hw_monitor = HardwareMonitor(check_interval=2.0).start()

    # Hàm này được luồng ngầm gọi để "Vẫy cờ"
    def trigger_db_update(self):
        self.db_updated_flag = True

    def run(self):
        stream = CameraStream().start()
        print("=== HỆ THỐNG GIÁM SÁT ĐANG CHẠY ===")
        try:
            while True:
                t_start = time.perf_counter()
                
                # --- [BẢN VÁ]: KIỂM TRA CỜ BÁO HIỆU ---
                # Thay vì 10 giây nạp 1 lần, chỉ nạp khi có sự kiện thay đổi
                if self.db_updated_flag:
                    self.known_users = self.db.load_all_users()
                    self.db_updated_flag = False
                    print("-> [CAMERA] Đã nạp lại Database vào bộ nhớ NGAY LẬP TỨC!")

                ret, frame = stream.read()
                if not ret or frame is None: continue
                
                orig_h, orig_w = frame.shape[:2]
                padded, scale, pad_w, pad_h = letterbox_image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), target_size=640)
                
                with self.npu_lock:
                    detections, _ = self.yolo_engine.infer(np.expand_dims(padded, axis=0).astype(np.uint8), verbose=False, conf_threshold=0.5)
                
                self.tracker.mark_all_missed()
                
                if detections:
                    detections = scale_detections_to_original(detections, orig_h, orig_w, scale, pad_w, pad_h)
                    for det in detections:
                        ymin, xmin, ymax, xmax = int(det['y1']), int(det['x1']), int(det['y2']), int(det['x2'])
                        cx, cy = (xmin + xmax) // 2, (ymin + ymax) // 2
                        my, mx = int((ymax - ymin) * 0.1), int((xmax - xmin) * 0.1)
                        raw_face = frame[max(0, ymin - my):min(orig_h, ymax + my), max(0, xmin - mx):min(orig_w, xmax + mx)]
                        if raw_face.size == 0: continue
                        
                        processed_face = self.aligner.align(raw_face)
                        
                        with self.npu_lock:
                            curr_emb = get_face_embedding(self.arcface_engine, processed_face)
                            
                        _, smoothed_emb = self.tracker.update_track(cx, cy, curr_emb)
                        
                        best_name, best_sim = "Unknown", 0.0
                        for db_name, db_emb in self.known_users.items():
                            sim = calculate_cosine_similarity(db_emb, smoothed_emb)
                            if sim > best_sim: best_sim, best_name = sim, db_name
                                
                        conf = cosine_to_percentage(best_sim, self.rec_thresh)
                        color = (0, 255, 0) if best_sim > self.rec_thresh else (0, 0, 255)
                        
                        UIDrawer.draw_bounding_box(frame, xmin, ymin, xmax, ymax, f"{best_name} ({conf:.1f}%)", color)

                self.tracker.cleanup_lost_tracks()
                t_end = time.perf_counter()
                
                self.fps_history.append(1.0 / (t_end - t_start))
                if len(self.fps_history) > 15: self.fps_history.pop(0)
                fps = sum(self.fps_history) / len(self.fps_history)
                
                UIDrawer.draw_system_stats(frame, fps, self.hw_monitor.cpu_temp, self.hw_monitor.hailo_temp)
                
                cv2.imshow("Smart Lab Door", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'): break
        finally:
            stream.stop()
            self.hw_monitor.stop()
            cv2.destroyAllWindows()
