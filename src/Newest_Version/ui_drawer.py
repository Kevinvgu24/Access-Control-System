import cv2

class UIDrawer:
    @staticmethod
    def draw_bounding_box(frame, xmin, ymin, xmax, ymax, label, color):
        """Vẽ khung hình chữ nhật và in tên + phần trăm"""
        cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), color, 2)
        cv2.putText(frame, label, (xmin, ymin - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        return frame

    @staticmethod
    def draw_system_stats(frame, fps, cpu_temp, hailo_temp):
        """Vẽ các chỉ số sức khỏe của hệ thống ở góc trái màn hình"""
        cv2.putText(frame, f"FPS: {fps:.1f}", (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
        cv2.putText(frame, f"CPU: {cpu_temp:.1f}C | Hailo: {hailo_temp:.1f}C", (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
        return frame