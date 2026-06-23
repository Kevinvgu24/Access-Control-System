import os
# pyrefly: ignore [missing-import]
import cv2
import time
import glob
import numpy as np
import threading

from common import letterbox_image, scale_detections_to_original
from face_engine import get_face_embedding
from database import FaceDatabase

# Yield duration (seconds) between inferences
_SYNC_YIELD_S = 0.04

class AutoSyncManager:
    def __init__(self, yolo_hef, arcface_hef, aligner, db_dir, npu_lock, on_db_update):
        self.yolo_hef      = yolo_hef
        self.arcface_hef   = arcface_hef
        self.aligner        = aligner
        self.db_dir         = db_dir
        self.db_path        = os.path.join(db_dir, "smart_door.db")
        self.db             = FaceDatabase(self.db_path)
        self.npu_lock       = npu_lock
        self.on_db_update   = on_db_update
        self.running        = False

    def start(self):
        self.running = True
        threading.Thread(target=self._sync_loop, daemon=True).start()
        print("-> [SYNC SERVICE] Hot-reload watcher started.")

    def _get_folder_mtimes(self) -> dict[str, float]:
        """Snapshot of {folder_name: mtime} — cheap OS stat, no disk reads."""
        result = {}
        try:
            for entry in os.scandir(self.db_dir):
                if entry.is_dir():
                    result[entry.name] = entry.stat().st_mtime
        except OSError:
            pass
        return result

    def _sync_loop(self):
        # Initialise mtime snapshot from current disk state
        last_mtimes: dict[str, float] = self._get_folder_mtimes()
        # Load DB once at startup
        known_users: dict = self.db.load_all_users()

        while self.running:
            time.sleep(1)

            current_mtimes = self._get_folder_mtimes()

            # Fast path: if nothing changed on disk, skip everything
            if current_mtimes == last_mtimes:
                continue

            # Something changed — compute diff without touching the database
            current_folders = set(current_mtimes.keys())
            known_set       = set(known_users.keys())

            db_changed = False

            # ── Detect deleted folders ────────────────────────────────────────
            deleted_folders = known_set - current_folders
            for user_name in deleted_folders:
                print(f"\n[-] HOT-RELOAD: '{user_name}' folder removed — revoking access.")
                self.db.delete_user(user_name)
                known_users.pop(user_name, None)
                db_changed = True

            # ── Detect new folders ────────────────────────────────────────────
            new_folders = current_folders - known_set
            if new_folders:
                print(f"\n[*] HOT-RELOAD: New folders {list(new_folders)} detected. Attempting to allocate NPU context for enrollment...")
                
                try:
                    from hailo_platform import VDevice
                    from common import HailoPythonInferenceEngine

                    # Dynamically allocate NPU context for offline syncing
                    temp_vdevice = VDevice()
                    temp_yolo = HailoPythonInferenceEngine(self.yolo_hef, target=temp_vdevice)
                    temp_arcface = HailoPythonInferenceEngine(self.arcface_hef, target=temp_vdevice)

                    for user_name in new_folders:
                        print(f"[*] Scanning biometric patterns for user: '{user_name}'...")
                        user_path   = os.path.join(self.db_dir, user_name)
                        image_paths = (
                            glob.glob(os.path.join(user_path, '*.[jp][pn]g')) +
                            glob.glob(os.path.join(user_path, '*.[JP][PN]G'))
                        )

                        embeddings = []
                        for img_path in image_paths:
                            img = cv2.imread(img_path)
                            if img is None:
                                continue

                            orig_h, orig_w = img.shape[:2]
                            padded, scale, pad_w, pad_h = letterbox_image(
                                cv2.cvtColor(img, cv2.COLOR_BGR2RGB), target_size=640
                            )

                            with self.npu_lock:
                                detections, _ = temp_yolo.infer(
                                    np.expand_dims(padded, axis=0).astype(np.uint8),
                                    verbose=False, conf_threshold=0.4
                                )
                            time.sleep(_SYNC_YIELD_S)

                            if not detections:
                                continue

                            detections = scale_detections_to_original(
                                detections, orig_h, orig_w, scale, pad_w, pad_h
                            )
                            best_det = max(detections, key=lambda x: x['conf'])
                            ymin = int(best_det['y1']); xmin = int(best_det['x1'])
                            ymax = int(best_det['y2']); xmax = int(best_det['x2'])
                            my = int((ymax - ymin) * 0.1)
                            mx = int((xmax - xmin) * 0.1)
                            raw_face = img[
                                max(0, ymin - my) : min(orig_h, ymax + my),
                                max(0, xmin - mx) : min(orig_w, xmax + mx),
                            ]
                            if raw_face.size == 0:
                                continue

                            if 'landmarks' in best_det and len(best_det['landmarks']) >= 5:
                                processed_face = self.aligner.align_with_landmarks(img, best_det['landmarks'])
                                if processed_face is None:
                                    processed_face = self.aligner.align(raw_face)
                            else:
                                processed_face = self.aligner.align(raw_face)

                            with self.npu_lock:
                                embeddings.append(get_face_embedding(temp_arcface, processed_face))
                            time.sleep(_SYNC_YIELD_S)

                        if embeddings:
                            avg_emb = np.mean(embeddings, axis=0)
                            norm_emb = avg_emb / np.linalg.norm(avg_emb)
                            self.db.save_user(user_name, norm_emb)
                            known_users[user_name] = norm_emb
                            print(f"[+] '{user_name}' enrolled successfully.\n")
                            db_changed = True
                        else:
                            print(f"[-] Skipped '{user_name}': no face detected.\n")

                    # Gracefully clean up/release NPU context
                    del temp_yolo
                    del temp_arcface
                    del temp_vdevice
                    print("-> [SYNC SERVICE] Temporary NPU context released.")

                except Exception as e:
                    print(f"\n[-] HOT-RELOAD WARNING: Cannot run enrollment for new folders. The NPU device is currently occupied by the live stream.")
                    print(f"    Error details: {e}")
                    print(f"    Please enroll new users using 'register.py' when the live stream is not running.\n")

            # Update mtime snapshot
            last_mtimes = current_mtimes

            if db_changed:
                self.on_db_update()
