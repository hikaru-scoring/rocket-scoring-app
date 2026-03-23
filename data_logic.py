# data_logic.py
"""Data fetching and scoring logic for ROCKET-1000."""
import os
import json
import streamlit as st
import requests

API_BASE = "https://ll.thespacedevs.com/2.2.0/config/launcher/"
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "launcher_cache.json")

AXES_LABELS = [
    "Track Record",
    "Reliability Streak",
    "Payload Capacity",
    "Cost Efficiency",
    "Reusability & Innovation",
]

LOGIC_DESC = {
    "Track Record": "Historical success rate across all launches",
    "Reliability Streak": "Consecutive successful launches",
    "Payload Capacity": "Maximum payload to Low Earth Orbit",
    "Cost Efficiency": "Cost per kilogram to orbit",
    "Reusability & Innovation": "Landing capability and reuse track record",
}


def _clamp(value, lo, hi):
    """Clamp a numeric value between lo and hi."""
    return max(lo, min(hi, value))


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_all_launchers() -> list:
    """Fetch launcher configs, using local cache first then API fallback."""
    # Try local cache first (always available on deploy)
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)

    # Fallback: try API (may be rate-limited on free tier)
    all_results = []
    offset = 0
    limit = 100
    try:
        while True:
            resp = requests.get(
                API_BASE,
                params={"limit": limit, "offset": offset},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            all_results.extend(results)
            if not data.get("next"):
                break
            offset += limit
    except Exception:
        return all_results  # return whatever we got so far
    return all_results


def score_launcher(launcher: dict) -> dict:
    """Score a single launcher across 5 axes. Returns scored dict."""
    name = launcher.get("full_name") or launcher.get("name") or "Unknown"
    short_name = launcher.get("name") or name
    family = launcher.get("family") or ""

    total_launches = launcher.get("total_launch_count") or 0
    successful = launcher.get("successful_launches") or 0
    consecutive = launcher.get("consecutive_successful_launches") or 0
    leo = launcher.get("leo_capacity") or 0
    gto = launcher.get("gto_capacity") or 0
    launch_cost = launcher.get("launch_cost") or 0
    reusable = bool(launcher.get("reusable"))
    successful_landings = launcher.get("successful_landings") or 0
    attempted_landings = launcher.get("attempted_landings") or 0
    maiden_flight = launcher.get("maiden_flight") or ""
    description = launcher.get("description") or ""
    length = launcher.get("length")
    diameter = launcher.get("diameter")
    launch_mass = launcher.get("launch_mass")
    thrust = launcher.get("thrust")

    # --- Axis 1: Track Record (200) ---
    if total_launches > 0:
        success_rate = successful / total_launches
        ax1 = _clamp(success_rate * 200, 0, 200)
    else:
        success_rate = 0.0
        ax1 = 0

    # --- Axis 2: Reliability Streak (200) ---
    ax2 = _clamp(consecutive * 2, 0, 200)

    # --- Axis 3: Payload Capacity (200) ---
    effective_leo = leo if leo else (gto * 2 if gto else 0)
    if effective_leo > 0:
        ax3 = _clamp(effective_leo / 150, 0, 200)
    else:
        ax3 = 0

    # --- Axis 4: Cost Efficiency (200) ---
    if launch_cost and effective_leo and effective_leo > 0:
        cost_per_kg = launch_cost / effective_leo
        ax4 = _clamp(200 - (cost_per_kg / 50), 0, 200)
    else:
        ax4 = 100  # neutral when data unavailable

    # --- Axis 5: Reusability & Innovation (200) ---
    base = 100 if reusable else 50
    landing_denom = max(attempted_landings, 1)
    landing_bonus = (successful_landings / landing_denom) * 100
    ax5 = _clamp(base + landing_bonus, 0, 200)

    axes = {
        "Track Record": round(ax1, 1),
        "Reliability Streak": round(ax2, 1),
        "Payload Capacity": round(ax3, 1),
        "Cost Efficiency": round(ax4, 1),
        "Reusability & Innovation": round(ax5, 1),
    }
    total = round(sum(axes.values()), 1)

    return {
        "name": short_name,
        "full_name": name,
        "family": family,
        "axes": axes,
        "total": total,
        "success_rate": round(success_rate * 100, 1) if total_launches > 0 else 0.0,
        "total_launches": total_launches,
        "leo_capacity": effective_leo,
        "launch_cost": launch_cost,
        "reusable": reusable,
        "consecutive_successes": consecutive,
        "maiden_flight": maiden_flight,
        "description": description,
        "length": length,
        "diameter": diameter,
        "launch_mass": launch_mass,
        "thrust": thrust,
    }


def score_all_launchers() -> list:
    """Score all launchers with at least 1 launch, sorted by total desc."""
    raw = fetch_all_launchers()
    scored = []
    for launcher in raw:
        total_launches = launcher.get("total_launch_count") or 0
        if total_launches < 1:
            continue
        scored.append(score_launcher(launcher))
    scored.sort(key=lambda x: x["total"], reverse=True)
    return scored
