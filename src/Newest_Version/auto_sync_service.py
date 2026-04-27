import os
import cv2
import time
import glob
import numpy as np
import threading

from common import letterbox_image, scale_detections_to_original
from face_engine import get_face_embedding
from database import FaceDatabase

class AutoSyncManager:
    # --- [BẢN VÁ]: Nhận thêm hàm callback (on_db_update) từ hệ thống chính ---
    def __init__(self, yolo_engine, arcface_engine, aligner, db_dir, npu_lock, on_db_update):
        self.yolo_engine = yolo_engine
        self.arcface_engine = arcface_engine
        self.aligner = aligner
        self.db_dir = db_dir
        self.db_path = os.path.join(db_dir, "smart_door.db")
        self.db = FaceDatabase(self.db_path)
        self.npu_lock = npu_lock
        self.on_db_update = on_db_update  # Hàm dùng để vẫy cờ
        self.running = False

    def start(self):
        self.running = True
        threading.Thread(target=self._sync_loop, daemon=True).start()
        print("-> [SYNC SERVICE] Trình quản lý Đồng bộ Siêu tốc (1s) đã khởi chạy!")

    def _sync_loop(self):
        while self.running:
            if not os.path.exists(self.db_dir):
                time.sleep(1)
                continue

            known_users = self.db.load_all_users()
            folders = [f for f in os.listdir(self.db_dir) if os.path.isdir(os.path.join(self.db_dir, f))]
            
            db_changed = False # Cờ theo dõi xem vòng lặp này có thay đổi gì không
            
            # 1. TÌM NGƯỜI BỊ XÓA THƯ MỤC
            deleted_users = [u for u in known_users if u not in folders]
            for user_name in deleted_users:
                print(f"\n[-] HOT-RELOAD: Phát hiện thư mục '{user_name}' đã biến mất.")
                self.db.delete_user(user_name)
                db_changed = True # Đánh dấu là có thay đổi
            
            # 2. TÌM NGƯỜI MỚI THÊM THƯ MỤC
            new_users = [u for u in folders if u not in known_users]
            for user_name in new_users:
                print(f"\n[*] HOT-RELOAD: Phát hiện '{user_name}'. NPU đang chuẩn bị quét...")
                user_path = os.path.join(self.db_dir, user_name)
                image_paths = glob.glob(os.path.join(user_path, '*.[jp][pn]g')) + glob.glob(os.path.join(user_path, '*.[JP][PN]G'))
                
                embeddings = []
                for img_path in image_paths:
                    img = cv2.imread(img_path)
                    if img is None: continue
                    orig_h, orig_w = img.shape[:2]
                    padded, scale, pad_w, pad_h = letterbox_image(cv2.cvtColor(img, cv2.COLOR_BGR2RGB), target_size=640)
                    
                    with self.npu_lock:
                        detections, _ = self.yolo_engine.infer(np.expand_dims(padded, axis=0).astype(np.uint8), verbose=False, conf_threshold=0.4)
                    
                    if detections:
                        detections = scale_detections_to_original(detections, orig_h, orig_w, scale, pad_w, pad_h)
                        best_det = max(detections, key=lambda x: x['conf'])
                        ymin, xmin, ymax, xmax = int(best_det['y1']), int(best_det['x1']), int(best_det['y2']), int(best_det['x2'])
                        my, mx = int((ymax - ymin) * 0.1), int((xmax - xmin) * 0.1)
                        raw_face = img[max(0, ymin - my):min(orig_h, ymax + my), max(0, xmin - mx):min(orig_w, xmax + mx)]
                        
                        if raw_face.size > 0:
                            processed_face = self.aligner.align(raw_face)
                            with self.npu_lock:
                                embeddings.append(get_face_embedding(self.arcface_engine, processed_face))

                if embeddings:
                    avg_emb = np.mean(embeddings, axis=0)
                    self.db.save_user(user_name, avg_emb / np.linalg.norm(avg_emb))
                    print(f"[+] '{user_name}' đã được cấp quyền truy cập.\n")
                    db_changed = True # Đánh dấu là có thay đổi
                else:
                    print(f"[-] Bỏ qua '{user_name}': Không tìm thấy mặt.\n")

            # NẾU CÓ THAY ĐỔI, VẪY CỜ BÁO CHO CAMERA BIẾT
            if db_changed:
                self.on_db_update()

            # Giảm thời gian chờ xuống 1 giây để phản ứng cực nhanh
            time.sleep(1)
