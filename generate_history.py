"""
Generate simulated score history for ROCKET-1000.
Uses launcher_cache.json to estimate what scores would have been
at monthly intervals from each rocket's maiden flight to now.
"""
import json
import math
import os
from datetime import datetime, timedelta

CACHE_FILE = "launcher_cache.json"
HISTORY_FILE = "scores_history.json"


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


def _to_num(val):
    try:
        return float(val) if val else 0
    except (ValueError, TypeError):
        return 0


def compute_score(total_launches, successful, consecutive, effective_leo, thrust_kn,
                  launch_cost, reusable, successful_landings, attempted_landings):
    """Compute total score given cumulative stats at a point in time."""
    # Axis 1: Track Record
    if total_launches > 0:
        success_rate = successful / total_launches
        confidence = min(total_launches / 10, 1.0)
        ax1 = _clamp(success_rate * 200 * confidence, 0, 200)
    else:
        ax1 = 0

    # Axis 2: Reliability Streak
    ax2 = _clamp(consecutive * 2, 0, 200)

    # Axis 3: Payload Capacity (75% payload + 25% thrust)
    payload_score = 0
    if effective_leo > 0:
        payload_score = _clamp((math.log2(effective_leo) / 15) * 200, 0, 200)
    thrust_score = 0
    if thrust_kn > 0:
        thrust_score = _clamp((math.log2(thrust_kn) / 17) * 200, 0, 200)
    if effective_leo > 0 and thrust_kn > 0:
        ax3 = payload_score * 0.75 + thrust_score * 0.25
    elif effective_leo > 0:
        ax3 = payload_score
    elif thrust_kn > 0:
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

    return int(round(ax1 + ax2 + ax3 + ax4 + ax5))


def simulate_rocket_history(launcher):
    """Generate monthly score snapshots for a single rocket."""
    total_launches = int(_to_num(launcher.get("total_launch_count")))
    if total_launches < 1:
        return None

    name = launcher.get("full_name") or launcher.get("name") or "Unknown"
    maiden = launcher.get("maiden_flight") or ""
    if not maiden or len(maiden) < 4:
        return None

    try:
        # Parse maiden flight date
        if len(maiden) >= 10:
            start_date = datetime.strptime(maiden[:10], "%Y-%m-%d")
        else:
            start_date = datetime(int(maiden[:4]), 1, 1)
    except (ValueError, IndexError):
        return None

    now = datetime(2026, 3, 24)
    if start_date >= now:
        return None

    # Static properties (don't change over time)
    successful = int(_to_num(launcher.get("successful_launches")))
    failed = int(_to_num(launcher.get("failed_launches")))
    consecutive_final = int(_to_num(launcher.get("consecutive_successful_launches")))
    leo = _to_num(launcher.get("leo_capacity"))
    gto = _to_num(launcher.get("gto_capacity"))
    effective_leo = leo if leo else (gto * 2 if gto else 0)
    thrust_kn = _to_num(launcher.get("to_thrust"))
    launch_cost = _to_num(launcher.get("launch_cost"))
    reusable = bool(launcher.get("reusable"))
    successful_landings_final = int(_to_num(launcher.get("successful_landings")))
    attempted_landings_final = int(_to_num(launcher.get("attempted_landings")))

    # Distribute launches over time
    # Assume failures happen in the first 30% of the program
    total_months = max(1, (now.year - start_date.year) * 12 + (now.month - start_date.month))

    # Build a launch timeline: distribute launches across months
    # More launches in recent months (exponential ramp-up is realistic)
    monthly_snapshots = {}

    for month_offset in range(0, total_months + 1, 1):
        snapshot_date = start_date + timedelta(days=month_offset * 30.44)
        if snapshot_date > now:
            break

        # Progress: 0.0 to 1.0
        progress = month_offset / total_months if total_months > 0 else 1.0

        # Cumulative launches at this point (S-curve distribution)
        cum_launches = int(total_launches * min(progress ** 0.8, 1.0))
        if cum_launches < 1 and month_offset > 0:
            cum_launches = 1

        # Failures concentrated in early phase
        if failed > 0:
            failure_progress = min(progress / 0.4, 1.0)  # 40% of program has all failures
            cum_failures = int(failed * failure_progress)
        else:
            cum_failures = 0

        cum_successful = max(0, cum_launches - cum_failures)

        # Consecutive streak: builds up in later phases
        if progress > 0.5 and cum_failures >= failed:
            # All failures are behind us, streak is building
            streak_launches = cum_launches - (cum_successful - consecutive_final) if cum_successful > consecutive_final else cum_launches
            cum_consecutive = min(int(consecutive_final * min((progress - 0.5) * 2, 1.0)), consecutive_final)
        else:
            cum_consecutive = max(0, int(consecutive_final * max(0, progress - 0.3) / 0.7))

        # Landings: only in later phases (SpaceX started landing ~2015)
        if attempted_landings_final > 0:
            landing_progress = max(0, (progress - 0.5) * 2)  # landings in latter half
            cum_attempted = int(attempted_landings_final * landing_progress)
            cum_landed = int(successful_landings_final * landing_progress)
        else:
            cum_attempted = 0
            cum_landed = 0

        score = compute_score(
            cum_launches, cum_successful, cum_consecutive,
            effective_leo, thrust_kn, launch_cost, reusable,
            cum_landed, cum_attempted
        )

        date_str = snapshot_date.strftime("%Y-%m-%d")

        # Only record monthly (1st of each month approx)
        month_key = snapshot_date.strftime("%Y-%m")
        if month_key not in monthly_snapshots:
            monthly_snapshots[month_key] = (date_str, score)

    return name, monthly_snapshots


def main():
    print("Generating simulated score history...")

    with open(CACHE_FILE, "r") as f:
        launchers = json.load(f)

    # Load existing history (keep today's real data)
    history = {}
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)

    # Track how many rockets we process
    count = 0
    # Only generate history for top rockets (by launch count) to keep file manageable
    active_launchers = [l for l in launchers if (l.get("total_launch_count") or 0) >= 1]
    active_launchers.sort(key=lambda x: x.get("total_launch_count", 0), reverse=True)

    for launcher in active_launchers:
        result = simulate_rocket_history(launcher)
        if not result:
            continue

        name, snapshots = result
        count += 1

        for month_key, (date_str, score) in snapshots.items():
            # Use 1st of month as date key
            history_date = f"{month_key}-01"
            if history_date not in history:
                history[history_date] = {}
            # Don't overwrite real recorded data
            if history_date in history and name in history[history_date]:
                continue
            history[history_date] = history.get(history_date, {})
            history[history_date][name] = score

    # Sort by date
    sorted_history = dict(sorted(history.items()))

    with open(HISTORY_FILE, "w") as f:
        json.dump(sorted_history, f, indent=2)

    dates = sorted(sorted_history.keys())
    print(f"Processed {count} rockets")
    print(f"History spans {dates[0]} to {dates[-1]}")
    print(f"Total date entries: {len(dates)}")

    # Show sample for Falcon 9 Block 5
    sample_name = "SpaceX Falcon 9 Block 5"
    sample_scores = []
    for d in dates[-12:]:
        s = sorted_history[d].get(sample_name)
        if s:
            sample_scores.append(f"{d}: {s}")
    if sample_scores:
        print(f"\nSample: {sample_name}")
        for line in sample_scores:
            print(f"  {line}")


if __name__ == "__main__":
    main()
