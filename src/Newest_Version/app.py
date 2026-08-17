import time
import os
import sys
os.environ["HAILORT_LOGGER_PATH"] = "NONE"
import numpy as np
import gc
import cv2
import ctypes

# GStreamer and GLib Imports
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import hailo

from utils import cosine_to_percentage
from hardware import HardwareMonitor
from database import FaceDatabase

# Access log → Firestore (fail-safe, non-blocking). Config via ACS_* env vars.
import threading
try:
    import firebase_admin
    from firebase_admin import credentials, firestore as _fb_firestore
except Exception:
    firebase_admin = None
    _fb_firestore = None

ACS_SERVICE_ACCOUNT = os.environ.get(
    "ACS_SERVICE_ACCOUNT",
    "/home/kevinvgu/Access-Control-System/serviceAccountKey.json",
)
ACS_LAB_ID       = os.environ.get("ACS_LAB_ID", "")
ACS_CLUSTER_ID   = os.environ.get("ACS_CLUSTER_ID", "")
ACS_NODE_ID      = os.environ.get("ACS_NODE_ID", "")
ACS_LOG_COOLDOWN = 10.0

_fs_db       = None
_last_logged = {}
_log_lock    = threading.Lock()


def _init_access_log():
    global _fs_db
    if _fs_db is not None:
        return _fs_db
    if firebase_admin is None or not ACS_LAB_ID:
        return None
    if not os.path.exists(ACS_SERVICE_ACCOUNT):
        print(f"[access-log] skip: no service account at {ACS_SERVICE_ACCOUNT}")
        return None
    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app(credentials.Certificate(ACS_SERVICE_ACCOUNT))
        _fs_db = _fb_firestore.client()
    except Exception as e:
        print(f"[access-log] init failed (skip): {e}")
        _fs_db = None
    return _fs_db


def _write_access_event(name, class_id, confidence):
    try:
        client = _init_access_log()
        if client is None:
            return
        client.collection("labs").document(ACS_LAB_ID) \
            .collection("accessEvents").add({
                "occurredAt":   _fb_firestore.SERVER_TIMESTAMP,
                "displayName":  name if class_id == 0 else None,
                "universityId": None,
                "method":       "face",
                "result":       "granted" if class_id == 0 else "denied",
                "confidence":   float(confidence),
                "reason":       "recognized" if class_id == 0 else "unknown_face",
                "nodeId":       ACS_NODE_ID,
                "clusterId":    ACS_CLUSTER_ID,
            })
    except Exception as e:
        print(f"[access-log] write failed (skip): {e}")


def log_access_event(name, class_id, confidence):
    if firebase_admin is None or not ACS_LAB_ID:
        return
    key = name if class_id == 0 else "__unknown__"
    now = time.time()
    with _log_lock:
        if now - _last_logged.get(key, 0.0) < ACS_LOG_COOLDOWN:
            return
        _last_logged[key] = now
    threading.Thread(
        target=_write_access_event, args=(name, class_id, confidence), daemon=True
    ).start()

# [CĂN CHỈNH] Tọa độ 5 điểm tham chiếu chuẩn của ArcFace MobileFaceNet (112×112)
# Thứ tự: mắt trái, mắt phải, mũi, miệng trái, miệng phải
ARCFACE_REFERENCE_5PTS = np.array([
    [38.2946, 51.6963],
    [73.5318, 51.5014],
    [56.0252, 71.7366],
    [41.5493, 92.3655],
    [70.7299, 92.2041]
], dtype=np.float32)

class GstMapInfo(ctypes.Structure):
    _fields_ = [
        ("memory", ctypes.c_void_p),
        ("flags", ctypes.c_int),
        ("data", ctypes.c_void_p),
        ("size", ctypes.c_size_t),
        ("maxsize", ctypes.c_size_t),
        ("user_data", ctypes.c_void_p * 4),
        ("_gst_reserved", ctypes.c_void_p * 4)
    ]

try:
    libgst = ctypes.CDLL("libgstreamer-1.0.so.0")
except OSError:
    libgst = ctypes.CDLL("libgstreamer-1.0.so")

libgst.gst_buffer_map.argtypes = [ctypes.c_void_p, ctypes.POINTER(GstMapInfo), ctypes.c_int]
libgst.gst_buffer_map.restype = ctypes.c_bool
libgst.gst_buffer_unmap.argtypes = [ctypes.c_void_p, ctypes.POINTER(GstMapInfo)]
libgst.gst_buffer_unmap.restype = None

class ProfessionalSmartDoor:
    def __init__(self, yolo_hef, arcface_hef, anti_spoofing_hef, lbf_model_path, database_dir, rec_thresh=0.45, close_thresh=130):
        self.yolo_hef = yolo_hef
        self.arcface_hef = arcface_hef
        self.rec_thresh = rec_thresh
        self.close_thresh = close_thresh
        self.stationary_max_dist = 20

        # Load DB
        self.db_path = os.path.join(database_dir, "smart_door.db")
        self.db = FaceDatabase(self.db_path)
        self.known_users = self.db.load_all_users()
        print(f"-> Loaded {len(self.known_users)} users from SQLite.")

        # Rebuild matrix
        self._known_names = []
        self._known_matrix = None
        self._rebuild_db_matrix()
        self._sync_db_to_binary()

        # Monitor DB file modification time for cross-process hot-reloads
        self._last_db_mtime = self._get_db_mtime()

        # Hardware Monitor
        self.hw_monitor = HardwareMonitor(check_interval=2.0).start()

        # Pipeline variables
        self.pipeline = None
        self.loop = None
        self.stats_overlay = None
        self._frame_count = 0
        self._fps_start_time = time.time()
        self._fps = 0.0
        self.recognition_callback = None
        self.recognition_enabled = True
        # [OPT] Cache appsink frame dimensions — caps.get_structure() mỗi frame là lãng phí
        self._cached_appsink_size = None

    def _get_db_mtime(self):
        try:
            return os.stat(self.db_path).st_mtime
        except Exception:
            return 0.0

    def _rebuild_db_matrix(self):
        """Build L2-normalised (N×512) matrix for one-shot vectorised search."""
        if not self.known_users:
            self._known_names = []
            self._known_matrix = None
            return
        names = list(self.known_users.keys())
        vecs = np.stack(list(self.known_users.values())).astype(np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        self._known_names = names
        self._known_matrix = vecs / np.where(norms > 0, norms, 1.0)

    def _sync_db_to_binary(self):
        """
        [CHỨC NĂNG] Đồng bộ cơ sở dữ liệu người dùng từ SQLite ra một tệp nhị phân phẳng (db.bin).
        [LIÊN KẾT] Tệp db.bin này sẽ được bộ so khớp C++ (libdb_matcher_post.so) đọc vào bộ nhớ 
                  ở tầng GStreamer để so khớp vector embedding với tốc độ cao bằng ngôn ngữ C++.
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        workspace_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
        bin_path = os.path.join(workspace_dir, "scratch", "db.bin")
        try:
            os.makedirs(os.path.dirname(bin_path), exist_ok=True)
            with open(bin_path, "wb") as f:
                n = len(self.known_users)
                # Ghi số lượng người dùng (int32)
                f.write(np.int32(n).tobytes())
                for name, emb in self.known_users.items():
                    # Ghi tên người dùng cố định 64 bytes (null-padded)
                    name_bytes = name.encode('utf-8')[:63]
                    name_bytes = name_bytes + b'\x00' * (64 - len(name_bytes))
                    f.write(name_bytes)
                    # Ghi vector embedding 512 chiều (float32)
                    f.write(emb.astype(np.float32).tobytes())
            print(f"-> Synced {n} users to {bin_path} for C++ DB Matcher.")
        except Exception as e:
            print(f"[ERROR] Failed to sync DB to binary: {e}")

    def _search_db(self, embedding: np.ndarray) -> tuple[str, float]:
        """
        [CHỨC NĂNG] Hàm dự phòng so khớp cơ sở dữ liệu bằng Python (sử dụng nhân ma trận BLAS).
        [LIÊN KẾT] Chỉ dùng khi cần gọi so khớp trực tiếp trong Python (không tham gia vào live pipeline).
        """
        if self._known_matrix is None:
            return "Unknown", 0.0
        # Chuẩn hóa vector đầu vào
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        sims = self._known_matrix @ embedding.astype(np.float32)  # shape (N,)
        idx = int(np.argmax(sims))
        best_sim = float(sims[idx])
        if best_sim >= self.rec_thresh:
            return self._known_names[idx], best_sim
        else:
            return "Unknown", best_sim

    def on_new_frame_probe(self, pad, info, user_data):
        buffer = info.get_buffer()
        if buffer is None:
            return Gst.PadProbeReturn.OK

        # [CHỨC NĂNG] Tự động tải lại cơ sở dữ liệu khi có cập nhật từ tiến trình đăng ký khuôn mặt khác (như register.py)
        # [LIÊN KẾT] Kiểm tra mtime của file SQLite -> cập nhật RAM matrix -> đồng bộ lại file db.bin để bộ so khớp C++ nạp lại.
        current_mtime = self._get_db_mtime()
        if current_mtime != self._last_db_mtime:
            self.known_users = self.db.load_all_users()
            self._rebuild_db_matrix()
            self._sync_db_to_binary()
            self._last_db_mtime = current_mtime
            print("-> [GStreamer] Database update detected! Reloaded search matrix and synced to binary.")

        # Calculate FPS
        self._frame_count += 1
        now = time.time()
        elapsed = now - self._fps_start_time
        if elapsed >= 1.0:
            self._fps = self._frame_count / elapsed
            self._frame_count = 0
            self._fps_start_time = now

            # Update stats overlay text (every 1 second)
            if self.stats_overlay:
                cpu_t = self.hw_monitor.cpu_temp
                hailo_t = self.hw_monitor.hailo_temp
                ram_mb = self.hw_monitor.ram_mb
                stats_text = f"FPS: {self._fps:.1f} | CPU: {cpu_t:.1f}C | Hailo: {hailo_t:.1f}C | RAM: {ram_mb:.1f}MB"
                self.stats_overlay.set_property("text", stats_text)
            
            # Force immediate garbage collection of PyGObject wrappers
            gc.collect()

        # [CHỨC NĂNG] Nhận danh sách các đối tượng khuôn mặt (Detections) từ metadata của buffer
        # [LIÊN KẾT] Các đối tượng này được sinh ra từ yolo26_landmark_post.cpp và cập nhật bởi db_matcher_post.cpp
        roi = hailo.get_roi_from_buffer(buffer)
        detections = roi.get_objects_typed(hailo.HAILO_DETECTION)
        
        # Lấy kích thước hiện tại của khung hình video
        caps = pad.get_current_caps()
        if caps:
            structure = caps.get_structure(0)
            w = structure.get_int("width")[1]
            h = structure.get_int("height")[1]
        else:
            w, h = 640, 640

        # [CHỨC NĂNG] Ánh xạ bộ nhớ đệm GStreamer thô bằng ctypes (Zero-Copy) để cho phép vẽ đè trong Python
        # [LIÊN KẾT] Khắc phục lỗi PyGObject cấm ghi đè vùng nhớ (ReadOnly), giúp OpenCV vẽ HUD trực tiếp cực nhanh
        if getattr(self, "recognition_enabled", True):
            buf_ptr = hash(buffer)
            map_info = GstMapInfo()
            success = libgst.gst_buffer_map(buf_ptr, ctypes.byref(map_info), 1)
            if success:
                try:
                    # Ép kiểu dữ liệu sang con trỏ byte C và bọc thành mảng NumPy (Không nhân bản vùng nhớ)
                    data_ptr = ctypes.cast(map_info.data, ctypes.POINTER(ctypes.c_ubyte))
                    arr = np.ctypeslib.as_array(data_ptr, shape=(h, w, 3))
                    
                    detections_info = []
                    for det in detections:
                        bbox = det.get_bbox()
                        xmin = bbox.xmin()
                        ymin = bbox.ymin()
                        w_box = bbox.width()
                        h_box = bbox.height()
                        
                        # Chuyển đổi tọa độ bbox từ tỉ lệ (%) sang pixel thực tế của khung hình
                        x1 = int(xmin * w)
                        y1 = int(ymin * h)
                        x2 = int((xmin + w_box) * w)
                        y2 = int((ymin + h_box) * h)
                        
                        # Giới hạn tọa độ trong biên khung hình tránh crash OpenCV
                        x1 = max(0, min(x1, w - 1))
                        y1 = max(0, min(y1, h - 1))
                        x2 = max(0, min(x2, w - 1))
                        y2 = max(0, min(y2, h - 1))
                        
                        # Lấy class_id từ C++ DB Matcher: 0 = Đã nhận diện (Xanh lá), 1 = Unknown (Đỏ)
                        class_id = det.get_class_id()
                        label = det.get_label()
                        
                        color = (0, 255, 0) if class_id == 0 else (0, 0, 255)
                        
                        # Vẽ góc Sci-Fi nổi bật (2 đoạn thẳng ngắn ở mỗi góc vuông của Bounding Box)
                        length = int(min(x2 - x1, y2 - y1) * 0.18)
                        length = max(10, min(length, 30))
                        thickness = 3
                        
                        # Góc trên bên trái
                        cv2.line(arr, (x1, y1), (x1 + length, y1), color, thickness)
                        cv2.line(arr, (x1, y1), (x1, y1 + length), color, thickness)
                        # Góc trên bên phải
                        cv2.line(arr, (x2, y1), (x2 - length, y1), color, thickness)
                        cv2.line(arr, (x2, y1), (x2, y1 + length), color, thickness)
                        # Góc dưới bên trái
                        cv2.line(arr, (x1, y2), (x1 + length, y2), color, thickness)
                        cv2.line(arr, (x1, y2), (x1, y2 - length), color, thickness)
                        # Góc dưới bên phải
                        cv2.line(arr, (x2, y2), (x2 - length, y2), color, thickness)
                        cv2.line(arr, (x2, y2), (x2, y2 - length), color, thickness)
                        
                        # [LIÊN KẾT] Đọc kết quả phân lớp "recognition" được đính kèm bởi db_matcher_post.cpp
                        display_text = label
                        rec_confidence = 0.0
                        for sub in det.get_objects():
                            if isinstance(sub, hailo.HailoClassification):
                                if sub.get_classification_type() == "recognition":
                                    display_text = sub.get_label()
                                    try:
                                        rec_confidence = sub.get_confidence()
                                    except Exception:
                                        rec_confidence = 0.0
                                    break

                        log_access_event(display_text, class_id, rec_confidence)

                        # Vẽ nhãn tên kèm phần trăm tương đồng lên phía trên bounding box (có đổ bóng viền đen dễ nhìn)
                        font = cv2.FONT_HERSHEY_SIMPLEX
                        font_scale = 0.55
                        text_thickness = 2
                        cv2.putText(arr, display_text, (x1, y1 - 8), font, font_scale, (0, 0, 0), text_thickness + 2, cv2.LINE_AA)
                        cv2.putText(arr, display_text, (x1, y1 - 8), font, font_scale, color, text_thickness, cv2.LINE_AA)
                        
                        # [LIÊN KẾT] Vẽ các điểm landmarks (5 điểm mốc) được sinh ra từ mô hình YOLOv8-Face
                        for sub in det.get_objects():
                            if isinstance(sub, hailo.HailoLandmarks):
                                for pt in sub.get_points():
                                    px = int(x1 + pt.x() * (x2 - x1))
                                    py = int(y1 + pt.y() * (y2 - y1))
                                    px = max(0, min(px, w - 1))
                                    py = max(0, min(py, h - 1))
                                    cv2.circle(arr, (px, py), 3, (255, 0, 255), -1)
                        
                        detections_info.append({
                            "class_id": class_id,
                            "label": display_text
                        })
                        
                    if len(detections_info) > 0 and self.recognition_callback is not None:
                        self.recognition_callback(detections_info)
                finally:
                    libgst.gst_buffer_unmap(buf_ptr, ctypes.byref(map_info))

        return Gst.PadProbeReturn.OK

    def on_face_crop_probe(self, pad, info, user_data):
        """
        [CĂN CHỈNH KHUÔN MẶT] Python pad probe trên queue_align.src
        Thực hiện Affine alignment bằng 5 điểm landmark YOLO trước khi ArcFace NPU
        trích xuất embedding. Dùng ctypes để ghi trực tiếp vào buffer 112×112.
        Fallback an toàn: nếu thiếu landmark hoặc ma trận không hợp lệ → giữ nguyên ảnh.
        """
        buffer = info.get_buffer()
        if buffer is None:
            return Gst.PadProbeReturn.OK

        # Lấy HailoROI từ sub-buffer của hailocropper
        try:
            roi = hailo.get_roi_from_buffer(buffer)
        except Exception:
            return Gst.PadProbeReturn.OK

        # Tìm HailoLandmarks trong metadata
        landmarks_pts = None
        for obj in roi.get_objects():
            if isinstance(obj, hailo.HailoLandmarks):
                pts = obj.get_points()
                if len(pts) >= 5:
                    landmarks_pts = [[pt.x(), pt.y()] for pt in pts[:5]]
                break

        if not landmarks_pts:
            return Gst.PadProbeReturn.OK

        # Map buffer với ctypes để ghi trực tiếp (giống on_new_frame_probe)
        buf_ptr = hash(buffer)
        map_info = GstMapInfo()
        success = libgst.gst_buffer_map(buf_ptr, ctypes.byref(map_info), 1)
        if not success:
            return Gst.PadProbeReturn.OK

        try:
            data_ptr = ctypes.cast(map_info.data, ctypes.POINTER(ctypes.c_ubyte))
            arr = np.ctypeslib.as_array(data_ptr, shape=(112, 112, 3))

            # Scale landmark [0,1] → pixel trong không gian 112×112
            src_pts = np.array(
                [[pt[0] * 112.0, pt[1] * 112.0] for pt in landmarks_pts],
                dtype=np.float32
            )

            M, _ = cv2.estimateAffinePartial2D(
                src_pts, ARCFACE_REFERENCE_5PTS, method=cv2.LMEDS
            )

            if M is not None:
                scale = np.sqrt(M[0, 0]**2 + M[0, 1]**2)
                if 0.5 <= scale <= 2.0:
                    aligned = cv2.warpAffine(
                        arr.copy(), M, (112, 112),
                        flags=cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_CONSTANT,
                        borderValue=(0, 0, 0)
                    )
                    np.copyto(arr, aligned)
        except Exception:
            pass  # Fallback: giữ nguyên ảnh thô
        finally:
            libgst.gst_buffer_unmap(buf_ptr, ctypes.byref(map_info))

        return Gst.PadProbeReturn.OK

    def on_new_appsink_sample(self, appsink, callback):
        sample = appsink.emit("pull-sample")
        if sample:
            buffer = sample.get_buffer()

            # [OPT] Cache (w, h) sau lần đọc đầu tiên — caps không thay đổi khi pipeline PLAYING
            if self._cached_appsink_size is None:
                caps = sample.get_caps()
                if caps:
                    structure = caps.get_structure(0)
                    self._cached_appsink_size = (
                        structure.get_int("width")[1],
                        structure.get_int("height")[1]
                    )
                else:
                    self._cached_appsink_size = (640, 640)
            w, h = self._cached_appsink_size

            buf_ptr = hash(buffer)
            map_info = GstMapInfo()
            success = libgst.gst_buffer_map(buf_ptr, ctypes.byref(map_info), 1)
            if success:
                try:
                    data_ptr = ctypes.cast(map_info.data, ctypes.POINTER(ctypes.c_ubyte))
                    arr = np.ctypeslib.as_array(data_ptr, shape=(h, w, 3))
                    callback(arr.copy())
                except Exception as e:
                    print(f"[ERROR] Appsink frame mapping failed: {e}")
                finally:
                    libgst.gst_buffer_unmap(buf_ptr, ctypes.byref(map_info))
        return Gst.FlowReturn.OK

    def run(self, width=640, height=480, source="0", headless=False, appsink_callback=None):
        Gst.init(None)

        # Determine source type and build the source string directly
        is_live = str(source).isdigit() or str(source).startswith("/dev/video")
        
        if is_live:
            dev = f"/dev/video{source}" if str(source).isdigit() else source
            # Direct MJPG Software pipeline configuration: most robust for USB webcams at 1920x1080
            source_str = (
                f"v4l2src device={dev} ! "
                f"image/jpeg, width={width}, height={height}, framerate=30/1 ! "
                f"jpegdec ! "
                f"videoconvert n-threads=2 ! "
                f"videoscale n-threads=2 ! "
                f"video/x-raw, width=640, height=640, format=RGB"
            )
            selected_name = "MJPG Software (Software Decoding/Scaling/Conversion)"
        else:
            source_str = (
                f"filesrc location=\"{source}\" ! decodebin ! "
                f"videoconvert n-threads=2 ! "
                f"videoscale n-threads=2 ! "
                f"video/x-raw, width=640, height=640, format=RGB"
            )
            selected_name = "File Software (Software Scaling/Conversion)"

        # Sink configuration
        use_headless = headless or "DISPLAY" not in os.environ
        sync_val = "false" if is_live else "true"
        if appsink_callback is not None:
            display_str = f"videoconvert n-threads=2 ! video/x-raw, format=RGB ! appsink name=appsink sync={sync_val} emit-signals=true max-buffers=1 drop=true"
        elif use_headless:
            display_str = f"fakesink sync={sync_val} name=sink"
        else:
            display_str = f"videoconvert n-threads=2 ! autovideosink sync={sync_val} name=sink"

        # Khai báo đường dẫn đến các thư viện xử lý C++ Tappas đã được biên dịch (.so)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        yolo_post_so = os.path.join(project_root, "src/Native_Tappas_CPP/build/libyolo26_landmark_post.so")
        arcface_post_so = os.path.join(project_root, "src/Native_Tappas_CPP/build/libarcface_post.so")
        db_matcher_post_so = os.path.join(project_root, "src/Native_Tappas_CPP/build/libdb_matcher_post.so")
        # [MỚI] Filter căn chỉnh khuôn mặt bằng 5 điểm landmark của YOLO (Affine Partial 2D)
        face_align_so = os.path.join(project_root, "src/Native_Tappas_CPP/build/libface_align.so")
        cropper_so = "/usr/lib/aarch64-linux-gnu/hailo/tappas/post_processes/cropping_algorithms/libdetection_croppers.so"

        # Định nghĩa Pipeline GStreamer kết nối phần cứng và phần mềm
        pipeline_str = (
            f"{source_str} ! " # Lấy nguồn camera và decode/scale sang 640x640 RGB
            f"queue name=queue_scale max-size-buffers=3 leaky=downstream max-size-bytes=0 max-size-time=0 ! "
            
            # [NPU] Nhận dạng khuôn mặt và landmarks bằng YOLOv8-Face trên Hailo NPU
            f"hailonet hef-path={self.yolo_hef} vdevice-group-id=smart_door ! "
            f"queue name=queue_yolo max-size-buffers=3 max-size-bytes=0 max-size-time=0 ! "
            
            # [C++] Giải mã tensor đầu ra của YOLOv8-Face sang tọa độ hộp và 5 điểm mốc
            f"hailofilter so-path={yolo_post_so} ! "
            f"queue name=queue_filter1 max-size-buffers=3 max-size-bytes=0 max-size-time=0 ! "
            
            # [C++] Theo vết khuôn mặt qua các khung hình liên tiếp để theo dõi ID
            f"hailotracker ! "
            f"queue name=queue_tracker max-size-buffers=3 max-size-bytes=0 max-size-time=0 ! "
            
            # [C++] Chia luồng: Cắt ảnh khuôn mặt (crop_detections) để gửi sang nhánh nhận diện ArcFace
            f"hailocropper so-path={cropper_so} function-name=all_detections internal-offset=true name=cropper "
            
            # [C++] Gộp luồng: Nhận ảnh gốc (bypass) từ src_0 và vector embedding từ src_1 để đồng bộ lại
            f"hailoaggregator name=agg ! "
            f"queue name=queue_agg_out max-size-buffers=3 max-size-bytes=0 max-size-time=0 ! "
            
            # [C++] So khớp vector nhận diện của khuôn mặt với file nhị phân db.bin
            f"hailofilter so-path={db_matcher_post_so} name=db_matcher ! "
            f"queue name=queue_db_matcher max-size-buffers=3 max-size-bytes=0 max-size-time=0 ! "
            
            # [Python] Nơi đăng ký pad probe để vẽ các góc Sci-Fi lên khung hình thô
            f"videoconvert name=overlay ! "
            f"queue name=queue_overlay max-size-buffers=3 leaky=downstream max-size-bytes=0 max-size-time=0 ! "
            
            # [GStreamer] Hiển thị các thông tin hệ thống (FPS, CPU Temp, RAM,...) lên góc trên cùng
            f"textoverlay name=stats_overlay valignment=top halignment=left font-desc=\"Sans, 16\" ! "
            f"{display_str} " # Gửi khung hình cuối cùng ra màn hình hiển thị hoặc fakesink
            
            # [NHÁNH BYPASS]: Truyền khung hình gốc có gắn metadata đi thẳng đến bộ gộp luồng
            f"cropper.src_0 ! "
            f"queue name=queue_bypass max-size-buffers=3 leaky=downstream max-size-bytes=0 max-size-time=0 ! "
            f"agg.sink_0 "
            
            # [NHÁNH NHẬN DIỆN]: Lấy ảnh khuôn mặt đã cắt từ src_1
            f"cropper.src_1 ! "
            f"queue name=queue_crop_path max-size-buffers=30 max-size-bytes=0 max-size-time=0 ! "

            # Chuyển đổi định dạng kích thước chuẩn 112x112 RGB cho ArcFace
            f"video/x-raw, width=112, height=112, format=RGB ! "

            # [Python Probe] Căn chỉnh khuôn mặt sẽ được thực hiện bởi on_face_crop_probe
            # đăng ký trên src pad của queue này (sau khi pipeline được khởi tạo)
            f"queue name=queue_align max-size-buffers=30 max-size-bytes=0 max-size-time=0 ! "

            # [NPU] Chạy mô hình trích xuất đặc trưng ArcFace (512 chiều) trên NPU
            f"hailonet hef-path={self.arcface_hef} vdevice-group-id=smart_door ! "
            f"queue name=queue_arcface max-size-buffers=30 max-size-bytes=0 max-size-time=0 ! "

            # [C++] Giải mã đặc trưng từ NPU sang đối tượng con HailoMatrix gắn vào khuôn mặt
            f"hailofilter so-path={arcface_post_so} ! "
            f"queue name=queue_filter2 max-size-buffers=30 max-size-bytes=0 max-size-time=0 ! "

            # Đưa đặc trưng nhận diện về bộ gộp luồng agg để ráp nối lại với khung hình gốc
            f"agg.sink_1"
        )

        print(f"\n=== INITIALIZING GSTREAMER TAPPAS PIPELINE ({selected_name}) ===")
        try:
            self.pipeline = Gst.parse_launch(pipeline_str)
        except GLib.Error as e:
            print(f"[ERROR] Failed to parse pipeline string: {e}")
            sys.exit(1)

        self.stats_overlay = self.pipeline.get_by_name("stats_overlay")

        # Register signal handlers
        import signal
        def sigint_handler(sig, frame):
            print("\n-> Force stopping pipeline and exiting...")
            self.stop()
        signal.signal(signal.SIGINT, sigint_handler)

        overlay = self.pipeline.get_by_name("overlay")
        if not overlay:
            print("[ERROR] Could not find overlay element by name!")
            self.stop()

        pad = overlay.get_static_pad("sink")
        pad.add_probe(Gst.PadProbeType.BUFFER, self.on_new_frame_probe, None)

        # [CĂN CHỈNH] Đăng ký probe trên queue_align src pad để căn chỉnh khuôn mặt
        # trước khi ArcFace NPU xử lý embedding
        align_queue = self.pipeline.get_by_name("queue_align")
        if align_queue:
            align_pad = align_queue.get_static_pad("src")
            if align_pad:
                align_pad.add_probe(Gst.PadProbeType.BUFFER, self.on_face_crop_probe, None)
                print("-> [Face Aligner] Python probe registered on queue_align.src")
            else:
                print("[WARN] Could not get queue_align src pad")
        else:
            print("[WARN] queue_align element not found")

        if appsink_callback is not None:
            appsink = self.pipeline.get_by_name("appsink")
            if appsink:
                appsink.connect("new-sample", self.on_new_appsink_sample, appsink_callback)
                print("-> [GStreamer] Connected appsink new-sample callback.")
            else:
                print("[WARN] Could not find appsink element in pipeline.")

        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            print("[ERROR] Failed to transition pipeline to PLAYING state.")
            bus = self.pipeline.get_bus()
            msg = bus.pop_filtered(Gst.MessageType.ERROR, Gst.CLOCK_TIME_NONE)
            if msg:
                err, debug = msg.parse_error()
                print(f"\n================ GSTREAMER ERROR ================")
                print(f"Error: {err.message}")
                print(f"Debug Info: {debug}")
                print(f"=================================================\n")
            self.stop()

        if appsink_callback is not None:
            print("=== SYSTEM RUNNING IN GUI MODE (no GLib loop in this thread) ===")
            return

        self.loop = GLib.MainLoop()
        print("=== SYSTEM RUNNING — press Ctrl+C to quit ===")
        try:
            self.loop.run()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self):
        print("-> Stopping ProfessionalSmartDoor...")
        if self.loop:
            try:
                self.loop.quit()
            except Exception:
                pass
        # Bypassing Gst.State.NULL to prevent the known dlclose() segfault on exit.
        # OS process termination handles resource release safely.
        os._exit(0)

