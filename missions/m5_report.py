"""M5 — Optimization Report: combine M1-M4 into baseline-vs-optimized (deck §1/§11).

Run: python missions/m5_report.py   ->  outputs/report.md + outputs/savings.png
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import os
from missions._common import num, catalog_by_type, load_csv, ROOT
from finops import report, sustainability
from missions import m1_efficiency_audit, m2_inference_levers, m3_purchasing, m4_allocation

DAYS = 30
# one tier down for over-provisioned ("util-lie") GPUs
RIGHTSIZE_MAP = {"H100": "A100", "H200": "H100", "A100": "A10G", "A10G": "L4", "L4": "L4"}


def table(headers: list[str], rows: list[list]) -> str:
    return "\n".join(["| " + " | ".join(headers) + " |",
                      "| " + " | ".join(["---"] * len(headers)) + " |"] +
                     ["| " + " | ".join(map(str, row)) + " |" for row in rows])


def analysis(r1: dict, r2: dict, r3: dict, r4: dict, baseline: float, levers: dict) -> str:
    """Reproducible write-up, analysis questions and both extension measurements."""
    cat = catalog_by_type()
    tokens = load_csv("token_usage.csv")
    tel = load_csv("gpu_telemetry.csv")
    jobs = load_csv("workloads.csv")
    groups = r2["reasoning"]["groups"]
    budget = r2["reasoning"]
    carbon = r3["carbon"]
    top_team = max(r4["by_team"], key=r4["by_team"].get)
    # Re-price for shares rather than adding rounded team totals.
    allocation_total = r2["stages"][-1]["usd"]
    fleet_daily = sum(num(cat[r["gpu_type"]]["on_demand_hr"]) for r in tel)
    missing = sum(not r["team"].strip() or not r["project"].strip() for r in tokens)
    highest = max(r1["summary"], key=lambda r: r["gpu_util_pct"])
    # A small, explicitly labelled counterfactual using unchanged real CSV rows.
    above_cap_rows = ([r for r in tokens if int(num(r["is_reasoning"]))][:3] +
                      [r for r in tokens if not int(num(r["is_reasoning"]))][:7])
    above_cap = m2_inference_levers.reasoning_budget(above_cap_rows)
    sections = [
        "## Phạm vi, dữ liệu và baseline trước khi sửa",
        "",
        "Học viên: Trịnh Hoàng Tùng — 2A202602937. Hoàn thành ngày 13/10/2026. "
        "Đã đọc CODELAB.md, Guide.md, README_en.md, README.md, Rubric.md và source finops/missions. "
        "Đây là mô phỏng với giá và hệ số tháng 6/2026, seed=25; không phải giá cloud hiện tại.",
        "",
        table(["CSV", "Số dòng", "Nhận xét"], [
            ["price_catalog.csv", len(cat), "7 GPU; giá tier, HBM, FLOPs, bandwidth, watts"],
            ["gpu_telemetry.csv", len(tel), "11 GPU × 24 giờ; mỗi dòng là 1 GPU-hour"],
            ["token_usage.csv", len(tokens), f"{r2['total_tokens']:,} token; {missing} request thiếu project"],
            ["workloads.csv", len(jobs), "8 job; days khác nhau, num_gpus và interruptible quyết định quy mô"]]),
        "",
        "Đã sinh dữ liệu, đọc cả 4 CSV bằng pandas và lưu kết quả M2/M3 trong report.md trước khi sửa. "
        "Các extension giữ nguyên phép tính tiền M2/M3; bảng này tái lập baseline đã lưu và đối chiếu sau sửa:",
        "",
        table(["Chỉ số", "Trước extension", "Sau extension"], [
            ["M2 USD/ngày", f"{r2['optimized_daily']:.2f}", f"{r2['optimized_daily']:.2f}"],
            ["M2 USD/1M-token", f"{r2['optimized_per_m']:.3f}", f"{r2['optimized_per_m']:.3f}"],
            ["M2 savings", f"{r2['savings_pct']:.1f}%", f"{r2['savings_pct']:.1f}%"],
            ["M3 optimized USD/30 ngày", f"{r3['optimized_monthly']:,}", f"{r3['optimized_monthly']:,}"],
            ["M3 savings", f"{r3['savings_pct']:.1f}%", f"{r3['savings_pct']:.1f}%"]]),
        "",
        "M5 giữ cách tổng hợp của starter: baseline = 30 × M2 baseline/ngày + M3 on-demand/30 ngày; "
        "optimized = baseline − tổng bốn lever (làm tròn USD). M1 right-sizing/idle là tiềm năng bổ sung "
        "giả định áp dụng trong cùng portfolio M3. CSV không ánh xạ gpu_id → job_id, nên chưa chứng minh "
        "các khoản đó độc lập với purchasing; mức tổng ở đầu báo cáo là kịch bản, không phải tiết kiệm đã xác nhận. "
        "Không cộng chi phí điện của extension vào tiền thuê GPU hoặc savings để tránh tính trùng. "
        "Token chỉ có cho inference; không chia tổng chi phí training+inference cho token M2.",
        "",
        f"Chỉ tính hai lever có baseline tương ứng (M2+M3), savings = "
        f"${levers['Inference (cascade/cache/batch)'] + levers['Purchasing (spot/reserved)']:,.0f} "
        f"({(levers['Inference (cascade/cache/batch)'] + levers['Purchasing (spot/reserved)']) / baseline:.2%}); "
        "các đề xuất M1 cần kiểm chứng riêng trước khi chốt ngân sách.",
        "",
        "## Kết quả M1–M4 và trả lời Guide",
        "",
        "### M1 — GPU-Util và idle (Guide 4.3)",
        "",
        table(["GPU", "Loại", "Util %", "MFU", "MBU", "Idle giờ/ngày"], [
            [r['gpu_id'], r['gpu_type'], r['gpu_util_pct'], r['mfu'], r['mbu'], r['idle_hours']]
            for r in r1["summary"]]),
        "",
        f"GPU có util cao nhất là {highest['gpu_id']}: {highest['gpu_util_pct']}%, "
        f"MFU {highest['mfu']:.3f}. Flag gồm " + ", ".join(r["gpu_id"] for r in r1["lies"]) + ". "
        "GPU-Util đo thời gian có kernel hoạt động, không đo số FLOPs hữu ích: kernel có thể chờ bộ nhớ, "
        "chạy phép toán ít dùng tensor core hoặc có batch nhỏ. Telemetry này chứng minh lệch util/MFU, "
        "nhưng chưa đủ profiler để xác định nguyên nhân. Với decode, MFU thấp có thể bình thường do memory-bound; "
        "cần MBU, VRAM và throughput, không tự kết luận GPU lỗi.",
        "",
        f"gpu-h100-5 idle 8 giờ/ngày: 8 × $2.50 = ${r1['idle_waste_daily']:.2f}/ngày, "
        f"${r1['idle_waste_daily'] * DAYS:,.0f}/30 ngày. Tổng fleet M1 on-demand "
        f"${fleet_daily:.2f}/ngày; idle chiếm {r1['idle_waste_daily'] / fleet_daily:.2%} "
        f"chi phí fleet và {levers['Kill idle GPUs'] / baseline:.2%} baseline kịch bản M5.",
        "",
        table(["Đề xuất starter", "Savings USD/30 ngày", "Giới hạn"], [
            [f"{r['gpu_id']}: {r['gpu_type']} → {RIGHTSIZE_MAP.get(r['gpu_type'], r['gpu_type'])}",
             f"{max(0, num(cat[r['gpu_type']]['on_demand_hr']) - num(cat[RIGHTSIZE_MAP.get(r['gpu_type'], r['gpu_type'])]['on_demand_hr'])) * 24 * DAYS:.2f}",
             "Chưa benchmark throughput/VRAM/BW; chỉ là tiềm năng"] for r in r1["lies"]]),
        "",
        "### M2 — Inference (Guide 5.4)",
        "",
        table(["Bước", "USD/ngày", "USD/1M-token", "Savings thêm USD/ngày"], [
            [s["stage"], f"{s['usd']:.4f}", f"{s['per_m']:.3f}", f"{s['saved']:.4f}"]
            for s in r2["stages"]]),
        "",
        "Cascade đóng góp lớn nhất vì phần lớn request dùng model nhỏ. Các khoản thêm được tính theo "
        "thứ tự cascade → cache → batch, cùng số token, nên không đếm trùng. 0.50 × 0.10 = 0.05 "
        "chỉ đúng với phần input cache 100%; output vẫn trả giá output trước batch. Không batch hội thoại "
        "cần phản hồi ngay hoặc request có deadline thấp. Cache ở starter chưa tính write/storage cost "
        "vì CSV không có prefix/read-count; đây không phải extension cache economics.",
        "",
        "### M3 — Purchasing (Guide 6.4)",
        "",
        table(["Job", "GPU", "Tier", "On-demand USD/30 ngày", "Optimized USD/30 ngày"], [
            [r["job_id"], r["gpu_type"], r["tier"], f"{r['on_demand']:,}", f"{r['optimized']:,}"]
            for r in r3["recommendations"]]),
        "",
        "Spot được chọn cho " + ", ".join(r["job_id"] for r in r3["recommendations"] if r["tier"] == "spot") + ". "
        "Các job cho phép gián đoạn và chạy dưới 24h/ngày. Effective hours = GPU-hours × "
        "(1 + 0.03 + 0.05 × 0.5) = 1.055 × GPU-hours: thêm checkpoint và chạy lại sau thu hồi; "
        "rate 0.05/giờ là giả định starter, không phải số đo thực tế.",
        "",
        f"M3 quy đổi mọi job thành 30 ngày: ${r3['on_demand_monthly']:,} → "
        f"${r3['optimized_monthly']:,}, tiết kiệm {r3['savings_pct']:.1f}%. "
        "Reserved phù hợp chat/rag chạy 24h và search chạy 18h nếu nhu cầu dài hạn ổn định. "
        "Nhưng CSV chỉ chứng minh 30 ngày: không đủ cơ sở cam kết 3 năm. On-demand phù hợp hơn nếu "
        "job kết thúc sau kỳ này và không tái sử dụng capacity. Starter tính reserved theo giờ sử dụng, "
        "chưa tính toàn bộ giờ cam kết; search 18h/ngày có thể bị đánh giá quá lạc quan. "
        "Break-even 55% của policy dùng discount 45%, không phải mọi GPU đều có discount đó.",
        "",
        "### M4 — Allocation (Guide 7.4)",
        "",
        table(["Team", "USD/ngày", "% tiền inference"], [
            [name, f"{cost:.2f}", f"{cost / allocation_total:.2%}"]
            for name, cost in sorted(r4["by_team"].items(), key=lambda item: -item[1])]),
        "",
        f"Team tốn nhiều nhất: {top_team}. Coverage chính xác {(len(tokens)-missing)/len(tokens):.3%} "
        f"({len(tokens)-missing}/{len(tokens)}), vượt gate 80% → chargeback_ready={r4['chargeback_ready']}. "
        "Còn request thiếu project cần bổ sung trước khi chargeback theo project. "
        "FOCUS giúp chuẩn hoá tên cột, tiền tệ, kỳ phí và tags để so sánh nhiều provider. "
        "focus_export.csv có 50 dòng mẫu với BilledCost/team/project; đây là FOCUS-style tối giản, "
        "không phải toàn bộ hóa đơn hay chứng nhận tuân thủ đầy đủ schema FOCUS. "
        "Tỷ trọng team có thể lệch nhẹ do làm tròn USD.",
        "",
        "## Extension 4 — Ngân sách reasoning",
        "",
        table(["is_reasoning", "Request (%)", "Input token", "Output token", "Token (%)", "Baseline USD", "Optimized USD (%)", "Wh (%)"], [
            [flag, f"{g['requests']} ({g['requests_share']:.3%})", f"{g['input_tokens']:,}",
             f"{g['output_tokens']:,}", f"{g['tokens']:,} ({g['tokens_share']:.3%})",
             f"{g['baseline_usd']:.4f}", f"{g['usd']:.4f} ({g['usd_share']:.3%})",
             f"{g['wh']:.3f} ({g['wh_share']:.3%})"] for flag, g in groups.items()]),
        "",
        table(["Cap 10% traffic", "Trước", "Sau", "Tiết kiệm"], [
            ["Reasoning request", groups[1]["requests"], budget["reasoning_requests_after"], budget["rerouted_requests"]],
            ["USD/ngày", f"{budget['usd_before']:.4f}", f"{budget['usd_after']:.4f}", f"{budget['usd_saved']:.4f}"],
            ["Wh/ngày", f"{budget['wh_before']:.3f}", f"{budget['wh_after']:.3f}", f"{budget['wh_saved']:.3f}"]]),
        "",
        f"Traffic reasoning {groups[1]['requests_share']:.3%} đã dưới 10%, nên không đổi request, model hay output "
        "và savings bằng 0. Hệ số 80× là giả định trong sustainability.py trên cùng số token; "
        "dataset còn nhân output reasoning 6×, nên tỷ trọng năng lượng tổng khác 80× tỷ trọng request. "
        f"Nếu tính cùng {groups[1]['tokens']:,} token của nhóm reasoning, "
        f"Wh không reasoning = {groups[1]['wh']/sustainability.REASONING_ENERGY_MULTIPLIER:.3f}, "
        f"Wh reasoning = {groups[1]['wh']:.3f}; phần tăng = {budget['reasoning_extra_wh_same_tokens']:.3f} Wh. "
        "Đây là mô hình năng lượng, chưa phải đo điện thực.",
        "",
        "Kiểm tra nhánh vượt cap bằng mẫu giả lập 10 request lấy nguyên dòng CSV: 3 reasoning + 7 thường "
        "(không đại diện traffic đầy đủ). Quota 10% giữ 1 reasoning, chuyển 2 request dư sang không reasoning:",
        "",
        table(["Mẫu 30% reasoning", "Trước cap", "Sau cap"], [
            ["Reasoning request", 3, above_cap["reasoning_requests_after"]],
            ["USD", f"{above_cap['usd_before']:.6f}", f"{above_cap['usd_after']:.6f}"],
            ["Wh", f"{above_cap['wh_before']:.3f}", f"{above_cap['wh_after']:.3f}"]]),
        "",
        "Routing đề xuất: chỉ bật reasoning cho task nhiều bước hoặc confidence <0.70; "
        "confidence threshold là giả định cần hiệu chỉnh bằng eval chất lượng. Dành tối đa 10% quota "
        "cho request ưu tiên. CSV không có confidence/complexity nên mô phỏng vượt cap giữ request "
        "đầu tiên theo thứ tự CSV; request dư chỉ tắt energy multiplier, giữ model và số token/output. "
        "Vì giá theo token không có surcharge reasoning, kịch bản fixed-token này không tự tiết kiệm USD. "
        "Muốn giảm output/model phải đo chất lượng và tính lại token/cost, chưa giả định trong báo cáo.",
        "",
        "## Extension 5 — Carbon-aware scheduling",
        "",
        "Chỉ chọn interruptible=1. GPU-hours = hours_per_day × days × num_gpus; "
        "Wh = catalog watts × GPU-hours. Dùng ngày thực tế, không quy đổi 30 ngày như purchasing. "
        "Watts là proxy công suất catalog; chưa gồm PUE, checkpoint/rework, network transfer hoặc giá GPU theo vùng. "
        "Giữ cùng GPU, công việc và Wh khi so vùng.",
        "",
        table(["Job", "Ngày", "GPU-hours", "Wh", "us-east-1 gCO2e", "europe-north1 gCO2e", "Giảm gCO2e"], [
            [j["job_id"], f"{j['days']:.0f}", f"{j['gpu_hours']:,.0f}", f"{j['wh']:,.0f}",
             f"{j['carbon_before_g']:,.1f}", f"{j['carbon_after_g']:,.1f}",
             f"{j['carbon_before_g']-j['carbon_after_g']:,.1f}"] for j in carbon["jobs"]]),
        "",
        table(["Vùng", "USD/kWh", "gCO2e/kWh", "Tiền điện USD", "gCO2e"], [
            [r["region"], f"{r['usd_per_kwh']:.3f}", r["g_per_kwh"],
             f"{r['electricity_usd']:.3f}", f"{r['carbon_g']:,.1f}"] for r in carbon["regions"]]),
        "",
        f"Tổng {carbon['total_wh']:,.0f} Wh; carbon {carbon['carbon_before_g']:,.1f} → "
        f"{carbon['carbon_after_g']:,.1f} gCO2e, giảm {carbon['carbon_saved_g']:,.1f} gCO2e "
        f"({carbon['carbon_saved_g']/carbon['carbon_before_g']:.2%}). "
        f"Sạch nhất: {carbon['cleanest_region']}; điện rẻ nhất: {carbon['cheapest_region']}. "
        f"Chính sách cân bằng: chọn điện rẻ nhất trong các vùng giảm carbon ≥75% so us-east-1 → "
        f"{carbon['balanced_region']}. Nhãn cheapest+cleanest trong Guide/starter không đúng bảng REGION_PRICE_KWH. "
        "Các mã vùng được dùng đúng như dữ liệu mô phỏng, chưa xác minh availability của GPU ở provider thực. "
        "Job training/eval có thể chạy xa users nhưng cần xem data residency, truyền dữ liệu và deadline; "
        "job inference không interruptible được giữ nguyên để bảo toàn latency.",
        "",
        "## Bài viết ngắn — khuyến nghị cho NimbusAI",
        "",
        f"Inference giảm từ ${r2['baseline_daily']:.2f} xuống ${r2['optimized_daily']:.2f}/ngày, "
        f"từ ${r2['baseline_per_m']:.3f} xuống ${r2['optimized_per_m']:.3f}/1M-token "
        f"({r2['savings_pct']:.1f}%). Trong inference, cascade có tác động lớn nhất; trong tổng ngân sách, "
        "purchasing lớn nhất vì tiền GPU-hours vượt tiền request API. Hai extension bổ sung là đo quota "
        "reasoning và so carbon theo vùng. Cap hiện tại không giảm tiền/điện vì traffic đã dưới ngưỡng; "
        "carbon giảm khi chuyển cùng lượng công việc, nhưng đây là thay đổi vị trí, không phải giảm throughput.",
        "",
        f"Năng lượng/truy vấn ở đầu báo cáo là trung bình toàn traffic gồm reasoning: "
        f"{budget['wh_before'] / len(tokens):.3f} Wh. Mẫu 800 token không reasoning trong starter vẫn "
        f"là {sustainability.wh_per_query(800):.2f} Wh và "
        f"{sustainability.carbon_g(sustainability.wh_per_query(800)):.3f} gCO2e ở us-east-1; "
        "mẫu này không phải median token đo được từ CSV.",
        "",
        "1. Tắt capacity idle có lịch rõ ràng; profile gpu-h100-4 và gpu-a10g-1, benchmark trước right-sizing. "
        "Idle có lợi ngay, right-sizing cần kiểm chứng cả VRAM/BW và tokens/s.",
        "2. Ưu tiên spot có checkpoint cho job gián đoạn; xác nhận nhu cầu dài hạn và toàn bộ giờ cam kết "
        "trước reserved. Đồng thời triển khai cascade theo eval chất lượng, cache theo khả năng tái sử dụng, "
        "batch cho nightly eval; theo dõi USD/1M-token và latency.",
        "3. Duy trì gate tags, bổ sung project còn thiếu; theo dõi quota reasoning và Wh. Dùng vùng "
        "điện rẻ hoặc carbon thấp cho job linh hoạt theo mục tiêu công ty và ràng buộc dữ liệu.",
        "",
        "## Tái lập và kiểm tra",
        "",
        "Chạy từ thư mục lab bằng Python trong .venv: `python -X utf8 data/generate.py`, "
        "`python -X utf8 missions/run_all.py`, `python -X utf8 verify.py`, `python -m pytest -q`. "
        "report.md, savings.png và focus_export.csv được sinh lại ở đúng đường dẫn sẵn có. "
        "Bài viết ngắn riêng để nộp bài: [outputs/writeup.md](writeup.md). Không sửa tests/ hay bonus/.",
    ]
    return "\n".join(sections)


def run(verbose: bool = True) -> dict:
    r1 = m1_efficiency_audit.run(verbose=False)
    r2 = m2_inference_levers.run(verbose=False)
    r3 = m3_purchasing.run(verbose=False)
    r4 = m4_allocation.run(verbose=False)
    cat = catalog_by_type()

    # --- buckets ---
    infer_savings = (r2["baseline_daily"] - r2["optimized_daily"]) * DAYS
    purchasing_savings = r3["on_demand_monthly"] - r3["optimized_monthly"]

    idle_savings = r1["idle_waste_daily"] * DAYS
    rightsize_savings = 0.0
    for lie in r1["lies"]:
        cur = lie["gpu_type"]
        tgt = RIGHTSIZE_MAP.get(cur, cur)
        delta = num(cat[cur]["on_demand_hr"]) - num(cat[tgt]["on_demand_hr"])
        rightsize_savings += max(0.0, delta) * 24 * DAYS

    levers = {
        "Inference (cascade/cache/batch)": round(infer_savings),
        "Purchasing (spot/reserved)": round(purchasing_savings),
        "Right-size util-lies": round(rightsize_savings),
        "Kill idle GPUs": round(idle_savings),
    }
    baseline = r2["baseline_daily"] * DAYS + r3["on_demand_monthly"]
    optimized = baseline - sum(levers.values())
    total_pct = sum(levers.values()) / baseline * 100 if baseline else 0.0

    # --- sustainability snapshot ---
    reasoning_groups = r2["reasoning"]["groups"]
    requests = sum(g["requests"] for g in reasoning_groups.values())
    wh = r2["reasoning"]["wh_before"] / requests if requests else 0.0
    sust = {
        "wh_per_query": wh,
        "carbon_g": sustainability.carbon_g(wh, "us-east-1"),
        "best_region": min(sustainability.REGION_CARBON, key=sustainability.REGION_CARBON.get),
        "cheapest_region": min(sustainability.REGION_PRICE_KWH, key=sustainability.REGION_PRICE_KWH.get),
    }

    md = report.build_report(baseline, optimized, levers, sustainability=sust)
    md += "\n\n" + analysis(r1, r2, r3, r4, baseline, levers) + "\n"
    out_md = os.path.join(ROOT, "outputs", "report.md")
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(md)
    png = report.savings_waterfall(levers, os.path.join(ROOT, "outputs", "savings.png"), baseline)

    if verbose:
        if hasattr(_sys.stdout, "reconfigure"):
            _sys.stdout.reconfigure(encoding="utf-8")
        print("== M5 Optimization Report ==")
        print(md)
        print(f"\nWritten: outputs/report.md" + (f" + outputs/savings.png" if png else " (matplotlib absent: PNG skipped)"))

    return {"baseline_monthly": round(baseline), "optimized_monthly": round(optimized),
            "levers": levers, "total_savings_pct": round(total_pct, 1)}


if __name__ == "__main__":
    run()
