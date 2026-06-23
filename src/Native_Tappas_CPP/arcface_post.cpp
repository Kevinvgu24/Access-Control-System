#include <vector>
#include <string>
#include <cmath>
#include <iostream>
#include <algorithm>
#include <map>
#include "hailo_objects.hpp"
#include "hailo_common.hpp"

extern "C" void filter(HailoROIPtr roi);

void filter(HailoROIPtr roi) {
    // Lấy toàn bộ danh sách các tensors đầu ra
    std::vector<HailoTensorPtr> tensors = roi->get_tensors();
    if (tensors.empty()) return;

    // Tìm tensor đầu ra chứa đặc trưng (fc1) bằng matching suffix
    HailoTensorPtr fc_tensor = nullptr;
    for (auto &t : tensors) {
        std::string name = t->name();
        if (name.length() >= 3 && name.compare(name.length() - 3, 3, "fc1") == 0) {
            fc_tensor = t;
            break;
        }
    }

    // Nếu không tìm thấy, fallback lấy tensor đầu tiên
    if (!fc_tensor) {
        fc_tensor = tensors[0];
    }

    bool is_uint16 = (fc_tensor->format().type == HailoTensorFormatType::HAILO_FORMAT_TYPE_UINT16);
    
    // Đọc 512 chiều vector đặc trưng (ArcFace embedding)
    std::vector<float> embedding(512, 0.0f);
    float sum_sq = 0.0f;
    for (int i = 0; i < 512; ++i) {
        float val = fc_tensor->get_full_percision(0, 0, i, is_uint16);
        embedding[i] = val;
        sum_sq += val * val;
    }

    // Chuẩn hóa L2 vector đặc trưng
    float norm = std::sqrt(sum_sq);
    if (norm > 0.0f) {
        for (int i = 0; i < 512; ++i) {
            embedding[i] /= norm;
        }
    }

    // Tạo đối tượng HailoMatrix chứa vector đặc trưng đã được chuẩn hóa
    auto matrix_obj = std::make_shared<HailoMatrix>(embedding, 1, 512, 1);
    
    // Đính kèm đối tượng Matrix vào ROI để hailoaggregator tự động gộp về luồng chính
    roi->add_object(matrix_obj);
}
