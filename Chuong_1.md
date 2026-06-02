# CHƯƠNG 1: TỔNG QUAN VỀ ĐỀ TÀI VÀ CÁC NGHIÊN CỨU LIÊN QUAN

### 1.1 Tổng quan về giám sát SOP trong công nghiệp 4.0

#### 1.1.1 Khái niệm, vai trò SOP trong sản xuất
Quy trình Thao tác Chuẩn (SOP - Standard Operating Procedure) là hệ thống các văn bản chỉ dẫn chi tiết từng bước thực hiện công việc sản xuất hoặc vận hành, được thiết lập nhằm duy trì tính đồng nhất, chất lượng sản phẩm đầu ra và đảm bảo an toàn lao động [1]. Trong bối cảnh công nghiệp lắp ráp linh kiện điện tử, cơ khí chính xác hay ép nhựa định hình (như tại nhà máy HTMP), vai trò của SOP là cực kỳ then chốt:
*   **Chuẩn hóa thao tác:** Giảm thiểu sự biến động trong kỹ năng thao tác giữa các công nhân cũ và mới.
*   **Đảm bảo chất lượng:** Ngăn ngừa việc lắp ráp thiếu linh kiện hoặc lắp sai trình tự làm ảnh hưởng tới chức năng của sản phẩm.
*   **Tối ưu hóa thời gian chu kỳ (Cycle Time):** Định hình các bước làm việc khoa học, loại bỏ các động tác thừa để đạt năng suất thiết kế tối đa [2].

![Hình 1.1: Tài liệu quy trình thao tác chuẩn SOP thực tế tại trạm lắp ráp](images/figure_1_1.png)

#### 1.1.2 Các loại vi phạm SOP và hệ quả kinh tế
Trong thực tế sản xuất tại các nhà máy, việc công nhân vi phạm quy trình SOP diễn ra khá phổ biến do các yếu tố như mệt mỏi, phân tâm, áp lực sản lượng hoặc do lỗi chủ quan. Các loại vi phạm thường gặp bao gồm:
*   **Bỏ bước (Skip Step):** Công nhân không thực hiện một hoặc nhiều bước trung gian (ví dụ: không lắp gioăng cao su, không bôi keo tản nhiệt) mà chuyển thẳng tới bước tiếp theo.
*   **Sai trình tự (Out-of-Order Assembly):** Thực hiện bước sau trước bước trước (ví dụ: thực hiện bấm nút hoàn thành chu kỳ hoặc bắt vít cố định trước khi đặt chi tiết nhựa vào khuôn gá).
*   **Sai thời gian chu kỳ (Timing Violation):** Không tuân thủ thời gian tối thiểu của các bước đặc thù, ví dụ như thời gian giữ mối hàn hoặc thời gian kiểm jig (dwell time) quá nhanh, dẫn tới sản phẩm không đạt tiêu chuẩn kỹ thuật [3].
*   **Quay lại bước 1 sớm (Premature Restart):** Công nhân đưa tay về vùng lấy phôi của chu kỳ mới khi chu kỳ cũ chưa kết thúc.

Hệ quả kinh tế của các lỗi vi phạm SOP là vô cùng lớn. Việc lắp ráp sai quy trình dẫn tới tỷ lệ phế phẩm (Scrap Rate) tăng cao, tăng khối lượng sản phẩm phải làm lại (Rework), gây lãng phí nguyên vật liệu và nhân công. Nghiêm trọng hơn, nếu sản phẩm lỗi lọt qua khâu kiểm tra ngoại quan (QA/QC) và xuất xưởng đến tay khách hàng, doanh nghiệp sẽ phải đối mặt với chi phí thu hồi sản phẩm khổng lồ, bồi thường thiệt hại và làm suy giảm nghiêm trọng uy tín thương hiệu trên thị trường [4].

#### 1.1.3 Hiện trạng giám sát SOP tại các nhà máy Việt Nam
Hiện nay, phần lớn các nhà máy sản xuất công nghiệp tại Việt Nam vẫn áp dụng phương pháp giám sát SOP thủ công truyền thống:
*   **Giám sát trực tiếp bởi con người:** Các tổ trưởng (line leaders) hoặc kỹ sư quản lý chất lượng (QC) đi tuần tra dọc theo các chuyền sản xuất để quan sát ngẫu nhiên thao tác của công nhân.
*   **Hạn chế cố hữu:** Phương pháp này mang tính rời rạc, không thể giám sát liên tục 24/7 tất cả các trạm lắp ráp. Con người dễ mệt mỏi, mất tập trung và có xu hướng đánh giá cảm tính. Chi phí nhân sự cho đội ngũ QC rất cao nhưng hiệu quả kiểm soát lỗi không triệt để. Khi phát hiện sản phẩm lỗi ở cuối chuyền, việc truy cứu ngược lại xem công nhân trạm nào làm sai bước nào gặp rất nhiều khó khăn do thiếu bằng chứng hình ảnh ghi nhận lịch sử thao tác [5]. Do đó, việc tự động hóa quá trình giám sát thao tác bằng công nghệ thị giác máy tính là xu hướng tất yếu.

---

### 1.2 Tổng quan các công trình nghiên cứu liên quan

#### 1.2.1 Giám sát thao tác dựa trên nhận diện tư thế cơ thể (Skeleton-based)
Một hướng tiếp cận phổ biến trong nhận diện hành động con người là dựa trên thông tin khung xương (Skeleton-based Action Recognition). Các nghiên cứu trong nhóm này sử dụng camera đo chiều sâu (RGB-D) hoặc các thuật toán ước lượng tư thế (Pose Estimation) như OpenPose để trích xuất tọa độ các khớp nối cơ thể [6]. Sau đó, các mô hình đồ thị tích chập thời-không (Spatio-Temporal Graph Convolutional Networks - ST-GCN) được áp dụng để phân loại hành động dựa trên sự thay đổi vị trí của các khớp nối theo thời gian [7].
*   **Ưu điểm:** Khả năng mô tả chuyển động cơ thể ở mức độ toàn cảnh tốt, ít bị ảnh hưởng bởi sự thay đổi của ánh sáng môi trường hay màu sắc quần áo.
*   **Nhược điểm:** Phù hợp hơn cho các hành động vĩ mô (chạy, nhảy, ngã) của cả cơ thể. Trong các công đoạn lắp ráp công nghiệp, công nhân chủ yếu ngồi làm việc tại chỗ, cơ thể di chuyển rất ít, các thao tác tinh vi hầu như chỉ diễn ra ở ngón tay và bàn tay. Các mô hình Skeleton-based toàn thân có độ phức tạp tính toán rất lớn và không đủ độ nhạy để nhận diện các thay đổi nhỏ trên bàn tay.

![Hình 1.2: Minh họa nhận diện hành động dựa trên khung xương cơ thể (Skeleton-based) và mạng đồ thị ST-GCN](images/figure_1_2.png)

#### 1.2.2 Nhận diện hành động dùng 3D-CNN và Two-Stream Networks
Mạng tích chập 3 chiều (3D-CNN) như C3D, I3D [8] mở rộng bộ lọc tích chập sang chiều thời gian để trích xuất đồng thời đặc trưng không gian và động học từ các đoạn video clip ngắn. Mặt khác, kiến trúc dòng kép (Two-Stream Networks) chia luồng xử lý thành hai nhánh: một nhánh xử lý hình ảnh tĩnh (Spatial Stream) để trích xuất đặc trưng hình dáng vật thể, và một nhánh xử lý luồng quang học (Temporal Stream - Optical Flow) để nắm bắt thông tin chuyển động giữa các khung hình liên tiếp [9].
*   **Ưu điểm:** Đạt độ chính xác rất cao trên các tập dữ liệu hành động chuẩn (UCF101, HMDB51) nhờ khả năng biểu diễn thông tin temporal sâu sắc.
*   **Nhược điểm:** Khối lượng tham số của mô hình 3D-CNN cực kỳ lớn, yêu cầu năng lực tính toán phần cứng cực mạnh (phải sử dụng card đồ họa GPU chuyên dụng cao cấp). Việc tính toán luồng quang học (Optical Flow) trong thời gian thực là một nút thắt cổ chai về mặt hiệu năng. Do đó, hướng tiếp cận này hoàn toàn bất khả thi khi triển khai trên các máy chủ CPU-only sẵn có tại nhà máy.

![Hình 1.3: Sơ đồ kiến trúc mạng dòng kép Two-Stream Networks thể hiện nhánh không gian (Spatial Stream) và nhánh thời gian (Temporal Stream - Optical Flow)](images/figure_1_3.png)

#### 1.2.3 Hướng tiếp cận MediaPipe Keypoints + LSTM – ưu/nhược điểm
Để giảm thiểu tài nguyên tính toán, một số nghiên cứu đề xuất giải pháp hai giai đoạn gọn nhẹ hơn:
1.  Sử dụng thư viện **MediaPipe Hands** của Google để phát hiện và trích xuất tọa độ 3D của 21 điểm khóa xương bàn tay (keypoints) trên mỗi khung hình với tốc độ rất nhanh trên CPU [10].
2.  Đưa chuỗi tọa độ 21 keypoints này qua mạng bộ nhớ dài-ngắn hạn (**LSTM - Long Short-Term Memory**) hoặc GRU để phân loại các bước thao tác dựa trên phân tích chuỗi thời gian [11].

```
+------------------+     +--------------------------+     +------------------------+
|  Khung hình ảnh  | --->| MediaPipe Hands          | --->| Mạng LSTM/GRU          |
|  (CPU/Real-time) |     | (Trích xuất 21 Keypoints)|     | (Phân loại bước SOP)   |
+------------------+     +--------------------------+     +------------------------+
                                                                     │
                                                                     ▼
                                                         Kết quả phân loại bước
```
*Hình 1.3: Sơ đồ luồng xử lý của phương pháp MediaPipe Hands + LSTM truyền thống*

![Hình 1.4: Minh họa 21 điểm khóa (Keypoints) của bàn tay người được xác định và đánh số thứ tự từ 0 đến 20 bởi mô hình MediaPipe Hands](images/figure_1_4.png)

*   **Ưu điểm:** Khối lượng dữ liệu đầu vào của mạng LSTM chỉ là tọa độ các điểm khóa (thưa thớt) thay vì toàn bộ pixel ảnh, giúp mô hình huấn luyện cực kỳ nhanh, dung lượng nhẹ và chạy mượt mà trên CPU của các máy tính phổ thông.
*   **Nhược điểm nghiêm trọng trong thực tế:** Hướng tiếp cận này cực kỳ nhạy cảm và kém ổn định đối với hiện tượng che khuất (**occlusions**). Trong lắp ráp công nghiệp thực tế, bàn tay công nhân liên tục tương tác với linh kiện nhựa, kim loại, dụng cụ bắt vít, hoặc bị che bởi chính khuôn gá và bàn tay còn lại. Khi xảy ra che khuất dù chỉ một phần, thuật toán MediaPipe sẽ tính toán sai lệch lớn tọa độ các keypoint hoặc không thể phát hiện được bàn tay (trả về null) [12]. Sự đứt gãy hoặc nhiễu loạn trong chuỗi tọa độ đầu vào này khiến mô hình LSTM đưa ra các dự đoán sai lệch hoàn toàn, dẫn tới tỷ lệ báo động giả (False Positives) tăng vọt, gây ức chế và làm gián đoạn công việc của công nhân.

#### 1.2.4 Khoảng trống nghiên cứu và sự cần thiết của giải pháp mới
Từ việc phân tích các công trình nghiên cứu trên, có thể thấy một khoảng trống công nghệ lớn giữa lý thuyết học thuật và thực tiễn triển khai nhà máy:
*   Các giải pháp chính xác cao (3D-CNN, Two-Stream) thì quá nặng nề, đòi hỏi GPU đắt đỏ và khó bảo trì.
*   Các giải pháp gọn nhẹ chạy được trên CPU (MediaPipe + LSTM) thì lại hoạt động kém ổn định trong điều kiện che khuất và nhiễu ảnh thực tế của nhà máy.
*   Chưa có giải pháp nào giải quyết tối ưu bài toán: **Vừa kháng nhiễu che khuất tốt, vừa đảm bảo xử lý thời gian thực đa luồng ổn định trên CPU-only máy chủ sẵn có.**

Do đó, việc nghiên cứu xây dựng một giải pháp kết hợp giữa phát hiện vật thể học sâu hiệu năng cao (chỉ cần phát hiện hộp bao bàn tay bằng YOLOv11 ONNX) và mô hình hóa logic không gian - trạng thái (Spatial Zone-based Logic & FSM) là vô cùng cấp thiết nhằm lấp đầy khoảng trống công nghệ này.

---

### 1.3 Giải pháp đề xuất và đóng góp của đồ án

Để giải quyết triệt để các thách thức trên, đồ án đề xuất giải pháp giám sát thao tác SOP dựa trên sự kết hợp giữa **mô hình YOLOv11 tối ưu hóa ONNX** chạy trên CPU và **Động cơ Không gian Vùng (Spatial Zone Engine)** phối hợp với **Máy trạng thái hữu hạn (FSM)**.

```
+------------------+     +--------------------------+     +------------------------+
|  Khung hình ảnh  | --->| YOLOv11 Hand (ONNX CPU)  | --->| Spatial Zone Engine    |
|  (RTSP Stream)   |     | (Phát hiện Bbox bàn tay) |     | (Point-in-Polygon ROI) |
+------------------+     +--------------------------+     +------------------------+
                                                                     │
                                                                     ▼
+------------------+     +--------------------------+     +------------------------+
|  Cảnh báo loa /  | <---| Web Dashboard hiển thị   | <---| Lõi logic SOP FSM      |
|  Cắt video clip  |     | (REST API & Socket.IO)   |     | (Kiểm tra thứ tự bước) |
+------------------+     +--------------------------+     +------------------------+
```
*Hình 1.4: Sơ đồ giải pháp đề xuất tích hợp YOLOv11, Spatial Engine và FSM*

![Hình 1.5: Sơ đồ khối kiến trúc hệ thống chi tiết của giải pháp giám sát SOP đề xuất](images/figure_1_5.png)

Các đóng góp chính của đồ án bao gồm:
1.  **Thiết kế giải pháp kháng che khuất cao:** Thay vì cố gắng trích xuất các điểm khớp ngón tay vốn dễ bị che lấp, giải pháp đề xuất chỉ tập trung phát hiện hộp bao (Bounding Box) bàn tay bằng YOLOv11. Sử dụng thuật toán Point-in-Polygon để kiểm tra sự tương tác giữa hộp bao bàn tay và các vùng ROI đa giác đã định nghĩa sẵn. Cách tiếp cận này có độ bền vững cao trước hiện tượng che khuất bán phần.
2.  **Tối ưu hóa sâu trên môi trường CPU-only:** Chuyển đổi mô hình YOLOv11 sang định dạng ONNX Runtime tối ưu luồng, thiết kế cơ chế xử lý đa luồng bất đồng bộ (RTSP stream reader độc lập với AI thread) giúp hệ thống đạt tốc độ xử lý thời gian thực (15 FPS/camera) trên máy chủ CPU Xeon, loại bỏ hoàn toàn sự phụ thuộc vào GPU.
3.  **Cơ chế lưu trữ sự kiện vi phạm thông minh:** Thiết kế bộ đệm khung hình vòng trên bộ nhớ RAM (Frame Ring Buffer) cho phép trích xuất ngược 20 giây trước khi lỗi xảy ra và 5 giây sau đó để cắt lưu clip ngắn. Giải pháp này giúp nhà máy tiết kiệm hơn 95% dung lượng ổ cứng so với việc ghi hình 24/7 nhưng vẫn đảm bảo có video lỗi làm bằng chứng đối soát.
4.  **Cấu hình quy trình linh hoạt:** Tách biệt hoàn toàn logic kiểm soát bước lắp ráp khỏi mã nguồn thông qua tệp cấu hình YAML của sản phẩm TFF4040, giúp hệ thống dễ dàng mở rộng và tùy biến khi thay đổi quy trình sản xuất.

---

### 1.4 Bố cục của đồ án
Nội dung báo cáo đồ án tốt nghiệp được tổ chức thành 5 chương chính:
*   **Chương 1: Tổng quan về đề tài và các nghiên cứu liên quan:** Giới thiệu bối cảnh, lý do chọn đề tài, khảo sát các nghiên cứu đi trước, phân tích ưu nhược điểm để rút ra giải pháp đề xuất và các đóng góp của đồ án.
*   **Chương 2: Cơ sở lý thuyết và các công nghệ nền tảng:** Trình bày cơ sở khoa học của mô hình YOLOv11, ONNX Runtime CPU, thuật toán Point-in-Polygon, mô hình FSM toán học và các công nghệ phụ trợ (RTSP, Python multi-threading, Flask-SocketIO, YAML).
*   **Chương 3: Phân tích và thiết kế hệ thống:** Chi tiết về các yêu cầu FR/NFR, xây dựng các sơ đồ UML (Use Case, Component, Deployment, Sequence), thiết kế database MySQL, kiến trúc chi tiết các module phần mềm.
*   **Chương 4: Xây dựng, tối ưu hóa và thực nghiệm đánh giá:** Trình bày quá trình huấn luyện YOLOv11-hand, các giải pháp tối ưu CPU, thực nghiệm chi tiết quy trình TFF4040 (9 bước), đo đạc hiệu năng (latency, RAM, CPU, disk), phân tích độ chính xác (F1-score, confusion matrix), benchmark so sánh với MediaPipe+LSTM, và phân tích lỗi.
*   **Chương 5: Kết luận và hướng phát triển tương lai:** Tổng kết các kết quả đạt được, chỉ ra các hạn chế và hướng phát triển nâng cấp hệ thống.
