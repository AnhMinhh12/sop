import time
import numpy as np
import os
import sys

# Thêm đường dẫn gốc vào python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from shared.inference_engine import InferenceEngine
    import psutil
except ImportError as e:
    print(f"ImportError: {e}")
    sys.exit(1)

def run_benchmark():
    # Đường dẫn model từ log: shared/models/yolo/TFF4040_roboflow.onnx
    model_path = "shared/models/yolo/TFF4040_roboflow.onnx"
    if not os.path.exists(model_path):
        model_path = "models/yolo/hand_detector.onnx"
        if not os.path.exists(model_path):
            print("Model ONNX not found!")
            sys.exit(1)
            
    print(f"Benchmarking model: {model_path}")
    
    # Khởi tạo InferenceEngine (singleton)
    # Trong config.yaml: num_threads = 4, input_size = 416
    engine = InferenceEngine(model_path=model_path, num_threads=4, input_size=416)
    
    # Tạo frame giả lập (RGB, 480x640x3)
    dummy_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    # Chạy warm-up 10 lần
    print("Warming up engine...")
    for _ in range(10):
        _ = engine.infer(dummy_frame)
        
    # Chạy test 100 lần đo latency
    print("Running 100 benchmark iterations...")
    latencies = []
    for _ in range(100):
        start = time.perf_counter()
        res = engine.infer(dummy_frame)
        end = time.perf_counter()
        if res is not None:
            # Lấy latency nội bộ đo bởi InferenceEngine (chỉ tính thời gian chạy ONNX session.run)
            # Hoặc thời gian bao gồm cả preprocess đo bằng time.perf_counter() bên ngoài.
            # Ta lấy thời gian đo từ bên ngoài vì nó bao gồm cả Letterbox Resize + Blob creation.
            latencies.append((end - start) * 1000) 
        time.sleep(0.01) # nghỉ ngắn 10ms
        
    avg_latency = np.mean(latencies)
    min_latency = np.min(latencies)
    max_latency = np.max(latencies)
    std_latency = np.std(latencies)
    
    print("\n=== BENCHMARK RESULTS ===")
    print(f"Average Frame Processing Latency (incl. preprocess): {avg_latency:.2f} ms/frame")
    print(f"Min Latency:     {min_latency:.2f} ms")
    print(f"Max Latency:     {max_latency:.2f} ms")
    print(f"Std Dev:         {std_latency:.2f} ms")
    
    # Đo mức độ chiếm dụng CPU của process khi chạy liên tục
    print("\nMeasuring CPU utilization (running continuous inference for 5 seconds)...")
    p = psutil.Process(os.getpid())
    start_time = time.time()
    count = 0
    p.cpu_percent(interval=None) # reset cpu counter
    
    while time.time() - start_time < 5.0:
        _ = engine.infer(dummy_frame)
        count += 1
        
    cpu_usage = p.cpu_percent(interval=None)
    num_cores = psutil.cpu_count()
    cpu_normalized = cpu_usage / num_cores if num_cores else cpu_usage
    
    print(f"Total inferences: {count}")
    print(f"Process CPU usage: {cpu_usage:.1f}%")
    print(f"Normalized CPU usage (all cores): {cpu_normalized:.2f}%")

if __name__ == "__main__":
    run_benchmark()
