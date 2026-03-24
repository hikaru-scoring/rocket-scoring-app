"""
Daily score recorder for ROCKET-1000 — runs via GitHub Actions.
Fetches current scores for all rockets and appends to scores_history.json.
"""
import json
import os
import math
import requests
from datetime import datetime, timezone

HISTORY_FILE = "scores_history.json"
CACHE_FILE = "launcher_cache.json"
API_BASE = "https://ll.thespacedevs.com/2.2.0/config/launcher/"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


def _to_num(val):
    try:
        return float(val) if val else 0
    except (ValueError, TypeError):
        return 0


def fetch_launchers():
    """Fetch from cache first, then API."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)

    all_results = []
    offset = 0
    limit = 100
    try:
        while True:
            resp = requests.get(API_BASE, params={"limit": limit, "offset": offset}, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            all_results.extend(data.get("results", []))
            if not data.get("next"):
                break
            offset += limit
    except Exception as e:
        print(f"API error: {e}")
    return all_results


def score_launcher(launcher):
    """Score a single launcher. Returns (name, total_score) or None."""
    total_launches = int(_to_num(launcher.get("total_launch_count")))
    if total_launches < 1:
        return None

    name = launcher.get("full_name") or launcher.get("name") or "Unknown"
    successful = int(_to_num(launcher.get("successful_launches")))
    consecutive = int(_to_num(launcher.get("consecutive_successful_launches")))
    leo = _to_num(launcher.get("leo_capacity"))
    gto = _to_num(launcher.get("gto_capacity"))
    launch_cost = _to_num(launcher.get("launch_cost"))
    reusable = bool(launcher.get("reusable"))
    successful_landings = int(_to_num(launcher.get("successful_landings")))
    attempted_landings = int(_to_num(launcher.get("attempted_landings")))
    thrust = _to_num(launcher.get("to_thrust"))

    # Axis 1: Track Record
    success_rate = successful / total_launches
    confidence = min(total_launches / 10, 1.0)
    ax1 = _clamp(success_rate * 200 * confidence, 0, 200)

    # Axis 2: Reliability Streak
    ax2 = _clamp(consecutive * 2, 0, 200)

    # Axis 3: Payload Capacity (75% payload + 25% thrust)
    effective_leo = leo if leo else (gto * 2 if gto else 0)
    payload_score = 0
    if effective_leo > 0:
        payload_score = _clamp((math.log2(effective_leo) / 15) * 200, 0, 200)
    thrust_score = 0
    if thrust > 0:
        thrust_score = _clamp((math.log2(thrust) / 17) * 200, 0, 200)
    if effective_leo > 0 and thrust > 0:
        ax3 = payload_score * 0.75 + thrust_score * 0.25
    elif effective_leo > 0:
        ax3 = payload_score
    elif thrust > 0:
        ax3 = thrust_score
    else:
        ax3 = 0

    # Axis 4: Cost Efficiency
    if launch_cost and effective_leo and effective_leo > 0:
        cost_per_kg = launch_cost / effective_leo
        if cost_per_kg > 0:
            ax4 = _clamp((5.5 - math.log10(cost_per_kg)) * 75, 0, 200)
        else:
            ax4 = 200
    else:
        ax4 = 100

    # Axis 5: Reusability & Innovation
    base = 100 if reusable else 50
    landing_denom = max(attempted_landings, 1)
    landing_bonus = (successful_landings / landing_denom) * 100
    ax5 = _clamp(base + landing_bonus, 0, 200)

    total = round(ax1 + ax2 + ax3 + ax4 + ax5, 1)
    return (name, int(total))


def main():
    print(f"Recording ROCKET-1000 scores for {TODAY}")

    # Load existing history
    history = {}
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)

    if TODAY in history:
        print(f"Scores for {TODAY} already recorded. Skipping.")
        return

    launchers = fetch_launchers()
    print(f"Loaded {len(launchers)} launchers")

    today_scores = {}
    for launcher in launchers:
        result = score_launcher(launcher)
        if result:
            name, score = result
            today_scores[name] = score

    print(f"Scored {len(today_scores)} rockets")

    # Top 10
    top = sorted(today_scores.items(), key=lambda x: x[1], reverse=True)[:10]
    for name, score in top:
        print(f"  {name}: {score}")

    history[TODAY] = today_scores

    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

    print(f"Saved to {HISTORY_FILE}")


if __name__ == "__main__":
    main()
