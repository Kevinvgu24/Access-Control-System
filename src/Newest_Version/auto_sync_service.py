import hashlib
import os
import cv2
import time
import numpy as np
import threading

from common import letterbox_image, scale_detections_to_original
from face_engine import get_face_embedding
from database import FaceDatabase


class AutoSyncManager:
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

    def __init__(self, yolo_engine, arcface_engine, aligner, db_dir, npu_lock, on_db_update, sync_interval=1.0):
        self.yolo_engine = yolo_engine
        self.arcface_engine = arcface_engine
        self.aligner = aligner
        self.db_dir = db_dir
        self.db_path = os.path.join(db_dir, "smart_door.db")
        self.db = FaceDatabase(self.db_path)
        self.npu_lock = npu_lock
        self.on_db_update = on_db_update
        self.sync_interval = sync_interval
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.thread.start()
        print("-> [SYNC SERVICE] Auto-sync service started.")
        return self

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)

    def _sync_loop(self):
        while self.running:
            try:
                if os.path.exists(self.db_dir):
                    self._sync_once()
            except Exception as e:
                print(f"[SYNC SERVICE] Loi khi dong bo database: {e}")

            time.sleep(self.sync_interval)

    def _sync_once(self):
        known_users = self.db.load_all_users()
        sync_signatures = self.db.load_sync_signatures()
        folders = [
            f for f in os.listdir(self.db_dir)
            if os.path.isdir(os.path.join(self.db_dir, f))
        ]

        db_changed = False

        tracked_users = set(known_users) | set(sync_signatures)
        deleted_users = [u for u in tracked_users if u not in folders]
        for user_name in deleted_users:
            print(f"\n[-] HOT-RELOAD: Folder '{user_name}' was removed.")
            self.db.delete_user(user_name)
            db_changed = True

        for user_name in folders:
            user_path = os.path.join(self.db_dir, user_name)
            image_paths = self._get_image_paths(user_path)
            image_signature = self._build_image_signature(user_path, image_paths)
            has_profile = user_name in known_users
            stored_signature = sync_signatures.get(user_name)

            if stored_signature == image_signature and (has_profile or not image_paths):
                continue

            action = "Cap nhat" if has_profile else "Them moi"
            print(f"\n[*] HOT-RELOAD: {action} '{user_name}'. NPU dang quet anh...")

            if not image_paths:
                if has_profile:
                    self.db.delete_user(user_name)
                    db_changed = True
                self.db.save_sync_signature(user_name, image_signature)
                print(f"[-] Bo qua '{user_name}': khong co anh hop le.\n")
                continue

            embedding = self._build_user_embedding(user_name, image_paths)
            if embedding is None:
                print(f"[-] Bo qua '{user_name}': khong tim thay khuon mat hop le.\n")
                continue

            self.db.save_user(user_name, embedding)
            self.db.save_sync_signature(user_name, image_signature)
            db_changed = True
            print(f"[+] '{user_name}' da duoc dong bo/cap nhat quyen truy cap.\n")

        if db_changed:
            self.on_db_update()

    def _get_image_paths(self, user_path):
        image_paths = []
        for root, _, files in os.walk(user_path):
            for file_name in files:
                ext = os.path.splitext(file_name)[1].lower()
                if ext in self.IMAGE_EXTENSIONS:
                    image_paths.append(os.path.join(root, file_name))
        return sorted(image_paths)

    def _build_image_signature(self, user_path, image_paths):
        digest = hashlib.sha256()
        for img_path in image_paths:
            try:
                stat = os.stat(img_path)
            except OSError:
                continue
            rel_path = os.path.relpath(img_path, user_path).replace("\\", "/")
            digest.update(f"{rel_path}:{stat.st_size}:{stat.st_mtime_ns}\n".encode("utf-8"))
        return digest.hexdigest()

    def _build_user_embedding(self, user_name, image_paths):
        embeddings = []
        for img_path in image_paths:
            img = cv2.imread(img_path)
            if img is None:
                continue

            orig_h, orig_w = img.shape[:2]
            padded, scale, pad_w, pad_h = letterbox_image(cv2.cvtColor(img, cv2.COLOR_BGR2RGB), target_size=640)

            with self.npu_lock:
                detections, _ = self.yolo_engine.infer(
                    np.expand_dims(padded, axis=0).astype(np.uint8),
                    verbose=False,
                    conf_threshold=0.4,
                )

            if not detections:
                continue

            detections = scale_detections_to_original(detections, orig_h, orig_w, scale, pad_w, pad_h)
            best_det = max(detections, key=lambda x: x["conf"])
            ymin, xmin = int(best_det["y1"]), int(best_det["x1"])
            ymax, xmax = int(best_det["y2"]), int(best_det["x2"])
            my, mx = int((ymax - ymin) * 0.1), int((xmax - xmin) * 0.1)
            raw_face = img[
                max(0, ymin - my):min(orig_h, ymax + my),
                max(0, xmin - mx):min(orig_w, xmax + mx),
            ]

            if raw_face.size == 0:
                continue

            processed_face = self.aligner.align(raw_face)
            with self.npu_lock:
                embeddings.append(get_face_embedding(self.arcface_engine, processed_face))

        if not embeddings:
            return None

        avg_emb = np.mean(embeddings, axis=0)
        norm = np.linalg.norm(avg_emb)
        if norm == 0:
            print(f"[-] Bo qua '{user_name}': embedding co norm bang 0.")
            return None
        return avg_emb / norm
