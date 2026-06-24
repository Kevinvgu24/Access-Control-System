import os
import time
import shutil
import urllib.request
import firebase_admin
from firebase_admin import credentials, firestore

# Đường dẫn cấu hình
DB_DIR = "/home/kevinvgu/Access-Control-System/database"
SERVICE_ACCOUNT_PATH = "/home/kevinvgu/Access-Control-System/serviceAccountKey.json"

def download_image(url, save_path):
    """Tải ảnh sinh trắc từ Storage / UploadThing về thư mục local"""
    try:
        # Giả lập User-Agent tránh bị chặn tải ảnh
        opener = urllib.request.build_opener()
        opener.addheaders = [('User-agent', 'Mozilla/5.0')]
        urllib.request.install_opener(opener)
        
        urllib.request.urlretrieve(url, save_path)
        print(f"  [+] Đã tải ảnh: {save_path}")
        return True
    except Exception as e:
        print(f"  [-] Lỗi khi tải ảnh từ {url}: {e}")
        return False

def sync_firestore():
    if not os.path.exists(SERVICE_ACCOUNT_PATH):
        print(f"\n[LỖI] Không tìm thấy tệp cấu hình Firebase tại: {SERVICE_ACCOUNT_PATH}")
        print("Vui lòng tải tệp Service Account Key (dạng .json) từ Firebase Console:")
        print("Project Settings -> Service Accounts -> Generate New Private Key")
        print(f"Và đặt tên là 'serviceAccountKey.json' tại thư mục: /home/kevinvgu/Access-Control-System/\n")
        return

    # Khởi tạo Firebase Admin SDK
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred)
    db = firestore.client()

    print("=========================================================")
    print(" KHỞI ĐỘNG DỊCH VỤ ĐỒNG BỘ CLOUD FIREBASE -> LOCAL DEVICE")
    print("=========================================================")
    print(f"-> Đang lắng nghe thay đổi trên Firestore '/users'...")
    print(f"-> Thư mục lưu trữ local: {DB_DIR}")
    print("---------------------------------------------------------")

    def on_snapshot(col_snapshot, changes, read_time):
        firestore_users = {}
        
        # Duyệt qua toàn bộ users đang active trên Firestore
        for doc in col_snapshot:
            data = doc.to_dict()
            status = data.get("status", "active")
            if status == "active":
                full_name = data.get("fullName")
                if full_name:
                    # Lấy danh sách ảnh sinh trắc từ subcollection 'faceImages'
                    images_ref = doc.reference.collection("faceImages")
                    image_docs = images_ref.stream()
                    urls = []
                    for img_doc in image_docs:
                        img_data = img_doc.to_dict()
                        url = img_data.get("storagePath")
                        if url:
                            urls.append(url)
                    firestore_users[full_name] = urls

        # Lấy danh sách thư mục local hiện tại (trừ file DB sqlite)
        local_folders = [
            f for f in os.listdir(DB_DIR) 
            if os.path.isdir(os.path.join(DB_DIR, f)) and f != "smart_door.db"
        ]

        # 1. Xóa thư mục của những user bị xóa/khóa trên Cloud
        for folder in local_folders:
            if folder not in firestore_users:
                print(f"[-] Phát hiện rút quyền truy cập: '{folder}'. Đang xóa thư mục local...")
                shutil.rmtree(os.path.join(DB_DIR, folder))

        # 2. Tạo thư mục và tải ảnh cho user mới/cập nhật
        for name, urls in firestore_users.items():
            user_dir = os.path.join(DB_DIR, name)
            if not os.path.exists(user_dir):
                os.makedirs(user_dir)
                print(f"[+] Phát hiện người dùng mới đăng ký: '{name}'. Tạo thư mục...")

            # Kiểm tra và tải các ảnh chưa có ở local
            for idx, url in enumerate(urls):
                ext = "png" if ".png" in url.lower() else "jpg"
                img_name = f"face_{idx}.{ext}"
                img_path = os.path.join(user_dir, img_name)

                if not os.path.exists(img_path):
                    print(f" -> Đang tải ảnh sinh trắc {idx+1}/{len(urls)} cho '{name}'...")
                    download_image(url, img_path)

    # Đăng ký lắng nghe thời gian thực (Real-time Listener)
    users_query = db.collection("users")
    users_query.on_snapshot(on_snapshot)

    # Giữ thread chạy vô hạn
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n-> Đã dừng dịch vụ đồng bộ.")

if __name__ == "__main__":
    sync_firestore()
