"""M3 — Purchasing Strategy: break-even, tier choice, spot-checkpoint sim (deck §4).

Run: python missions/m3_purchasing.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num, catalog_by_type
from finops import pricing, sustainability

DAYS = 30


def carbon_schedule(jobs: list[dict], cat: dict) -> dict:
    """Compare identical GPU-hours in each region, using actual job days.

    Catalog watts is an illustrative power proxy, excluding PUE, transfer and
    checkpoint overhead. Region changes do not change workload or GPU price.
    """
    baseline_region = "us-east-1"
    cleanest = min(sustainability.REGION_CARBON, key=sustainability.REGION_CARBON.get)
    cheapest = min(sustainability.REGION_PRICE_KWH, key=sustainability.REGION_PRICE_KWH.get)
    # Explicit policy: cheapest region that cuts grid carbon by at least 75%.
    eligible = [region for region, carbon in sustainability.REGION_CARBON.items()
                if carbon <= sustainability.REGION_CARBON[baseline_region] * 0.25]
    balanced = min(eligible, key=sustainability.REGION_PRICE_KWH.get)
    comparisons = []
    for j in jobs:
        if not int(num(j["interruptible"])):
            continue
        hours = num(j["hours_per_day"]) * num(j["days"]) * num(j["num_gpus"])
        wh = num(cat[j["gpu_type"]]["watts"]) * hours
        comparisons.append({"job_id": j["job_id"], "days": num(j["days"]),
                            "gpu_hours": hours, "wh": wh,
                            "carbon_before_g": sustainability.carbon_g(wh, baseline_region),
                            "carbon_after_g": sustainability.carbon_g(wh, cleanest)})
    total_wh = sum(j["wh"] for j in comparisons)
    regions = [{"region": region, "usd_per_kwh": sustainability.REGION_PRICE_KWH[region],
                "g_per_kwh": carbon, "electricity_usd": sustainability.energy_cost_usd(total_wh, region),
                "carbon_g": sustainability.carbon_g(total_wh, region)}
               for region, carbon in sustainability.REGION_CARBON.items()]
    before = sustainability.carbon_g(total_wh, baseline_region)
    after = sustainability.carbon_g(total_wh, cleanest)
    return {"jobs": comparisons, "regions": regions, "total_wh": total_wh,
            "baseline_region": baseline_region, "cleanest_region": cleanest,
            "cheapest_region": cheapest, "balanced_region": balanced,
            "carbon_before_g": before, "carbon_after_g": after,
            "carbon_saved_g": before - after}


def run(verbose: bool = True) -> dict:
    jobs = load_csv("workloads.csv")
    cat = catalog_by_type()
    on_demand_monthly = optimized_monthly = 0.0
    recs = []
    for j in jobs:
        gtype = j["gpu_type"]
        ngpu = int(num(j["num_gpus"]))
        hpd = num(j["hours_per_day"])
        interruptible = bool(int(num(j["interruptible"])))
        c = cat[gtype]
        gpu_hours = hpd * DAYS * ngpu
        od = num(c["on_demand_hr"])
        on_demand_cost = gpu_hours * od

        tier = pricing.recommend_tier(hpd, interruptible)
        if tier == "spot":
            sim = pricing.spot_checkpoint_cost(gpu_hours, num(c["spot_hr"]), od)
            opt_cost = sim["spot_cost"]
        elif tier == "reserved":
            opt_cost = gpu_hours * num(c["reserved_3yr_hr"])
        else:
            opt_cost = on_demand_cost

        on_demand_monthly += on_demand_cost
        optimized_monthly += opt_cost
        recs.append({"job_id": j["job_id"], "gpu_type": gtype, "tier": tier,
                     "on_demand": round(on_demand_cost), "optimized": round(opt_cost)})

    savings = on_demand_monthly - optimized_monthly
    savings_pct = savings / on_demand_monthly * 100 if on_demand_monthly else 0.0
    carbon = carbon_schedule(jobs, cat)

    if verbose:
        print("== M3 Purchasing Strategy ==")
        print(f"break-even utilization @ 45% reserved discount = {pricing.break_even_utilization(0.45):.0%}")
        print(f"{'job':18}{'gpu':7}{'tier':11}{'on-demand':>12}{'optimized':>12}")
        for r in recs:
            print(f"{r['job_id']:18}{r['gpu_type']:7}{r['tier']:11}${r['on_demand']:>11,}${r['optimized']:>11,}")
        print(f"\nmonthly: on-demand ${on_demand_monthly:,.0f} -> optimized ${optimized_monthly:,.0f}  ({savings_pct:.1f}% saved)")
        print("Carbon-aware scheduling (actual job days, catalog watts):")
        for j in carbon["jobs"]:
            print(f"  {j['job_id']:18} {j['gpu_hours']:8.0f} GPU-h  {j['wh']:10.0f} Wh  "
                  f"{j['carbon_before_g']:.1f} -> {j['carbon_after_g']:.1f} gCO2e")
        for r in carbon["regions"]:
            print(f"  {r['region']:16} ${r['usd_per_kwh']:.3f}/kWh  {r['g_per_kwh']} g/kWh  "
                  f"electricity=${r['electricity_usd']:.3f}  carbon={r['carbon_g']:.1f} gCO2e")
        print(f"  Cleanest={carbon['cleanest_region']}; cheapest={carbon['cheapest_region']}; "
              f"balanced (>=75% less carbon)={carbon['balanced_region']}; "
              f"saved={carbon['carbon_saved_g']:.1f} gCO2e")

    return {"recommendations": recs, "on_demand_monthly": round(on_demand_monthly),
            "optimized_monthly": round(optimized_monthly), "savings_pct": round(savings_pct, 1),
            "carbon": carbon}


if __name__ == "__main__":
    run()
