#include <vector>
#include <string>
#include <cmath>
#include <iostream>
#include <fstream>
#include <sys/stat.h>
#include <algorithm>
#include "hailo_objects.hpp"
#include "hailo_common.hpp"

class WritableDetection : public HailoDetection {
public:
    void set_class_id(int class_id) {
        this->m_class_id = class_id;
    }
};

struct DBUser {
    std::string name;
    std::vector<float> embedding;
};

std::vector<DBUser> g_db_users;
time_t g_last_mtime = 0;

// [CHỨC NĂNG] Nạp/Tự động nạp lại cơ sở dữ liệu người dùng từ file nhị phân db.bin
// [LIÊN KẾT] Hàm này kiểm tra thời gian sửa đổi (mtime) của file db.bin. Nếu phát hiện thay đổi 
//           (do Python ghi đè khi cập nhật SQLite), nó sẽ tự động đọc lại để bộ so khớp C++ luôn cập nhật.
void reload_db() {
    std::string bin_path = "/home/kevinvgu/Access-Control-System-main/scratch/db.bin";
    struct stat attr;
    if (stat(bin_path.c_str(), &attr) != 0) return;
    if (attr.st_mtime == g_last_mtime) return; // Không thay đổi thì không nạp lại để tiết kiệm tài nguyên
    
    std::ifstream f(bin_path, std::ios::binary);
    if (!f.is_open()) return;
    
    int n = 0;
    f.read(reinterpret_cast<char*>(&n), sizeof(n)); // Đọc số lượng người dùng
    
    std::vector<DBUser> new_users;
    for (int i = 0; i < n; ++i) {
        char name_buf[64];
        f.read(name_buf, 64); // Đọc tên người dùng cố định 64 bytes
        std::string name(name_buf);
        
        std::vector<float> emb(512);
        f.read(reinterpret_cast<char*>(emb.data()), 512 * sizeof(float)); // Đọc vector embedding 512 chiều
        
        new_users.push_back({name, emb});
    }
    
    g_db_users = new_users;
    g_last_mtime = attr.st_mtime;
    std::cout << "[C++ DB Matcher] Loaded " << g_db_users.size() << " users from binary." << std::endl;
}

extern "C" void filter(HailoROIPtr roi);

// [CHỨC NĂNG] Hàm lọc chính xử lý từng frame hình đi qua GStreamer
// [LIÊN KẾT] Nhận đầu vào là các đối tượng (ví dụ khuôn mặt) đã được nhận dạng ở đầu luồng, 
//           sau đó so khớp và đính kèm nhãn tên người dùng vào metadata.
void filter(HailoROIPtr roi) {
    reload_db(); // Gọi nạp lại cơ sở dữ liệu nếu có sự thay đổi từ bên ngoài
    
    std::vector<HailoObjectPtr> objects_to_remove;
    std::vector<HailoObjectPtr> objects_to_add;
    
    // Duyệt qua toàn bộ đối tượng trong khung hình chính (Main ROI)
    for (auto &obj : roi->get_objects()) {
        if (obj->get_type() == HAILO_DETECTION) {
            auto det = std::dynamic_pointer_cast<HailoDetection>(obj);
            if (!det) continue;
            
            // [LIÊN KẾT] Lấy đối tượng con chứa vector embedding 512 chiều được sinh ra bởi libarcface_post.so
            // Lấy đối tượng HailoMatrix mới nhất ở cuối danh sách để đảm bảo tính thời gian thực
            HailoMatrixPtr matrix = nullptr;
            for (auto &sub : det->get_objects()) {
                if (sub->get_type() == HAILO_MATRIX) {
                    matrix = std::dynamic_pointer_cast<HailoMatrix>(sub);
                }
            }
            
            if (matrix) {
                std::vector<float> embedding = matrix->get_data();
                if (embedding.size() != 512) continue;
                
                std::string best_name = "Unknown";
                float best_sim = -1.0f;
                
                // [CHỨC NĂNG] Thực hiện so khớp cosine (tích vô hướng) với tốc độ cao bằng C++
                for (const auto &user : g_db_users) {
                    float dot = 0.0f;
                    for (int i = 0; i < 512; ++i) {
                        dot += embedding[i] * user.embedding[i];
                    }
                    if (dot > best_sim) {
                        best_sim = dot;
                        best_name = user.name;
                    }
                }
                
                int class_id = 1;  // Mặc định class_id = 1 (Unknown / Viền đỏ)
                std::string display_text = "Unknown";
                std::string label_text = "Unknown";
                
                // Nếu vượt ngưỡng nhận diện (0.45) thì đổi sang Known (Green box) và tính % tương đồng
                if (best_sim >= 0.45f) {
                    class_id = 0;  // class_id = 0 (Known / Viền xanh)
                    float percentage = (best_sim - 0.45f) / (1.0f - 0.45f) * 100.0f;
                    if (percentage < 0.0f) percentage = 0.0f;
                    if (percentage > 100.0f) percentage = 100.0f;
                    
                    char buf[128];
                    snprintf(buf, sizeof(buf), "%s (%.1f%%)", best_name.c_str(), percentage);
                    display_text = buf;
                    label_text = best_name;
                }
                
                // [CHỨC NĂNG] Nhân bản đối tượng khuôn mặt để ghi đè thuộc tính mà không làm hỏng dữ liệu gốc của Tracker
                auto cloned_det = std::dynamic_pointer_cast<HailoDetection>(det->clone());
                if (cloned_det) {
                    // Cập nhật class_id (0: Xanh, 1: Đỏ) và giữ nguyên nhãn gốc là "face" để tracker tiếp tục hoạt động liên tục
                    auto writable_det = std::static_pointer_cast<WritableDetection>(cloned_det);
                    writable_det->set_class_id(class_id);
                    cloned_det->set_label("face");
                    
                    // [CHỨC NĂNG] Xóa bỏ các metadata phân loại cũ và loại bỏ đối tượng HailoMatrix cũ khỏi bản sao
                    // [LIÊN KẾT] Tránh bộ theo vết (hailotracker) tự động sao chép các vector embedding cũ qua từng frame,
                    //           giúp giải quyết lỗi rò rỉ bộ nhớ và lỗi đứng yên phần trăm nhận diện.
                    std::vector<HailoObjectPtr> subs_to_remove;
                    for (auto &sub : cloned_det->get_objects()) {
                        if (sub->get_type() == HAILO_CLASSIFICATION) {
                            auto cl = std::dynamic_pointer_cast<HailoClassification>(sub);
                            if (cl && cl->get_classification_type() == "recognition") {
                                subs_to_remove.push_back(sub);
                            }
                        } else if (sub->get_type() == HAILO_MATRIX) {
                            subs_to_remove.push_back(sub);
                        }
                    }
                    for (auto &sub : subs_to_remove) {
                        cloned_det->remove_object(sub);
                    }
                    
                    // Thêm kết quả phân lớp "recognition" mới chứa tên và phần trăm nhận diện thực tế
                    float clamped_sim = std::max(0.0f, std::min(best_sim, 1.0f));
                    auto cl_obj = std::make_shared<HailoClassification>("recognition", class_id, display_text, clamped_sim);
                    cloned_det->add_object(cl_obj);
                    
                    // Đưa vào hàng chờ để thực hiện thay thế sau vòng lặp tránh lỗi lỗi tham chiếu vòng lặp (iterator invalidation)
                    objects_to_remove.push_back(det);
                    objects_to_add.push_back(cloned_det);
                }
            }
        }
    }
    
    // Apply object replacement in the main ROI list
    for (auto &obj : objects_to_remove) {
        roi->remove_object(obj);
    }
    for (auto &obj : objects_to_add) {
        roi->add_object(obj);
    }
}
