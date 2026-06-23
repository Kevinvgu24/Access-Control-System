#!/bin/bash

# 1. Đi vào thư mục làm việc
cd /home/kevinvgu/Access-Control-System-main/src/Native_Tappas_CPP/

echo "============================================="
echo " BIÊN DỊCH HẬU XỬ LÝ C++ TAPPAS (YOLOv8-Face)"
echo "============================================="

# Tạo thư mục build và tiến hành compile
mkdir -p build
cd build
cmake ..
make -j$(nproc)

if [ $? -ne 0 ]; then
    echo "[LỖI] Biên dịch mã nguồn C++ thất bại!"
    exit 1
fi

echo "-> Biên dịch thành công: build/libyolo26_landmark_post.so"
cd ..

# 2. Kích hoạt môi trường ảo hailo_env và khai báo PYTHONPATH
source /home/kevinvgu/hailo_env/bin/activate
export PYTHONPATH="/home/kevinvgu/hailo_env/lib/python3.13/site-packages:/usr/lib/python3/dist-packages"

# 3. Bật dịch vụ chia sẻ NPU của HailoRT
export HAILORT_USE_SERVICE=1

echo "============================================="
echo " KHỞI CHẠY ĐƯỜNG ỐNG NATIVE C++ TAPPAS"
echo "============================================="

# Chạy pipeline với camera mặc định (/dev/video0) ở chế độ headless để debug terminal
python3 main_native_tappas.py --source 0 --headless
