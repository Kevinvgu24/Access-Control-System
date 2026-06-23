import os
import cv2
import glob
import argparse
import numpy as np

from hailo_platform import VDevice 
from common import HailoPythonInferenceEngine, letterbox_image, scale_detections_to_original

from face_engine import FaceAligner
from database import FaceDatabase

def get_face_embedding(engine, image):
    if image.shape[:2] != (112, 112): image = cv2.resize(image, (112, 112))
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    input_tensor = np.expand_dims(rgb, axis=0).astype(np.uint8)
    raw_output, _ = engine.infer(input_tensor, verbose=False, task='recognition')
    if isinstance(raw_output, list): emb = raw_output[0]
    elif isinstance(raw_output, dict): emb = list(raw_output.values())[0]
    else: emb = raw_output
    return emb.flatten()

def auto_sync_database(yolo_hef, arcface_hef, lbf_model_path, database_dir):
    if not os.path.exists(database_dir):
        os.makedirs(database_dir)
        
    db_path = os.path.join(database_dir, "smart_door.db")
    db = FaceDatabase(db_path)
    known_users = db.load_all_users()
    
    # Lấy danh sách các thư mục con trong database/
    folders = [f for f in os.listdir(database_dir) if os.path.isdir(os.path.join(database_dir, f))]
    new_users = [u for u in folders if u not in known_users]
    
    if not new_users:
        print("-> [REGISTER] Không có người dùng mới. Dữ liệu đã đồng bộ.")
        return

    print(f"-> [REGISTER] Phát hiện {len(new_users)} người dùng mới. Đang cấp phát NPU...")
    shared_vdevice = VDevice()
    yolo_engine = HailoPythonInferenceEngine(yolo_hef, target=shared_vdevice)
    arcface_engine = HailoPythonInferenceEngine(arcface_hef, target=shared_vdevice)
    aligner = FaceAligner(lbf_model_path)

    for user_name in new_users:
        user_path = os.path.join(database_dir, user_name)
        print(f"[*] Đang quét sinh trắc cho: '{user_name}'...")
        
        image_paths = glob.glob(os.path.join(user_path, '*.[jp][pn]g'))
        image_paths += glob.glob(os.path.join(user_path, '*.[JP][PN]G'))
        
        embeddings = []
        for img_path in image_paths:
            img = cv2.imread(img_path)
            if img is None: continue
            
            orig_h, orig_w = img.shape[:2]
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            padded, scale, pad_w, pad_h = letterbox_image(img_rgb, target_size=640)
            
            detections, _ = yolo_engine.infer(np.expand_dims(padded, axis=0).astype(np.uint8), verbose=False, conf_threshold=0.4)
            if detections:
                detections = scale_detections_to_original(detections, orig_h, orig_w, scale, pad_w, pad_h)
                best_det = max(detections, key=lambda x: x['conf'])
                
                ymin, xmin, ymax, xmax = int(best_det['y1']), int(best_det['x1']), int(best_det['y2']), int(best_det['x2'])
                my, mx = int((ymax - ymin) * 0.1), int((xmax - xmin) * 0.1)
                
                raw_face = img[max(0, ymin - my):min(orig_h, ymax + my), max(0, xmin - mx):min(orig_w, xmax + mx)]
                if raw_face.size == 0: continue
                
                processed_face = aligner.align(raw_face)
                embeddings.append(get_face_embedding(arcface_engine, processed_face))

        if embeddings:
            avg_embedding = np.mean(embeddings, axis=0)
            final_embedding = avg_embedding / np.linalg.norm(avg_embedding)
            db.save_user(user_name, final_embedding)
            print(f"[+] Đã lưu '{user_name}' vào SQLite thành công!")
        else:
            print(f"[-] Bỏ qua '{user_name}': Không tìm thấy khuôn mặt hợp lệ.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--yolo_hef", type=str, required=True)
    parser.add_argument("--arcface_hef", type=str, required=True)
    parser.add_argument("--db_dir", type=str, default="/home/kevinvgu/hailo-rpi5-examples/smart_lab/database")
    parser.add_argument("--lbf_model", type=str, default="/home/kevinvgu/hailo-rpi5-examples/smart_lab/src/lbfmodel.yaml")
    args = parser.parse_args()
    
    auto_sync_database(args.yolo_hef, args.arcface_hef, args.lbf_model, args.db_dir)
