# CHƯƠNG 2: CƠ SỞ LÝ THUYẾT VÀ CÁC CÔNG NGHỆ NỀN TẢNG

### 2.1 Phát hiện vật thể học sâu với họ mô hình YOLO

#### 2.1.1 Sự tiến hóa của dòng mô hình YOLO (You Only Look Once)
YOLO (You Only Look Once) là cột mốc quan trọng trong lĩnh vực thị giác máy tính, chuyển đổi bài toán phát hiện vật thể từ hai giai đoạn (two-stage) phức tạp thành bài toán hồi quy một giai đoạn (one-stage) thời gian thực [13]:
*   **YOLOv1 (2016):** Đề xuất ý tưởng chia khung hình thành lưới $S \times S$, dự đoán trực tiếp tọa độ hộp bao (Bounding Box) và xác suất phân lớp bằng một mạng CNN duy nhất. Tốc độ rất nhanh nhưng độ chính xác định vị còn hạn chế.
*   **YOLOv3 (2018):** Giới thiệu mạng xương sống Darknet-53, cơ chế dự đoán đa quy mô (Multi-scale Predictions) thông qua các hộp neo (Anchor Boxes) tính toán trước bằng thuật toán K-means. Độ chính xác được nâng cao đáng kể, đặc biệt trên các vật thể nhỏ.
*   **YOLOv8 (2023):** Chuyển dịch sang kiến trúc không neo (Anchor-free), tách biệt đầu ra phân loại và định vị (Decoupled Head), và sử dụng module C2f để trích xuất đặc trưng đa lớp tốt hơn.
*   **YOLOv11 (2024):** Phiên bản tối ưu hóa sâu sắc cả về kiến trúc mạng lẫn hiệu năng xử lý. YOLOv11 tinh chỉnh module C3k2 và cơ chế chia C2f để tối đa hóa độ chính xác mà không làm tăng đáng kể khối lượng tham số. Nhờ vậy, YOLOv11 đạt hiệu năng vượt trội khi chạy trên phần cứng giới hạn như CPU.

#### 2.1.2 Kiến trúc YOLOv11-hand
Mô hình YOLOv11 được cấu hình huấn luyện để phát hiện một lớp duy nhất là "bàn tay người" (hand). Cấu trúc mô hình gồm ba phần chính:
1.  **Backbone (Mạng xương sống):** Sử dụng các tầng tích chập kết hợp khối C3k2 để trích xuất đặc trưng hình học từ ảnh đầu vào $416 \times 416$.
2.  **Neck (Cổ mạng):** Sử dụng cấu trúc PANet (Path Aggregation Network) để kết hợp các đặc trưng từ tầng nông (độ phân giải cao, chi tiết hình học tốt) và tầng sâu (độ phân giải thấp, ngữ nghĩa cao), giúp phát hiện bàn tay ở nhiều tỷ lệ khoảng cách khác nhau.
3.  **Head (Đầu ra):** Sử dụng Decoupled Head phân tách luồng tính toán hộp bao (Bbox) và phân loại đối tượng.

![Hình 2.1: Sơ đồ khối kiến trúc chi tiết các tầng mạng YOLOv11 bao gồm phần Backbone, Neck và các Decoupled Heads](images/figure_2_1.png)

#### 2.1.3 Các hàm mất mát và chỉ số đánh giá
YOLOv11 sử dụng sự kết hợp của hai hàm mất mát tiên tiến cho phần định vị hộp bao [14]:
*   **Complete IoU (CIoU) Loss:** Tối ưu hóa khoảng cách tâm, tỷ lệ diện tích giao trên hợp (IoU) và tỷ lệ khung hình của hộp bao dự đoán so với hộp bao thực tế (Ground Truth):
    $$\mathcal{L}_{\text{CIoU}} = 1 - \text{IoU} + \frac{\rho^2(b, b^{gt})}{c^2} + \alpha v$$
    Trong đó $b, b^{gt}$ lần lượt là tâm hộp dự đoán và thực tế, $\rho$ là khoảng cách Euclidean, $c$ là đường chéo hộp bao tối thiểu chứa cả hai hộp, và $v$ đo lường sự nhất quán của tỷ lệ khung hình.
*   **Distribution Focal Loss (DFL):** Hồi quy vị trí hộp dưới dạng phân phối xác suất thay vi một giá trị đơn lẻ, giúp mô hình nhạy bén hơn với các ranh giới mờ hoặc bị che khuất của bàn tay.

Hệ thống được đánh giá bằng các chỉ số học thuật chuẩn:
*   **Precision (Độ chính xác):** Tỷ lệ bàn tay phát hiện đúng trên tổng số phát hiện của mô hình.
*   **Recall (Độ nhạy):** Tỷ lệ bàn tay được mô hình phát hiện trên tổng số bàn tay thực tế có trong ảnh.
*   **mAP@50 (Mean Average Precision tại IoU=0.5):** Diện tích dưới đường cong Precision-Recall tại ngưỡng khớp IoU 50%, là thước đo chuẩn của mô hình phát hiện đối tượng.

---

### 2.2 Tăng tốc suy luận trên CPU với ONNX Runtime

#### 2.2.1 Định dạng mô hình mở ONNX
Mô hình sau khi huấn luyện trên PyTorch thường ở dạng file `.pt` chứa toàn bộ cấu trúc đồ thị tính toán động của PyTorch. Để tối ưu hóa, mô hình được export sang định dạng **ONNX (Open Neural Network Exchange)** [15]. ONNX chuẩn hóa các toán tử toán học thành một đồ thị tĩnh có hướng (Dataflow Graph), cho phép tối ưu hóa độc lập với framework huấn luyện ban đầu.

#### 2.2.2 Cơ chế tối ưu hóa của ONNX Runtime trên CPU
ONNX Runtime là bộ công cụ thực thi đồ thị ONNX tĩnh được thiết kế để khai thác triệt để sức mạnh phần cứng CPU thông qua các tầng tối ưu hóa:
*   **Hợp nhất các tầng (Layer Fusion):** Tự động gộp các phép toán liên tiếp như phép tích chập (Conv), chuẩn hóa batch (Batch Normalization), và hàm kích hoạt (ReLU/Sigmoid) thành một nhân tính toán (Kernel) duy nhất để giảm băng thông truy cập bộ nhớ đệm L1/L2.
*   **Tối ưu hóa đa luồng (Threading Model):** 
    *   *Intra-op threads:* Song song hóa việc tính toán bên trong một toán tử đơn lẻ (ví dụ: chia nhỏ ma trận trong phép nhân chập Conv).
    *   *Inter-op threads:* Song song hóa việc tính toán giữa các toán tử độc lập trong đồ thị.
*   **Vector hóa bằng tập lệnh AVX-512:** CPU Intel Xeon Silver 4510 hỗ trợ tập lệnh AVX-512, cho phép thực hiện các phép toán số học dấu phẩy động trên thanh ghi 512-bit (chứa được 16 số float 32-bit). ONNX Runtime sinh mã máy tận dụng tối đa AVX-512 để nhân chập ma trận song song, nâng hiệu năng xử lý CPU lên gấp nhiều lần.

![Hình 2.2: Đồ thị trực quan minh họa cơ chế hợp nhất toán tử (Operator/Layer Fusion) trong ONNX Runtime](images/figure_2_2.png)

#### 2.2.3 So sánh lý thuyết PyTorch CPU vs ONNX Runtime CPU
*   **PyTorch CPU:** Thực thi đồ thị động, quản lý bộ nhớ linh hoạt nhưng có overhead lớn, luồng xử lý bị cản trở bởi cơ chế khóa GIL (Global Interpreter Lock) của Python khi chạy đa luồng. Độ trễ suy luận YOLOv11 dao động từ 180 - 250 ms/khung hình.
*   **ONNX Runtime CPU:** Thực thi đồ thị tĩnh, tối ưu hóa mức độ biên dịch C++, giao tiếp trực tiếp với phần cứng thông qua các thư viện toán học tối ưu như Intel oneDNN. Độ trễ suy luận giảm xuống chỉ còn 35 - 45 ms/khung hình, đảm bảo tính thời gian thực.

---

### 2.3 Hình học tính toán: Thuật toán Point-in-Polygon

#### 2.3.1 Đặc tả vùng ROI bằng tọa độ chuẩn hóa
Mỗi vùng không gian làm việc trên bàn thao tác (ví dụ: vùng khuôn gá `mold`, vùng nút nhấn `button_right`) được định nghĩa bằng một đa giác phẳng gồm $M$ đỉnh:
$$P = \{v_1, v_2, ..., v_M\} \text{ với } v_i = (x_i, y_i) \in [0, 1]^2$$
Các tọa độ đỉnh được chuẩn hóa về đoạn $[0,1]$ bằng cách chia cho chiều rộng $W$ và chiều cao $H$ của khung hình. Điều này giúp tọa độ vùng ROI không bị ảnh hưởng khi thay đổi độ phân giải của luồng video camera.

#### 2.3.2 Giải thuật Ray Casting (Chiếu tia)
Để kiểm tra một điểm $T = (x_t, y_t)$ (tâm centroid của bàn tay) có nằm trong đa giác $P$ hay không, thuật toán chiếu một tia nằm ngang bắt đầu từ $T$ hướng sang bên phải theo chiều dương trục $X$ [16].
Phương trình của tia:
$$R(t) = (x_t + t, y_t), \quad t \ge 0$$
Với mỗi cạnh của đa giác nối từ đỉnh $v_i = (x_i, y_i)$ đến $v_{i+1} = (x_{i+1}, y_{i+1})$, ta kiểm tra sự giao cắt của tia với đoạn thẳng này. Cạnh đa giác giao cắt với tia khi và chỉ khi:
$$\min(y_i, y_{i+1}) \le y_t < \max(y_i, y_{i+1})$$
Và tọa độ giao điểm $x_{\text{intersect}}$ trên trục $X$ thỏa mãn:
$$x_{\text{intersect}} = x_i + \frac{(y_t - y_i) \cdot (x_{i+1} - x_i)}{y_{i+1} - y_i} > x_t$$
Ta đếm tổng số lần giao cắt $k$. Trạng thái của điểm $T$ được xác định:
$$\text{PointInPolygon}(T, P) = \begin{cases} 
\text{Trong đa giác} & \text{nếu } k \pmod 2 \neq 0 \\ 
\text{Ngoài đa giác} & \text{nếu } k \pmod 2 = 0 
\end{cases}$$

![Hình 2.3: Đồ họa hình học minh họa giải thuật chiếu tia Ray Casting kiểm tra điểm nằm trong/ngoài đa giác ROI phẳng](images/figure_2_3.png)

#### 2.3.3 Khái niệm Convex Hull (Bao lồi)
Bao lồi (Convex Hull) của một tập hợp điểm $X$ trên mặt phẳng là đa giác lồi nhỏ nhất chứa tất cả các điểm trong $X$ [17]. Trong đồ án này, giải thuật bao lồi được ứng dụng trong module theo dõi vết bàn tay (Hand Tracking) để ước lượng bao lồi từ tập hợp các điểm góc của hộp bao bàn tay hoặc dùng để gom cụm tọa độ chuyển động của công nhân nhằm tự động chuẩn hóa vùng ROI hoạt động động.

> **[CHÈN HÌNH 2.4: Đồ họa hình học minh họa tập hợp các điểm và đa giác bao lồi Convex Hull nhỏ nhất bao quanh chúng]**

---

### 2.4 Mô hình hóa quy trình bằng Máy trạng thái hữu hạn (FSM)

#### 2.4.1 Cơ sở toán học của FSM
Máy trạng thái hữu hạn (Finite State Machine - FSM) là mô hình toán học của tính toán được định nghĩa bởi bộ 5 thành số [18]:
$$M = (S, \Sigma, \delta, s_0, F)$$
Trong đó:
*   $S = \{s_0, s_1, s_2, ..., s_9, s_{\text{violation}}, s_{\text{completed}}\}$: Tập hợp hữu hạn các trạng thái của quy trình. Với sản phẩm TFF4040, tập $S$ bao gồm trạng thái rảnh rỗi (Idle), 9 trạng thái tương ứng với 9 bước SOP, trạng thái báo lỗi Vi phạm (Violation) và trạng thái Hoàn thành (Completed).
*   $\Sigma = \{e_{\text{zone\_enter}}, e_{\text{zone\_leave}}, e_{\text{timeout}}, e_{\text{dwell\_ok}}\}$: Tập hợp các sự kiện đầu vào kích hoạt chuyển trạng thái, được sinh ra từ việc phân tích vị trí bàn tay của Động cơ Không gian.
*   $\delta: S \times \Sigma \rightarrow S$: Hàm chuyển trạng thái định nghĩa quy luật dịch chuyển giữa các bước. Ví dụ:
    $$\delta(s_{\text{Step\_1}}, e_{\text{dwell\_ok}}) = s_{\text{Step\_2}}$$
    $$\delta(s_{\text{Step\_1}}, e_{\text{timeout}}) = s_{\text{violation}}$$
*   $s_0 \in S$: Trạng thái khởi đầu của hệ thống (`s_0 = Idle`).
*   $F = \{s_{\text{completed}}\} \subset S$: Trạng thái kết thúc thành công của một chu kỳ lắp ráp sản phẩm.

> **[CHÈN HÌNH 2.5: Đồ thị trạng thái và chuyển tiếp của một máy trạng thái hữu hạn (FSM) tổng quát mô tả các nút trạng thái và cạnh sự kiện đầu vào]**

#### 2.4.2 Sự vượt trội của FSM so với mô hình xác suất chuỗi (LSTM/HMM)
Đối với bài toán kiểm soát quy trình nghiệp vụ SOP nghiêm ngặt trong nhà máy, FSM sở hữu những ưu điểm vượt trội so với các mô hình xác suất như LSTM hay Hidden Markov Model (HMM):
*   **Tính xác định tuyệt đối (Deterministic):** FSM hoạt động dựa trên các quy tắc logic toán học rõ ràng. Nếu công nhân thực hiện đúng các bước, máy sẽ chuyển tuần tự; nếu làm sai, FSM lập tức nhảy về trạng thái lỗi `violation`. Ngược lại, các mô hình LSTM hay HMM đưa ra dự đoán mang tính xác suất (ví dụ: xác suất bước tiếp theo là bước 3 là 85%). Điều này dễ dẫn tới lỗi phân loại sai do nhiễu số liệu, gây báo động nhầm.
*   **Dễ cấu hình và bảo trì:** Quy trình FSM được khai báo tường minh dưới dạng tệp tin YAML tĩnh. Khi nhà máy thay đổi quy trình (ví dụ thêm bước hoặc đổi thứ tự vùng), chỉ cần sửa lại tệp YAML. Với LSTM hay HMM, bất kỳ sự thay đổi nhỏ nào trong quy trình cũng yêu cầu kỹ sư phải thu thập lại toàn bộ dữ liệu video và thực hiện huấn luyện (retrain) lại mô hình từ đầu, rất tốn kém và không khả thi trong sản xuất công nghiệp linh hoạt.
*   **Khả năng giải thích được (Explainability):** Khi xảy ra lỗi vi phạm, FSM chỉ ra chính xác bước hiện tại bị lỗi là gì, lỗi do quá thời gian (timeout) hay do bỏ bước (skip step), giúp kỹ sư hệ thống dễ dàng phân tích nguyên nhân lỗi.

---

### 2.5 Các công nghệ nền tảng bổ trợ

#### 2.5.1 Camera IP và giao thức truyền phát RTSP
Camera IP giám sát truyền tải luồng video kỹ thuật số thông qua giao thức truyền phát thời gian thực **RTSP (Real-Time Streaming Protocol)** [19].
Cấu trúc URI kết nối RTSP chuẩn:
`rtsp://username:password@ip_address:port/h264_stream`
Luồng video được nén bằng chuẩn H.264 để tối ưu hóa băng thông truyền tải qua mạng LAN nội bộ. FrameProcessor nhận luồng RTSP này, giải nén thành các ma trận điểm ảnh RGB (numpy array) để đưa vào hàng đợi xử lý AI.

#### 2.5.2 Lập trình đa luồng (Python Multi-threading) và khóa tương hỗ (Lock)
Do Python bị giới hạn bởi Global Interpreter Lock (GIL) - chỉ cho phép một luồng CPU thực thi mã Python tại một thời điểm - việc lập trình song song cần được thiết kế cẩn thiện:
*   **RTSP Thread:** Chạy luồng đọc frame từ camera liên tục bằng OpenCV (`cv2.VideoCapture`). Luồng này chạy độc lập để tránh hiện tượng nghẽn bộ đệm frame của camera (gây trễ hình).
*   **AI Inference Thread:** Chạy độc lập, lấy frame mới nhất từ hàng đợi và gọi ONNX Runtime để suy luận.
*   **Daemon Threads:** Các tiến trình chạy nền giám sát hệ thống như daemon quản lý dọn dẹp bộ nhớ đĩa (`StorageCleanup`) hoạt động định kỳ mà không gây ảnh hưởng tới luồng xử lý chính.
*   **Khóa tương hỗ (Lock):** Do lõi `InferenceEngine` là một singleton dùng chung, khóa `threading.Lock` được sử dụng để serialize các yêu cầu suy luận từ nhiều camera thread khác nhau, đảm bảo an toàn luồng (thread-safety) khi truy cập tài nguyên mô hình ONNX dùng chung.

#### 2.5.3 Flask-SocketIO và truyền phát video MJPEG
*   **Flask:** Framework Web siêu nhỏ gọn bằng Python được sử dụng để xây dựng các API RESTful cung cấp cấu hình hệ thống, lịch sử sự kiện và dữ liệu thống kê.
*   **Flask-SocketIO:** Tích hợp giao thức WebSocket cho phép truyền thông hai chiều thời gian thực giữa máy chủ và trình duyệt web dashboard [20]. Khi FSM phát hiện vi phạm, sự kiện `violation` lập tức được push xuống dashboard để hiển thị cảnh báo đỏ và phát còi mà không cần client phải gửi request polling liên tục.
*   **MJPEG (Motion JPEG) Streaming:** Luồng hình ảnh sau khi vẽ các hộp bao bàn tay và đa giác ROI được nén dưới dạng ảnh JPEG riêng lẻ và truyền phát trực tiếp qua HTTP bằng phương thức phản hồi Multipart (`multipart/x-mixed-replace`). Đây là cơ chế stream video nhẹ nhàng, tương thích ngược tốt với mọi trình duyệt mà không cần cài đặt plugin bổ trợ.

#### 2.5.4 Tệp YAML cấu hình hệ thống
YAML (YAML Ain't Markup Language) là định dạng dữ liệu tuần tự hóa thân thiện với con người, được sử dụng để định nghĩa toàn bộ cấu hình hệ thống và SOP sản phẩm. Định dạng này giúp tách biệt dữ liệu cấu hình khỏi mã nguồn logic, hỗ trợ định nghĩa các thông số như ngưỡng tin cậy (confidence threshold), các điểm tọa độ đa giác ROI và trình tự logic FSM một cách trực quan, khoa học.
