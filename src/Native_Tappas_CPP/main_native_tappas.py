import os
import sys
import argparse
import signal
import gi

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

# Add the Newest_Version directory to system path to import database and utils modules
sys.path.append("/home/kevinvgu/Access-Control-System-main/src/Newest_Version")
sys.path.append("/usr/lib/python3/dist-packages")
sys.path.append("/lib/python3/dist-packages")

import numpy as np
import hailo
from database import FaceDatabase
from utils import cosine_to_percentage

class NativeTappasRunner:
    def __init__(self, db_path, rec_thresh=0.45):
        self.db = FaceDatabase(db_path)
        self.known_users = self.db.load_all_users()
        self.rec_thresh = rec_thresh
        
        self._known_names = []
        self._known_matrix = None
        self._rebuild_db_matrix()
        print(f"-> [Native TAPPAS] Loaded {len(self._known_names)} users from SQLite.")

    def _rebuild_db_matrix(self):
        if not self.known_users:
            return
        names = list(self.known_users.keys())
        vecs = np.stack(list(self.known_users.values())).astype(np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        self._known_names = names
        self._known_matrix = vecs / np.where(norms > 0, norms, 1.0)

    def search_db(self, embedding):
        if self._known_matrix is None:
            return "Unknown", 0.0
        # Normalize incoming embedding
        embedding = embedding / np.linalg.norm(embedding)
        sims = self._known_matrix @ embedding.astype(np.float32)
        idx = int(np.argmax(sims))
        best_sim = float(sims[idx])
        if best_sim > self.rec_thresh:
            return self._known_names[idx], best_sim
        return "Unknown", best_sim

    def on_new_frame_probe(self, pad, info, user_data):
        buffer = info.get_buffer()
        if buffer is None:
            return Gst.PadProbeReturn.OK

        # Retrieve the main HailoROI metadata from the GStreamer buffer
        roi = hailo.get_roi_from_buffer(buffer)
        
        # Iterate over all detected faces (HailoDetection objects)
        detections = roi.get_objects_typed(hailo.HAILO_DETECTION)
        for det in detections:
            # Check sub-objects attached to the face
            sub_objects = det.get_objects()
            for sub in sub_objects:
                # If a sub-object is a Matrix, it contains the 512-dim ArcFace embedding!
                if isinstance(sub, hailo.HailoMatrix):
                    embedding = np.array(sub.get_data())
                    
                    # Run vectorized search in database
                    name, similarity = self.search_db(embedding)
                    conf = cosine_to_percentage(similarity, self.rec_thresh)
                    
                    print(f"[NPU MATCH] Face Recognized: {name} ({conf:.1f}%) | Cosine Similarity: {similarity:.4f}")
                    
        return Gst.PadProbeReturn.OK

def main():
    parser = argparse.ArgumentParser(description="Pure C++ TAPPAS Face Recognition Runner")
    parser.add_argument("--yolo_hef", type=str, default="/home/kevinvgu/Access-Control-System-main/models/yolo26_landmark.hef")
    parser.add_argument("--arcface_hef", type=str, default="/home/kevinvgu/Access-Control-System-main/models/arcface_mobilefacenet.hef")
    parser.add_argument("--yolo_post_so", type=str, default="/home/kevinvgu/Access-Control-System-main/src/Native_Tappas_CPP/build/libyolo26_landmark_post.so")
    parser.add_argument("--db_dir", type=str, default="/home/kevinvgu/Access-Control-System-main/database")
    parser.add_argument("--source", type=str, default="0", help="Camera ID or video file path")
    parser.add_argument("--cam_width", type=int, default=640, help="Camera capture width (default: 640, lower = less CPU)")
    parser.add_argument("--cam_height", type=int, default=480, help="Camera capture height (default: 480, lower = less CPU)")
    parser.add_argument("--headless", action="store_true", help="Run with fakesink (no display, saves CPU)")
    args = parser.parse_args()

    Gst.init(None)

    db_path = os.path.join(args.db_dir, "smart_door.db")
    runner = NativeTappasRunner(db_path=db_path)

    # ── Video Source Configuration Candidates ───────────────────────────────────
    is_live = args.source.isdigit() or args.source.startswith("/dev/video")
    
    source_candidates = []
    if is_live:
        dev = f"/dev/video{args.source}" if args.source.isdigit() else args.source
        
        # Candidate 1: Raw Hardware (Zero-CPU: Capture raw format and scale/convert using Broadcom ISP)
        source_candidates.append({
            "name": "Raw Hardware (Zero-CPU Scaling/Conversion)",
            "source": (
                f"v4l2src device={dev} ! "
                f"video/x-raw, width={args.cam_width}, height={args.cam_height}, framerate=30/1 ! "
                f"v4l2convert ! "
                f"video/x-raw, width=640, height=640, format=RGB"
            )
        })
        
        # Candidate 2: MJPG Hardware (Low-CPU: Capture MJPG, decode, and scale/convert using Broadcom ISP)
        source_candidates.append({
            "name": "MJPG Hardware (Hardware-Accelerated Scaling/Conversion)",
            "source": (
                f"v4l2src device={dev} ! "
                f"image/jpeg, width={args.cam_width}, height={args.cam_height}, framerate=30/1 ! "
                f"jpegdec ! "
                f"v4l2convert ! "
                f"video/x-raw, width=640, height=640, format=RGB"
            )
        })
        
        # Candidate 3: Raw Software (Capture raw, scale/convert in software)
        source_candidates.append({
            "name": "Raw Software (Software Scaling/Conversion)",
            "source": (
                f"v4l2src device={dev} ! "
                f"video/x-raw, width={args.cam_width}, height={args.cam_height}, framerate=30/1 ! "
                f"videoconvert n-threads=2 ! "
                f"videoscale n-threads=2 ! "
                f"video/x-raw, width=640, height=640, format=RGB"
            )
        })
        
        # Candidate 4: MJPG Software (Fallback: Capture MJPG, decode, scale/convert in software)
        source_candidates.append({
            "name": "MJPG Software (Software Decoding/Scaling/Conversion - Fallback)",
            "source": (
                f"v4l2src device={dev} ! "
                f"image/jpeg, width={args.cam_width}, height={args.cam_height}, framerate=30/1 ! "
                f"jpegdec ! "
                f"videoconvert n-threads=2 ! "
                f"videoscale n-threads=2 ! "
                f"video/x-raw, width=640, height=640, format=RGB"
            )
        })
    else:
        # File Source Candidates
        source_candidates.append({
            "name": "File Hardware (Hardware-Accelerated Scaling/Conversion)",
            "source": (
                f"filesrc location=\"{args.source}\" ! decodebin ! "
                f"v4l2convert ! "
                f"video/x-raw, width=640, height=640, format=RGB"
            )
        })
        source_candidates.append({
            "name": "File Software (Software Scaling/Conversion)",
            "source": (
                f"filesrc location=\"{args.source}\" ! decodebin ! "
                f"videoconvert n-threads=2 ! "
                f"videoscale n-threads=2 ! "
                f"video/x-raw, width=640, height=640, format=RGB"
            )
        })

    # ── Sink Configuration ─────────────────────────────────────────────────────
    use_headless = args.headless or "DISPLAY" not in os.environ
    sync_val = "false" if is_live else "true"
    if use_headless:
        display_str = f"fakesink sync={sync_val} name=sink"
    else:
        display_str = f"videoconvert n-threads=2 ! autovideosink sync={sync_val} name=sink"

    # Standard TAPPAS precompiled SO paths
    cropper_so = "/usr/lib/aarch64-linux-gnu/hailo/tappas/post_processes/cropping_algorithms/libdetection_croppers.so"
    arcface_post_so = "/home/kevinvgu/Access-Control-System-main/src/Native_Tappas_CPP/build/libarcface_post.so"

    # ── Try Candidate Pipelines ────────────────────────────────────────────────
    pipeline = None
    selected_name = None
    pipeline_str = None
    
    print("\n=== SELECTING OPTIMAL GSTREAMER PIPELINE ===")
    for candidate in source_candidates:
        test_str = (
            f"{candidate['source']} ! "
            f"queue name=queue_scale max-size-buffers=3 leaky=downstream max-size-bytes=0 max-size-time=0 ! "
            f"hailonet hef-path={args.yolo_hef} vdevice-group-id=smart_door ! "
            f"queue name=queue_yolo max-size-buffers=3 max-size-bytes=0 max-size-time=0 ! "
            f"hailofilter so-path={args.yolo_post_so} ! "
            f"queue name=queue_filter1 max-size-buffers=3 max-size-bytes=0 max-size-time=0 ! "
            f"hailotracker ! "
            f"queue name=queue_tracker max-size-buffers=3 max-size-bytes=0 max-size-time=0 ! "
            f"hailocropper so-path={cropper_so} function-name=all_detections internal-offset=true name=cropper "
            f"hailoaggregator name=agg ! "
            f"queue name=queue_agg_out max-size-buffers=3 max-size-bytes=0 max-size-time=0 ! "
            f"hailooverlay ! "
            f"queue name=queue_overlay max-size-buffers=3 leaky=downstream max-size-bytes=0 max-size-time=0 ! "
            f"{display_str} "
            
            f"cropper.src_0 ! "
            f"queue name=queue_bypass max-size-buffers=3 leaky=downstream max-size-bytes=0 max-size-time=0 ! "
            f"agg.sink_0 "
            
            f"cropper.src_1 ! "
            f"queue name=queue_crop_path max-size-buffers=30 max-size-bytes=0 max-size-time=0 ! "
            f"video/x-raw, width=112, height=112, format=RGB ! "
            f"hailonet hef-path={args.arcface_hef} vdevice-group-id=smart_door ! "
            f"queue name=queue_arcface max-size-buffers=30 max-size-bytes=0 max-size-time=0 ! "
            f"hailofilter so-path={arcface_post_so} ! "
            f"queue name=queue_filter2 max-size-buffers=30 max-size-bytes=0 max-size-time=0 ! "
            f"agg.sink_1"
        )
        
        print(f"-> Testing: {candidate['name']}...")
        try:
            test_pipeline = Gst.parse_launch(test_str)
            # Transition to READY state to ensure elements exist and can link
            test_pipeline.set_state(Gst.State.READY)
            ret, state, pending = test_pipeline.get_state(500 * Gst.MSECOND)
            if ret != Gst.StateChangeReturn.FAILURE:
                # Success! Release elements for final launch
                test_pipeline.set_state(Gst.State.NULL)
                pipeline = test_pipeline
                selected_name = candidate['name']
                pipeline_str = test_str
                print(f"--> [SUCCESS] Selected pipeline: {selected_name}\n")
                break
            else:
                print(f"--> [FAILED] READY state change failed for {candidate['name']}\n")
                test_pipeline.set_state(Gst.State.NULL)
        except GLib.Error as e:
            print(f"--> [FAILED] Parsing failed for {candidate['name']}: {e}\n")

    if not pipeline:
        print("[ERROR] None of the GStreamer pipeline configurations succeeded.")
        sys.exit(1)

    print("=== STARTING NATIVE C++ TAPPAS PIPELINE ===")
    print(f"Active Pipeline String: {pipeline_str}\n")

    # Bulletproof SIGINT handler to immediately kill process and release NPU
    def sigint_handler(sig, frame):
        print("\n-> Force stopping pipeline and exiting...")
        try:
            pipeline.set_state(Gst.State.NULL)
        except Exception:
            pass
        os._exit(0)

    signal.signal(signal.SIGINT, sigint_handler)

    # Register a python probe to get embeddings from buffer metadata
    overlay = pipeline.get_by_name("hailooverlay0")
    if not overlay:
        for element in pipeline.iterate_recurse():
            if "hailooverlay" in element.get_name():
                overlay = element
                break

    if not overlay:
        print("[WARNING] Could not find hailooverlay element, registering probe on sink instead.")
        sink = pipeline.get_by_name("sink")
        pad = sink.get_static_pad("sink")
    else:
        pad = overlay.get_static_pad("src")

    pad.add_probe(Gst.PadProbeType.BUFFER, runner.on_new_frame_probe, None)

    ret = pipeline.set_state(Gst.State.PLAYING)
    if ret == Gst.StateChangeReturn.FAILURE:
        print("[ERROR] Failed to transition pipeline to PLAYING state.")
        bus = pipeline.get_bus()
        msg = bus.pop_filtered(Gst.MessageType.ERROR, Gst.CLOCK_TIME_NONE)
        if msg:
            err, debug = msg.parse_error()
            print(f"\n================ GSTREAMER ERROR ================")
            print(f"Error: {err.message}")
            print(f"Debug Info: {debug}")
            print(f"=================================================\n")
        sys.exit(1)

    loop = GLib.MainLoop()

    try:
        loop.run()
    except KeyboardInterrupt:
        pass
    finally:
        pipeline.set_state(Gst.State.NULL)
        print("-> Native pipeline stopped.")

if __name__ == "__main__":
    main()
