#!/bin/bash
# Script setup_edge.sh - Chuẩn bị Edge server
# Chạy trên máy Edge: bash setup_edge.sh <hub_url> <api_key>
# Ví dụ: bash setup_edge.sh http://10.0.10.100:5001 my-secret-key

set -e

HUB_URL=${1:-"http://localhost:5001"}
API_KEY=${2:-"change-me-in-production"}

echo "=== Edge Setup ==="
echo "Hub URL: $HUB_URL"
echo ""

# Create folder structure
mkdir -p edge_log
mkdir -p shared/models/yolo
mkdir -p projects/sop_monitoring/config
mkdir -p projects/sop_monitoring/core/engines

# Create config.yaml
cat > edge_config.yaml << EOF
camera:
  id: "edge_camera"
  name: "Edge Camera"
  rtsp_url: "rtsp://admin:password@192.168.1.100:554/Streaming/Channels/101"
  resolution: [640, 480]

hub:
  url: "$HUB_URL"
  api_key: "$API_KEY"

ai:
  model_path: "shared/models/yolo/laprap.onnx"
  input_size: 416

sop:
  file: "projects/sop_monitoring/config/laprap.yaml"

push:
  interval_sec: 1.0
  quality: 60
EOF

echo "Created: edge_config.yaml"
echo ""
echo "=== Setup Complete ==="
echo "1. Copy ONNX model vào: shared/models/yolo/"
echo "2. Copy SOP config vào: projects/sop_monitoring/config/"
echo "3. Chạy: python edge_client/main.py --config edge_config.yaml"
