"""M2 — Inference Cost Levers: $/1M-token, batch x cache x cascade (deck §7).

Run: python missions/m2_inference_levers.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num
from finops import pricing, sustainability

# $/1M tokens (input, output) — illustrative 2026.
MODEL_PRICES = {"small": (0.20, 0.40), "large": (3.00, 15.00)}


def reasoning_budget(rows: list[dict], cap_fraction: float = 0.10) -> dict:
    """Measure a fixed-token counterfactual; pricing has no reasoning surcharge.

    Excess reasoning requests keep their model/output/cache/batch; only their
    energy multiplier changes. This is a planning assumption, not a quality test.
    CSV order breaks ties because no complexity/confidence scores are available.
    """
    if not 0 <= cap_fraction <= 1:
        raise ValueError("cap_fraction must be between 0 and 1")
    groups = {flag: {"requests": 0, "input_tokens": 0, "output_tokens": 0,
                     "tokens": 0, "baseline_usd": 0.0, "usd": 0.0, "wh": 0.0}
              for flag in (0, 1)}
    limit = int(len(rows) * cap_fraction)
    retained = rerouted = 0
    after_wh = 0.0
    for r in rows:
        flag = int(num(r["is_reasoning"]))
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        pin, pout = MODEL_PRICES[r["route_tier"]]
        cost = pricing.request_cost(inp, out, pin, pout,
                                    cached_in=int(num(r["cached_input_tokens"])),
                                    batch=bool(int(num(r["is_batch"]))))
        wh = sustainability.wh_per_query(inp + out, is_reasoning=bool(flag))
        g = groups[flag]
        g["requests"] += 1
        g["input_tokens"] += inp
        g["output_tokens"] += out
        g["tokens"] += inp + out
        g["baseline_usd"] += pricing.request_cost(inp, out, *MODEL_PRICES["large"])
        g["usd"] += cost
        g["wh"] += wh
        use_reasoning = bool(flag) and retained < limit
        if use_reasoning:
            retained += 1
        elif flag:
            rerouted += 1
        after_wh += sustainability.wh_per_query(inp + out, is_reasoning=use_reasoning)
    total_cost = sum(g["usd"] for g in groups.values())
    total_wh = sum(g["wh"] for g in groups.values())
    if not rerouted:
        after_wh = total_wh  # Exactly zero savings when the cap changes nothing.
    total_tokens = sum(g["tokens"] for g in groups.values())
    for g in groups.values():
        for key, denominator in (("requests", len(rows)), ("tokens", total_tokens),
                                 ("usd", total_cost), ("wh", total_wh)):
            g[key + "_share"] = g[key] / denominator if denominator else 0.0
    return {"groups": groups, "cap_fraction": cap_fraction, "cap_requests": limit,
            "rerouted_requests": rerouted, "reasoning_requests_after": retained,
            "usd_before": total_cost, "usd_after": total_cost,
            "wh_before": total_wh, "wh_after": after_wh,
            "usd_saved": 0.0, "wh_saved": max(0.0, total_wh - after_wh),
            "reasoning_extra_wh_same_tokens": groups[1]["wh"] * (1 - 1 / sustainability.REASONING_ENERGY_MULTIPLIER)}


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    base_cost = opt_cost = cascade_cost = cache_cost = 0.0
    total_tokens = 0
    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        cached = int(num(r["cached_input_tokens"]))
        is_batch = bool(int(num(r["is_batch"])))
        total_tokens += inp + out
        # BASELINE: naive deployment — everything on the large model, no cache, no batch
        lin, lout = MODEL_PRICES["large"]
        base_cost += pricing.request_cost(inp, out, lin, lout)
        # OPTIMIZED: cascade (route_tier), prompt caching, batch API
        pin, pout = MODEL_PRICES[r["route_tier"]]
        cascade_cost += pricing.request_cost(inp, out, pin, pout)
        cache_cost += pricing.request_cost(inp, out, pin, pout, cached_in=cached)
        opt_cost += pricing.request_cost(inp, out, pin, pout, cached_in=cached, batch=is_batch)

    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0
    stages = [
        {"stage": "Baseline", "usd": base_cost, "saved": 0.0},
        {"stage": "Cascade", "usd": cascade_cost, "saved": base_cost - cascade_cost},
        {"stage": "+ Cache", "usd": cache_cost, "saved": cascade_cost - cache_cost},
        {"stage": "+ Batch", "usd": opt_cost, "saved": cache_cost - opt_cost},
    ]
    for stage in stages:
        stage["per_m"] = pricing.dollars_per_million(stage["usd"], total_tokens)
    reasoning = reasoning_budget(rows)

    if verbose:
        print("== M2 Inference Cost Levers ==")
        print(f"requests={len(rows)}  tokens={total_tokens:,}")
        print(f"baseline  : ${base_cost:,.2f}/day   ${base_pm:.3f}/1M-token")
        print(f"optimized : ${opt_cost:,.2f}/day   ${opt_pm:.3f}/1M-token")
        print(f"savings   : {savings_pct:.1f}%  (cascade + caching + batch)")
        print(f"discount stack (batch + 100% cache): {pricing.discount_stack(batch=True, cache_hit_frac=1.0):.3f} of naive")
        print("Sequential levers ($/day; marginal savings):")
        for stage in stages:
            print(f"  {stage['stage']:10} ${stage['usd']:.4f}  ${stage['per_m']:.3f}/1M-token  saved=${stage['saved']:.4f}")
        print("Reasoning budget (same tokens/model/output):")
        for flag, g in reasoning["groups"].items():
            print(f"  is_reasoning={flag}: {g['requests']} requests ({g['requests_share']:.3%}), "
                  f"{g['tokens']:,} tokens, ${g['usd']:.4f} ({g['usd_share']:.3%} cost), "
                  f"{g['wh']:.3f} Wh ({g['wh_share']:.3%} energy)")
        print(f"  Cap 10%: rerouted={reasoning['rerouted_requests']}; "
              f"USD {reasoning['usd_before']:.4f} -> {reasoning['usd_after']:.4f}; "
              f"Wh {reasoning['wh_before']:.3f} -> {reasoning['wh_after']:.3f}")

    return {
        "baseline_daily": round(base_cost, 2), "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3), "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1), "total_tokens": total_tokens,
        "stages": stages, "reasoning": reasoning,
    }


if __name__ == "__main__":
    run()
