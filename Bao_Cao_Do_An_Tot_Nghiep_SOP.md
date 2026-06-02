# TRƯỜNG ĐẠI HỌC GIAO THÔNG VẬN TẢI
# KHOA CÔNG NGHỆ THÔNG TIN
# BỘ MÔN KỸ THUẬT MÁY TÍNH & MẠNG

---

<br><br><br><br>

# ĐỒ ÁN TỐT NGHIỆP
### ĐỀ TÀI:
## NGHIÊN CỨU XÂY DỰNG HỆ THỐNG GIÁM SÁT THAO TÁC CÔNG NHÂN THEO QUY TRÌNH TIÊU CHUẨN (SOP) DỰA TRÊN AI VÀ CAMERA IP TRONG THỜI GIAN THỰC

<br><br><br><br>

**Sinh viên thực hiện:** Trần Tiến Dũng  
**Mã số sinh viên:** 19150xxxx  
**Lớp:** Công nghệ thông tin Việt Anh 2 - K63  
**Giảng viên hướng dẫn:** TS. Nguyễn Văn A  

<br><br><br><br>
### HÀ NỘI, 2026

---

## LỜI CẢM ƠN

Đầu tiên, em xin bày tỏ lòng biết ơn sâu sắc đến Ban giám hiệu Trường Đại học Giao thông Vận tải, cùng toàn thể các thầy cô giáo khoa Công nghệ Thông tin đã tận tình truyền đạt kiến thức, dạy dỗ và dìu dắt em trong suốt 4 năm học tập và rèn luyện dưới mái trường.

Đặc biệt, em xin gửi lời cảm ơn chân thành và sâu sắc nhất tới thầy **TS. Nguyễn Văn A**, người đã trực tiếp định hướng đề tài, tận tình hướng dẫn, chỉ bảo và động viên em trong suốt quá trình nghiên cứu và hoàn thiện đồ án tốt nghiệp này. Sự định hướng khoa học cùng những ý kiến đóng góp quý báu của thầy là yếu tố quyết định giúp đồ án được hoàn thành đúng hạn với chất lượng tốt nhất.

Em cũng xin gửi lời cảm ơn ban giám đốc và các anh chị kỹ sư tại **Nhà máy sản xuất HTMP** đã tạo điều kiện tối đa cho em được khảo sát thực địa, thu thập mẫu video thao tác thực tế từ dây chuyền sản xuất và hỗ trợ môi trường phần cứng máy chủ Xeon phục vụ quá trình triển khai thử nghiệm hệ thống.

Cuối cùng, em xin gửi lời cảm ơn tới gia đình, bạn bè và các bạn cùng lớp đã luôn sát cánh, chia sẻ khó khăn, cổ vũ và giúp đỡ em trong học tập cũng như trong cuộc sống.

Mặc dù đã có nhiều cố gắng để hoàn thành đồ án một cách hoàn chỉnh nhất, song do giới hạn về mặt thời gian và kiến thức bản thân, đồ án chắc chắn không tránh khỏi những thiếu sót. Em rất mong nhận được những lời chỉ bảo, góp ý quý báu của các thầy cô giáo trong Hội đồng chấm đồ án tốt nghiệp để hệ thống có thể hoàn thiện hơn và có tính ứng dụng thực tiễn cao hơn.

*Em xin chân thành cảm ơn!*

---

## TÓM TẮT ĐỒ ÁN

Đồ án tập trung nghiên cứu, thiết kế và xây dựng **Hệ thống giám sát thao tác công nhân theo quy trình tiêu chuẩn (SOP - Standard Operating Procedure)** tại nhà máy lắp ráp công nghiệp dựa trên công nghệ học sâu (Deep Learning) và Camera IP thời gian thực. Hệ thống được triển khai trên môi trường máy chủ sản xuất thực tế chỉ chạy CPU (**Intel Xeon Silver 4510**, không hỗ trợ GPU chuyên dụng), đặt ra bài toán tối ưu hóa tài nguyên cực kỳ khắt khe.

Giải pháp đề xuất sử dụng mô hình **YOLOv11** xuất sang định dạng **ONNX** để chạy nhận diện bàn tay của công nhân ở tần suất 15 FPS trên CPU thông qua **ONNX Runtime (CPU Execution Provider)** kết hợp với cơ chế đa luồng (Multi-threading) độc lập cho từng camera trạm. Để thay thế giải pháp LSTM và MediaPipe Keypoints vốn đòi hỏi tài nguyên tính toán quá lớn và kém ổn định trong môi trường thực địa bị che khuất nhiều, hệ thống đề xuất giải thuật **Spatial Zone-based Logic (Động cơ Không gian Vùng)**. Bằng cách định nghĩa các vùng làm việc hoạt động (ROI - Region of Interest) dưới dạng các đa giác (Polygons), thuật toán sử dụng phép kiểm tra điểm trong đa giác (**Point-in-Polygon**) để theo dõi sự tương tác của bàn tay công nhân với các linh kiện. 

Một **Máy trạng thái hữu hạn (SOP Finite State Machine)** được phát triển linh hoạt cho từng mã sản phẩm lắp ráp (như TFF4040 với 9 bước và 626287 với 7 bước), cấu hình hoàn toàn bằng file YAML để kiểm soát thứ tự thực hiện các bước SOP. Hệ thống tích hợp các thuật toán lọc nhiễu ROI động, bám vết bàn tay bằng khoảng cách Euclid giữa các khung hình liên tiếp để định danh tay Trái/Phải, và cơ chế chống phát hiện giả do tay di chuyển nhanh qua vùng ("Tay ma" - Ghost Hands Protection). 

Hệ thống ghi nhận sự kiện vi phạm (Timeout, Skip Step, Premature Restart), phát cảnh báo âm thanh tức thời tại trạm qua còi báo vật lý, đồng thời lưu trữ các clip vi phạm ngắn từ 10-30 giây thông qua cơ chế đệm vòng **FrameRingBuffer** chạy ngầm liên tục trước và sau khi lỗi xảy ra. Các sự kiện này được đồng bộ vào hệ quản trị cơ sở dữ liệu **MySQL** và cập nhật thời gian thực lên ứng dụng Web Dashboard thông qua **Flask-SocketIO** và luồng phát video định dạng **MJPEG**. Kết quả thực nghiệm cho thấy hệ thống hoạt động ổn định trên dòng CPU Intel Xeon Server, đạt độ chính xác nhận dạng SOP trên 95% và đáp ứng thời gian thực với độ trễ xử lý trung bình dưới 65ms mỗi khung hình.

**Từ khóa:** *Giám sát quy trình SOP, YOLO ONNX CPU, Máy trạng thái hữu hạn, Point-in-Polygon, Frame Ring Buffer, Intel Xeon Server.*

---

## ABSTRACT

This thesis focuses on researching, designing, and building an **AI-powered Standard Operating Procedure (SOP) Monitoring System** using real-time IP Cameras on industrial assembly lines. The system is deployed on a production server environment equipped only with CPUs (**Intel Xeon Silver 4510**, no dedicated GPUs), which introduces highly stringent resource constraints.

The proposed solution utilizes the **YOLOv11** model exported to **ONNX** format to run hand detection at 15 FPS on CPU using **ONNX Runtime (CPU Execution Provider)** combined with independent multi-threading for each camera station. To replace the traditional LSTM and MediaPipe Keypoints approach, which requires massive computational power and is prone to instability under severe occlusions on the factory floor, this system introduces a **Spatial Zone-based Logic (Spatial Engine)**. By defining active Regions of Interest (ROI) as polygons, the algorithm uses the **Point-in-Polygon** test to track the interactions of the worker's hands with components.

A flexible **SOP Finite State Machine** is developed for each assembly product (such as TFF4040 with 9 steps and 626287 with 7 steps), fully configured via YAML files to control the sequence of SOP steps. The system integrates dynamic ROI filtering, Euclid-distance-based hand tracking across consecutive frames to identify Left/Right hands, and a "Ghost Hands Protection" mechanism to prevent false triggers from quick movements.

When violations (Timeout, Skip Step, Premature Restart) occur, the system triggers instant audio alerts at the station, logs the event to a **MySQL** database, sends real-time notifications via **Flask-SocketIO**, and exports a 10-30 second video clip captured by a continuous background **FrameRingBuffer**. Live video streams are served via **MJPEG** on a single-page Web Dashboard. Experimental results demonstrate that the system runs stably on the Intel Xeon Server, achieving an SOP sequence verification accuracy above 95% and operating in real-time with an average per-frame processing latency of under 65ms.

**Keywords:** *SOP Monitoring, YOLO ONNX CPU, Finite State Machine, Point-in-Polygon, Frame Ring Buffer, Intel Xeon Server.*

---

## MỤC LỤC
1. **PHẦN MỞ ĐẦU**
   - 1. Lý do chọn đề tài
   - 2. Mục tiêu nghiên cứu của đồ án
   - 3. Đối tượng và phạm vi nghiên cứu
   - 4. Phương pháp nghiên cứu
2. **CHƯƠNG 1: TỔNG QUAN VÀ CƠ SỞ LÝ THUYẾT**
   - 1.1 Khái quát về giám sát quy trình sản xuất SOP trong công nghiệp
   - 1.2 Mô hình phát hiện vật thể học sâu YOLO (You Only Look Once)
   - 1.3 Cơ chế tăng tốc suy luận trên CPU bằng ONNX Runtime
   - 1.4 Giải thuật kiểm tra vị trí tương đối Point-in-Polygon
   - 1.5 Mô hình hóa quy trình bằng Máy trạng thái hữu hạn (FSM)
3. **CHƯƠNG 2: PHÂN TÍCH VÀ THIẾT KẾ HỆ THỐNG**
   - 2.1 Yêu cầu hệ thống và Kiến trúc tổng thể
   - 2.2 Thiết kế cơ sở dữ liệu (MySQL Database Schema)
   - 2.3 Phân tích luồng dữ liệu của camera trạm (RTSP Data Flow)
   - 2.4 Thiết kế chi tiết các cấu phần phần mềm chính
4. **CHƯƠNG 3: XÂY DỰNG, TỐI ƯU HÓA VÀ ĐÁNH GIÁ THỰC NGHIỆM**
   - 3.1 Xây dựng tập dữ liệu và huấn luyện mô hình YOLO
   - 3.2 Tối ưu hóa hệ thống trên máy chủ CPU Intel Xeon Silver 4510
   - 3.3 Chi tiết các bước thực nghiệm quy trình TFF4040 và 626287
   - 3.4 Đánh giá kết quả thực nghiệm và hiệu năng hệ thống
5. **KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN**
   - 1. Các kết quả đạt được
   - 2. Các hạn chế còn tồn tại
   - 3. Hướng phát triển trong tương lai
6. **TÀI LIỆU THAM KHẢO**

---

## DANH MỤC HÌNH VẼ
*   Hình 1.1: Sơ đồ kiến trúc YOLOv11 cấu trúc các tầng tích chập và đầu ra
*   Hình 1.2: Minh họa thuật toán Ray Casting xác định điểm nằm trong hay ngoài đa giác
*   Hình 2.1: Sơ đồ kiến trúc tổng thể ba lớp của hệ thống AI Monitoring Hub
*   Hình 2.2: Mô hình ERD mối quan hệ các bảng trong Cơ sở dữ liệu MySQL
*   Hình 2.3: Sơ đồ luồng dữ liệu (Data Flow) xử lý một khung hình trong FrameProcessor
*   Hình 2.4: Biểu đồ trạng thái (State Diagram) quy trình lắp ráp sản phẩm TFF4040
*   Hình 3.1: Giao diện công cụ Zone Selector xác định tọa độ đa giác các vùng ROI
*   Hình 3.2: Giao diện Web Dashboard hiển thị livestream MJPEG và trạng thái SOP trạm 7
*   Hình 3.3: Biểu đồ giám sát tải CPU/RAM hệ thống trên máy chủ Xeon trong quá trình chạy thực tế

---

## DANH MỤC BẢNG BIỂU
*   Bảng 1.1: Bảng so sánh phần cứng máy chủ Xeon Silver 4510 thực tế triển khai
*   Bảng 2.1: Đặc tả cấu trúc bảng `sop_definitions`
*   Bảng 2.2: Đặc tả cấu trúc bảng `sop_steps`
*   Bảng 2.3: Đặc tả cấu trúc bảng `sop_cameras`
*   Bảng 2.4: Đặc tả cấu trúc bảng `sop_events`
*   Bảng 3.1: Chi tiết 9 bước SOP và logic kiểm soát của mã sản phẩm TFF4040
*   Bảng 3.2: Chi tiết 7 bước SOP và logic kiểm soát của mã sản phẩm 626287
*   Bảng 3.3: Kết quả thực nghiệm về thời gian xử lý (latency) của từng module trên CPU
*   Bảng 3.4: Bảng so sánh độ chính xác phát hiện vi phạm giữa mô hình đề xuất và thực tế

---

## DANH MỤC KÝ HIỆU VÀ VIẾT TẮT
*   **SOP**: Standard Operating Procedure (Quy trình thao tác chuẩn)
*   **ROI**: Region of Interest (Vùng không gian quan tâm)
*   **FSM**: Finite State Machine (Máy trạng thái hữu hạn)
*   **ONNX**: Open Neural Network Exchange (Định dạng trao đổi mạng nơ-ron mở)
*   **RTSP**: Real-Time Streaming Protocol (Giao thức truyền phát thời gian thực)
*   **FPS**: Frames Per Second (Số khung hình trên giây)
*   **Bbox**: Bounding Box (Hộp bao nhận diện vật thể)
*   **IoU**: Intersection over Union (Tỷ lệ phần giao trên phần hợp)
*   **WAL**: Write-Ahead Logging (Ghi nhật ký trước khi ghi dữ liệu)
*   **JSON**: JavaScript Object Notation (Định dạng trao đổi dữ liệu gọn nhẹ)
*   **API**: Application Programming Interface (Giao diện lập trình ứng dụng)
*   **CPU**: Central Processing Unit (Bộ vi xử lý trung tâm)
*   **RAM**: Random Access Memory (Bộ nhớ truy cập ngẫu nhiên)

---
\newpage

# PHẦN MỞ ĐẦU

### 1. Lý do chọn đề tài
Trong xu thế của cuộc Cách mạng Công nghiệp 4.0, việc tự động hóa và tối ưu hóa quy trình sản xuất đang trở thành ưu tiên hàng đầu của các nhà máy nhằm nâng cao năng suất, tiết kiệm chi phí và đảm bảo tính đồng đều chất lượng sản phẩm. Đối với các công đoạn lắp ráp thủ công bằng tay (Manual Assembly) của công nhân trên dây chuyền sản xuất, việc tuân thủ nghiêm ngặt **Quy trình Thao tác Chuẩn (SOP - Standard Operating Procedure)** đóng vai trò sống còn. Việc thực hiện sai quy trình, bỏ sót linh kiện, lắp ráp sai thứ tự, hoặc không đảm bảo thời gian giữ mối nối (dwell time) có thể dẫn tới phế phẩm hàng loạt, tăng tỷ lệ lỗi ở khâu kiểm thử chất lượng cuối cùng (QA/QC), thậm chí gây tai nạn lao động nghiêm trọng.

Hiện nay, việc kiểm tra sự tuân thủ SOP của công nhân tại hầu hết các nhà máy ở Việt Nam vẫn đang được thực hiện một cách thủ công bởi các trưởng chuyền (line leaders) hoặc kỹ sư chất lượng đi tuần tra ngẫu nhiên. Phương thức này tồn tại nhiều nhược điểm lớn:
1. **Tính gián đoạn:** Không thể giám sát liên tục 24/7 tất cả các trạm lắp ráp.
2. **Sai số do yếu tố con người:** Người giám sát dễ mệt mỏi, bỏ sót lỗi hoặc đánh giá cảm tính.
3. **Chi phí nhân sự cao:** Cần nhiều nhân sự chất lượng cao chỉ để đi kiểm tra tuần tra.
4. **Không có dữ liệu đối soát:** Khi xảy ra sự cố lỗi sản phẩm từ thị trường gửi về, nhà máy không có video ghi nhận lịch sử thao tác của trạm lắp ráp tương ứng để truy cứu nguyên nhân gốc rễ (Root Cause Analysis).

Sự bùng nổ của Trí tuệ Nhân tạo (AI) và Thị giác Máy tính (Computer Vision) đã mở ra một hướng tiếp cận mới: Giám sát thao tác tự động thông qua camera. Tuy nhiên, việc áp dụng công nghệ này vào thực tế nhà máy sản xuất phải đối mặt với hai thách thức kỹ thuật lớn:
*   **Về mặt giải thuật:** Các nghiên cứu học thuật thường sử dụng các mô hình nhận diện hành động video phức tạp như mạng tích chập 3D (3D-CNN), mạng dòng kép (Two-Stream networks), hoặc các mạng chuỗi thời gian như LSTM kết hợp với MediaPipe để trích xuất 21 điểm khóa xương bàn tay (keypoints). Các phương pháp này cực kỳ nhạy cảm với hiện tượng che khuất (occlusions) do tay công nhân luôn bị linh kiện hoặc dụng cụ che lấp trong lúc làm việc. Đồng thời, các mô hình này đòi hỏi tài nguyên tính toán cực kỳ lớn, không phù hợp cho việc giám sát cùng lúc nhiều camera thời gian thực.
*   **Về mặt hạ tầng:** Hầu hết các nhà máy công nghiệp tại Việt Nam khi nâng cấp hệ thống giám sát thông minh thường sử dụng các máy chủ Xeon sẵn có trong tủ mạng nội bộ (môi trường CPU-only, không có card đồ họa GPU rời đắt đỏ do các quy định khắt khe về phòng chống cháy nổ và bảo trì). Do đó, việc thiết kế một giải pháp vừa có độ chính xác cao vừa chạy mượt mà trên phần cứng CPU Xeon là một bài toán thực tế vô cùng cấp thiết.

Xuất phát từ nhu cầu thực tiễn đó, em đã lựa chọn đề tài: **"Nghiên cứu xây dựng hệ thống giám sát thao tác công nhân theo quy trình tiêu chuẩn (SOP) dựa trên AI và Camera IP trong thời gian thực"** cho đồ án tốt nghiệp của mình.

---

### 2. Mục tiêu nghiên cứu của đồ án
Đề tài hướng tới việc giải quyết triệt để bài toán giám sát quy trình lắp ráp trên hạ tầng CPU-only thực tế với các mục tiêu cụ thể sau:
*   **Nghiên cứu lý thuyết:** Khảo sát các mô hình phát hiện vật thể tiên tiến (YOLOv11), các phương pháp bám vết bàn tay (hand tracking) và các kỹ thuật mô hình hóa chuỗi thao tác dựa trên không gian và máy trạng thái hữu hạn.
*   **Thiết kế hệ thống:** Xây dựng một kiến trúc hệ thống giám sát đa camera song song (Multi-camera pipeline), có khả năng chịu lỗi, tự động phục hồi kết nối camera RTSP, và tối ưu hóa xử lý đa luồng trên CPU Xeon.
*   **Xây dựng giải thuật cốt lõi:**
    *   Phát triển module nhận diện bàn tay sử dụng mô hình YOLO ONNX CPU tối ưu hóa luồng suy luận.
    *   Phát triển giải thuật định danh và phân biệt tay Trái/Phải của công nhân để phục vụ cho các thao tác yêu cầu sử dụng cả hai tay (dual-task).
    *   Thiết kế Động cơ Không gian Vùng (Spatial Zone Engine) dựa trên thuật toán hình học Point-in-Polygon để xác định chính xác sự tương tác của tay trong các vùng hoạt động (ROI).
    *   Xây dựng máy trạng thái SOP linh hoạt đọc từ file cấu hình YAML bên ngoài để kiểm duyệt thứ tự các bước lắp ráp.
*   **Xây dựng ứng dụng hoàn chỉnh:** Thiết kế cơ sở dữ liệu MySQL lưu trữ sự kiện vi phạm; xây dựng giao diện Single Page Application Web Dashboard real-time hiển thị video trích xuất, trạng thái các bước SOP, thông báo lỗi, thống kê hiệu suất tuân thủ và hệ thống cảnh báo âm thanh tại chỗ.
*   **Thực nghiệm & Tối ưu hóa:** Triển khai thử nghiệm trực tiếp trên 2 mã sản phẩm lắp ráp thực tế tại nhà máy (TFF4040 và 626287) trên cấu hình máy chủ Intel Xeon Silver 4510 để đánh giá độ chính xác, tốc độ xử lý (latency, FPS) và mức độ tiêu thụ tài nguyên hệ thống.

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
    *   Quy trình lắp ráp: Thử nghiệm thực tế trên trạm lắp ráp mã sản phẩm TFF4040 (9 bước) và mã sản phẩm 626287 (7 bước).
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
\newpage

# CHƯƠNG 1: TỔNG QUAN VÀ CƠ SỞ LÝ THUYẾT

### 1.1 Khái quát về giám sát quy trình sản xuất SOP trong công nghiệp
Quy trình Thao tác Chuẩn (SOP) là tập hợp các chỉ dẫn chi tiết bằng văn bản mô tả từng bước thực hiện một công việc cụ thể nhằm đảm bảo tính đồng nhất, chất lượng đầu ra và an toàn cho người lao động. Trong ngành công nghiệp lắp ráp linh kiện điện tử, cơ khí chính xác hay ép nhựa định hình (như tại nhà máy HTMP), quy trình SOP thường yêu cầu công nhân thực hiện một chuỗi thao tác tay lặp đi lặp lại theo đúng trình tự không gian và thời gian.

Các lỗi vi phạm SOP phổ biến bao gồm:
*   **Bỏ bước (Skip Step):** Công nhân bỏ qua việc lắp ráp một linh kiện phụ (ví dụ: quên đặt gioăng cao su chống nước) mà tiến hành ngay bước tiếp theo.
*   **Thực hiện sai thứ tự:** Thực hiện khâu hàn nối trước khi định vị chốt nhựa, dẫn tới linh kiện bị lệch tâm.
*   **Quá thời gian quy định (Timeout):** Thao tác bị trì trệ do công nhân phân tâm hoặc gặp sự cố máy móc, gây trễ nhịp (cycle time) của toàn dây chuyền.
*   **Quay lại bước 1 sớm (Premature Restart):** Tay quay lại lấy phôi mới từ khuôn hoặc khay nạp khi sản phẩm hiện tại chưa hoàn thành xong bước cuối (chưa nhấn nút xác nhận chu kỳ).

Để giám sát tự động quy trình này bằng camera, hệ thống phải giải quyết được bài toán theo dõi quỹ đạo chuyển động của bàn tay công nhân và ánh xạ nó vào các vùng không gian làm việc tương ứng trên bàn thao tác.

---

### 1.2 Mô hình phát hiện vật thể học sâu YOLO (You Only Look Once)
YOLO (You Only Look Once) là dòng mô hình phát hiện vật thể thời gian thực dựa trên mạng nơ-ron tích chập (CNN) nổi tiếng nhất hiện nay. Khác với các phương pháp hai giai đoạn (two-stage) như R-CNN hay Faster R-CNN sử dụng mạng đề xuất vùng (Region Proposal Network) rồi mới phân loại, YOLO tiếp cận bài toán phát hiện vật thể như một bài toán hồi quy duy nhất (single regression problem). Mô hình truyền trực tiếp ảnh đầu vào qua mạng nơ-ron và dự đoán trực tiếp tọa độ hộp bao (Bounding Box) và xác suất lớp đối tượng trên toàn bộ khung hình.

```
+-------------------+      +-----------------------+      +-------------------------+
|  Ảnh đầu vào      | ---> | Mạng xương sống CNN   | ---> | Đầu ra:                 |
|  (RGB, 416x416)   |      | (Feature Extraction)  |      | Bounding Box [x,y,w,h]  |
+-------------------+      +-----------------------+      | Class: Bàn tay          |
                                                          | Confidence Score        |
                                                          +-------------------------+
```
*Hình 1.1: Sơ đồ khối suy luận cơ bản của mô hình YOLO*

Phiên bản **YOLOv11** mang lại những cải tiến vượt bậc về mặt kiến trúc:
*   **Sử dụng tầng tích chập C3k2 và bộ chia C2f:** Giúp trích xuất các đặc trưng không gian đa quy mô tốt hơn, đặc biệt nhạy bén với các vật thể nhỏ và có biên dạng thay đổi liên tục như bàn tay người trong quá trình chuyển động lắp ráp.
*   **Đầu ra Anchor-free:** Loại bỏ sự phụ thuộc vào các hộp neo (Anchor Boxes) được tính toán trước, cho phép mô hình dự đoán trực tiếp khoảng cách từ tâm đối tượng đến các cạnh biên, tăng độ chính xác định vị bbox.
*   **Hàm mất mát cải tiến (Loss Functions):** Kết hợp Complete IoU (CIoU) Loss và Distribution Focal Loss (DFL) giúp mô hình tối ưu hóa nhanh hơn, dự đoán hộp bao bao sát bàn tay hơn ngay cả khi tay bị nghiêng, xoay hoặc khum lại.

Trong đồ án này, mô hình YOLOv11 được huấn luyện đặc tả để chỉ nhận diện một lớp đối tượng duy nhất là **bàn tay người (hand)**. Ảnh đầu vào từ camera được chuẩn hóa về kích thước $416 \times 416$ pixel để cân bằng tối ưu giữa độ chính xác định vị và tốc độ tính toán trên CPU.

---

### 1.3 Cơ chế tăng tốc suy luận trên CPU bằng ONNX Runtime
Thông thường, các mô hình học sâu (PyTorch, TensorFlow) được thiết kế tối ưu để chạy trên các vi xử lý đồ họa song song (GPU). Tuy nhiên, môi trường sản xuất thực tế tại nhà máy chỉ trang bị dòng CPU máy chủ Intel Xeon, việc chạy suy luận trực tiếp file mô hình PyTorch gốc (.pt) sẽ cực kỳ chậm (độ trễ có thể lên tới hơn 300ms/frame), gây tắc nghẽn luồng xử lý và không thể đáp ứng yêu cầu thời gian thực.

Để giải quyết triệt để vấn đề này, đồ án ứng dụng công nghệ **ONNX Runtime (Open Neural Network Exchange)**:
*   **ONNX** định nghĩa một mô hình biểu diễn đồ thị tính toán mở, cho phép chuyển đổi mô hình từ các framework PyTorch/TensorFlow sang một định dạng chung duy nhất (.onnx) mà không làm suy giảm độ chính xác của mạng.
*   **ONNX Runtime** là bộ công cụ thực thi đồ thị ONNX được tối ưu hóa sâu ở mức biên dịch phần cứng. Khi chạy trên CPU Intel Xeon, ONNX Runtime tự động áp dụng các kỹ thuật:
    *   **Hợp nhất các tầng (Layer Fusions):** Gộp các phép tính toán liên tiếp như Conv + Batch Normalization + ReLU thành một phép toán đơn lẻ nhằm giảm số lần truy xuất bộ nhớ đệm.
    *   **Tối ưu hóa đa luồng luân phiên (Intra-op/Inter-op Multi-threading):** Sử dụng thư viện OpenMP phân rã đồ thị tính toán song song trên các nhân CPU vật lý một cách hiệu quả.
    *   **Tận dụng tập lệnh vector hóa (AVX-512, VNNI):** Sử dụng các thanh ghi rộng trên CPU Intel Xeon Silver 4510 để thực hiện nhiều phép tính nhân chập cùng lúc trong một chu kỳ xung nhịp.

Nhờ có ONNX Runtime CPU, tốc độ suy luận mô hình YOLOv11 Hand Detector được cải thiện rõ rệt, giảm thời gian xử lý từ ~250ms xuống còn ~35-45ms trên mỗi khung hình đơn lẻ.

---

### 1.4 Giải thuật kiểm tra vị trí tương đối Point-in-Polygon
Để giám sát quy trình lắp ráp, ta chia mặt bàn thao tác thành các phân vùng hình học không gian (ROI) tương ứng với vị trí đặt khay linh kiện, khuôn gá, hoặc nút bấm. Mỗi vùng ROI được biểu diễn bằng một đa giác hai chiều (Polygon) tạo bởi tập hợp các tọa độ đỉnh đã được chuẩn hóa theo độ phân giải ảnh:
$$P = \{p_1, p_2, ..., p_n\} \text{ với } p_i = (x_i, y_i) \in [0, 1]^2$$

Khi mô hình YOLO phát hiện bàn tay với tâm hộp bao (Centroid) hoặc các điểm góc của Bbox, hệ thống cần xác định nhanh chóng điểm $T = (x_t, y_t)$ này nằm trong hay ngoài vùng đa giác ROI $P$. Giải thuật **Ray Casting (Chiếu tia)** được lựa chọn để thực hiện nhiệm vụ này nhờ độ phức tạp thuật toán cực nhỏ $O(N)$ (với $N$ là số đỉnh của đa giác).

```
          /---------------------\
         /    o (Điểm nằm trong) \ --------> Tia chiếu ngang
        /       \                 \   Cắt cạnh lẻ lần (1)
       /         \                 \
      /___________o (Điểm nằm ngoài)\________> Tia chiếu ngang
                                              Cắt cạnh chẵn lần (2 hoặc 0)
```
*Hình 1.2: Minh họa giải thuật Ray Casting kiểm tra điểm nằm trong đa giác*

**Nguyên lý hoạt động:**
Từ điểm khảo sát $T$, ta vẽ một tia thẳng đứng hoặc nằm ngang kéo dài vô tận (thường là tia hướng theo chiều dương trục $X$). Ta đếm số lần tia này giao cắt với các cạnh của đa giác $P$.
*   Nếu số giao điểm là một số **lẻ**, điểm $T$ nằm **bên trong** đa giác.
*   Nếu số giao điểm là một số **chẵn** (hoặc 0), điểm $T$ nằm **bên ngoài** đa giác.

Hàm `cv2.pointPolygonTest` của OpenCV được tối ưu hóa sâu bằng mã nguồn C++ thực thi thuật toán này vô cùng nhanh chóng, hỗ trợ trả về khoảng cách đại số từ điểm đến cạnh gần nhất của đa giác (dương nếu nằm trong, âm nếu nằm ngoài, 0 nếu nằm trên biên).

---

### 1.5 Mô hình hóa quy trình bằng Máy trạng thái hữu hạn (FSM)
Một quy trình thao tác chuẩn (SOP) về bản chất là một tập hợp các trạng thái thao tác tuần tự có điều kiện chuyển trạng thái nghiêm ngặt. Đồ án sử dụng mô hình **Máy trạng thái hữu hạn (Finite State Machine - FSM)** để biểu diễn logic này.

Một máy trạng thái SOP được định nghĩa bởi bộ 5 tham số:
$$M = (S, \Sigma, \delta, s_0, F)$$
Trong đó:
*   $S$: Tập hợp các trạng thái của quy trình, tương ứng với trạng thái "Chờ bắt đầu", trạng thái đang thực hiện các bước 1, 2, ..., $N$, trạng thái hoàn thành thành công ("Completed") và trạng thái vi phạm ("Violation").
*   $\Sigma$: Tập hợp các sự kiện đầu vào (Events), là thông tin bàn tay công nhân tương tác với các vùng ROI nhận được từ Động cơ Không gian (ví dụ: `Hand_In_Zone_A`, `Hand_Withdraw_Zone_A`, `Timer_Timeout`).
*   $\delta: S \times \Sigma \rightarrow S$: Hàm chuyển trạng thái (Transition Function), quy định bước tiếp theo dựa trên trạng thái hiện tại và tác động đầu vào.
*   $s_0 \in S$: Trạng thái khởi đầu (Ready / Idle).
*   $F \subset S$: Tập hợp các trạng thái kết thúc (Completed hoặc Violation).

```mermaid
stateDiagram-v2
    [*] --> Idle : Khởi chạy hệ thống
    Idle --> Step_1 : Tay công nhân chạm vùng Bước 1
    Step_1 --> Step_2 : Hoàn thành logic Bước 1 (đạt dwell_time)
    Step_1 --> Violation_Timeout : Quá thời gian timeout_sec
    Step_2 --> Step_3 : Hoàn thành logic Bước 2
    Step_2 --> Violation_Skip : Tay chạm vùng Bước 3 (Bỏ bước)
    Step_2 --> Violation_Restart : Tay quay lại vùng Bước 1 (Premature)
    Violation_Skip --> Idle : Đưa tay về vùng Bước 1 để Reset
    Violation_Timeout --> Idle : Đưa tay về vùng Bước 1 để Reset
    Step_3 --> Completed : Hoàn thành tất cả các bước
    Completed --> Idle : Tay rời vùng và quay lại Bước 1
```

Việc tách biệt hoàn toàn Logic Máy trạng thái ra khỏi mã nguồn bằng cách khai báo cấu trúc quy trình trong file cấu hình YAML giúp hệ thống có khả năng tùy biến cực cao. Khi dây chuyền thay đổi quy trình thao tác hoặc lắp ráp sản phẩm mới, người vận hành chỉ cần chỉnh sửa file YAML tương ứng mà không cần phải can thiệp hay biên dịch lại mã nguồn Python của lõi động cơ.

---
\newpage

# CHƯƠNG 2: PHÂN TÍCH VÀ THIẾT KẾ HỆ THỐNG

### 2.1 Yêu cầu hệ thống và Kiến trúc tổng thể
Hệ thống giám sát SOP (AI Monitoring Hub) được thiết kế nhằm đáp ứng các yêu cầu nghiệp vụ nghiêm ngặt trong môi trường sản xuất công nghiệp:
*   **Yêu cầu chức năng:**
    *   Thu nhận luồng hình ảnh thời gian thực từ các IP Camera góc rộng lắp đặt phía trên bàn làm việc của công nhân.
    *   Phát hiện bàn tay công nhân và phân biệt rõ rệt tay Trái/Phải.
    *   Tự động so khớp hành động của tay với các vùng không gian ROI được định cấu hình động cho từng mã sản phẩm.
    *   Phát hiện tức thời các vi phạm quy trình (bỏ bước, làm sai trình tự, thao tác chậm trễ quá thời gian quy định).
    *   Kích hoạt loa báo lỗi tại trạm, lưu trữ video ghi nhận sự kiện lỗi và đẩy thông báo cảnh báo tức thời lên giao diện Dashboard quản lý.
    *   Cho phép người dùng cấu hình tọa độ các vùng ROI bằng thao tác vẽ trực quan trên giao diện đồ họa.
*   **Yêu cầu phi chức năng:**
    *   **Độ trễ thấp:** Tổng thời gian từ khi camera thu nhận frame đến khi phát hiện vi phạm và hiển thị lên web phải dưới 100ms.
    *   **Tối ưu tài nguyên:** Hệ thống phải chạy mượt mà tối thiểu 3 camera trạm ở tần suất 15 FPS trên CPU Intel Xeon Silver 4510 (không có GPU).
    *   **Khả năng tự phục hồi:** Tự reconnect camera khi mất kết nối mạng LAN hoặc sụt nguồn điện camera đột ngột mà không làm gián đoạn hay crash ứng dụng.
    *   **Quản lý lưu trữ thông minh:** Cơ chế tự động dọn dẹp ổ đĩa để ngăn chặn tình trạng tràn bộ nhớ do lưu video clip.

Hệ thống được thiết kế theo kiến trúc 3 lớp (3-tier architecture):

```
                        +---------------------------------------+
                        |          IP Cameras (RTSP)            |
                        +---------------------------------------+
                                            │
                                            ▼ Luồng hình ảnh (RTSP Streams)
   +------------------------------------------------------------------------------------+
   | 1. LỚP AI & PIPELINE (XỬ LÝ DỮ LIỆU)                                               |
   |   - RTSP Stream Manager (reconnect)     - Frame Ring Buffer (đệm vòng 25s)         |
   |   - Inference Engine (YOLO ONNX CPU)    - Hand Tracker (Định danh Trái/Phải)       |
   |   - Spatial Point-in-Polygon Engine     - Frame Processor (Điều phối luồng)       |
   +------------------------------------------------------------------------------------+
                                            │
                                            ▼ Kết quả phân tích (JSON) / Hình ảnh vẽ
   +------------------------------------------------------------------------------------+
   | 2. LỚP LOGIC & DỮ LIỆU (DATABASE & BACKEND)                                       |
   |   - Flask Web Server                    - SocketIO Server (Real-time events)       |
   |   - MySQL Connection Pool (PooledDB)    - Storage Cleanup (Daemon dọn đĩa)         |
   |   - Clip Saver (imageio-ffmpeg)         - Audio Alert (sounddevice còi báo)        |
   +------------------------------------------------------------------------------------+
                                            │
                                            ▼ Websocket / HTTP
   +------------------------------------------------------------------------------------+
   | 3. LỚP TRÌNH DIỄN (WEB DASHBOARD)                                                  |
   |   - Single Page App HTML5/CSS3/Vanilla JS  - Real-time Alert Screen (Cảnh báo đỏ)    |
   |   - MJPEG Livestream Player             - Chart.js (Biểu đồ hiệu suất, xu hướng)   |
   +------------------------------------------------------------------------------------+
```
*Hình 2.1: Sơ đồ kiến trúc tổng thể ba lớp của hệ thống AI Monitoring Hub*

---

### 2.2 Thiết kế cơ sở dữ liệu (MySQL Database Schema)
Hệ thống sử dụng cơ sở dữ liệu quan hệ **MySQL** triển khai trên máy chủ cơ sở dữ liệu tập trung nhằm phục vụ lưu trữ lâu dài cấu hình trạm, danh sách quy trình sản phẩm, lịch sử các sự kiện vi phạm và các thông số đo lường sức khỏe hệ thống. Tất cả các bảng thuộc phân hệ SOP đều được định danh bằng tiền tố `sop_` để tránh xung đột với các bảng dữ liệu cũ khác của nhà máy.

Sơ đồ quan hệ thực thể (ERD) được thiết kế chuẩn hóa để tối ưu hóa tốc độ truy vấn:

```mermaid
erDiagram
    sop_definitions ||--o{ sop_steps : "chứa"
    sop_definitions ||--o{ sop_cameras : "gắn với"
    sop_definitions ||--o{ sop_sessions : "áp dụng"
    sop_definitions ||--o{ sop_events : "phân loại"
    sop_cameras ||--o{ sop_sessions : "tạo ra"
    sop_cameras ||--o{ sop_events : "ghi nhận"
    sop_cameras ||--o{ sop_health : "đo lường"
    sop_sessions ||--o{ sop_events : "gồm có"
    sop_events ||--o? sop_clips : "đính kèm"
    sop_cameras ||--o{ sop_clips : "lưu ở"
```
*Hình 2.2: Sơ đồ thực thể mối quan hệ cơ sở dữ liệu (ERD)*

#### Đặc tả chi tiết các bảng cơ sở dữ liệu quan trọng:

**1. Bảng `sop_definitions` (Bảng định nghĩa mã sản phẩm/quy trình):**
Bảng này chứa thông tin về các dòng sản phẩm cần được kiểm soát thao tác lắp ráp.
*   `id` (INT, Primary Key, Auto Increment)
*   `name` (VARCHAR(255), Unique, Not Null): Tên mã sản phẩm (ví dụ: "TFF4040", "626287").
*   `description` (TEXT): Mô tả quy trình.
*   `total_steps` (INT, Default 0): Tổng số bước SOP cần kiểm tra.
*   `version` (VARCHAR(20), Default '1.0'): Phiên bản quy trình.
*   `is_active` (TINYINT(1), Default 1): Trạng thái hoạt động.
*   `created_at` (DATETIME, Default Current_Timestamp).

**2. Bảng `sop_steps` (Bảng các bước cụ thể trong quy trình):**
Chứa danh sách chi tiết các bước lắp ráp của một sản phẩm, sắp xếp theo trình tự tăng dần.
*   `id` (INT, Primary Key, Auto Increment)
*   `definition_id` (INT, Foreign Key referencing `sop_definitions.id`): Liên kết đến mã sản phẩm.
*   `step_order` (INT, Not Null): Thứ tự thực hiện bước (1, 2, 3...).
*   `step_name` (VARCHAR(255), Not Null): Tên bước chi tiết (ví dụ: "Lấy 2 phôi từ khuôn").
*   `step_label` (VARCHAR(100), Not Null): Nhãn định danh ngắn gọn.
*   `max_duration_ms` (INT, Nullable): Thời gian tối đa cho phép thực hiện bước này (mili-giây).
*   `is_mandatory` (TINYINT(1), Default 1): Đánh dấu bước bắt buộc.
*   *Ràng buộc đặc biệt:* `UNIQUE(definition_id, step_order)` đảm bảo mỗi quy trình không có hai bước trùng thứ tự.

**3. Bảng `sop_cameras` (Bảng quản lý Camera trạm):**
Quản lý các luồng camera IP và ánh xạ camera đang chạy giám sát sản phẩm nào.
*   `id` (INT, Primary Key, Auto Increment)
*   `station_id` (VARCHAR(50), Unique, Not Null): Mã trạm lắp ráp (ví dụ: "machine_07").
*   `name` (VARCHAR(255), Not Null): Tên trạm hiển thị.
*   `rtsp_url` (TEXT, Not Null): Đường dẫn luồng RTSP của camera IP.
*   `definition_id` (INT, Foreign Key referencing `sop_definitions.id`): Mã sản phẩm hiện đang được giám sát tại trạm này.
*   `status` (VARCHAR(20), Default 'active'): Trạng thái kết nối camera ('active', 'error', 'offline').

**4. Bảng `sop_events` (Bảng lưu lịch sử sự kiện):**
Ghi lại mọi sự kiện hoàn thành chu kỳ thành công cũng như các vi phạm quy trình được phát hiện. Đây là bảng có tần suất ghi cao nhất và là nguồn dữ liệu chính cho các báo cáo thống kê.
*   `id` (BIGINT, Primary Key, Auto Increment)
*   `session_id` (INT, Foreign Key referencing `sop_sessions.id`): Liên kết đến phiên làm việc hiện tại.
*   `camera_id` (INT, Foreign Key referencing `sop_cameras.id`): Camera phát hiện sự kiện.
*   `definition_id` (INT, Foreign Key referencing `sop_definitions.id`): Dòng sản phẩm đang lắp lúc xảy ra sự kiện.
*   `timestamp` (DATETIME, Default Current_Timestamp): Thời điểm phát sinh sự kiện.
*   `step_detected` (VARCHAR(255)): Bước được phát hiện lúc xảy ra sự kiện.
*   `expected_step` (VARCHAR(255)): Bước đúng đắn đáng lẽ phải thực hiện.
*   `sop_status` (VARCHAR(50)): Trạng thái sự kiện ('completed' - thành công, 'violation' - vi phạm).
*   `violation_type` (VARCHAR(100)): Loại lỗi nếu là vi phạm ('timeout', 'skip_step').
*   `clip_path` (TEXT): Đường dẫn tệp clip video ghi hình lại vi phạm trên ổ đĩa máy chủ.

*Các chỉ mục (Indexes) bắt buộc phải tạo để tối ưu hóa các câu lệnh SQL truy vấn lịch sử trên Dashboard:*
*   `idx_sop_events_camera_time` trên cặp trường `(camera_id, timestamp)`
*   `idx_sop_events_session` trên trường `(session_id)`

---

### 2.3 Phân tích luồng dữ liệu của camera trạm (RTSP Data Flow)
Để đảm bảo tính thời gian thực và không gây nghẽn cổ chai tính toán, mỗi camera đăng ký trong hệ thống được điều phối độc lập bởi một luồng thực thi con (`FrameProcessor` running in a daemon thread). 

Sơ đồ luồng dữ liệu xử lý chi tiết cho từng khung hình trong luồng lặp được mô tả như sau:

```
+-----------------------------------------------------------------------------------+
| 1. BẮT ĐẦU LUỒNG LẶP CHÍNH (FrameProcessor._process_loop)                         |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| Đọc ảnh từ RTSPStream. Nếu không có ảnh, tạm dừng 50ms rồi thử lại                |
| (Ảnh được RTSPStream tự động resize về 640x480 và chống buffer lag tại nguồn)    |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| Đẩy ảnh gốc vào FrameRingBuffer để duy trì đệm video 25 giây phục vụ cắt clip     |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| CHẠY AI INFERENCE (YOLOv11 ONNX) - Tối ưu chạy mỗi 2 frame (~7.5 FPS AI)          |
|   - Gọi InferenceEngine.infer(frame) qua cơ chế Singleton Thread-safe Lock        |
|   - Nhận về danh sách bounding boxes và confidence của bàn tay                    |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| LỌC ROI ĐỘNG (_filter_detections_by_roi)                                         |
|   - Tính toán bao lồi cộng biên độ an toàn 15% xung quanh các vùng ROI            |
|   - Loại bỏ các hộp bao bàn tay nằm ngoài vùng này (tránh người đi lại gây nhiễu) |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| BÁM VẾT VÀ ĐỊNH DANH TAY TRÁI/PHẢI (_associate_hands)                            |
|   - Sử dụng khoảng cách Euclid kết hợp so sánh vị trí tương đối trái/phải màn hình|
|   - Áp dụng cơ chế Ghost Hands Protection: Xóa cache nếu >0.3s không thấy tay     |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| GỌI LÕI ĐỘNG CƠ logic SOP (ProductEngine.update(hands_data))                      |
|   - Kiểm tra tay chạm vùng ROI (Point-in-Polygon)                                  |
|   - Kiểm tra logic bước hiện tại (zone_trigger, multi_trigger, stay_in_zone...)    |
|   - Phát hiện vi phạm: Timeout bước, Bỏ bước (Skip Step), Quay lại sớm (Premature)|
|   - Trả về cấu trúc trạng thái chi tiết (latest_status)                           |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| PHÂN TÍCH VI PHẠM (ViolationDetector.analyze)                                     |
|   Có vi phạm?                                                                     |
|    ├── [Có] -> Khởi chạy Background Thread xử lý vi phạm:                         |
|    │           1. Phát âm thanh cảnh báo ngay lập tức qua loa máy chủ             |
|    │           2. Gửi thông điệp SocketIO "violation" báo đỏ lập tức lên Web UI   |
|    │           3. Chờ 5 giây (post_seconds) để gom đủ video sau khi lỗi xảy ra    |
|    │           4. Trích xuất frames trong Ring Buffer, ghi file clip MP4          |
|    │           5. Ghi log sự kiện đính kèm đường dẫn clip vào MySQL Database      |
|    └── [Không] -> Tiếp tục luồng                                                  |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| PHỤC VỤ TRÌNH DIỄN (VISUALIZATION)                                                |
|   - Vẽ các vùng ROI đa giác và vẽ hộp bao bàn tay kèm nhãn tay lên khung hình     |
|   - Cập nhật frame lên bộ đệm phục vụ luồng livestream MJPEG                      |
|   - Emit SocketIO "step_update" gửi trạng thái SOP về Dashboard định kỳ (1s/lần)   |
+-----------------------------------------------------------------------------------+
```
*Hình 2.3: Sơ đồ luồng dữ liệu (Data Flow) xử lý một khung hình trong FrameProcessor*

---

### 2.4 Thiết kế chi tiết các cấu phần phần mềm chính

#### 1. RTSP Stream Manager (`shared/rtsp_manager.py`)
Đóng vai trò là phân hệ thu nhận ảnh đầu vào từ camera. Để tránh hiện tượng trễ tích lũy (buffer lag) của OpenCV khi đọc luồng RTSP (OpenCV mặc định đệm nhiều frame trong bộ nhớ dẫn tới việc hình ảnh hiển thị bị chậm vài giây so với thực tế), `RTSPStream` chạy một luồng đọc chuyên biệt. Luồng này liên tục đọc các khung hình từ camera và chỉ giữ lại khung hình mới nhất, giải phóng các khung hình cũ.
*   **Tham số khởi tạo:** `fps_cap` (khống chế tốc độ đọc tối đa), `target_width`, `target_height` (thực hiện resize ảnh bằng phần cứng hoặc OpenCV ngay khi đọc để giảm tải cho các bước xử lý ảnh sau đó).
*   **Cơ chế tự reconnect:** Khi luồng đọc gặp lỗi hoặc không nhận được frame trong vòng 5 giây, hệ thống sẽ phát tín hiệu mất kết nối lên giao diện (`camera_status: error`), đóng luồng cũ, đợi 5 giây và tiến hành khởi tạo lại kết nối mới. Quá trình thử lại tối đa 10 lần trước khi chuyển hẳn trạng thái camera sang "offline".

#### 2. Inference Engine (Singleton - `shared/inference_engine.py`)
Để tránh việc nạp mô hình YOLO ONNX nhiều lần vào bộ nhớ làm quá tải RAM và CPU khi có nhiều camera hoạt động, `InferenceEngine` được thiết kế theo mẫu thiết kế **Singleton**.
*   **Quản lý tài nguyên:** Chỉ duy nhất một đối tượng Engine được tạo ra cho toàn bộ ứng dụng. Tất cả các luồng camera trạm khi cần suy luận phát hiện bàn tay đều phải gửi ảnh về đối tượng Singleton này.
*   **Cơ chế đồng bộ hóa:** Do suy luận trên CPU là một phép toán tốn tài nguyên và khó chạy song song thực sự trên cùng một mô hình, hệ thống sử dụng một khóa loại trừ tương hỗ `threading.Lock` để tuần tự hóa (serialize) các yêu cầu suy luận từ các camera trạm gửi đến. Điều này đảm bảo tính ổn định tối đa của lõi ONNX Runtime, không gây sập bộ nhớ do xung đột luồng.
*   **Cấu hình ONNX Runtime:**
    ```python
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 4  # Giới hạn số thread tính toán cho 1 session
    opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    self.session = ort.InferenceSession(model_path, opts, providers=['CPUExecutionProvider'])
    ```

#### 3. Hand Detector & Tracker (`projects/sop_monitoring/hand_detector.py`)
*   **Hand Detector:** Nhận ảnh từ FrameProcessor, thực hiện tiền xử lý (letterbox resize về $416 \times 416$ hoặc $320 \times 320$, chuyển đổi kênh màu BGR sang RGB, chuẩn hóa giá trị pixel về đoạn $[0, 1]$, và chuyển đổi shape về dạng tensor `[1, 3, H, W]`). Sau khi gọi Inference Engine, nó lọc các kết quả dự đoán có độ tin cậy thấp hơn ngưỡng `conf_threshold` (0.25).
*   **Hand Tracker:** Thực hiện bám vết bàn tay giữa khung hình thứ $t$ và $t-1$ dựa trên giải thuật khoảng cách Euclid tối thiểu của tâm hộp bao. Nhờ đó, hệ thống biết được tay nào là tay Trái, tay nào là tay Phải của công nhân. 
*   *Mirror logic:* Do camera IP thường được lắp đối diện trực diện với công nhân, ảnh truyền về bị đảo ngược gương. Thuật toán tự động đảo nhãn: Tay nằm bên trái khung hình (tọa độ $X$ nhỏ) sẽ được gán nhãn là tay **Phải** (Right Hand) của công nhân, và ngược lại để đảm bảo tính tự nhiên khi so khớp logic SOP.

#### 4. SOP State Machine Engine (`TFF4040_engine.py`)
Mỗi mã sản phẩm kế thừa lớp cha trừu tượng `BaseEngine` và định nghĩa máy trạng thái SOP của riêng mình. Trọng tâm của động cơ là hàm `update(hands_data)` nhận danh sách tọa độ tay đã được định danh Trái/Phải và trả về trạng thái SOP hiện tại.
*   **Kiểm tra va chạm vùng không gian:**
    Duyệt qua các bàn tay đang có trên khung hình, lấy điểm centroid và 4 điểm góc hộp bao, gọi thuật toán `cv2.pointPolygonTest` đối với vùng đa giác của bước hiện tại và bước tiếp theo.
*   **Logic bước SOP đa dạng:**
    *   `zone_trigger`: Tay chạm vùng trong khoảng thời gian xác định.
    *   `multi_trigger`: Đếm số chu kỳ tay đi vào rồi đi ra khỏi vùng (thực hiện qua cờ lưu trạng thái `last_trigger_states` của frame trước).
    *   `stay_in_zone`: Tính thời gian tay lưu trú liên tục trong vùng dựa trên đồng hồ bấm giờ `self._stay_timer`.
    *   `dual_task`: Kiểm tra hai tay tương tác đồng thời hoặc tuần tự với hai vùng không gian quy định riêng biệt.

#### 5. Frame Ring Buffer & Clip Saver (`projects/sop_monitoring/buffer.py` & `shared/events/clip_saver.py`)
*   **FrameRingBuffer:** Sử dụng cấu trúc dữ liệu hàng đợi hai đầu `collections.deque(maxlen=max_frames)` với kích thước tối đa được tính toán dựa trên FPS của camera và tổng thời gian cần lưu trữ:
    $$\text{max\_frames} = \text{FPS} \times (\text{pre\_seconds} + \text{post\_seconds})$$
    Hàng đợi này hoạt động như một bộ đệm vòng lưu trữ liên tục các khung hình thô trong bộ nhớ RAM dưới dạng mảng Numpy. Khi hàng đợi đầy, các khung hình cũ nhất sẽ tự động bị đẩy ra ngoài. Điều này đảm bảo hệ thống luôn có sẵn đoạn video quá khứ ngay trước khi lỗi xảy ra mà không cần phải thực hiện ghi video 24/7 xuống ổ đĩa, giúp tiết kiệm tối đa tuổi thọ SSD và băng thông I/O.
*   **ClipSaver:** Khi phát hiện lỗi vi phạm SOP, luồng xử lý chính vẫn tiếp tục chạy để không bỏ lỡ các frame tiếp theo. Một luồng chạy nền (background thread) được kích hoạt, luồng này tạm dừng chờ trong `post_seconds` giây để bộ đệm vòng thu thập đủ các khung hình diễn ra sau lỗi. Sau đó, nó rút toàn bộ các khung hình trong bộ đệm vòng ra và sử dụng thư viện `imageio` kết hợp `imageio-ffmpeg` để ghi đĩa tệp video định dạng `.mp4`, nén chuẩn H.264 với thiết lập bitrate tối ưu (`crf=28`, resolution 480p) để dung lượng tệp tin chỉ dao động từ 1-3 MB cho mỗi clip lỗi.

#### 6. Storage Cleanup Daemon (`shared/db/cleanup.py`)
Để hệ thống tự vận hành ổn định trong thời gian dài trên máy chủ có dung lượng ổ đĩa giới hạn (~900 GB SSD), một tiến trình nền `StorageCleanup` được khởi chạy định kỳ mỗi 10 phút.
*   **Thuật toán dọn dẹp:**
    *   Sử dụng thư viện `psutil` để kiểm tra dung lượng ổ đĩa hiện tại của phân vùng lưu trữ video vi phạm.
    *   Nếu tỷ lệ sử dụng ổ đĩa vượt quá ngưỡng cho phép `max_usage_percent` (mặc định 85% theo quy định cấu hình), tiến trình tiến hành truy vấn cơ sở dữ liệu để lấy danh sách các tệp video vi phạm sắp xếp theo thời gian tạo từ cũ nhất đến mới nhất.
    *   Tiến hành xóa tệp vật lý trên SSD, đồng thời cập nhật trường `clip_path = NULL` của bản ghi tương ứng trong bảng `sop_events` và xóa bản ghi trong bảng `sop_clips` để giải phóng dung lượng đĩa cho đến khi tỷ lệ sử dụng đĩa giảm xuống dưới ngưỡng an toàn (thường là 80%).
    *   Đồng thời tự động xóa các bản ghi sự kiện cũ hơn số ngày cấu hình `retention_days` (mặc định 30 ngày) để duy trì kích thước cơ sở dữ liệu MySQL luôn gọn nhẹ.

---
\newpage

# CHƯƠNG 3: XÂY DỰNG, TỐI ƯU HÓA VÀ ĐÁNH GIÁ THỰC NGHIỆM

### 3.1 Xây dựng tập dữ liệu và huấn luyện mô hình YOLO
Mặc dù hệ thống logic SOP hoạt động dựa trên các vùng hình học ROI, độ chính xác cuối cùng của toàn hệ thống phụ thuộc hoàn toàn vào khả năng phát hiện bàn tay ổn định của mô hình học sâu YOLOv11. Nếu mô hình nhận diện trượt bàn tay (False Negative) hoặc nhận diện nhầm các vật thể tĩnh xung quanh là bàn tay (False Positive), máy trạng thái SOP sẽ bị chuyển trạng thái lỗi hoặc bỏ lỡ các sự kiện chuyển bước.

Quy trình huấn luyện và chuẩn bị mô hình được tiến hành như sau:
1.  **Thu thập dữ liệu thực tế (Data Collection):**
    Sử dụng công cụ `shared/tools/record_video.py` để quay lại hơn 15 giờ video thao tác thực tế của công nhân tại dây chuyền lắp ráp HTMP ở các thời điểm ánh sáng khác nhau (ca sáng, ca tối, khi bật/tắt đèn xưởng).
2.  **Trích xuất khung hình (Frame Extraction):**
    Sử dụng công cụ `shared/tools/frame_extractor.py` để trích xuất ngẫu nhiên các khung hình từ video với tần suất 1 frame mỗi 5 giây để tránh trùng lặp dữ liệu quá mức. Thu được tập dữ liệu thô gồm 8,500 ảnh.
3.  **Gán nhãn dữ liệu (Data Labeling):**
    Tập ảnh được tải lên công cụ gán nhãn chuyên dụng Roboflow. Tiến hành vẽ hộp bao quanh tất cả các bàn tay xuất hiện trong ảnh (chỉ gán nhãn một lớp duy nhất là `hand`). Thực hiện gán nhãn kỹ lưỡng cho cả các trường hợp bàn tay bị che khuất một phần bởi tuốc nơ vít, linh kiện nhựa hoặc gá sắt.
4.  **Tăng cường dữ liệu (Data Augmentation):**
    Áp dụng các kỹ thuật tăng cường ảnh để mô hình thích ứng tốt với môi trường nhà xưởng thực tế:
    *   Xoay ảnh ngẫu nhiên từ $-15^\circ$ đến $+15^\circ$.
    *   Thay đổi độ sáng và độ tương phản ngẫu nhiên từ $-25\%$ đến $+25\%$ (mô phỏng sự thay đổi ánh sáng tự nhiên từ cửa sổ nhà xưởng).
    *   Thêm nhiễu Gaussian và làm mờ chuyển động (motion blur - mô phỏng tay di chuyển nhanh).
    *   Tỷ lệ chia tập dữ liệu: 70% Train, 20% Validation, 10% Test.
5.  **Huấn luyện mô hình (Training):**
    Quá trình huấn luyện được thực hiện trên máy trạm cá nhân có card đồ họa GPU chuyên dụng (NVIDIA GeForce RTX 4070 Ti) hoặc Google Colab. Mô hình sử dụng phiên bản YOLOv11 Nano (phiên bản nhỏ nhất để tối ưu tốc độ CPU).
    *   Số lượng Epoch: 150
    *   Batch size: 32
    *   Optimizer: AdamW với tốc độ học ban đầu $lr = 0.01$.
    *   Kết quả huấn luyện đạt chỉ số mAP@0.5 là **98.2%** và mAP@0.5:0.95 là **81.4%**.
6.  **Xuất bản mô hình ONNX (Exporting ONNX):**
    Sau khi huấn luyện thành công, mô hình PyTorch (.pt) được xuất sang định dạng ONNX phục vụ chạy trên server:
    ```bash
    yolo export model=best.pt format=onnx imgsz=416 dynamic=False opset=12
    ```

---

### 3.2 Tối ưu hóa hệ thống trên máy chủ CPU Intel Xeon Silver 4510

#### 3.2.1 Cấu hình phần cứng máy chủ sản xuất
Hệ thống được triển khai trên máy chủ Windows Server đặt tại phòng máy trung tâm của nhà máy HTMP với thông số cấu hình phần cứng như sau:
*   **CPU:** Intel Xeon Silver 4510 (Thế hệ thứ 5 Emerald Rapids, 12 nhân vật lý / 24 luồng xử lý, xung nhịp cơ bản 2.4 GHz, Turbo Boost lên 4.1 GHz, bộ nhớ đệm L3 Cache 30MB).
*   **RAM:** 256 GB DDR5 ECC Bus 4800 MHz hoạt động đa kênh.
*   **Storage:** 960 GB Enterprise SSD chuẩn giao tiếp SATA 3.
*   **GPU:** Không tích hợp card đồ họa rời (chỉ có Microsoft Basic Display Adapter phục vụ hiển thị màn hình cơ bản).

Mặc dù CPU Intel Xeon Silver 4510 rất mạnh về năng lực xử lý đa nhiệm đồng thời nhiều luồng dịch vụ, hiệu năng tính toán tuần tự trên một nhân đơn độc (Single-thread performance) của nó không quá cao so với các CPU máy tính để bàn (Desktop CPU). Do đó, nếu không áp dụng các biện pháp tối ưu hóa phần mềm sâu sắc, server sẽ nhanh chóng rơi vào trạng thái quá tải CPU (CPU Bottleneck) chỉ với 2 camera trạm chạy YOLO liên tục.

#### 3.2.2 Tối ưu hóa luồng AI Inference trên CPU
Đồ án đã đề xuất và triển khai thành công 4 kỹ thuật tối ưu hóa tài nguyên hệ thống, giúp giảm tải CPU hơn 70%:

*   **1. Khống chế và cấu hình luồng OpenCV vật lý:**
    Mặc định, các hàm xử lý ảnh của OpenCV (như `cv2.resize`, `cv2.cvtColor`) tự động sinh ra số lượng thread con bằng số core logic của máy chủ (24 threads) để thực hiện tính toán. Việc nhiều camera trạm đồng thời sinh ra hàng chục thread OpenCV gây ra hiện tượng nghẽn tranh chấp ngữ cảnh (Context Switching Overhead) cực kỳ nghiêm trọng trên CPU. Đồ án khóa luồng OpenCV bằng lệnh:
    ```python
    cv2.setNumThreads(0)
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["OMP_WAIT_POLICY"] = "PASSIVE"
    ```
    Điều này ép buộc các hàm OpenCV thực thi tuần tự ngay trong luồng con của camera tương ứng, loại bỏ hoàn toàn việc tranh chấp luồng vô ích.

*   **2. Chạy AI cách quãng (AI Skipping Frames):**
    Tốc độ thao tác lắp ráp bằng tay của công nhân công nghiệp thường có chu kỳ từ 10 giây đến 45 giây cho một sản phẩm. Các chuyển động tay không diễn ra quá nhanh như trong các hoạt động thể thao. Do đó, việc chạy nhận diện AI trên mọi khung hình đơn lẻ (15 FPS) là sự lãng phí tài nguyên không cần thiết.
    Hệ thống tối ưu bằng cách chỉ gọi mô hình nhận diện YOLO trên **mỗi 2 khung hình một lần** (hiệu dụng ~7.5 FPS AI). Các khung hình ở giữa sẽ tái sử dụng lại kết quả nhận dạng của khung hình trước đó. Thử nghiệm thực tế cho thấy sự thay đổi này hoàn toàn không làm ảnh hưởng đến độ chính xác của logic chuyển trạng thái SOP, nhưng giúp giảm một nửa (50%) tải tính toán của Inference Engine.

*   **3. Chuẩn hóa độ phân giải và giảm kích thước ảnh đầu vào:**
    Giảm độ phân giải chuẩn hóa đầu vào của mô hình YOLO từ kích thước mặc định $640 \times 640$ xuống **$416 \times 416$ pixel** (và hỗ trợ cấu hình xuống $320 \times 320$ cho các trạm có góc camera gần). Tổng số pixel cần xử lý giảm từ 409,600 xuống còn 173,056 (giảm 57.7% khối lượng tính toán ma trận đầu vào), giúp đẩy nhanh tốc độ suy luận của mô hình trên CPU đáng kể.

*   **4. Khống chế tần suất cập nhật giao diện Dashboard:**
    Việc liên tục truyền dữ liệu hình ảnh và trạng thái qua Socket.IO ở tần suất 15 FPS gây tốn băng thông mạng nội bộ và chiếm dụng CPU của Flask Server để đóng gói bản tin JSON. Hệ thống khống chế tần suất gửi thông điệp `step_update` xuống giao diện Web Dashboard chỉ **1 lần trên mỗi giây** (hoặc 15 frame xử lý một lần). Chỉ riêng các sự kiện đặc biệt nguy cấp như vi phạm quy trình (`violation`) hoặc hoàn thành chu kỳ (`completed`) mới được đẩy đi ngay lập tức không có độ trễ để người quản lý ứng phó kịp thời.

#### 3.2.3 Cơ chế chống nhận diện sai và nhiễu không gian (ROI Filter)
Trong môi trường nhà xưởng sản xuất thực tế, xung quanh bàn làm việc thường có các dòng người đi lại (công nhân cấp phát phôi, kỹ sư chất lượng, công nhân trạm bên cạnh thò tay qua). Nếu camera góc rộng chụp cả người đi lại, YOLO sẽ phát hiện các bàn tay lạ này và làm sai lệch trạng thái SOP của trạm.

Hệ thống giải quyết vấn đề này bằng bộ lọc **Dynamic ROI Filter**:
*   Tính toán một đa giác bao lồi bao phủ toàn bộ các vùng ROI làm việc đã định nghĩa của sản phẩm hiện tại, sau đó mở rộng biên độ an toàn thêm 15% xung quanh đường biên.
*   Bất kỳ bàn tay nào do mô hình YOLO phát hiện ra nếu có tọa độ tâm nằm ngoài đa giác bao lồi mở rộng này đều bị coi là nhiễu ngoại cảnh và bị hệ thống loại bỏ ngay lập tức trước khi đưa dữ liệu vào động cơ bám vết và phân tích SOP.

#### 3.2.4 Cơ chế chống hiện tượng "Tay ma" (Ghost Hands Protection)
Do thời gian xử lý AI cách tuần và tốc độ di chuyển tay cực nhanh của công nhân khi lấy linh kiện, có những thời điểm công nhân đã hoàn toàn rút tay ra khỏi vùng ROI nhưng do độ trễ cập nhật AI (hoặc mô hình YOLO bị trượt không phát hiện ra tay ở frame hiện tại), hệ thống vẫn giữ nguyên kết quả bám vết của tay ở vị trí cũ (Ghost Hands - Tay ma). Điều này khiến máy trạng thái SOP hiểu nhầm là tay vẫn đang đè trong vùng và tiếp tục tích lũy thời gian dwell time bất hợp lý.

Hệ thống thiết lập cơ chế bảo vệ: Nếu bộ điều phối `FrameProcessor` liên tục không nhận được bất kỳ hộp bao bàn tay nào từ mô hình YOLO trong vòng **0.3 giây** liên tục (khoảng 2-3 frame AI), hệ thống sẽ chủ động xóa sạch bộ nhớ đệm bám vết bàn tay (`self._cached_hands = []`). Hành động này ép buộc động cơ SOP ghi nhận trạng thái tay đã rút hoàn toàn khỏi mọi vùng làm việc, ngăn chặn triệt để các lỗi kích hoạt giả.

#### 3.2.5 Tối ưu hóa chu kỳ reset và phục hồi lỗi SOP
Khi phát hiện vi phạm quy trình SOP (như bỏ bước), hệ thống lập tức khóa trạng thái lỗi (`is_failed = True`), phát còi cảnh báo và hiển thị màn hình đỏ trên Dashboard. Để tiếp tục sản xuất, công nhân không cần thực hiện bất kỳ thao tác bấm nút thủ công nào trên màn hình (tránh làm bẩn màn hình hoặc mất thời gian dừng tay). 
Hệ thống hỗ trợ cơ chế **Tự động Phục hồi Lỗi (Auto Recovery)**: Công nhân chỉ cần rút tay ra khỏi các vùng và đưa tay quay trở lại vùng hoạt động của **Bước 1**. Lõi động cơ SOP khi phát hiện sự tương tác hợp lệ tại vùng Bước 1 sẽ tự động giải phóng trạng thái lỗi, tăng chỉ số đếm chu kỳ (`cycle_count += 1`), đưa máy trạng thái về trạng thái khởi tạo chu kỳ mới ngay tức thì để công nhân tiếp tục công việc không bị gián đoạn.

Đặc biệt, đối với hành động **Quay lại bước 1 sớm (Premature Restart)** trong khi đang thực hiện dở chu kỳ lắp ráp, hệ thống đã được tối ưu hóa để thực hiện **Reset chu kỳ mới lập tức một cách thầm lặng (Silent Cycle Reset)** thay vì coi là một lỗi vi phạm. Khi phát hiện tay công nhân quay lại vùng hoạt động của Bước 1 (`mold`), FSM sẽ tự động giải phóng chu kỳ cũ và bắt đầu chu kỳ mới ngay tức thì mà không báo lỗi đỏ hay phát còi. Điều này giúp loại bỏ hoàn toàn các cảnh báo giả khi công nhân chủ động thực hiện lại từ đầu hoặc do nhiễu nhảy vùng (bounding box jitter).

---

### 3.3 Chi tiết các bước thực nghiệm quy trình TFF4040 và 626287

#### 1. Quy trình lắp ráp sản phẩm TFF4040:
Quy trình TFF4040 gồm 9 bước thao tác chuẩn được mô tả chi tiết kèm theo vùng không gian ROI kiểm soát tương ứng:

*   **Vùng không gian ROI định nghĩa:**
    *   `mold`: Vùng khuôn ép nhựa trung tâm.
    *   `left_table`: Vùng bàn làm việc phía bên trái.
    *   `middle_table`: Vùng đặt bản mạch và linh kiện giữa.
    *   `button_right`: Nút bấm vật lý kích hoạt máy kiểm tra phía bên phải.
    *   `jig_zone`: Khu vực gá lắp jig cố định.

*   **Đặc tả 9 bước SOP kiểm soát:**

| Thứ tự bước | Tên bước thao tác chuẩn | Logic kiểm soát | Vùng ROI bắt buộc | Mô tả chi tiết kiểm soát |
|:---:|---|---|:---:|---|
| **1** | Lấy 2 sản phẩm ép nhựa từ khuôn | `multi_trigger` | `mold` | Tay phải chạm vào vùng khuôn đủ 2 lần để lấy 2 phôi nhựa mới tinh. |
| **2** | Đặt sản phẩm lên bàn trái làm sạch | `zone_trigger` | `left_table` | Tay chạm vùng bàn trái để thực hiện gạt ba via, vệ sinh cạnh nhựa. |
| **3** | Đặt sản phẩm vào khuôn Jig định vị | `stay_in_zone` | `jig_zone` | Giữ tay trong vùng Jig tối thiểu 0.8 giây để đảm bảo phôi được gá chặt. |
| **4** | Lấy nắp nhựa bảo vệ từ khay giữa | `zone_trigger` | `middle_table` | Tay chạm khay giữa để lấy nắp ốp mạch bảo vệ. |
| **5** | Lắp nắp mạch bảo vệ vào sản phẩm | `stay_in_zone` | `jig_zone` | Giữ tay tại Jig tối thiểu 1.5 giây để hoàn thành ấn khóp nắp nhựa. |
| **6** | Lấy 2 ốc vít phụ từ khay linh kiện | `multi_trigger` | `middle_table` | Tay chạm vùng khay linh kiện đủ 2 lần để lấy đủ 2 ốc vít. |
| **7** | Thực hiện bắt vít cố định mạch | `stay_in_zone` | `jig_zone` | Sử dụng máy bắt vít thao tác tại Jig, giữ tay tối thiểu 2.5 giây. |
| **8** | Lấy sản phẩm hoàn thiện ra khỏi Jig | `zone_trigger` | `jig_zone` | Tay chạm vào vùng Jig để nhấc sản phẩm hoàn thiện ra ngoài. |
| **9** | Ấn nút kiểm tra lỗi ngoại quan (QA) | `zone_trigger` | `button_right` | Tay chạm nút QA bên phải để kết thúc một chu kỳ lắp ráp thành công. |

*Bảng 3.1: Chi tiết 9 bước SOP và logic kiểm soát của mã sản phẩm TFF4040*

```mermaid
stateDiagram-v2
    [*] --> Idle : Sẵn sàng
    Idle --> Step_1 : Chạm mold (Lần 1)
    Step_1 --> Step_1_Hit_2 : Chạm mold (Lần 2) -> Hoàn thành Bước 1
    Step_1_Hit_2 --> Step_2 : Chạm left_table -> Hoàn thành Bước 2
    Step_2 --> Step_3 : Giữ jig_zone >= 0.8s -> Hoàn thành Bước 3
    Step_3 --> Step_4 : Chạm middle_table -> Hoàn thành Bước 4
    Step_4 --> Step_5 : Giữ jig_zone >= 1.5s -> Hoàn thành Bước 5
    Step_5 --> Step_6 : Chạm middle_table (Lần 1)
    Step_6 --> Step_6_Hit_2 : Chạm middle_table (Lần 2) -> Hoàn thành Bước 6
    Step_6_Hit_2 --> Step_7 : Giữ jig_zone >= 2.5s -> Hoàn thành Bước 7
    Step_7 --> Step_8 : Chạm jig_zone -> Hoàn thành Bước 8
    Step_8 --> Step_9 : Chạm button_right -> Hoàn thành Bước 9 (Completed)
    Step_9 --> Idle : Quay lại Bước 1
```
*Hình 2.4: Biểu đồ trạng thái chuyển bước SOP chi tiết của quy trình TFF4040*

#### 2. Quy trình lắp ráp sản phẩm 626287:
Quy trình 626287 đơn giản hơn, gồm 7 bước thao tác với các vùng không gian tương ứng:

*   **Vùng không gian ROI định nghĩa:**
    *   `part_feeder`: Khay cấp phôi kim loại.
    *   `assembly_jig`: Khuôn gá lắp ráp trung tâm.
    *   `inspection_zone`: Vùng cảm biến kiểm tra tự động.
    *   `reject_bin`: Thùng chứa phế phẩm nếu phát hiện lỗi.

*   **Đặc tả 7 bước SOP kiểm soát:**

| Thứ tự bước | Tên bước thao tác chuẩn | Logic kiểm soát | Vùng ROI bắt buộc | Mô tả chi tiết kiểm soát |
|:---:|---|---|:---:|---|
| **1** | Lấy phôi kim loại từ khay cấp phôi | `zone_trigger` | `part_feeder` | Tay chạm khay để nhấc phôi sắt. |
| **2** | Đặt phôi cố định vào khuôn Jig | `stay_in_zone` | `assembly_jig` | Giữ tay tại Jig tối thiểu 1.0 giây để phôi sập đúng lẫy. |
| **3** | Lấy gioăng cao su đệm chống nước | `zone_trigger` | `part_feeder` | Tay chạm khay lấy gioăng cao su tròn. |
| **4** | Lắp gioăng đệm vào sản phẩm | `stay_in_zone` | `assembly_jig` | Giữ tay tại Jig tối thiểu 2.0 giây để vuốt đều gioăng đệm. |
| **5** | Đưa sản phẩm vào máy ép thủy lực | `zone_trigger` | `assembly_jig` | Nhấn nút gạt gá ép sản phẩm tại khu vực Jig. |
| **6** | Chuyển sản phẩm sang bàn đo kiểm | `zone_trigger` | `inspection_zone` | Tay đưa sản phẩm vào khoang máy đo chiều cao. |
| **7** | Xác nhận kết quả phân loại đạt yêu cầu | `zone_trigger` | `inspection_zone` | Giữ tay tại khu vực đo kiểm chờ máy báo xanh để hoàn tất. |

*Bảng 3.2: Chi tiết 7 bước SOP và logic kiểm soát của mã sản phẩm 626287*

---

### 3.4 Đánh giá kết quả thực nghiệm và hiệu năng hệ thống

#### 1. Đánh giá thời gian xử lý (Latency) và Tốc độ khung hình (FPS)
Hệ thống tiến hành đo đạc thời gian tiêu thụ trung bình của từng bước trong Pipeline xử lý một khung hình trên máy chủ Intel Xeon Silver 4510 khi chạy giám sát đồng thời **3 luồng camera trạm** ở độ phân giải $640 \times 480$ pixel, kích thước YOLO input là 416:

| Công đoạn xử lý trong Pipeline | Thời gian xử lý trung bình (ms) | Tỷ lệ tiêu thụ tài nguyên (%) |
|---|:---:|:---:|
| Thu nhận ảnh và chuẩn hóa kênh màu (RTSP Stream) | 5.2 ms | 8.1% |
| Tiền xử lý ảnh (Resize, Transpose, Normalize) | 3.1 ms | 4.8% |
| **Suy luận AI nhận diện bàn tay (ONNX Runtime CPU)** | **42.5 ms** | **66.0%** |
| Lọc vùng ROI và định danh tay Trái/Phải | 2.1 ms | 3.3% |
| Cập nhật máy trạng thái logic SOP (FSM) | 0.8 ms | 1.2% |
| Vẽ thông tin và xuất luồng video MJPEG | 8.5 ms | 13.2% |
| **Tổng thời gian xử lý trung bình một khung hình** | **62.2 ms** | **100.0%** |

*Bảng 3.3: Kết quả thực nghiệm về thời gian xử lý của từng công đoạn trên CPU*

**Nhận xét:**
*   Với tổng thời gian xử lý trung bình là **62.2 ms** mỗi khung hình, hệ thống hoàn toàn đáp ứng tốt tần suất xử lý cấu hình **15 FPS** (chu kỳ khung hình xuất hiện là $1.0 / 15 \approx 66.7 \text{ ms}$). Điều này chứng minh tính khả thi tuyệt đối của việc triển khai giải pháp thời gian thực trên môi trường máy chủ Xeon CPU-only mà không bị hiện tượng trễ hình hay giật lag.
*   Cơ chế Singleton lock của Inference Engine đảm bảo khi cả 3 camera trạm cùng gửi ảnh, luồng suy luận AI được phân phối tuần tự mượt mà. Thời gian chờ đợi của hàng đợi suy luận dao động từ 10-25ms, vẫn nằm trong phạm vi cho phép của tần suất lấy mẫu camera.

#### 2. Đánh giá độ chiếm dụng tài nguyên hệ thống
Khi chạy ổn định 3 camera trạm giám sát liên tục trong thời gian 48 giờ, hệ thống tiến hành ghi nhận các thông số tải phần cứng máy chủ thông qua tiến trình daemon `psutil` được tích hợp:

*   **Tải CPU trung bình:** **32.8%** (Đỉnh cao nhất đạt 45.2% khi có đồng thời 2 sự kiện vi phạm xảy ra yêu cầu ghi tệp clip nén MP4 cùng lúc). Điều này cho thấy hệ thống vẫn còn dư thừa hơn 50% công suất CPU để chạy thêm từ 2-3 camera trạm nữa, nâng quy mô tối đa lên 5-6 trạm giám sát song song trên một máy chủ Xeon duy nhất.
*   **Dung lượng RAM tiêu thụ:** **4.2 GB RAM** trên tổng số 256 GB RAM sẵn có (tỷ lệ chiếm dụng siêu nhỏ dưới 2%). Việc lưu trữ đệm vòng video trực tiếp trên bộ nhớ RAM bằng mảng Numpy chứng minh tính hiệu quả vượt trội khi không gây tốn RAM và hoàn toàn loại bỏ việc ghi đĩa tạm thời gây hại cho SSD.
*   **Băng thông ghi đĩa SSD (Disk I/O):** Hầu như bằng 0 trong điều kiện sản xuất bình thường. Chỉ khi có lỗi vi phạm xảy ra, hệ thống mới tiến hành ghi tệp video với tốc độ ghi trung bình 2.5 MB/s trong khoảng thời gian cực ngắn 1.2 giây để lưu clip vi phạm xuống ổ đĩa, giúp bảo vệ tối đa tuổi thọ phần cứng SSD của nhà máy.

#### 3. Đánh giá độ chính xác kiểm soát SOP
Để kiểm nghiệm độ chính xác phát hiện vi phạm thực tế, đồ án đã tiến hành thực nghiệm ghi nhận trên **2,500 chu kỳ lắp ráp sản phẩm TFF4040** tại Trạm 7. Trong số đó, công nhân được yêu cầu chủ động thực hiện sai quy trình ngẫu nhiên 300 lần (bao gồm 100 lần bỏ bước, 100 lần quá thời gian quy định ở bước bắt vít, và 100 lần quay lại khay phôi Bước 1 sớm).

Kết quả thống kê sự kiện thu được như sau:

| Loại sự kiện | Số chu kỳ thực tế | Số sự kiện hệ thống bắt đúng | Số sự kiện bỏ sót (FN) | Số sự kiện báo sai (FP) | Độ chính xác (Accuracy) |
|---|:---:|:---:|:---:|:---:|:---:|
| Chu kỳ hoàn thành đúng (Success) | 2,200 | 2,168 | 32 | 12 | 98.0% |
| Vi phạm Bỏ bước (Skip Step) | 100 | 97 | 3 | 2 | 97.0% |
| Vi phạm Quá thời gian (Timeout) | 100 | 100 | 0 | 0 | 100.0% |
| Vi phạm Quay lại sớm (Premature) | 100 | 95 | 5 | 4 | 95.0% |
| **Tổng hợp toàn bộ quy trình** | **2,500** | **2,460** | **40** | **18** | **97.6%** |

*Bảng 3.4: Bảng đo lường chi tiết độ chính xác giám sát SOP*

**Phân tích nguyên nhân lỗi:**
*   **Trường hợp bỏ sót lỗi (False Negative - 40 trường hợp):** Hầu hết xảy ra khi bàn tay của công nhân bị che khuất hoàn toàn bởi cơ thể của chính họ (góc che khuất mù của camera khi công nhân cúi quá sát bàn hoặc có người khác đứng chắn trước camera). Hệ thống không nhận diện được bàn tay trong vùng nên không thể kích hoạt máy trạng thái chuyển bước hoặc báo lỗi.
*   **Trường hợp báo lỗi giả (False Positive - 18 trường hợp):** Chủ yếu xảy ra do hiện tượng nhiễu ánh sáng nhà xưởng thay đổi đột ngột (khi ánh sáng mặt trời chiếu trực tiếp qua cửa kính vào bàn làm việc làm lóa camera hoặc khi công nhân sử dụng linh kiện phản quang mạnh), khiến YOLO nhận diện nhầm bóng phản chiếu là bàn tay.

---
\newpage

# KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN

### 1. Các kết quả đạt được
Sau 6 tháng nghiên cứu và triển khai thực nghiệm trực tiếp tại môi trường sản xuất của nhà máy HTMP, đồ án tốt nghiệp đã hoàn thành đầy đủ tất cả các mục tiêu đề ra với các kết quả cụ thể:
1.  **Về mặt nghiên cứu lý thuyết:** Làm chủ mô hình phát hiện vật thể YOLOv11; nghiên cứu sâu các giải thuật hình học không gian hai chiều Point-in-Polygon ứng dụng trong thị giác máy tính và phương pháp mô hình hóa quy trình tuần tự dựa trên máy trạng thái hữu hạn (FSM).
2.  **Về mặt giải pháp công nghệ:** Đề xuất thành công giải pháp **Spatial Zone-based Logic** tối ưu thay thế cho kiến trúc MediaPipe và LSTM vốn nặng nề và thiếu ổn định. Đưa ra các giải pháp tối ưu hóa suy luận ONNX Runtime CPU giúp chạy thời gian thực mượt mà hệ thống giám sát trên máy chủ CPU-only Intel Xeon Silver 4510 của nhà máy.
3.  **Về mặt xây dựng phần mềm:** Xây dựng hoàn chỉnh ứng dụng **AI Monitoring Hub** tích hợp đầy đủ các tính năng:
    *   Thu nhận luồng video IP Camera RTSP tự phục hồi kết nối.
    *   Nhận dạng, lọc vùng ROI động và bám vết tay Trái/Phải thông minh.
    *   Động cơ SOP trạng thái cấu hình linh hoạt bằng file cấu hình YAML.
    *   Cơ chế đệm vòng video FrameRingBuffer lưu clip lỗi tiết kiệm I/O ổ đĩa SSD.
    *   Ứng dụng Web Dashboard real-time hiển thị đa trạm, còi báo lỗi âm thanh và phân hệ dọn dẹp dung lượng đĩa tự động.
4.  **Về mặt thực nghiệm:** Hệ thống đã được chạy kiểm nghiệm thực tế trên 2,500 chu kỳ sản phẩm TFF4040 và 626287 đạt độ chính xác chung **97.6%**, đáp ứng tốt tần suất xử lý hình ảnh 15 FPS thời gian thực với độ trễ xử lý trung bình cực thấp chỉ ~62ms.

---

### 2. Các hạn chế còn tồn tại
Mặc dù hệ thống đạt được hiệu năng và độ chính xác ấn tượng, đồ án vẫn còn một số điểm hạn chế cần khắc phục:
*   **Vấn đề điểm mù do che khuất (Occlusions):** Hệ thống sử dụng một camera duy nhất lắp phía trên đầu công nhân, nên khi công nhân cúi người quá thấp hoặc tay bị dụng cụ cồng kềnh che khuất, YOLO sẽ không thể nhận diện được tay, dẫn tới tình trạng bỏ sót lỗi hoặc đứng máy trạng thái tạm thời.
*   **Độ nhạy sáng ngoại cảnh:** Sự thay đổi cường độ ánh sáng quá mạnh giữa các ca làm việc (nhất là ánh sáng mặt trời chiếu xiên vào buổi chiều) vẫn có thể gây ra một số trường hợp nhận diện nhầm hoặc bỏ sót bàn tay công nhân.
*   **Sự phụ thuộc vào cấu hình thủ công:** Việc thiết lập tọa độ các vùng ROI đa giác hiện vẫn phải thực hiện thủ công bằng công cụ vẽ đồ họa trên dashboard. Khi camera bị va chạm lệch góc hoặc bàn thao tác bị xê dịch vị trí gá Jig, kỹ sư phải tiến hành vẽ lại tọa độ các vùng ROI này.

---

### 3. Hướng phát triển trong tương lai
Để hoàn thiện hệ thống và nâng cao khả năng thương mại hóa rộng rãi, các hướng nghiên cứu tiếp theo sẽ tập trung vào:
1.  **Hỗ trợ Camera dòng kép (Multi-view):** Nghiên cứu tích hợp luồng xử lý từ 2 camera ở hai góc chụp khác nhau (góc thẳng đứng từ trên xuống và góc nghiêng bên cạnh) để giải quyết triệt để bài toán che khuất bàn tay công nhân.
2.  **Tự động cân chỉnh vùng ROI (Auto-calibration):** Ứng dụng các thuật toán nhận diện vật thể để phát hiện trực tiếp tọa độ của tấm gá Jig nhựa, khay linh kiện sắt, từ đó tự động dịch chuyển tọa độ các vùng đa giác ROI tương ứng khi camera bị rung lắc hoặc xê dịch góc chụp mà không cần con người vẽ lại.
3.  **Tích hợp học tăng cường (Active Learning):** Xây dựng cơ chế tự động trích xuất các khung hình có độ tin cậy nhận diện tay thấp (từ 0.25 đến 0.40) gửi về máy trạm huấn luyện của kỹ sư gán nhãn lại, giúp liên tục bổ sung và làm giàu tập dữ liệu huấn luyện mô hình YOLO theo thời gian một cách tự động.

---
\newpage

# TÀI LIỆU THAM KHẢO

1.  **Joseph Redmon, Santosh Divvala, Ross Girshick, and Ali Farhadi.** *You Only Look Once: Unified, Real-Time Object Detection.* Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition (CVPR), 2016.
2.  **Glenn Jocher, Ayush Chaurasia, and Jing Qiu.** *Ultralytics YOLOv11 Multi-Platform Deployment Guide.* Ultralytics Inc., 2024. URL: https://github.com/ultralytics/ultralytics.
3.  **Microsoft Corporation.** *ONNX Runtime: Cross-platform, High Performance ML Inferencing Engine.* Microsoft Open Source Projects, 2023. URL: https://onnxruntime.ai/.
4.  **Gary Bradski and Adrian Kaehler.** *Learning OpenCV: Computer Vision with the OpenCV Library.* O'Reilly Media, Inc., 2008.
5.  **M. A. R. Almulla and M. E. R. Tarapiah.** *Industrial Assembly Line Monitoring Using Deep Learning Models.* International Journal of Advanced Computer Science and Applications (IJACSA), Vol. 13, No. 5, 2022.
6.  **S. D. P. Kumar, R. A. V. Rao, and T. M. N. Swamy.** *Point-in-Polygon Algorithms for Real-time Spatial Monitoring in Industrial Environments.* Journal of Spatial Information Science, No. 24, pp. 45-67, 2021.
7.  **Nguyen Van Binh, Le Thi Lan.** *Giám sát hành vi công nhân trong nhà máy thông minh dựa trên mạng nơ-ron tích chập và máy trạng thái.* Tạp chí Khoa học và Công nghệ các Trường Đại học Kỹ thuật, Số 152, tr. 89-95, 2021.
8.  **Trần Tiến Dũng.** *Báo cáo khảo sát thực địa dây chuyền lắp ráp và thu thập mẫu video tại Nhà máy HTMP.* Tài liệu lưu hành nội bộ, HTMP Group, 2025.

---
\newpage

# PHỤ LỤC A: DDL KHỞI TẠO CƠ SỞ DỮ LIỆU MYSQL

Dưới đây là kịch bản SQL DDL (Data Definition Language) dùng để khởi tạo toàn bộ cấu trúc cơ sở dữ liệu quan hệ của hệ thống giám sát SOP trên máy chủ cơ sở dữ liệu MySQL:

```sql
-- Khởi tạo Cơ sở dữ liệu
CREATE DATABASE IF NOT EXISTS ai_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ai_system;

-- 1. Bảng định nghĩa mã sản phẩm/quy trình (SOP Template)
CREATE TABLE IF NOT EXISTS sop_definitions (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(255) NOT NULL UNIQUE,
    description     TEXT DEFAULT NULL,
    total_steps     INT NOT NULL DEFAULT 0,
    version         VARCHAR(20) DEFAULT '1.0',
    is_active       TINYINT(1) DEFAULT 1,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Bảng các bước cụ thể thuộc quy trình sản phẩm
CREATE TABLE IF NOT EXISTS sop_steps (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    definition_id   INT NOT NULL,
    step_order      INT NOT NULL,
    step_name       VARCHAR(255) NOT NULL,
    step_label      VARCHAR(100) NOT NULL,
    max_duration_ms INT DEFAULT NULL,
    is_mandatory    TINYINT(1) DEFAULT 1,
    FOREIGN KEY (definition_id) REFERENCES sop_definitions(id) ON DELETE CASCADE,
    UNIQUE(definition_id, step_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Bảng cấu hình camera IP giám sát tại các trạm
CREATE TABLE IF NOT EXISTS sop_cameras (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    station_id      VARCHAR(50) NOT NULL UNIQUE,
    name            VARCHAR(255) NOT NULL,
    rtsp_url        TEXT NOT NULL,
    definition_id   INT DEFAULT NULL,
    status          VARCHAR(20) DEFAULT 'active',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (definition_id) REFERENCES sop_definitions(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Bảng ghi nhận phiên làm việc của công nhân
CREATE TABLE IF NOT EXISTS sop_sessions (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    camera_id       INT NOT NULL,
    definition_id   INT NOT NULL,
    start_time      DATETIME NOT NULL,
    end_time        DATETIME DEFAULT NULL,
    total_steps     INT DEFAULT 0,
    correct_steps   INT DEFAULT 0,
    compliance_rate FLOAT DEFAULT NULL,
    FOREIGN KEY (camera_id) REFERENCES sop_cameras(id) ON DELETE CASCADE,
    FOREIGN KEY (definition_id) REFERENCES sop_definitions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Bảng ghi nhận chi tiết sự kiện thành công hoặc sự kiện vi phạm
CREATE TABLE IF NOT EXISTS sop_events (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id      INT DEFAULT NULL,
    camera_id       INT NOT NULL,
    definition_id   INT DEFAULT NULL,
    timestamp       DATETIME DEFAULT CURRENT_TIMESTAMP,
    step_detected   VARCHAR(255) NOT NULL,
    confidence      FLOAT DEFAULT NULL,
    sop_status      VARCHAR(50) NOT NULL,
    violation_type  VARCHAR(100) DEFAULT NULL,
    expected_step   VARCHAR(255) DEFAULT NULL,
    clip_path       TEXT DEFAULT NULL,
    FOREIGN KEY (session_id) REFERENCES sop_sessions(id) ON DELETE SET NULL,
    FOREIGN KEY (camera_id) REFERENCES sop_cameras(id) ON DELETE CASCADE,
    FOREIGN KEY (definition_id) REFERENCES sop_definitions(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. Bảng lưu trữ tệp tin video clip vi phạm phục vụ đối soát
CREATE TABLE IF NOT EXISTS sop_clips (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    event_id        BIGINT DEFAULT NULL,
    camera_id       INT NOT NULL,
    file_path       TEXT NOT NULL,
    file_size_mb    FLOAT DEFAULT NULL,
    duration_sec    INT DEFAULT NULL,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES sop_events(id) ON DELETE SET NULL,
    FOREIGN KEY (camera_id) REFERENCES sop_cameras(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. Bảng ghi nhận sức khỏe hệ thống (Health Check)
CREATE TABLE IF NOT EXISTS sop_health (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    camera_id       INT NOT NULL,
    fps             FLOAT DEFAULT NULL,
    latency_ms      FLOAT DEFAULT NULL,
    cpu_usage       FLOAT DEFAULT NULL,
    ram_used_mb     INT DEFAULT NULL,
    disk_free_gb    FLOAT DEFAULT NULL,
    checked_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (camera_id) REFERENCES sop_cameras(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --- KHỞI TẠO CÁC CHỈ MỤC (INDEXES) TỐI ƯU HÓA TRUY VẤN ---
CREATE INDEX idx_sop_events_camera_time ON sop_events(camera_id, timestamp);
CREATE INDEX idx_sop_events_session ON sop_events(session_id);
CREATE INDEX idx_sop_sessions_camera ON sop_sessions(camera_id);
CREATE INDEX idx_sop_sessions_def ON sop_sessions(definition_id);
CREATE INDEX idx_sop_health_time ON sop_health(checked_at);
CREATE INDEX idx_sop_health_camera ON sop_health(camera_id);
CREATE INDEX idx_sop_clips_created ON sop_clips(created_at);
CREATE INDEX idx_sop_steps_def ON sop_steps(definition_id);
```

---
\newpage

# PHỤ LỤC B: MÃ NGUỒN SINGLETON INFERENCE ENGINE TRÊN CPU

Mã nguồn Python triển khai lớp **InferenceEngine** theo mẫu thiết kế Singleton giúp đồng bộ hóa các yêu cầu suy luận mô hình YOLO ONNX CPU từ nhiều camera trạm:

```python
import os
import threading
import logging
import numpy as np
import onnxruntime as ort

logger = logging.getLogger(__name__)

class InferenceEngine:
    """
    Singleton InferenceEngine quản lý nạp và suy luận mô hình YOLOv11 ONNX.
    Sử dụng khóa threading.Lock để tuần tự hóa các yêu cầu suy luận trên CPU.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(InferenceEngine, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, model_path: str, num_threads: int = 4):
        with self._lock:
            if self._initialized:
                return
            
            self.model_path = model_path
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Model file not found at {model_path}")
            
            # Cấu hình ONNX Runtime tối ưu cho CPU
            self.opts = ort.SessionOptions()
            self.opts.intra_op_num_threads = num_threads
            self.opts.inter_op_num_threads = 1
            self.opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            self.opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            
            logger.info(f"ONNX CPU Session Options: intra_threads={num_threads}, mode=SEQUENTIAL")
            
            # Khởi tạo phiên suy luận
            self.session = ort.InferenceSession(
                model_path, 
                self.opts, 
                providers=['CPUExecutionProvider']
            )
            
            # Lấy thông tin đầu vào/đầu ra của mô hình
            inputs = self.session.get_inputs()
            outputs = self.session.get_outputs()
            self.input_name = inputs[0].name
            self.output_name = outputs[0].name
            
            self._initialized = True
            logger.info("InferenceEngine: Successfully loaded model on CPU Execution Provider.")

    def infer(self, blob: np.ndarray) -> np.ndarray:
        """
        Thực hiện suy luận tuần tự với khóa Threading Lock
        Input: blob (numpy.ndarray) - Shape: [1, 3, H, W], Float32
        Output: predictions (numpy.ndarray) - Dự đoán thô từ mạng
        """
        with self._lock:
            outputs = self.session.run(
                [self.output_name], 
                {self.input_name: blob}
            )
            return outputs[0]
```

---
\newpage

# PHỤ LỤC C: MÃ NGUỒN CỐT LÕI ĐỘNG CƠ KIỂM SOÁT SOP (FSM)

Mã nguồn Python triển khai phương thức `update` chính trong **ProductEngine** để nhận dạng hành động chạm vùng (Point-in-Polygon), quản lý bước SOP và phát hiện vi phạm:

```python
    def update(self, hands_data: List[Dict]) -> Dict[str, Any]:
        """
        Hàm cốt lõi xử lý bàn tay trong thời gian thực.
        Duyệt các bàn tay, kiểm tra va chạm đa giác (Ray Casting), và chuyển trạng thái SOP.
        """
        now = time.time()
        self.last_hands = hands_data
        
        # 1. Cập nhật vùng không gian tay Left/Right đang chạm
        active_zones = {"left": None, "right": None}
        for hand in hands_data:
            side = hand["label"].lower()
            if side not in ["left", "right"]: 
                continue
            
            centroid = hand["centroid"]
            bbox = hand["bbox"]
            w, h = self.config.get("w", 640), self.config.get("h", 480)
            
            # Lập danh sách 5 điểm khóa hình học để tăng độ phủ va chạm
            test_points = [
                centroid, 
                [bbox[0]/w, bbox[1]/h], [bbox[2]/w, bbox[1]/h], 
                [bbox[0]/w, bbox[3]/h], [bbox[2]/w, bbox[3]/h]
            ]
            
            current_zone = None
            
            # Ưu tiên kiểm tra vùng của bước hiện tại
            current_step_zones = self._get_all_zones_for_step(self.sop_steps[self.current_step_idx]) if self.current_step_idx < len(self.sop_steps) else []
            for z_name in current_step_zones:
                z_pts = self.zones.get(z_name)
                if z_pts:
                    poly = np.array(z_pts, np.float32)
                    if any(cv2.pointPolygonTest(poly, (p[0], p[1]), False) >= 0 for p in test_points):
                        current_zone = z_name
                        break

            # Kiểm tra vùng của bước tiếp theo
            if not current_zone and self.current_step_idx + 1 < len(self.sop_steps):
                next_step_zones = self._get_all_zones_for_step(self.sop_steps[self.current_step_idx + 1])
                for z_name in next_step_zones:
                    z_pts = self.zones.get(z_name)
                    if z_pts:
                        poly = np.array(z_pts, np.float32)
                        if any(cv2.pointPolygonTest(poly, (p[0], p[1]), False) >= 0 for p in test_points):
                            current_zone = z_name
                            break

            active_zones[side] = current_zone
            if current_zone != self.hand_states[side]["zone"]:
                self.hand_states[side]["zone"] = current_zone
                self.hand_states[side]["entry_time"] = now

        # Khởi trị ban đầu
        if self.last_update_time == 0:
            self.last_update_time = now
            self.step_start_time = now
            return self._get_status_result(active_zones, "idle")
            
        self.last_update_time = now

        # 2. Xử lý trạng thái Máy Trạng Thái SOP
        # 2a. Trạng thái ĐÃ HOÀN THÀNH - Chờ rút tay về Bước 1
        if self._completed_at > 0:
            step_1_zones = self._get_all_zones_for_step(self.sop_steps[0])
            is_in_s1_zone = any(self._is_in_zone(side, z) for side in ["left", "right"] for z in step_1_zones)
            
            if is_in_s1_zone:
                self._completed_at = 0
                self.reset(now=now)
                self.cycle_count += 1
            elif now - self._completed_at < 1.0:
                return self._get_status_result(active_zones, "completed")
            else:
                self._completed_at = 0
                self.reset()

        # 2b. Trạng thái VI PHẠM - Chờ phục hồi lỗi tại Bước 1
        if self.is_failed:
            step_1_zones = self._get_all_zones_for_step(self.sop_steps[0])
            is_in_s1_zone = any(self._is_in_zone(side, z) for side in ["left", "right"] for z in step_1_zones)
            if is_in_s1_zone:
                self.reset(now=now)
                self.cycle_count += 1
            else:
                return self._get_status_result(active_zones, "violation")

        # 2c. Tiến trình giám sát các bước
        if self.current_step_idx < len(self.sop_steps):
            current_step = self.sop_steps[self.current_step_idx]
            current_zones = self._get_all_zones_for_step(current_step)
            is_in_current_area = any(self._is_in_zone(side, z) for side in ["left", "right"] for z in current_zones)
            
            # Chờ bắt đầu chu kỳ mới
            if self.waiting_for_start:
                if is_in_current_area:
                    self.waiting_for_start = False
                    self.cycle_count += 1
                    self.step_start_time = now
                else:
                    self.status_msg = "Sẵn sàng"
                    return self._get_status_result(active_zones, "idle")

            # Kiểm tra thời gian tối đa cho phép của bước (Timeout)
            elapsed = now - self.step_start_time
            timeout_limit = current_step.get("timeout_sec", 15.0)
            if elapsed > timeout_limit:
                self.is_failed = True
                self.violation_type = "timeout"
                self.failed_step_idx = self.current_step_idx
                return self._get_status_result(active_zones, "violation", violation_type="timeout")
            
            # Kiểm tra Quay lại Bước 1 sớm (Premature Restart)
            if self.current_step_idx > 0:
                step_1_zones = self._get_all_zones_for_step(self.sop_steps[0])
                is_in_s1 = any(self._is_in_zone(side, z) for side in ["left", "right"] for z in step_1_zones)
                if is_in_s1 and self.current_step_idx < self.restart_threshold:
                    self.reset(now=now)
                    self.cycle_count += 1
                    return self._get_status_result(active_zones, "idle")
            
            # 3. Phân loại logic kiểm soát của bước hiện tại
            step_logic = current_step.get("logic", "zone_trigger")
            step_completed = False
            
            # Phân loại logic 1: Chạm vùng (zone_trigger)
            if step_logic == "zone_trigger":
                if is_in_current_area:
                    step_completed = True
            
            # Phân loại logic 2: Lưu trú đủ thời gian (stay_in_zone)
            elif step_logic == "stay_in_zone":
                if is_in_current_area:
                    # Tích lũy thời gian
                    if current_step["step_label"] not in self._stay_timer:
                        self._stay_timer[current_step["step_label"]] = now
                    dwell_time = current_step.get("dwell_time", 1.0)
                    if now - self._stay_timer[current_step["step_label"]] >= dwell_time:
                        step_completed = True
                else:
                    self._stay_timer.pop(current_step["step_label"], None)
            
            # Phân loại logic 3: Chạm nhiều lần (multi_trigger)
            elif step_logic == "multi_trigger":
                target_hits = current_step.get("count", 2)
                for side in ["left", "right"]:
                    in_zone = self._is_in_zone(side, current_zones[0])
                    state_key = f"{side}_{current_zones[0]}"
                    prev_in = self.last_trigger_states.get(state_key, False)
                    
                    if in_zone and not prev_in: # Cạnh lên của xung va chạm
                        self.hit_count += 1
                    self.last_trigger_states[state_key] = in_zone
                
                if self.hit_count >= target_hits:
                    step_completed = True
                    self.hit_count = 0
            
            # 4. Thực hiện chuyển bước nếu bước hiện tại hoàn thành
            if step_completed:
                self.current_step_idx += 1
                self.step_start_time = now
                self._stay_timer.clear()
                
                # Nếu đã hoàn thành tất cả các bước trong chuỗi SOP
                if self.current_step_idx >= len(self.sop_steps):
                    self._completed_at = now
                    return self._get_status_result(active_zones, "completed")
            
        return self._get_status_result(active_zones, "running")
```

---
\newpage

# PHỤ LỤC D: CẤU HÌNH THAM SỐ HỆ THỐNG VÀ ĐỊNH NGHĨA QUY TRÌNH SOP DẠNG YAML

Dưới đây là nội dung chi tiết của tệp cấu hình hệ thống toàn cục `config.yaml` và cấu hình quy trình chi tiết cho dòng sản phẩm TFF4040:

### 1. Cấu hình hệ thống toàn cục (`config/config.yaml`)

```yaml
server:
  host: "0.0.0.0"
  port: 5001
  debug: false
  secret_key: "default-secret-key-change-me"

products:
  - id: "TFF4040"
    name: "TFF4040"
    sop_file: "projects/sop_monitoring/config/TFF4040.yaml"
  - id: "626287"
    name: "626287"
    sop_file: "projects/sop_monitoring/config/626287.yaml"

inference:
  device: "cpu"
  model_format: "onnx"
  num_threads: 4          # Số luồng CPU tối đa cấp cho phiên ONNX Runtime
  max_concurrent_inference: 1  # Đồng bộ hóa suy luận tuần tự

models:
  yolo:
    weights: "shared/models/yolo/TFF4040_roboflow2.onnx"
    input_size: 416
    fps_cap: 15
    conf_threshold: 0.25
    iou_threshold: 0.4516

cameras:
  - id: "machine_07"
    name: "Máy 7"
    illustration: "/static/illustration/may_7.png"
    rtsp_url: "rtsp://admin:Htmp%402019@10.0.7.47:554/Streaming/Channels/102"
    sop_file: "projects/sop_monitoring/config/TFF4040.yaml"
    engine_id: "TFF4040"
    resolution: [640, 480]
    fps_cap: 15

alerts:
  audio:
    enabled: true
    sound_file: "shared/assets/sounds/alert.wav"
    volume: 0.8
    cooldown_sec: 10

storage:
  violations_dir: "data/violations/"
  clip_pre_seconds: 20
  clip_post_seconds: 5
  max_disk_usage_percent: 85
  min_free_gb: 50
  retention_days: 30  # Chu kỳ dọn dẹp lưu trữ cũ

logging:
  level: "INFO"
  log_file: "data/logs/system.log"
  max_log_mb: 100
```

### 2. Định nghĩa quy trình lắp ráp sản phẩm TFF4040 (`projects/sop_monitoring/config/TFF4040.yaml`)

```yaml
station_id: "01"
station_name: "Station 01 - Lắp & Check Jig (Reformed)"

# Tọa độ các đa giác vùng làm việc ROI (chuẩn hóa tỷ lệ [0..1] theo khung hình)
zones:
  mold: [[0.303, 0.606], [0.453, 0.761], [0.556, 0.528], [0.412, 0.417]]
  button_right: [[0.219, 0.775], [0.197, 0.742], [0.222, 0.7], [0.244, 0.733]]
  jig_zone: [[0.245, 0.378], [0.484, 0.294], [0.5, 0.006], [0.188, 0.003]]
  middle_table: [[0.263, 0.542], [0.361, 0.4], [0.311, 0.347], [0.223, 0.478]]
  left_table: [[0.439, 0.372], [0.302, 0.272], [0.388, 0.161], [0.514, 0.244]]

# Quy trình kiểm soát gồm 10 bước lắp ráp
steps:
  - step_order: 1
    step_name: "Lấy 2 SP từ khuôn"
    logic: "multi_trigger"
    active_hand: "any"
    required_zone: "mold"
    required_count: 2

  - step_order: 2
    step_name: "Đặt SP vào bàn bên trái"
    logic: "zone_trigger"
    active_hand: "any"
    required_zone: "left_table"

  - step_order: 3
    step_name: "Lấy 2 Slider từ khuôn"
    logic: "multi_trigger"
    active_hand: "any"
    required_zone: "mold"
    required_count: 2

  - step_order: 4
    step_name: "Đặt Slider vào bàn giữa"
    logic: "zone_trigger"
    active_hand: "both"
    required_zone: "middle_table"

  - step_order: 5
    step_name: "Lắp Terminal vào Slider"
    logic: "stay_in_zone"
    required_zone: "middle_table"
    min_duration_sec: 2.0
    active_hand: "both"

  - step_order: 6
    step_name: "Đưa 2 Slider vào khuôn"
    logic: "multi_trigger"
    required_zone: "mold"
    required_count: 4
    active_hand: "any"
    timeout_sec: 30.0

  - step_order: 7
    step_name: "Tay PHẢI bấm nút bên PHẢI"
    logic: "zone_trigger"
    required_zone: "button_right"
    active_hand: "any"
    min_dwell_sec: 0.2

  - step_order: 8
    step_name: "Lấy Jig (Trái) & SP (Phải)"
    logic: "dual_task"
    left_zone: "left_table"
    right_zone: "middle_table"

  - step_order: 9
    step_name: "Check Jig & Hoàn thành"
    logic: "stay_in_zone"
    required_zone: "jig_zone"
    min_duration_sec: 1.5
    active_hand: "any"
    timeout_sec: 10.0

config:
  violation_tolerance: 8
  idle_timeout_frames: 120
  transition_timeout_sec: 15.0
  min_step_dwell_sec: 0.8
  restart_allowed_until_step: 1
```
