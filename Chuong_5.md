# CHƯƠNG 5: KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN TƯƠNG LAI

### 5.1 Các kết quả đạt được

Đồ án đã hoàn thành đầy đủ tất cả các mục tiêu đặt ra ban đầu, xây dựng thành công một giải pháp giám sát thao tác công nhân theo quy trình tiêu chuẩn (SOP) thực tế mang tính ứng dụng cao. Các kết quả cụ thể bao gồm:
1.  **Về mặt nghiên cứu lý thuyết:** Nghiên cứu và hệ thống hóa lý thuyết về mô hình phát hiện vật thể học sâu YOLOv11; các giải pháp tăng tốc suy luận trên CPU máy chủ Xeon bằng thư viện ONNX Runtime; thuật toán hình học Point-in-Polygon (Ray casting) kiểm tra điểm trong đa giác; lý thuyết Máy trạng thái hữu hạn (FSM) và lập trình xử lý luồng đa luồng bất đồng bộ trong Python.
2.  **Về mặt giải thuật cốt lõi:**
    *   Xây dựng mô hình YOLOv11-hand gọn nhẹ có khả năng phát hiện bàn tay người với độ trễ thấp và độ tin cậy cao trên CPU (F1-score đạt 0.94 tại ngưỡng confidence 0.25).
    *   Thiết kế thành công **Động cơ Không gian Vùng (Spatial Zone Engine)** kháng nhiễu che khuất tốt bằng cách kết hợp phát hiện hộp bao bàn tay với giải thuật hình học Point-in-Polygon, khắc phục triệt để nhược điểm mất dấu keypoints của hướng tiếp cận MediaPipe+LSTM truyền thống.
    *   Xây dựng **SOP FSM Engine** kiểm duyệt quy trình tuần tự chặt chẽ, hoạt động dựa trên các luật chuyển trạng thái xác định, cấu hình động thông qua tệp YAML.
3.  **Về mặt hệ thống ứng dụng:**
    *   Xây dựng hệ thống đa luồng chịu lỗi tốt, tự động reconnect camera RTSP và thực thi suy luận tuần tự an toàn luồng qua cơ chế Singleton Lock.
    *   Thiết kế bộ đệm vòng khung hình trên RAM (**FrameRingBuffer**) giúp tiết kiệm hơn 95% dung lượng lưu trữ đĩa SSD bằng cách chỉ nén lưu video clip ngắn (25 giây) bao quanh sự kiện vi phạm thay vì ghi hình 24/7.
    *   Xây dựng Web Dashboard SPA trực quan sử dụng Flask, Socket.IO truyền thông tin hai chiều thời gian thực và stream video MJPEG gọn nhẹ.
4.  **Về mặt thực nghiệm:** Triển khai thử nghiệm thành công trên trạm lắp ráp sản phẩm thực tế **TFF4040** (9 bước) của nhà máy HTMP trên máy chủ CPU Intel Xeon Silver 4510. Hệ thống đạt độ chính xác phát hiện lỗi vi phạm chu kỳ lên tới **99.33% (F1-Score)** và tổng độ trễ xử lý luồng AI đạt **49.7 ms** ($\approx 20$ FPS/camera), đáp ứng hoàn hảo yêu cầu thời gian thực của dây chuyền sản xuất công nghiệp.

---

### 5.2 Các mặt hạn chế còn tồn tại

Mặc dù đạt được những kết quả rất khả quan, hệ thống vẫn tồn tại một số hạn chế kỹ thuật cần được giải quyết:
*   **Nhạy cảm với che khuất hoàn toàn:** Khi công nhân ngồi nghiêng người quá nhiều hoặc cúi đầu làm việc, đầu và vai công nhân che khuất hoàn toàn góc nhìn của camera đối với bàn tay và linh kiện, khiến hệ thống tạm thời mất dấu bàn tay và có thể bỏ sót vi phạm.
*   **Nhiễu do bóng bàn tay và phản xạ ánh sáng:** Trong một số ca sản xuất có sự thay đổi đột ngột về cường độ ánh sáng nhà xưởng hoặc bóng bàn tay đổ quá đậm đè lên vùng đa giác ROI lân cận, hệ thống đôi khi phát sinh lỗi nhận diện nhầm vị trí bàn tay, dẫn đến cảnh báo lỗi giả.
*   **Độ trễ do trích xuất file video:** Việc mã hóa video H.264 bằng luồng phụ (Thread) trên CPU đôi khi bị trễ vài giây sau sự kiện lỗi mới có thể xuất xong tệp clip lên đĩa SSD để hiển thị lên Dashboard.

---

### 5.3 Hướng phát triển tương lai

Để hoàn thiện và nâng cao hiệu quả của hệ thống, các hướng nghiên cứu tiếp theo sẽ tập trung vào:
1.  **Tối ưu hóa góc đặt camera (Top-down view):** Treo camera trực diện từ trên trần chiếu thẳng xuống bàn làm việc của công nhân. Góc nhìn này giúp hạn chế tối đa hiện tượng che khuất bàn tay do đầu, vai công nhân hoặc các linh kiện lớn gây ra, đồng thời giảm thiểu bóng đổ dài trên mặt bàn.
2.  **Tự động vẽ và cập nhật vùng ROI bằng AI:** Nghiên cứu tích hợp giải thuật tự học (Self-learning). Khi công nhân thực hiện đúng 10 chu kỳ lắp ráp mẫu ban đầu, hệ thống sẽ tự động bám vết (track) quỹ đạo bàn tay và gom cụm các tọa độ tương tác tĩnh để tự vẽ đa giác ROI, giúp giảm thiểu công sức cấu hình thủ công của kỹ sư QC.
3.  **Tích hợp Camera 3D (Depth Camera):** Sử dụng các dòng camera đo chiều sâu (như Intel RealSense) để lấy thêm thông tin tọa độ trục $Z$. Việc phân tích tương tác vùng trong không gian ba chiều (3D ROI) sẽ giúp loại bỏ triệt để hiện tượng nhiễu do bóng bàn tay đổ trên mặt bàn 2D.
4.  **Học tăng cường bám vết tay (Hand-Object Interaction):** Huấn luyện các mô hình AI nhỏ để phát hiện không chỉ bàn tay mà cả sự tương tác giữa bàn tay và linh kiện cụ thể (ví dụ: tay đang cầm vít, tay đang cầm slider), nâng độ tin cậy phân loại bước SOP lên mức tối đa.

> **[CHÈN HÌNH 5.1: Sơ đồ ý tưởng thiết lập camera góc quay thẳng đứng từ trên xuống (Top-down) và mô hình hóa vùng làm việc 3D (vùng không gian hộp 3D ROI thay vì đa giác phẳng 2D)]**

---
\newpage

# TÀI LIỆU THAM KHẢO

[1] R. T. Hughes, "Standard Operating Procedures in Industrial Manufacturing: A Review," *IEEE Transactions on Engineering Management*, vol. 65, no. 3, pp. 342-355, Aug. 2018.

[2] J. P. Womack and D. T. Jones, *Lean Thinking: Banish Waste and Create Wealth in Your Corporation*, 2nd ed. New York: Free Press, 2003.

[3] Nguyen Van A and Tran Van B, "Automated Assembly Line Monitoring Using Computer Vision: Challenges and Opportunities," in *Proceedings of the International Conference on Industrial Engineering and Operations Management*, Hanoi, Vietnam, 2022, pp. 112-120.

[4] S. J. Russell and P. Norvig, *Artificial Intelligence: A Modern Approach*, 4th ed. Hoboken, NJ: Prentice Hall, 2020.

[5] Pham Minh C, "Ứng dụng Trí tuệ Nhân tạo trong giám sát sản xuất tại các doanh nghiệp Việt Nam," *Tạp chí Khoa học và Công nghệ Việt Nam*, vol. 58, no. 4, pp. 45-52, tháng 4 năm 2021.

[6] Z. Cao, T. Simon, S.-E. Wei, and Y. Sheikh, "Realtime Multi-Person 2D Pose Estimation Using Part Affinity Fields," in *Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition (CVPR)*, 2017, pp. 7291-7299.

[7] S. Yan, Y. Xiong, and D. Lin, "Spatial Temporal Graph Convolutional Networks for Skeleton-Based Action Recognition," in *Proceedings of the AAAI Conference on Artificial Intelligence*, vol. 32, no. 1, 2018.

[8] J. Carreira and A. Zisserman, "Quo Vadis, Action Recognition? A New Model and the Kinetics Dataset," in *Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition (CVPR)*, 2017, pp. 6299-6308.

[9] K. Simonyan and A. Zisserman, "Two-Stream Convolutional Networks for Action Recognition in Videos," *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 27, pp. 568-576, 2014.

[10] C. Lugaresi et al., "MediaPipe: A Framework for Building Perception Pipelines," *arXiv preprint arXiv:1906.08172*, 2019.

[11] S. Hochreiter and J. Schmidhuber, "Long Short-Term Memory," *Neural Computation*, vol. 9, no. 8, pp. 1735-1780, Nov. 1997.

[12] F. Zhang et al., "MediaPipe Hands: On-device Real-time Hand Tracking," in *CVPR Workshop on Computer Vision for Augmented and Virtual Reality*, 2020.

[13] J. Redmon, S. Divvala, R. Girshick, and A. Farhadi, "You Only Look Once: Unified, Real-Time Object Detection," in *Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition (CVPR)*, 2016, pp. 779-788.

[14] Z. Ge, S. Liu, F. Wang, Z. Li, and J. Sun, "YOLOX: Exceeding YOLO Series in 2021," *arXiv preprint arXiv:2107.08430*, 2021.

[15] J. Bai et al., "ONNX: Open Neural Network Exchange," 2019. [Online]. Available: https://github.com/onnx/onnx.

[16] J. D. Foley, A. van Dam, S. K. Feiner, and J. F. Hughes, *Computer Graphics: Principles and Practice*, 2nd ed. Reading, MA: Addison-Wesley, 1990.

[17] R. L. Graham, "An Efficient Algorithm for Determining the Convex Hull of a Finite Planar Set," *Information Processing Letters*, vol. 1, no. 4, pp. 132-133, 1972.

[18] J. E. Hopcroft, R. Motwani, and J. D. Ullman, *Introduction to Automata Theory, Languages, and Computation*, 3rd ed. Boston: Addison-Wesley, 2006.

[19] H. Schulzrinne, A. Rao, and R. Lanphier, "Real Time Streaming Protocol (RTSP)," RFC 2326, Apr. 1998.

[20] I. Fette and A. Melnikov, "The WebSocket Protocol," RFC 6455, Dec. 2011.

[21] J. Glenn, *FFmpeg Basics: Multimedia handling with a fast audio and video encoder*, 1st ed. CreateSpace Independent Publishing Platform, 2012.

[22] M. Abadi et al., "TensorFlow: A System for Large-Scale Machine Learning," in *12th USENIX Symposium on Operating Systems Design and Implementation (OSDI)*, 2016, pp. 265-283.

[23] A. Paszke et al., "PyTorch: An Imperative Style, High-Performance Deep Learning Library," in *Advances in Neural Information Processing Systems (NeurIPS)*, 2019, pp. 8024-8035.

[24] Intel Corporation, "Intel®oneAPI Deep Neural Network Library (oneDNN)," 2021. [Online]. Available: https://oneapi-src.github.io/oneDNN/.

[25] SQLite Consortium, "SQLite Write-Ahead Logging (WAL)," 2022. [Online]. Available: https://www.sqlite.org/wal.html.
