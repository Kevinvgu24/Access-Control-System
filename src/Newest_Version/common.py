"""Common utilities for Hailo-8L inference on YOLO26 (NMS-free dual-head model)"""

import numpy as np
import cv2
import time
from dataclasses import dataclass
from typing import Dict, Tuple, List
from hailo_platform import VDevice, HEF, ConfigureParams, InputVStreamParams, OutputVStreamParams, InferVStreams, HailoStreamInterface, FormatType


def sigmoid(x: np.ndarray) -> np.ndarray:
    """Vectorized sigmoid function for activation."""
    return 1.0 / (1.0 + np.exp(-x))


# ============================================================================
# Common Image Operations
# ============================================================================

def letterbox_image(img, target_size=640, color=(114, 114, 114)):
    """Resize image while preserving aspect ratio (letterbox padding)."""
    h, w = img.shape[:2]
    scale = min(target_size / h, target_size / w)
    new_w = int(w * scale)
    new_h = int(h * scale)
    
    resized = cv2.resize(img, (new_w, new_h))
    
    pad_w = (target_size - new_w) // 2
    pad_h = (target_size - new_h) // 2
    
    padded = np.full((target_size, target_size, 3), color, dtype=np.uint8)
    padded[pad_h:pad_h + new_h, pad_w:pad_w + new_w] = resized
    
    return padded, scale, pad_w, pad_h

def load_and_preprocess_image(img_path: str, target_size: int = 640, normalize: bool = False) -> Tuple[np.ndarray, Tuple[int, int], float, int, int]:
    """Load and preprocess image for inference.
    
    Args:
        img_path: Path to input image.
        target_size: Target size for inference (default 640x640).
        normalize: If True, normalize to [0,1]; if False, keep as uint8 [0,255].
    
    Returns:
        Tuple containing (input_tensor, original_size, scale, pad_w, pad_h).
    """
    img = cv2.imread(img_path)
    if img is None:
        raise FileNotFoundError(f"Image not found: {img_path}")
    
    # YOLO models expect RGB, but cv2.imread loads as BGR, so convert it
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    orig_h, orig_w = img.shape[:2]
    
    padded, scale, pad_w, pad_h = letterbox_image(img, target_size)
    
    if normalize:
        padded = padded.astype(np.float32) / 255.0
        input_tensor = np.expand_dims(padded, axis=0)
    else:
        input_tensor = np.expand_dims(padded, axis=0).astype(np.uint8)
    
    return input_tensor, (orig_h, orig_w), scale, pad_w, pad_h


def scale_detections_to_original(detections: List[dict], orig_h: int, orig_w: int, scale: float, pad_w: int, pad_h: int) -> List[dict]:
    """Scale detection coordinates from inference space (640x640) back to original image space.
    
    Args:
        detections: List of detection dictionaries with x1, y1, x2, y2 coordinates.
        orig_h, orig_w: Original image dimensions.
        scale: Scale factor used during preprocessing.
        pad_w, pad_h: Padding used during preprocessing.
    """
    for det in detections:
        # 1. Reverse padding, 2. Reverse scaling
        det['x1'] = max(0, min((det['x1'] - pad_w) / scale, orig_w))
        det['y1'] = max(0, min((det['y1'] - pad_h) / scale, orig_h))
        det['x2'] = max(0, min((det['x2'] - pad_w) / scale, orig_w))
        det['y2'] = max(0, min((det['y2'] - pad_h) / scale, orig_h))
        
    return detections


def format_detection_results(detections: List[dict], show_count: int = 10) -> str:
    """Format detection results for console display.
    
    Args:
        detections: List of detection dictionaries.
        show_count: Maximum number of detections to display (None to show all).
    
    Returns:
        Formatted string containing the results.
    """
    lines = []
    for i, det in enumerate(detections[:show_count] if show_count else detections):
        lines.append(f"  [{i+1}] {det['cls_name']} - conf={det['conf']:.2f}, bbox=[{det['x1']:.0f}, {det['y1']:.0f}, {det['x2']:.0f}, {det['y2']:.0f}]")
    return '\n'.join(lines)


def print_detection_summary(title: str, image_path: str, model_info: Dict, total_time_ms: float, 
                           conf_threshold: float, num_detections: int, output_path: str):
    """Print a formatted summary of the detection process."""
    print("\n" + "="*60)
    print(title)
    print("="*60)
    print(f"Image: {image_path}")
    for key, val in model_info.items():
        print(f"Model {key}: {val}")
    print(f"Total Time: {total_time_ms:.2f}ms")
    print(f"Confidence Threshold: {conf_threshold}")
    print(f"Detections: {num_detections}")
    print(f"Output: {output_path}")


@dataclass
class InferenceStats:
    """Dataclass to hold runtime statistics for inference."""
    preprocess_time: float
    hailo_inference_time: float
    postprocess_time: float
    total_time: float
    hailo_output_shape: str
    final_output_shape: str


class HailoPythonInferenceEngine:
    """Encapsulates Hailo-8L backbone combined with a Python-based post-processing head."""
    
    def __init__(self, hef_path: str, target: VDevice = None):
        """Initialize the hybrid inference engine and configure the Hailo device."""
        self.hef_path = hef_path
        
        # Initialize Hailo hardware
        self.target = target if target is not None else VDevice()
        self.hef = HEF(hef_path)
        configure_params = ConfigureParams.create_from_hef(self.hef, interface=HailoStreamInterface.PCIe)
        self.network_group = self.target.configure(self.hef, configure_params)[0]
        
        # Setup virtual streams
        self.input_vstream_params = InputVStreamParams.make(self.network_group)
        self.output_vstream_params = OutputVStreamParams.make(self.network_group, format_type=FormatType.FLOAT32)
        
        print(f"✓ Hailo engine initialized: {hef_path}")
        print(f"✓ Using Python head for dynamic shape-matching post-processing.")
    
    @staticmethod
    def preprocess(img_path: str, width: int = 640, height: int = 640, normalize: bool = False) -> Tuple[np.ndarray, Tuple[int, int], float, int, int]:
        """Preprocess image to a tensor and return original dimensions alongside preprocessing stats."""
        return load_and_preprocess_image(img_path, width, normalize)
    
    @staticmethod
    def load_image(img_path: str) -> np.ndarray:
        """Load and read the original image from the filesystem."""
        img = cv2.imread(img_path)
        if img is None:
            raise FileNotFoundError(f"Image not found: {img_path}")
        return img
    
    def _run_python_head(self, dequantized_results: Dict, conf_threshold: float) -> List[dict]:
        """Run python head logic on dequantized Hailo outputs using dynamic shape mapping."""
        
        reg_tensors = {}
        cls_tensors = {}
        num_classes = 1 # Default assumption
        
        # Automatically map outputs based on tensor shape (C=4 means regression, else classification)
        for name, data in dequantized_results.items():
            shape = data.shape
            spatial_dim = shape[1] # e.g., 80, 40, or 20
            channels = shape[-1]
            
            if channels == 4:
                reg_tensors[spatial_dim] = data
            else:
                cls_tensors[spatial_dim] = data
                num_classes = channels
        
        # Ensure we have the required 3 layers for both regression and classification
        if len(reg_tensors) != 3 or len(cls_tensors) != 3:
            print(f"Error: Expected 3 regression and 3 classification tensors. Found {len(reg_tensors)} reg, {len(cls_tensors)} cls")
            return []

        # Map grid spatial dimensions to model strides
        grid_to_stride = {80: 8, 40: 16, 20: 32}
        logit_threshold = -np.log(1.0 / conf_threshold - 1.0)
        
        results = []
        
        # Dynamically assign class map based on the detected number of classes
        if num_classes == 1:
            classes_map = {0: 'face'}
        else:
            classes_map = DetectionPostProcessor._load_coco_classes()
        
        # Process each grid level
        for grid_dim, stride in grid_to_stride.items():
            if grid_dim not in cls_tensors or grid_dim not in reg_tensors:
                continue
                
            cls_data = cls_tensors[grid_dim][0]  # Shape: (H, W, C)
            reg_data = reg_tensors[grid_dim][0]  # Shape: (H, W, 4)
            
            # Flatten spatial dimensions for vectorized operations
            cls_flat = cls_data.reshape(-1, num_classes)
            reg_flat = reg_data.reshape(-1, 4)
            
            # Find maximum logit and corresponding class ID for each anchor
            max_logits = cls_flat.max(axis=1)
            class_ids = cls_flat.argmax(axis=1)
            
            # Filter predictions utilizing the threshold mask
            mask = max_logits > logit_threshold
            if not mask.any():
                continue
            
            indices = np.where(mask)[0]
            scores = sigmoid(max_logits[indices])
            cls = class_ids[indices]
            
            # Calculate original grid coordinates
            rows = indices // grid_dim
            cols = indices % grid_dim
            
            # Decode bounding box distances
            l = reg_flat[indices, 0]
            t = reg_flat[indices, 1]
            r = reg_flat[indices, 2]
            b = reg_flat[indices, 3]
            
            # Convert distances into absolute coordinates
            x1 = (cols + 0.5 - l) * stride
            y1 = (rows + 0.5 - t) * stride
            x2 = (cols + 0.5 + r) * stride
            y2 = (rows + 0.5 + b) * stride
            
            # Assemble the final results
            for j in range(len(indices)):
                results.append({
                    'x1': round(float(x1[j]), 2),
                    'y1': round(float(y1[j]), 2),
                    'x2': round(float(x2[j]), 2),
                    'y2': round(float(y2[j]), 2),
                    'conf': round(float(scores[j]), 4),
                    'cls_id': int(cls[j]),
                    'cls_name': classes_map.get(int(cls[j]), 'N/A')
                })
        
        return results
    
    def infer(self, input_data: np.ndarray, verbose: bool = False, save_output: bool = False, conf_threshold: float = 0.5, task: str = 'detection'):
        """Run the complete hybrid inference pipeline."""
        stats = InferenceStats(
            preprocess_time=0, hailo_inference_time=0, 
            postprocess_time=0, total_time=0,
            hailo_output_shape="", final_output_shape=""
        )
        
        t_start = time.perf_counter()
        
        if verbose:
            print(f"[INFERENCE] Input shape: {input_data.shape}, dtype: {input_data.dtype}")
        
        with self.network_group.activate() as active_group:
            with InferVStreams(self.network_group, self.input_vstream_params, self.output_vstream_params) as infer_pipeline:
                
                # A. Hailo Backbone Inference
                if verbose: print(f"[STAGE 1] Running Hailo backbone...")
                t_hailo = time.perf_counter()
                hailo_results = infer_pipeline.infer(input_data)
                stats.hailo_inference_time = time.perf_counter() - t_hailo
                stats.hailo_output_shape = str({k: v.shape for k, v in hailo_results.items()})
                if verbose: print(f"  ✓ Hailo inference: {stats.hailo_inference_time*1000:.2f}ms")

                # B. Python Head Post-Processing
                if verbose: print(f"[STAGE 2] Running Python Head...")
                # B. Post-Processing based on task
                t_post = time.perf_counter()
                
                if task == 'recognition':
                    # Skip YOLO post-processing, return raw feature vectors for ArcFace
                    detections = list(hailo_results.values())
                    stats.postprocess_time = time.perf_counter() - t_post
                    stats.final_output_shape = f"Features: {len(detections)}"
                else:
                    # Run Python Head for YOLO Detection
                    if verbose: print(f"[STAGE 2] Running Python Head...")
                    detections = self._run_python_head(hailo_results, conf_threshold)
                    stats.postprocess_time = time.perf_counter() - t_post
                    stats.final_output_shape = f"{len(detections)} detections"
        
        return detections, stats


class DetectionPostProcessor:
    """Utility class to postprocess detections and draw bounding boxes using standardized class mapping."""
    
    COCO_CLASSES = None
    
    @classmethod
    def _load_coco_classes(cls):
        """Return standard COCO class names as a fallback."""
        if cls.COCO_CLASSES is not None:
            return cls.COCO_CLASSES
        
        # Standard COCO 80 classes dataset mapping
        cls.COCO_CLASSES = {
            0: 'person', 1: 'bicycle', 2: 'car', 3: 'motorcycle', 4: 'airplane', 5: 'bus', 6: 'train', 7: 'truck', 8: 'boat', 9: 'traffic light',
            10: 'fire hydrant', 11: 'stop sign', 12: 'parking meter', 13: 'bench', 14: 'bird', 15: 'cat', 16: 'dog', 17: 'horse', 18: 'sheep', 19: 'cow',
            20: 'elephant', 21: 'bear', 22: 'zebra', 23: 'giraffe', 24: 'backpack', 25: 'umbrella', 26: 'handbag', 27: 'tie', 28: 'suitcase', 29: 'frisbee',
            30: 'skis', 31: 'snowboard', 32: 'sports ball', 33: 'kite', 34: 'baseball bat', 35: 'baseball glove', 36: 'skateboard', 37: 'surfboard', 38: 'tennis racket', 39: 'bottle',
            40: 'wine glass', 41: 'cup', 42: 'fork', 43: 'knife', 44: 'spoon', 45: 'bowl', 46: 'banana', 47: 'apple', 48: 'sandwich', 49: 'orange',
            50: 'broccoli', 51: 'carrot', 52: 'hot dog', 53: 'pizza', 54: 'donut', 55: 'cake', 56: 'chair', 57: 'couch', 58: 'potted plant', 59: 'bed',
            60: 'dining table', 61: 'toilet', 62: 'tv', 63: 'laptop', 64: 'mouse', 65: 'remote', 66: 'keyboard', 67: 'cell phone', 68: 'microwave', 69: 'oven',
            70: 'toaster', 71: 'sink', 72: 'refrigerator', 73: 'book', 74: 'clock', 75: 'vase', 76: 'scissors', 77: 'teddy bear', 78: 'hair drier', 79: 'toothbrush'
        }
        
        return cls.COCO_CLASSES
    
    @staticmethod
    def postprocess(detections: np.ndarray, conf_threshold: float = 0.5) -> List[dict]:
        """Parse raw detection arrays and filter them by confidence score.
        
        Args:
            detections: Shape (num_detections, 6) containing [x1, y1, x2, y2, conf, cls].
            conf_threshold: Minimum confidence threshold.
            
        Returns:
            List of dictionaries containing the parsed detection data.
        """
        classes = DetectionPostProcessor._load_coco_classes()
        results = []
        
        for det in detections:
            conf = det[4]
            if conf >= conf_threshold:
                cls_id = int(det[5])
                cls_name = classes.get(cls_id) if isinstance(classes, dict) else classes[cls_id]
                results.append({
                    'x1': float(det[0]),
                    'y1': float(det[1]),
                    'x2': float(det[2]),
                    'y2': float(det[3]),
                    'conf': float(conf),
                    'cls_id': cls_id,
                    'cls_name': cls_name
                })
        return results
    
    @staticmethod
    def draw_bboxes(image: np.ndarray, detections: list, thickness: int = 2) -> np.ndarray:
        """Draw bounding boxes and class labels onto the target image."""
        img = image.copy()
        h, w = img.shape[:2]
        
        colors = [(0, 255, 0), (255, 0, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255)]
        
        for i, det in enumerate(detections):
            x1 = int(max(0, det['x1']))
            y1 = int(max(0, det['y1']))
            x2 = int(min(w, det['x2']))
            y2 = int(min(h, det['y2']))
            
            color = colors[i % len(colors)]
            cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)
            
            label = f"{det['cls_name']} {det['conf']:.2f}"
            cv2.putText(img, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        return img
