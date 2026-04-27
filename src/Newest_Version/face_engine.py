import cv2
import numpy as np
import math
import os
import sys

# Tọa độ tỷ lệ vàng của ArcFace
ARCFACE_REFERENCE_5PTS = np.array([
    [38.2946, 51.6963],  [73.5318, 51.5014],  
    [56.0252, 71.7366],  [41.5493, 92.3655],  [70.7299, 92.2041]   
], dtype=np.float32)

# --- CHUYỂN TỪ MAIN SANG ---
def get_face_embedding(engine, image):
    """Trích xuất Vector 512 chiều từ NPU Hailo"""
    if image.shape[:2] != (112, 112): image = cv2.resize(image, (112, 112))
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    input_tensor = np.expand_dims(rgb, axis=0).astype(np.uint8)
    raw_output, _ = engine.infer(input_tensor, verbose=False, task='recognition')
    if isinstance(raw_output, list): emb = raw_output[0]
    elif isinstance(raw_output, dict): emb = list(raw_output.values())[0]
    else: emb = raw_output
    return emb.flatten()

class FaceAligner:
    # (Giữ nguyên code class FaceAligner cũ của bạn)
    def __init__(self, lbf_model_path):
        if not os.path.exists(lbf_model_path):
            print(f"[LỖI PYTHON]: Đường dẫn '{lbf_model_path}' KHÔNG TỒN TẠI!")
            sys.exit(1)
        try:
            self.facemark = cv2.face.createFacemarkLBF()
            self.facemark.loadModel(lbf_model_path)
        except Exception as e:
            print(f"[LỖI OPENCV]: Không thể đọc lbfmodel.yaml. Chi tiết: {e}")
            sys.exit(1)

    def align(self, raw_face_crop):
        gray = cv2.cvtColor(raw_face_crop, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        bbox = np.array([[0, 0, w, h]], dtype=np.int32)
        ok, landmarks = self.facemark.fit(gray, bbox)
        if not ok or landmarks is None: return cv2.resize(raw_face_crop, (112, 112))
        pts = landmarks[0][0]
        landmarks_5pts = np.array([
            np.mean(pts[36:42], axis=0), np.mean(pts[42:48], axis=0),
            pts[30], pts[48], pts[54]
        ], dtype=np.float32)
        matrix, _ = cv2.estimateAffinePartial2D(landmarks_5pts, ARCFACE_REFERENCE_5PTS, method=cv2.LMEDS)
        if matrix is None: return cv2.resize(raw_face_crop, (112, 112))
        return cv2.warpAffine(raw_face_crop, matrix, (112, 112), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0))

class FaceTracker:
    # (Giữ nguyên code class FaceTracker cũ của bạn)
    def __init__(self, dist_threshold=150, max_missed=5, history_len=5):
        self.active_tracks = {}
        self.next_track_id = 0
        self.dist_threshold = dist_threshold
        self.max_missed = max_missed
        self.history_len = history_len

    def mark_all_missed(self):
        for t_id in list(self.active_tracks.keys()): self.active_tracks[t_id]['missed'] += 1

    def update_track(self, cx, cy, current_embedding):
        best_id = None
        min_dist = float('inf')
        for t_id, t_info in self.active_tracks.items():
            dist = math.hypot(cx - t_info['centroid'][0], cy - t_info['centroid'][1])
            if dist < self.dist_threshold and dist < min_dist:
                min_dist = dist; best_id = t_id

        if best_id is not None:
            self.active_tracks[best_id]['centroid'] = (cx, cy)
            self.active_tracks[best_id]['embs'].append(current_embedding)
            if len(self.active_tracks[best_id]['embs']) > self.history_len: self.active_tracks[best_id]['embs'].pop(0)
            self.active_tracks[best_id]['missed'] = 0
            track_id = best_id
        else:
            track_id = self.next_track_id
            self.next_track_id += 1
            self.active_tracks[track_id] = {'centroid': (cx, cy), 'embs': [current_embedding], 'missed': 0}

        smoothed_emb = np.mean(self.active_tracks[track_id]['embs'], axis=0)
        smoothed_emb = smoothed_emb / np.linalg.norm(smoothed_emb)
        return track_id, smoothed_emb

    def cleanup_lost_tracks(self):
        self.active_tracks = {k: v for k, v in self.active_tracks.items() if v['missed'] < self.max_missed}
