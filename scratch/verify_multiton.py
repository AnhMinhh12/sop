import os
import shutil
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from shared.inference_engine import InferenceEngine

def test_multiton():
    print("=== TESTING MULTITON INFERENCE ENGINE ===")
    
    # Clean up any leftover from previous runs
    test_model_path = "shared/models/yolo/laprap_test.onnx"
    if os.path.exists(test_model_path):
        os.remove(test_model_path)
        
    shutil.copy("shared/models/yolo/laprap.onnx", test_model_path)
    
    try:
        # Load the same model twice (should return the same instance)
        engine1 = InferenceEngine("shared/models/yolo/laprap.onnx")
        engine2 = InferenceEngine("shared/models/yolo/laprap.onnx")
        print(f"Same model comparison (expect True): {engine1 is engine2}")
        
        # Load a different model path (should return a different instance)
        engine3 = InferenceEngine(test_model_path)
        print(f"Different model comparison (expect False): {engine1 is engine3}")
        
        # Verify both paths are registered in the multiton registry
        loaded_paths = [os.path.basename(p) for p in InferenceEngine._instances.keys()]
        print(f"Registered models in cache: {loaded_paths}")
        
        # Verify fallback lookup (get_instance with no arguments returns first loaded or matching)
        default_engine = InferenceEngine.get_instance()
        print(f"Default engine fallback resolved (expect True): {default_engine is engine1}")
        
    finally:
        if os.path.exists(test_model_path):
            os.remove(test_model_path)

if __name__ == "__main__":
    test_multiton()
