cmake_minimum_required(VERSION 3.10)
project(yolo26_landmark_post)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3 -fPIC -Wall -shared")

# Tìm các dependencies cho GStreamer 1.0
find_package(PkgConfig REQUIRED)
pkg_check_modules(GST REQUIRED gstreamer-1.0)
pkg_check_modules(GST_VIDEO REQUIRED gstreamer-video-1.0)

# Tìm OpenCV (chỉ cần core + imgproc + calib3d để tối thiểu hóa binary size)
find_package(OpenCV REQUIRED COMPONENTS core imgproc calib3d)

# Khai báo include directories cho SDK TAPPAS, GStreamer & OpenCV
include_directories(
    /usr/include/hailo
    /usr/include/hailo/tappas
    ${GST_INCLUDE_DIRS}
    ${GST_VIDEO_INCLUDE_DIRS}
    ${OpenCV_INCLUDE_DIRS}
)

# Khai báo đích sinh ra là tệp thư viện liên kết động (.so)
add_library(yolo26_landmark_post SHARED yolo26_landmark_post.cpp)
add_library(arcface_post SHARED arcface_post.cpp)
add_library(db_matcher_post SHARED db_matcher_post.cpp)

# [MỚI] Face Alignment Filter: căn chỉnh khuôn mặt bằng 5 điểm landmark từ YOLO
# Sử dụng OpenCV Affine Partial 2D (in-place, zero-allocation trên buffer 112×112)
add_library(face_align SHARED face_align.cpp)

# Link thư viện GStreamer
target_link_libraries(yolo26_landmark_post
    ${GST_LIBRARIES}
)
target_link_libraries(arcface_post
    ${GST_LIBRARIES}
)
target_link_libraries(db_matcher_post
    ${GST_LIBRARIES}
)

# Link OpenCV + GStreamer-video cho face_align
target_link_libraries(face_align
    ${GST_LIBRARIES}
    ${GST_VIDEO_LIBRARIES}
    ${OpenCV_LIBS}
)
