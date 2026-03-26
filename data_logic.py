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
    "Payload Capacity": "Payload to LEO (75%) and thrust power (25%)",
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

    def _to_num(val):
        try:
            return float(val) if val else 0
        except (ValueError, TypeError):
            return 0

    total_launches = int(_to_num(launcher.get("total_launch_count")))
    successful = int(_to_num(launcher.get("successful_launches")))
    consecutive = int(_to_num(launcher.get("consecutive_successful_launches")))
    leo = _to_num(launcher.get("leo_capacity"))
    gto = _to_num(launcher.get("gto_capacity"))
    launch_cost = _to_num(launcher.get("launch_cost"))
    reusable = bool(launcher.get("reusable"))
    successful_landings = int(_to_num(launcher.get("successful_landings")))
    attempted_landings = int(_to_num(launcher.get("attempted_landings")))
    maiden_flight = launcher.get("maiden_flight") or ""
    description = launcher.get("description") or ""
    length = launcher.get("length")
    diameter = launcher.get("diameter")
    launch_mass = launcher.get("launch_mass")
    thrust = launcher.get("thrust")
    image_url = launcher.get("image_url") or ""
    active = bool(launcher.get("active"))
    manufacturer = launcher.get("manufacturer") or {}
    country_code = manufacturer.get("country_code", "") if isinstance(manufacturer, dict) else ""
    manufacturer_name = manufacturer.get("name", "") if isinstance(manufacturer, dict) else ""

    # --- Axis 1: Track Record (200) ---
    # Confidence penalty for low launch count: scale by min(total_launches/10, 1)
    if total_launches > 0:
        success_rate = successful / total_launches
        confidence = min(total_launches / 10, 1.0)  # 10+ launches = full confidence
        ax1 = _clamp(success_rate * 200 * confidence, 0, 200)
    else:
        success_rate = 0.0
        ax1 = 0

    # --- Axis 2: Reliability Streak (200) ---
    ax2 = _clamp(consecutive * 2, 0, 200)

    # --- Axis 3: Payload Capacity (200) ---
    # 75% payload (LEO) + 25% thrust, both on log scale
    import math
    effective_leo = leo if leo else (gto * 2 if gto else 0)
    thrust_kn = _to_num(thrust) if thrust else 0

    payload_score = 0
    if effective_leo > 0:
        payload_score = _clamp((math.log2(effective_leo) / 15) * 200, 0, 200)

    thrust_score = 0
    if thrust_kn > 0:
        # log2(12)≈3.6→42, log2(2400)≈11.2→132, log2(73550)≈16.2→191
        thrust_score = _clamp((math.log2(thrust_kn) / 17) * 200, 0, 200)

    if effective_leo > 0 and thrust_kn > 0:
        ax3 = payload_score * 0.75 + thrust_score * 0.25
    elif effective_leo > 0:
        ax3 = payload_score
    elif thrust_kn > 0:
        ax3 = thrust_score
    else:
        ax3 = 0

    # --- Axis 4: Cost Efficiency (200) ---
    # Log scale inverted: lower cost/kg = higher score
    # $500/kg = 200, $2,500/kg = 165, $10,000/kg = 115, $50,000/kg = 65, $200,000/kg = 15
    if launch_cost and effective_leo and effective_leo > 0:
        cost_per_kg = launch_cost / effective_leo
        if cost_per_kg > 0:
            # log10(500)=2.7, log10(200000)=5.3 → range ~2.6
            # Map: low cost = high score
            ax4 = _clamp((5.5 - math.log10(cost_per_kg)) * 75, 0, 200)
        else:
            ax4 = 200
    else:
        ax4 = None  # unavailable when data missing

    # --- Axis 5: Reusability & Innovation (200) ---
    base = 100 if reusable else 50
    landing_denom = max(attempted_landings, 1)
    landing_bonus = (successful_landings / landing_denom) * 100
    ax5 = _clamp(base + landing_bonus, 0, 200)

    all_axes = {
        "Track Record": round(ax1, 1) if ax1 is not None else None,
        "Reliability Streak": round(ax2, 1) if ax2 is not None else None,
        "Payload Capacity": round(ax3, 1) if ax3 is not None else None,
        "Cost Efficiency": round(ax4, 1) if ax4 is not None else None,
        "Reusability & Innovation": round(ax5, 1) if ax5 is not None else None,
    }
    unavailable_axes = [k for k, v in all_axes.items() if v is None]
    available = {k: v for k, v in all_axes.items() if v is not None}
    if available:
        raw_sum = sum(available.values())
        total = round(raw_sum / len(available) * 5, 1)
    else:
        total = 0

    return {
        "name": short_name,
        "full_name": name,
        "family": family,
        "axes": all_axes,
        "total": total,
        "unavailable_axes": unavailable_axes,
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
        "image_url": image_url,
        "active": active,
        "country_code": country_code,
        "manufacturer_name": manufacturer_name,
    }


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_rocket_news(rocket_name: str, max_items: int = 5) -> list:
    """Fetch recent news articles for a rocket from Spaceflight News API."""
    try:
        # Search by rocket short name (e.g. "Falcon 9" not "SpaceX Falcon 9 Block 5")
        search_term = rocket_name.split("(")[0].strip()
        resp = requests.get(
            "https://api.spaceflightnewsapi.net/v4/articles/",
            params={"limit": max_items, "search": search_term},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for article in data.get("results", []):
            results.append({
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "source": article.get("news_site", ""),
                "date": (article.get("published_at") or "")[:10],
                "image": article.get("image_url", ""),
            })
        return results
    except Exception:
        return []


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
