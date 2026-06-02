# PHẦN MỞ ĐẦU

### 1. Lý do chọn đề tài
Trong xu thế của cuộc Cách mạng Công nghiệp 4.0, việc tự động hóa và tối ưu hóa quy trình sản xuất đang trở thành ưu tiên hàng đầu của các nhà máy nhằm nâng cao năng suất, tiết kiệm chi phí và đảm bảo tính đồng đều chất lượng sản phẩm. Đối với các công đoạn lắp ráp thủ công bằng tay (Manual Assembly) của công nhân trên máy sản xuất, việc tuân thủ nghiêm ngặt **Quy trình Thao tác Chuẩn (SOP - Standard Operating Procedure)** đóng vai trò sống còn. Việc thực hiện sai quy trình, lắp ráp sai thứ tự có thể dẫn tới phế phẩm hàng loạt, tăng tỷ lệ lỗi ở khâu kiểm thử chất lượng cuối cùng (QA/QC).

Hiện nay, việc kiểm tra sự tuân thủ SOP của công nhân tại hầu hết các nhà máy ở Việt Nam vẫn đang được thực hiện một cách thủ công bởi các tổ trưởng (line leaders) hoặc kỹ sư chất lượng đi tuần tra ngẫu nhiên. Phương thức này tồn tại nhiều nhược điểm lớn:
1. **Tính gián đoạn:** Không thể giám sát liên tục 24/7 tất cả các trạm lắp ráp trên dây chuyền.
2. **Sai số do yếu tố con người:** Người giám sát dễ mệt mỏi, bỏ sót lỗi hoặc đánh giá cảm tính.
3. **Chi phí nhân sự cao:** Đòi hỏi nhiều nhân sự chất lượng cao chỉ để thực hiện việc tuần tra kiểm tra trực quan.
4. **Không có dữ liệu đối soát:** Khi xảy ra sự cố lỗi sản phẩm từ thị trường gửi về, nhà máy không có video ghi nhận lịch sử thao tác của trạm lắp ráp tương ứng để truy cứu nguyên nhân gốc rễ (Root Cause Analysis).

Sự bùng nổ của Trí tuệ Nhân tạo (AI) và Thị giác Máy tính (Computer Vision) đã mở ra một hướng tiếp cận mới: Giám sát thao tác tự động thông qua camera. Tuy nhiên, việc áp dụng công nghệ này vào thực tế nhà máy sản xuất phải đối mặt với hai thách thức kỹ thuật lớn:
*   **Về mặt giải thuật:** Các nghiên cứu học thuật thường sử dụng các mô hình nhận diện hành động video phức tạp như mạng tích chập 3D (3D-CNN), mạng dòng kép (Two-Stream networks), hoặc các mạng chuỗi thời gian như LSTM kết hợp với MediaPipe để trích xuất 21 điểm khóa xương bàn tay (keypoints). Các phương pháp này cực kỳ nhạy cảm với hiện tượng che khuất (occlusions) do tay công nhân luôn bị linh kiện hoặc dụng cụ che lấp trong lúc làm việc. Đồng thời, các mô hình này đòi hỏi tài nguyên tính toán cực kỳ lớn, không phù hợp cho việc giám sát cùng lúc nhiều camera thời gian thực.
*   **Về mặt hạ tầng:** Hầu hết các nhà máy công nghiệp tại Việt Nam khi nâng cấp hệ thống giám sát thông minh thường sử dụng các máy chủ sẵn có trong tủ mạng nội bộ (môi trường CPU-only, không có card đồ họa GPU rời đắt đỏ do các quy định khăt khe về phòng chống cháy nổ và bảo trì). Do đó, việc thiết kế một giải pháp vừa có độ chính xác cao vừa chạy mượt mà trên phần cứng CPU là một bài toán thực tế vô cùng cấp thiết.

Xuất phát từ nhu cầu thực tiễn đó, em đã lựa chọn đề tài: **"Nghiên cứu xây dựng hệ thống giám sát thao tác công nhân theo quy trình tiêu chuẩn (SOP) dựa trên AI và Camera IP trong thời gian thực"** cho đồ án tốt nghiệp của mình.

---

### 2. Mục tiêu nghiên cứu
Đề tài hướng tới việc giải quyết triệt để bài toán giám sát quy trình lắp ráp trên hạ tầng CPU-only thực tế với các mục tiêu cụ thể sau:
*   **Nghiên cứu lý thuyết:** Khảo sát các mô hình phát hiện vật thể tiên tiến (YOLOv11), các phương pháp bám vết bàn tay (hand tracking) và các kỹ thuật mô hình hóa chuỗi thao tác dựa trên không gian và máy trạng thái hữu hạn.
*   **Thiết kế hệ thống:** Xây dựng một kiến trúc hệ thống giám sát đa camera song song (Multi-camera pipeline), có khả năng chịu lỗi, tự động phục hồi kết nối camera RTSP, và tối ưu hóa xử lý đa luồng trên CPU.
*   **Xây dựng giải thuật cốt lõi:**
    *   Phát triển module nhận diện bàn tay sử dụng mô hình YOLO ONNX CPU tối ưu hóa luồng suy luận.
    *   Phát triển giải thuật định danh và phân biệt tay Trái/Phải của công nhân để phục vụ cho các thao tác yêu cầu sử dụng cả hai tay (dual-task).
    *   Thiết kế Động cơ Không gian Vùng (Spatial Zone Engine) dựa trên thuật toán hình học Point-in-Polygon để xác định chính xác sự tương tác của tay trong các vùng hoạt động (ROI).
    *   Xây dựng máy trạng thái SOP linh hoạt đọc từ file cấu hình YAML bên ngoài để kiểm duyệt thứ tự các bước lắp ráp.
*   **Xây dựng ứng dụng hoàn chỉnh:** Thiết kế cơ sở dữ liệu MySQL lưu trữ sự kiện vi phạm; xây dựng giao diện Single Page Application Web Dashboard real-time hiển thị video trích xuất, trạng thái các bước SOP, thông báo lỗi, thống kê hiệu suất tuân thủ và hệ thống cảnh báo âm thanh tại chỗ.
*   **Thực nghiệm & Tối ưu hóa:** Triển khai thử nghiệm trực tiếp trên mã sản phẩm lắp ráp thực tế TFF4040 tại nhà máy trên cấu hình máy chủ Intel Xeon Silver 4510 để đánh giá độ chính xác, tốc độ xử lý (latency, FPS) và mức độ tiêu thụ tài nguyên hệ thống.

---

### 3. Đối tượng và phạm vi nghiên cứu
*   **Đối tượng nghiên cứu:**
    *   Các thuật toán nhận dạng ảnh và phát hiện bàn tay bằng mô hình học sâu YOLO.
    *   Giải thuật hình học tính toán điểm trong đa giác (Point-in-Polygon).
    *   Mô hình máy trạng thái hữu hạn (FSM) biểu diễn quy trình tuần tự.
    *   Kỹ thuật lập trình đa luồng (multi-threading) và quản lý hàng đợi trong Python.
    *   Công nghệ tối ưu hóa suy luận ONNX Runtime trên nền tảng CPU.
*   **Phạm vi nghiên cứu:**
    *   Môi trường triển khai thực tế: Máy chủ Intel Xeon Silver 4510, 256GB RAM, không có GPU rời, chạy hệ điều hành Windows Server.
    *   Camera giám sát: Camera IP công nghiệp truyền luồng RTSP qua mạng LAN nội bộ.
    *   Quy trình lắp ráp: Thử nghiệm thực tế trên trạm lắp ráp mã sản phẩm TFF4040 (9 bước).
    *   Quy mô hệ thống: Giám sát song song từ 1 đến 5 camera trạm trong giai đoạn thử nghiệm đầu tiên.

---

### 4. Phương pháp nghiên cứu
Để thực hiện các mục tiêu đề ra, đồ án áp dụng kết hợp các phương pháp nghiên cứu sau:
1.  **Phương pháp nghiên cứu lý thuyết:** Đọc tài liệu khoa học, bài báo quốc tế về mô hình YOLO, ONNX Runtime, các bài toán giám sát hành động (Action Recognition) và các tài liệu kỹ thuật liên quan đến lập trình song song trong Python.
2.  **Phương pháp phân tích & thiết kế hệ thống:** Sử dụng ngôn ngữ UML để thiết kế kiến trúc phần mềm, biểu diễn luồng dữ liệu (DFD), sơ đồ hoạt động (Activity Diagram), sơ đồ thực thể mối quan hệ cơ sở dữ liệu (ERD).
3.  **Phương pháp thực nghiệm phần mềm (kỹ nghệ phần mềm):**
    *   Sử dụng Python làm ngôn ngữ lập trình chính.
    *   Sử dụng OpenCV làm thư viện xử lý ảnh nền tảng.
    *   Sử dụng ONNX Runtime để nạp và suy luận mô hình YOLOv11 ở định dạng ONNX.
    *   Xây dựng Web Server bằng Flask, Flask-SocketIO và cơ sở dữ liệu MySQL.
4.  **Phương pháp phân tích thống kê và đánh giá hiệu năng:** Đo lường các chỉ số FPS thực tế của camera, độ trễ suy luận AI (inference latency), mức độ chiếm dụng CPU/RAM của server, và ma trận nhầm lẫn (confusion matrix) của các bước SOP để đánh giá tính khả thi khi đưa hệ thống vào dây chuyền sản xuất thực tế.

---

### 5. Ý nghĩa khoa học và ý nghĩa thực tiễn của đề tài
*   **Ý nghĩa khoa học:**
    *   Đề xuất giải pháp **Spatial Zone-based Logic (Động cơ Không gian Vùng)** làm hướng tiếp cận thay thế tối ưu cho các mô hình MediaPipe và LSTM vốn nặng nề về năng lực tính toán và kém ổn định trong môi trường sản xuất thực tế bị che khuất nhiều.
    *   Ứng dụng thành công thuật toán hình học tính toán điểm trong đa giác (**Point-in-Polygon**) để xác định chính xác sự tương tác không gian giữa bàn tay công nhân và các khu vực làm việc (ROI).
    *   Thiết lập mô hình toán học Máy trạng thái hữu hạn (**FSM**) để kiểm duyệt trình tự và tính thời gian của quy trình lắp ráp sản xuất công nghiệp, đảm bảo tính linh hoạt cao nhờ tách biệt hoàn toàn cấu hình khai báo (YAML) khỏi mã nguồn hệ thống.
    *   Nghiên cứu và chứng minh tính khả thi của việc tối ưu hóa suy luận mô hình học sâu (Deep Learning Inference) thời gian thực trên các hệ thống CPU máy chủ Xeon bị giới hạn tài nguyên tính toán (không có GPU hỗ trợ).
*   **Ý nghĩa thực tiễn:**
    *   Hệ thống có khả năng triển khai trực tiếp vào các dây chuyền lắp ráp thực tế của nhà máy để hỗ trợ các kỹ sư chất lượng (QA/QC) giám sát sự tuân thủ SOP liên tục 24/7 mà không cần tuần tra thủ công.
    *   Hệ thống giúp cảnh báo lỗi ngay lập tức bằng âm thanh để công nhân kịp thời sửa sai tại chỗ, giảm tỷ lệ phế phẩm đầu ra của nhà máy.
    *   Cơ chế đệm vòng video (**FrameRingBuffer**) và tự động cắt lưu clip lỗi ngắn (10-30 giây) giúp tiết kiệm dung lượng ổ đĩa SSD đồng thời cung cấp dữ liệu hình ảnh trực quan phục vụ công tác truy tìm nguyên nhân gốc rễ (Root Cause Analysis).
    *   Giao diện web Single Page Application trực quan cho phép kỹ sư vận hành dễ dàng vẽ lại tọa độ các vùng ROI hoặc thay đổi các bước SOP của dòng sản phẩm mới thông qua các tệp YAML cấu hình.

---

### 6. Bố cục báo cáo
Nội dung của báo cáo đồ án tốt nghiệp được tổ chức thành 5 chương chính:
*   **Chương 1: Tổng quan về đề tài và các nghiên cứu liên quan:** Trình bày bối cảnh chung về giám sát quy trình sản xuất SOP trong công nghiệp 4.0, các loại lỗi vi phạm phổ biến và phân tích, so sánh các nghiên cứu khoa học đi trước để làm nổi bật khoảng trống nghiên cứu và giải pháp đề xuất của đồ án.
*   **Chương 2: Cơ sở lý thuyết và các công nghệ nền tảng:** Giới thiệu cơ sở khoa học của mô hình học sâu YOLOv11, định dạng ONNX Runtime và các kỹ thuật tối ưu hóa CPU máy chủ, giải thuật hình học tính toán Point-in-Polygon và Convex Hull, lý thuyết Máy trạng thái hữu hạn (FSM) cùng các công nghệ phụ trợ khác (RTSP, Threading, Flask-SocketIO, YAML).
*   **Chương 3: Phân tích và thiết kế hệ thống:** Phân tích các yêu cầu chức năng (FR), yêu cầu phi chức năng (NFR), xây dựng các sơ đồ UML (Use Case, Component, Deployment, Sequence Diagrams), thiết kế cơ sở dữ liệu MySQL, và kiến trúc chi tiết của các module xử lý (RTSP manager, Inference Engine, Spatial Zone Engine, SOP FSM, FrameRingBuffer).
*   **Chương 4: Xây dựng, tối ưu hóa và thực nghiệm đánh giá:** Chi tiết quá trình thu thập, gán nhãn tập dữ liệu bàn tay, cấu hình huấn luyện YOLOv11; các giải pháp lập trình tối ưu hóa CPU; thực nghiệm chi tiết quy trình TFF4040; đo đạc hiệu năng tốc độ xử lý (latency, FPS), độ ổn định tài nguyên (CPU, RAM, Disk I/O) và đánh giá độ chính xác SOP (confusion matrix, F1-Score), so sánh benchmark với phương pháp MediaPipe+LSTM.
*   **Chương 5: Kết luận và hướng phát triển tương lai:** Tổng kết lại các kết quả đạt được, chỉ ra các mặt hạn chế còn tồn tại và đề xuất các phương án nghiên cứu tiếp theo để nâng cấp hệ thống.
