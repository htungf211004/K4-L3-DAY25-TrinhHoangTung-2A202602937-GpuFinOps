# NimbusAI — GPU Cost Optimization Report

**Period:** monthly  
**Baseline spend:** $27,133  
**Optimized spend:** $14,626  
**Projected savings:** $12,507  (**46%**)

## Savings by lever

| Lever | Savings (USD) |
|---|---|
| Inference (cascade/cache/batch) | $1,212 |
| Purchasing (spot/reserved) | $10,040 |
| Right-size util-lies | $655 |
| Kill idle GPUs | $600 |

## Sustainability

- Energy per query: 13.20 Wh
- Carbon per query: 5.015 gCO2e
- Cleanest region: europe-north1
- Cheapest electricity region: us-east-wa

_Figures are June-2026 as-of snapshots; re-baseline before acting._

## Phạm vi, dữ liệu và baseline trước khi sửa

Học viên: Trịnh Hoàng Tùng — 2A202602937. Hoàn thành ngày 13/10/2026. Đã đọc CODELAB.md, Guide.md, README_en.md, README.md, Rubric.md và source finops/missions. Đây là mô phỏng với giá và hệ số tháng 6/2026, seed=25; không phải giá cloud hiện tại.

| CSV | Số dòng | Nhận xét |
| --- | --- | --- |
| price_catalog.csv | 7 | 7 GPU; giá tier, HBM, FLOPs, bandwidth, watts |
| gpu_telemetry.csv | 264 | 11 GPU × 24 giờ; mỗi dòng là 1 GPU-hour |
| token_usage.csv | 2400 | 7,533,027 token; 197 request thiếu project |
| workloads.csv | 8 | 8 job; days khác nhau, num_gpus và interruptible quyết định quy mô |

Đã sinh dữ liệu, đọc cả 4 CSV bằng pandas và lưu kết quả M2/M3 trong report.md trước khi sửa. Các extension giữ nguyên phép tính tiền M2/M3; bảng này tái lập baseline đã lưu và đối chiếu sau sửa:

| Chỉ số | Trước extension | Sau extension |
| --- | --- | --- |
| M2 USD/ngày | 8.48 | 8.48 |
| M2 USD/1M-token | 1.126 | 1.126 |
| M2 savings | 82.6% | 82.6% |
| M3 optimized USD/30 ngày | 15,627 | 15,627 |
| M3 savings | 39.1% | 39.1% |

M5 giữ cách tổng hợp của starter: baseline = 30 × M2 baseline/ngày + M3 on-demand/30 ngày; optimized = baseline − tổng bốn lever (làm tròn USD). M1 right-sizing/idle là tiềm năng bổ sung giả định áp dụng trong cùng portfolio M3. CSV không ánh xạ gpu_id → job_id, nên chưa chứng minh các khoản đó độc lập với purchasing; mức tổng ở đầu báo cáo là kịch bản, không phải tiết kiệm đã xác nhận. Không cộng chi phí điện của extension vào tiền thuê GPU hoặc savings để tránh tính trùng. Token chỉ có cho inference; không chia tổng chi phí training+inference cho token M2.

Chỉ tính hai lever có baseline tương ứng (M2+M3), savings = $11,252 (41.47%); các đề xuất M1 cần kiểm chứng riêng trước khi chốt ngân sách.

## Kết quả M1–M4 và trả lời Guide

### M1 — GPU-Util và idle (Guide 4.3)

| GPU | Loại | Util % | MFU | MBU | Idle giờ/ngày |
| --- | --- | --- | --- | --- | --- |
| gpu-h100-0 | H100 | 94.4 | 0.417 | 0.446 | 0 |
| gpu-h100-1 | H100 | 95.2 | 0.408 | 0.44 | 0 |
| gpu-h100-2 | H100 | 94.3 | 0.401 | 0.423 | 0 |
| gpu-h100-3 | H100 | 93.1 | 0.427 | 0.444 | 0 |
| gpu-h100-4 | H100 | 98.2 | 0.194 | 0.207 | 0 |
| gpu-h100-5 | H100 | 61.1 | 0.261 | 0.271 | 8 |
| gpu-a100-0 | A100 | 31.4 | 0.259 | 0.276 | 0 |
| gpu-a100-1 | A100 | 28.0 | 0.236 | 0.247 | 0 |
| gpu-a10g-0 | A10G | 25.0 | 0.219 | 0.235 | 0 |
| gpu-a10g-1 | A10G | 96.9 | 0.268 | 0.302 | 0 |
| gpu-l4-0 | L4 | 40.0 | 0.302 | 0.328 | 0 |

GPU có util cao nhất là gpu-h100-4: 98.2%, MFU 0.194. Flag gồm gpu-h100-4, gpu-a10g-1. GPU-Util đo thời gian có kernel hoạt động, không đo số FLOPs hữu ích: kernel có thể chờ bộ nhớ, chạy phép toán ít dùng tensor core hoặc có batch nhỏ. Telemetry này chứng minh lệch util/MFU, nhưng chưa đủ profiler để xác định nguyên nhân. Với decode, MFU thấp có thể bình thường do memory-bound; cần MBU, VRAM và throughput, không tự kết luận GPU lỗi.

gpu-h100-5 idle 8 giờ/ngày: 8 × $2.50 = $20.00/ngày, $600/30 ngày. Tổng fleet M1 on-demand $513.12/ngày; idle chiếm 3.90% chi phí fleet và 2.21% baseline kịch bản M5.

| Đề xuất starter | Savings USD/30 ngày | Giới hạn |
| --- | --- | --- |
| gpu-h100-4: H100 → A100 | 511.20 | Chưa benchmark throughput/VRAM/BW; chỉ là tiềm năng |
| gpu-a10g-1: A10G → L4 | 144.00 | Chưa benchmark throughput/VRAM/BW; chỉ là tiềm năng |

### M2 — Inference (Guide 5.4)

| Bước | USD/ngày | USD/1M-token | Savings thêm USD/ngày |
| --- | --- | --- | --- |
| Baseline | 48.8742 | 6.488 | 0.0000 |
| Cascade | 11.4756 | 1.523 | 37.3985 |
| + Cache | 10.2792 | 1.365 | 1.1965 |
| + Batch | 8.4846 | 1.126 | 1.7946 |

Cascade đóng góp lớn nhất vì phần lớn request dùng model nhỏ. Các khoản thêm được tính theo thứ tự cascade → cache → batch, cùng số token, nên không đếm trùng. 0.50 × 0.10 = 0.05 chỉ đúng với phần input cache 100%; output vẫn trả giá output trước batch. Không batch hội thoại cần phản hồi ngay hoặc request có deadline thấp. Cache ở starter chưa tính write/storage cost vì CSV không có prefix/read-count; đây không phải extension cache economics.

### M3 — Purchasing (Guide 6.4)

| Job | GPU | Tier | On-demand USD/30 ngày | Optimized USD/30 ngày |
| --- | --- | --- | --- | --- |
| job-train-llm | H100 | spot | 12,000 | 7,596 |
| job-train-embed | A100 | spot | 2,148 | 1,393 |
| job-finetune | H100 | spot | 900 | 570 |
| job-infer-chat | A10G | reserved | 4,320 | 2,592 |
| job-infer-rag | A100 | reserved | 3,866 | 2,160 |
| job-infer-search | L4 | reserved | 1,728 | 972 |
| job-dev-sandbox | A10G | spot | 480 | 203 |
| job-batch-eval | H100 | spot | 225 | 142 |

Spot được chọn cho job-train-llm, job-train-embed, job-finetune, job-dev-sandbox, job-batch-eval. Các job cho phép gián đoạn và chạy dưới 24h/ngày. Effective hours = GPU-hours × (1 + 0.03 + 0.05 × 0.5) = 1.055 × GPU-hours: thêm checkpoint và chạy lại sau thu hồi; rate 0.05/giờ là giả định starter, không phải số đo thực tế.

M3 quy đổi mọi job thành 30 ngày: $25,667 → $15,627, tiết kiệm 39.1%. Reserved phù hợp chat/rag chạy 24h và search chạy 18h nếu nhu cầu dài hạn ổn định. Nhưng CSV chỉ chứng minh 30 ngày: không đủ cơ sở cam kết 3 năm. On-demand phù hợp hơn nếu job kết thúc sau kỳ này và không tái sử dụng capacity. Starter tính reserved theo giờ sử dụng, chưa tính toàn bộ giờ cam kết; search 18h/ngày có thể bị đánh giá quá lạc quan. Break-even 55% của policy dùng discount 45%, không phải mọi GPU đều có discount đó.

### M4 — Allocation (Guide 7.4)

| Team | USD/ngày | % tiền inference |
| --- | --- | --- |
| assistant | 2.59 | 30.53% |
| search | 2.49 | 29.35% |
| eval | 1.79 | 21.10% |
| rag | 1.60 | 18.86% |

Team tốn nhiều nhất: assistant. Coverage chính xác 91.792% (2203/2400), vượt gate 80% → chargeback_ready=True. Còn request thiếu project cần bổ sung trước khi chargeback theo project. FOCUS giúp chuẩn hoá tên cột, tiền tệ, kỳ phí và tags để so sánh nhiều provider. focus_export.csv có 50 dòng mẫu với BilledCost/team/project; đây là FOCUS-style tối giản, không phải toàn bộ hóa đơn hay chứng nhận tuân thủ đầy đủ schema FOCUS. Tỷ trọng team có thể lệch nhẹ do làm tròn USD.

## Extension 4 — Ngân sách reasoning

| is_reasoning | Request (%) | Input token | Output token | Token (%) | Baseline USD | Optimized USD (%) | Wh (%) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2199 (91.625%) | 4,881,243 | 1,410,628 | 6,291,871 (83.524%) | 35.8031 | 7.0882 (83.541%) | 1887.561 (5.959%) |
| 1 | 201 (8.375%) | 462,194 | 778,962 | 1,241,156 (16.476%) | 13.0710 | 1.3965 (16.459%) | 29787.744 (94.041%) |

| Cap 10% traffic | Trước | Sau | Tiết kiệm |
| --- | --- | --- | --- |
| Reasoning request | 201 | 201 | 0 |
| USD/ngày | 8.4846 | 8.4846 | 0.0000 |
| Wh/ngày | 31675.305 | 31675.305 | 0.000 |

Traffic reasoning 8.375% đã dưới 10%, nên không đổi request, model hay output và savings bằng 0. Hệ số 80× là giả định trong sustainability.py trên cùng số token; dataset còn nhân output reasoning 6×, nên tỷ trọng năng lượng tổng khác 80× tỷ trọng request. Nếu tính cùng 1,241,156 token của nhóm reasoning, Wh không reasoning = 372.347, Wh reasoning = 29787.744; phần tăng = 29415.397 Wh. Đây là mô hình năng lượng, chưa phải đo điện thực.

Kiểm tra nhánh vượt cap bằng mẫu giả lập 10 request lấy nguyên dòng CSV: 3 reasoning + 7 thường (không đại diện traffic đầy đủ). Quota 10% giữ 1 reasoning, chuyển 2 request dư sang không reasoning:

| Mẫu 30% reasoning | Trước cap | Sau cap |
| --- | --- | --- |
| Reasoning request | 3 | 1 |
| USD | 0.063768 | 0.063768 |
| Wh | 621.729 | 226.958 |

Routing đề xuất: chỉ bật reasoning cho task nhiều bước hoặc confidence <0.70; confidence threshold là giả định cần hiệu chỉnh bằng eval chất lượng. Dành tối đa 10% quota cho request ưu tiên. CSV không có confidence/complexity nên mô phỏng vượt cap giữ request đầu tiên theo thứ tự CSV; request dư chỉ tắt energy multiplier, giữ model và số token/output. Vì giá theo token không có surcharge reasoning, kịch bản fixed-token này không tự tiết kiệm USD. Muốn giảm output/model phải đo chất lượng và tính lại token/cost, chưa giả định trong báo cáo.

## Extension 5 — Carbon-aware scheduling

Chỉ chọn interruptible=1. GPU-hours = hours_per_day × days × num_gpus; Wh = catalog watts × GPU-hours. Dùng ngày thực tế, không quy đổi 30 ngày như purchasing. Watts là proxy công suất catalog; chưa gồm PUE, checkpoint/rework, network transfer hoặc giá GPU theo vùng. Giữ cùng GPU, công việc và Wh khi so vùng.

| Job | Ngày | GPU-hours | Wh | us-east-1 gCO2e | europe-north1 gCO2e | Giảm gCO2e |
| --- | --- | --- | --- | --- | --- | --- |
| job-train-llm | 14 | 2,240 | 1,568,000 | 595,840.0 | 47,040.0 | 548,800.0 |
| job-train-embed | 5 | 200 | 80,000 | 30,400.0 | 2,400.0 | 28,000.0 |
| job-finetune | 3 | 36 | 25,200 | 9,576.0 | 756.0 | 8,820.0 |
| job-dev-sandbox | 22 | 352 | 52,800 | 20,064.0 | 1,584.0 | 18,480.0 |
| job-batch-eval | 30 | 90 | 63,000 | 23,940.0 | 1,890.0 | 22,050.0 |

| Vùng | USD/kWh | gCO2e/kWh | Tiền điện USD | gCO2e |
| --- | --- | --- | --- | --- |
| us-east-1 | 0.120 | 380 | 214.680 | 679,820.0 |
| us-west-2 | 0.070 | 120 | 125.230 | 214,680.0 |
| europe-north1 | 0.090 | 30 | 161.010 | 53,670.0 |
| europe-central2 | 0.180 | 660 | 322.020 | 1,180,740.0 |
| us-east-wa | 0.055 | 90 | 98.395 | 161,010.0 |

Tổng 1,789,000 Wh; carbon 679,820.0 → 53,670.0 gCO2e, giảm 626,150.0 gCO2e (92.11%). Sạch nhất: europe-north1; điện rẻ nhất: us-east-wa. Chính sách cân bằng: chọn điện rẻ nhất trong các vùng giảm carbon ≥75% so us-east-1 → us-east-wa. Nhãn cheapest+cleanest trong Guide/starter không đúng bảng REGION_PRICE_KWH. Các mã vùng được dùng đúng như dữ liệu mô phỏng, chưa xác minh availability của GPU ở provider thực. Job training/eval có thể chạy xa users nhưng cần xem data residency, truyền dữ liệu và deadline; job inference không interruptible được giữ nguyên để bảo toàn latency.

## Bài viết ngắn — khuyến nghị cho NimbusAI

Inference giảm từ $48.87 xuống $8.48/ngày, từ $6.488 xuống $1.126/1M-token (82.6%). Trong inference, cascade có tác động lớn nhất; trong tổng ngân sách, purchasing lớn nhất vì tiền GPU-hours vượt tiền request API. Hai extension bổ sung là đo quota reasoning và so carbon theo vùng. Cap hiện tại không giảm tiền/điện vì traffic đã dưới ngưỡng; carbon giảm khi chuyển cùng lượng công việc, nhưng đây là thay đổi vị trí, không phải giảm throughput.

Năng lượng/truy vấn ở đầu báo cáo là trung bình toàn traffic gồm reasoning: 13.198 Wh. Mẫu 800 token không reasoning trong starter vẫn là 0.24 Wh và 0.091 gCO2e ở us-east-1; mẫu này không phải median token đo được từ CSV.

1. Tắt capacity idle có lịch rõ ràng; profile gpu-h100-4 và gpu-a10g-1, benchmark trước right-sizing. Idle có lợi ngay, right-sizing cần kiểm chứng cả VRAM/BW và tokens/s.
2. Ưu tiên spot có checkpoint cho job gián đoạn; xác nhận nhu cầu dài hạn và toàn bộ giờ cam kết trước reserved. Đồng thời triển khai cascade theo eval chất lượng, cache theo khả năng tái sử dụng, batch cho nightly eval; theo dõi USD/1M-token và latency.
3. Duy trì gate tags, bổ sung project còn thiếu; theo dõi quota reasoning và Wh. Dùng vùng điện rẻ hoặc carbon thấp cho job linh hoạt theo mục tiêu công ty và ràng buộc dữ liệu.

## Tái lập và kiểm tra

Chạy từ thư mục lab bằng Python trong .venv: `python -X utf8 data/generate.py`, `python -X utf8 missions/run_all.py`, `python -X utf8 verify.py`, `python -m pytest -q`. report.md, savings.png và focus_export.csv được sinh lại ở đúng đường dẫn sẵn có. Bài viết ngắn riêng để nộp bài: [outputs/writeup.md](writeup.md). Không sửa tests/ hay bonus/.
