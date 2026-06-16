import onnxruntime as ort
import numpy as np

model_path = "shared/models/yolo/TFF4040_hand.onnx"
try:
    session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
    print("=== Model Inputs ===")
    for i in session.get_inputs():
        print(f"Name: {i.name}, Shape: {i.shape}, Type: {i.type}")
    
    print("\n=== Model Outputs ===")
    for o in session.get_outputs():
        print(f"Name: {o.name}, Shape: {o.shape}, Type: {o.type}")
        
    # Let's check model metadata
    meta = session.get_modelmeta()
    print("\n=== Model Metadata ===")
    print(f"Producer: {meta.producer_name}")
    print(f"Version: {meta.version}")
    print(f"Custom Metadata: {meta.custom_metadata_map}")
except Exception as e:
    print(f"Error loading model: {e}")
