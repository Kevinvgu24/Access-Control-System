import os
import argparse

# Đồng bộ hệ điều hành
os.environ["LC_ALL"] = "C.UTF-8"
os.environ["LANG"] = "C.UTF-8"

# Import não bộ hệ thống
from app import ProfessionalSmartDoor

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart Lab Door System")
    parser.add_argument("--yolo_hef", type=str, required=True, help="Đường dẫn đến model YOLO NPU")
    parser.add_argument("--arcface_hef", type=str, required=True, help="Đường dẫn đến model ArcFace NPU")
    parser.add_argument("--db_dir", type=str, required=True, help="Thư mục chứa SQLite Database")
    parser.add_argument("--lbf_model", type=str, required=True, help="Đường dẫn đến model LBF OpenCV")
    args = parser.parse_args()
    
    # Khởi tạo và chạy
    app = ProfessionalSmartDoor(args.yolo_hef, args.arcface_hef, args.lbf_model, args.db_dir)
    app.run()
