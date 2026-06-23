import time
import threading
from hailo_platform import Device


class HardwareMonitor:
    def __init__(self, check_interval=2.0):
        self.check_interval = check_interval
        self.running  = False
        self.cpu_temp  = 50.0
        self.hailo_temp = 50.0
        self.ram_mb = 0.0

    def start(self):
        self.running = True
        threading.Thread(target=self._monitor_loop, daemon=True).start()
        return self

    def _monitor_loop(self):
        # Open the Hailo device context ONCE and reuse it every poll cycle.
        # Previously this opened and closed a new Device() every 2 seconds,
        # causing repeated driver overhead.
        hailo_device = None
        try:
            device_infos = Device.scan()
            if device_infos:
                hailo_device = Device(device_infos[0])
                hailo_device.__enter__()
        except Exception as e:
            print(f"[HWMonitor] Could not open Hailo device: {e}")

        try:
            while self.running:
                # CPU temperature — sysfs read is fast
                try:
                    with open("/sys/class/thermal/thermal_zone0/temp") as f:
                        self.cpu_temp = float(f.read().strip()) / 1000.0
                except OSError:
                    pass

                # RAM RSS memory usage
                try:
                    with open("/proc/self/status") as f:
                        for line in f:
                            if line.startswith("VmRSS:"):
                                self.ram_mb = float(line.split()[1]) / 1024.0
                                break
                except Exception:
                    try:
                        import resource
                        self.ram_mb = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0
                    except Exception:
                        pass

                # Hailo chip temperature — reuse the already-open context
                if hailo_device is not None:
                    try:
                        temp_info = hailo_device.control.get_chip_temperature()
                        self.hailo_temp = temp_info.ts0_temperature
                    except Exception:
                        pass

                time.sleep(self.check_interval)
        finally:
            if hailo_device is not None:
                try:
                    hailo_device.__exit__(None, None, None)
                except Exception:
                    pass

    def stop(self):
        self.running = False
