import onnx
import onnxruntime as ort
import json

def main():
    model_path = "shared/models/yolo/TFF4040.onnx"
    print(f"Loading ONNX model to check metadata: {model_path}")
    model = onnx.load(model_path)
    
    # Check model metadata
    metadata = {}
    for prop in model.metadata_props:
        metadata[prop.key] = prop.value
        
    print("Metadata properties:")
    for k, v in metadata.items():
        if k == "names":
            try:
                names = json.loads(v.replace("'", '"'))
                print(f"  names: {names}")
            except Exception:
                print(f"  names (raw): {v}")
        else:
            print(f"  {k}: {v}")
            
    # Check input and output shapes
    sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    print("\nInputs:")
    for inp in sess.get_inputs():
        print(f"  name: {inp.name}, shape: {inp.shape}, type: {inp.type}")
    print("Outputs:")
    for out in sess.get_outputs():
        print(f"  name: {out.name}, shape: {out.shape}, type: {out.type}")

if __name__ == "__main__":
    main()
