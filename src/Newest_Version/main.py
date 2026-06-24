import os
import argparse

# Đồng bộ hệ điều hành và tắt logging HailoRT
os.environ["LC_ALL"] = "C.UTF-8"
os.environ["LANG"] = "C.UTF-8"
os.environ["HAILORT_LOGGER_PATH"] = "NONE"

# Import não bộ hệ thống
from app import ProfessionalSmartDoor

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart Lab Door System")
    parser.add_argument("--yolo_hef", type=str, required=True, help="Đường dẫn đến model YOLO NPU")
    parser.add_argument("--arcface_hef", type=str, required=True, help="Đường dẫn đến model ArcFace NPU")
    parser.add_argument("--anti_spoofing_hef", type=str, default="/home/kevinvgu/Access-Control-System/models/mobilenet_v3.hef", help="Đường dẫn đến model Anti-Spoofing NPU")
    parser.add_argument("--db_dir", type=str, required=True, help="Thư mục chứa SQLite Database")
    parser.add_argument("--lbf_model", type=str, required=True, help="Đường dẫn đến model LBF OpenCV")
    parser.add_argument("--close_thresh", type=int, default=130, help="Ngưỡng khoảng cách gần khuôn mặt (pixel)")
    parser.add_argument("--cam_width", type=int, default=640, help="Chiều rộng khung hình camera")
    parser.add_argument("--cam_height", type=int, default=480, help="Chiều cao khung hình camera")
    args = parser.parse_args()
    
    # Khởi tạo và chạy
    app = ProfessionalSmartDoor(
        args.yolo_hef,
        args.arcface_hef,
        args.anti_spoofing_hef,
        args.lbf_model,
        args.db_dir,
        close_thresh=args.close_thresh
    )
    app.run(width=args.cam_width, height=args.cam_height)
