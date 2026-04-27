import time
import threading
from hailo_platform import Device

class HardwareMonitor:
    def __init__(self, check_interval=2.0):
        self.check_interval = check_interval
        self.running = False
        self.cpu_temp = 50.0
        self.hailo_temp = 50.0

    def start(self):
        self.running = True
        threading.Thread(target=self._monitor_loop, daemon=True).start()
        return self

    def _monitor_loop(self):
        while self.running:
            # Đọc nhiệt độ CPU
            try:
                with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                    self.cpu_temp = float(f.read().strip()) / 1000.0
            except Exception:
                pass
            
            # Đọc nhiệt độ Hailo-8L (Native API)
            try:
                device_infos = Device.scan()
                if device_infos:
                    with Device(device_infos[0]) as target:
                        temp_info = target.control.get_chip_temperature()
                        self.hailo_temp = temp_info.ts0_temperature
            except Exception:
                pass
            
            time.sleep(self.check_interval)
            
    def stop(self):
        self.running = False