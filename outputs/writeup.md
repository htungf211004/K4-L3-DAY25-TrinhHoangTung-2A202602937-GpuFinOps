# Bài viết ngắn — GPU FinOps

**Học viên:** Trịnh Hoàng Tùng · **MSSV:** 2A202602937 · **Ngày:** 13/10/2026  
**Repo:** [K4-L3-DAY25-TrinhHoangTung-2A202602937-GpuFinOps](https://github.com/htungf211004/K4-L3-DAY25-TrinhHoangTung-2A202602937-GpuFinOps)

## 1. Baseline vs. Optimized

Lab dùng dữ liệu tổng hợp seed=25, giá và hệ số minh họa tháng 6/2026. Đã đọc source cùng CODELAB, Guide, README_en, README và Rubric. Kết quả trên cùng dữ liệu:

| Phạm vi | Baseline | Optimized | Tiết kiệm |
| --- | --- | --- | --- |
| Inference M2, USD/ngày | 48.87 | 8.48 | 82.6% |
| Inference M2, USD/1M-token | 6.488 | 1.126 | 82.6% |
| Purchasing M3, USD/30 ngày | 25,667 | 15,627 | 39.1% |
| Kịch bản tổng M5, USD/30 ngày | 27,133 | 14,626 | 12,507 USD; 46.1% |

M2 phục vụ 7,533,027 token/ngày; mẫu số không đổi khi áp dụng cascade/cache/batch. M3 quy đổi mọi job thành 30 ngày. M5 giữ phép tổng hợp starter, gồm tiềm năng right-sizing và idle. CSV chưa ánh xạ GPU telemetry sang job, nên chưa chứng minh hai khoản M1 độc lập với purchasing. Chỉ tính inference và purchasing, mức giảm là 11,252 USD, tương đương 41.47%. Không dùng token inference để chuẩn hóa cả chi phí training.

## 2. Phân tích từng đòn bẩy

| Đòn bẩy M5 | Tiết kiệm USD/30 ngày |
| --- | --- |
| Purchasing: spot/reserved | 10,040 |
| Inference: cascade/cache/batch | 1,212 |
| Right-size util-lies, tiềm năng | 655 |
| Tắt GPU idle, tiềm năng | 600 |

Purchasing đóng góp lớn nhất vì ngân sách GPU-hours lớn hơn tiền request. Trong inference, tính lần lượt cascade → thêm cache → thêm batch cho savings thêm 37.3985, 1.1965 và 1.7946 USD/ngày. Cascade lớn nhất vì phần lớn request được định tuyến sang model nhỏ. Cache giảm giá phần input tái sử dụng; batch giảm 50% bill của request đủ điều kiện. Tích 0.5 × 0.1 = 0.05 chỉ mô tả input cache hoàn toàn, không phải mọi token. Batch không phù hợp hội thoại cần phản hồi ngay; cache chưa có write/storage cost trong starter.

## 3. GPU-Util Lie và tác động tài chính

`gpu-h100-4` có util 98.2% nhưng MFU 0.194; `gpu-a10g-1` có util 96.9% nhưng MFU 0.268. Util đo thời gian GPU có kernel hoạt động, không đo FLOPs hữu ích. Kernel có thể chờ bộ nhớ hoặc dùng ít tensor core; telemetry chưa đủ để xác định nguyên nhân. Với decode, cần đối chiếu MBU và throughput trước khi kết luận.

Starter đề xuất H100 → A100 tiết kiệm 511.20 USD/30 ngày và A10G → L4 tiết kiệm 144 USD/30 ngày. Đây là tiềm năng theo chênh lệch giá, chưa benchmark VRAM, bandwidth và tokens/s. Riêng `gpu-h100-5` idle 8 giờ/ngày: 8 × 2.50 = 20 USD/ngày, tương đương 600 USD/30 ngày và 3.90% chi phí fleet M1.

## 4. Hai phần mở rộng và insight

**Extension 4 — Ngân sách reasoning:** code trong `missions/m2_inference_levers.py` tách request, input/output token, USD và Wh theo `is_reasoning`; M5 đưa kết quả vào báo cáo. Nhóm reasoning có 201/2,400 request (8.375%), nhưng chiếm 16.459% tiền inference tối ưu và 94.041% năng lượng. Hệ số 80× Wh trên cùng số token là giả định lab, không phải phép đo điện.

Cap 10% không tác động traffic hiện tại: USD/ngày giữ 8.4846, Wh/ngày giữ 31,675.305, savings đúng bằng 0. Mẫu kiểm tra riêng 3 reasoning + 7 thường giữ 1 reasoning sau cap, giảm 621.729 → 226.958 Wh; USD giữ 0.063768 vì model và token/output không đổi. Mẫu này không đại diện toàn traffic và chưa chứng minh chất lượng sau routing. Insight: quota request thấp vẫn có thể chi phối năng lượng; không tự suy ra tiết kiệm tiền từ việc tắt energy multiplier.

**Extension 5 — Carbon-aware scheduling:** code trong `missions/m3_purchasing.py` chọn 5 job interruptible, tính GPU-hours bằng giờ/ngày × ngày thực tế × số GPU, rồi Wh = catalog watts × GPU-hours. Giữ cùng công việc khi so cả 5 vùng. Tổng 1,789,000 Wh tạo 679,820 gCO₂e tại us-east-1, giảm xuống 53,670 gCO₂e tại europe-north1: giảm 626,150 gCO₂e (92.11%). Tiền điện tương ứng giảm 214.680 → 161.010 USD.

Vùng sạch nhất là europe-north1; điện rẻ nhất là us-east-wa (98.395 USD, 161,010 gCO₂e). Chính sách chọn điện rẻ nhất với carbon giảm ít nhất 75% chọn us-east-wa. Insight: mục tiêu rẻ và sạch dẫn đến lựa chọn khác nhau. Watts là proxy catalog, chưa gồm PUE/checkpoint/truyền dữ liệu; tiền điện không được cộng lại vào savings thuê GPU. Cần xem latency, data residency và GPU availability trước khi triển khai thực tế.

## 5. Ba hành động đầu tiên cho NimbusAI

1. Tắt GPU idle theo lịch; profile hai GPU bị flag, kiểm tra VRAM/BW và benchmark throughput trước right-sizing.
2. Dùng spot có checkpoint cho job gián đoạn; chỉ cam kết reserved khi có nhu cầu dài hạn. Áp dụng cascade qua eval chất lượng, cache cho prefix tái sử dụng và batch cho nightly eval; theo dõi USD/1M-token cùng latency.
3. Bổ sung 197 request thiếu project, duy trì gate tags 80%; coverage hiện tại 91.792%. Theo dõi quota reasoning và Wh, chỉ bật reasoning cho task nhiều bước hoặc confidence <0.70 (ngưỡng giả định cần hiệu chỉnh). Chọn vùng cho job linh hoạt theo mục tiêu tiền điện/carbon và ràng buộc dữ liệu.

**Kiểm tra:** `python verify.py` đạt **11/11**; `pytest -q` đạt **15/15**. Đã kiểm tra thêm cap dưới/vượt ngưỡng, dữ liệu rỗng, tổng carbon và tái lập seed. Số liệu chi tiết ở [report.md](report.md), biểu đồ [savings.png](savings.png), mẫu phân bổ [focus_export.csv](focus_export.csv).
