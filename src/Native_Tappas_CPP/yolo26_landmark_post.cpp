#include <vector>
#include <string>
#include <cmath>
#include <iostream>
#include <algorithm>
#include <map>
#include "hailo_objects.hpp"
#include "hailo_common.hpp"

#define NUM_CLASSES 1
#define CONF_THRESHOLD 0.5f

inline float sigmoid(float x) {
    return 1.0f / (1.0f + std::exp(-x));
}

struct Point2D {
    float x;
    float y;
    float confidence;
};

struct FaceDetection {
    float xmin, ymin, xmax, ymax;
    float confidence;
    std::vector<Point2D> landmarks;
};

float iou(const FaceDetection &a, const FaceDetection &b) {
    float x1 = std::max(a.xmin, b.xmin);
    float y1 = std::max(a.ymin, b.ymin);
    float x2 = std::min(a.xmax, b.xmax);
    float y2 = std::min(a.ymax, b.ymax);
    
    if (x1 >= x2 || y1 >= y2) return 0.0f;
    
    float intersection = (x2 - x1) * (y2 - y1);
    float area_a = (a.xmax - a.xmin) * (a.ymax - a.ymin);
    float area_b = (b.xmax - b.xmin) * (b.ymax - b.ymin);
    
    return intersection / (area_a + area_b - intersection);
}

std::vector<FaceDetection> nms(std::vector<FaceDetection> &dets, float iou_threshold) {
    std::sort(dets.begin(), dets.end(), [](const FaceDetection &a, const FaceDetection &b) {
        return a.confidence > b.confidence;
    });
    
    std::vector<FaceDetection> keep;
    std::vector<bool> suppressed(dets.size(), false);
    
    for (size_t i = 0; i < dets.size(); ++i) {
        if (suppressed[i]) continue;
        keep.push_back(dets[i]);
        for (size_t j = i + 1; j < dets.size(); ++j) {
            if (suppressed[j]) continue;
            if (iou(dets[i], dets[j]) > iou_threshold) {
                suppressed[j] = true;
            }
        }
    }
    return keep;
}

// Hàm entry point được gọi bởi phần tử GStreamer hailofilter
extern "C" void filter(HailoROIPtr roi);

void filter(HailoROIPtr roi) {
    // Lấy danh sách toàn bộ các output tensors từ NPU
    std::vector<HailoTensorPtr> tensors = roi->get_tensors();
    std::map<std::string, HailoTensorPtr> tensors_map;
    
    for (auto &t : tensors) {
        tensors_map[t->name()] = t;
    }

    const std::vector<int> GRID_SIZES = {80, 40, 20};
    const std::vector<int> STRIDES = {8, 16, 32};
    std::vector<FaceDetection> detections;

    // Tính toán logit threshold tương đương với conf_threshold trên sigmoid
    float logit_threshold = -std::log(1.0f / CONF_THRESHOLD - 1.0f);

    auto find_tensor_by_suffix = [&](const std::string &suffix) -> HailoTensorPtr {
        for (auto &pair : tensors_map) {
            if (pair.first.length() >= suffix.length() && 
                pair.first.compare(pair.first.length() - suffix.length(), suffix.length(), suffix) == 0) {
                return pair.second;
            }
        }
        return nullptr;
    };

    for (size_t i = 0; i < STRIDES.size(); ++i) {
        int grid = GRID_SIZES[i];
        int stride = STRIDES[i];

        std::string cls_suffix, reg_suffix, kpt_suffix;
        if (grid == 80) {
            cls_suffix = "conv67";
            reg_suffix = "conv63";
            kpt_suffix = "conv64";
        } else if (grid == 40) {
            cls_suffix = "conv86";
            reg_suffix = "conv82";
            kpt_suffix = "conv83";
        } else if (grid == 20) {
            cls_suffix = "conv103";
            reg_suffix = "conv98";
            kpt_suffix = "conv100";
        }

        auto cls_tensor = find_tensor_by_suffix(cls_suffix);
        auto reg_tensor = find_tensor_by_suffix(reg_suffix);
        auto kpt_tensor = find_tensor_by_suffix(kpt_suffix);

        if (!cls_tensor || !reg_tensor || !kpt_tensor) {
            continue;
        }

        // Tự động kiểm tra kiểu dữ liệu (UINT16 hay UINT8)
        bool is_uint16 = (cls_tensor->format().type == HailoTensorFormatType::HAILO_FORMAT_TYPE_UINT16);

        for (int r = 0; r < grid; ++r) {
            for (int c = 0; c < grid; ++c) {
                // Đọc phân phối lớp (class probability)
                float cls_score = cls_tensor->get_full_percision(r, c, 0, is_uint16);
                if (cls_score < logit_threshold) continue;

                float score = sigmoid(cls_score);

                // Decode Bounding Box (reg)
                float l = reg_tensor->get_full_percision(r, c, 0, is_uint16);
                float t = reg_tensor->get_full_percision(r, c, 1, is_uint16);
                float r_box = reg_tensor->get_full_percision(r, c, 2, is_uint16);
                float b = reg_tensor->get_full_percision(r, c, 3, is_uint16);

                float x1 = (c + 0.5f - l) * stride;
                float y1 = (r + 0.5f - t) * stride;
                float x2 = (c + 0.5f + r_box) * stride;
                float y2 = (r + 0.5f + b) * stride;

                // Decode 5 Landmarks (kpt)
                std::vector<Point2D> points;
                for (int k = 0; k < 5; ++k) {
                    float kpt_x = kpt_tensor->get_full_percision(r, c, k * 3, is_uint16);
                    float kpt_y = kpt_tensor->get_full_percision(r, c, k * 3 + 1, is_uint16);
                    float kpt_conf = sigmoid(kpt_tensor->get_full_percision(r, c, k * 3 + 2, is_uint16));

                    // Chuẩn hóa vị trí landmark về [0.0, 1.0] tương ứng với kích thước 640x640
                    float px = (kpt_x + c + 0.5f) * stride / 640.0f;
                    float py = (kpt_y + r + 0.5f) * stride / 640.0f;

                    px = std::max(0.0f, std::min(px, 1.0f));
                    py = std::max(0.0f, std::min(py, 1.0f));

                    Point2D kp_pt;
                    kp_pt.x = px;
                    kp_pt.y = py;
                    kp_pt.confidence = kpt_conf;
                    points.push_back(kp_pt);
                }

                FaceDetection det;
                det.xmin = std::max(0.0f, std::min(x1 / 640.0f, 1.0f));
                det.ymin = std::max(0.0f, std::min(y1 / 640.0f, 1.0f));
                det.xmax = std::max(0.0f, std::min(x2 / 640.0f, 1.0f));
                det.ymax = std::max(0.0f, std::min(y2 / 640.0f, 1.0f));
                det.confidence = score;
                det.landmarks = points;

                detections.push_back(det);
            }
        }
    }

    // Áp dụng Non-Maximum Suppression (NMS) để loại bỏ các box trùng lặp
    std::vector<FaceDetection> filtered_detections = nms(detections, 0.45f);

    // Gắn các đối tượng đã được lọc NMS vào ROI chính
    for (auto &det : filtered_detections) {
        float w = det.xmax - det.xmin;
        float h = det.ymax - det.ymin;
        
        HailoBBox bbox(det.xmin, det.ymin, w, h);
        
        // Gắn đối tượng Bounding Box
        auto detect_obj = std::make_shared<HailoDetection>(bbox, 0, "face", det.confidence);
        
        // Gắn đối tượng con Landmarks vào Bounding Box vừa tạo (phải chuẩn hóa tương đối với Bounding Box)
        std::vector<HailoPoint> hailo_points;
        for (auto &kp : det.landmarks) {
            float rx = (kp.x - det.xmin) / w;
            float ry = (kp.y - det.ymin) / h;
            rx = std::max(0.0f, std::min(rx, 1.0f));
            ry = std::max(0.0f, std::min(ry, 1.0f));
            hailo_points.push_back(HailoPoint(rx, ry, kp.confidence));
        }
        auto landmarks_obj = std::make_shared<HailoLandmarks>("face_landmarks", hailo_points);
        detect_obj->add_object(landmarks_obj);

        roi->add_object(detect_obj);
    }
}
