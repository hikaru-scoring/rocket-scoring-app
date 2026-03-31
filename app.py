# app.py
"""ROCKET-1000 — Launch Vehicle Scoring Platform."""
import io
import json
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data_logic import AXES_LABELS, LOGIC_DESC, score_all_launchers, fetch_rocket_news
from ui_components import inject_css, render_radar_chart
try:
    from pdf_report import generate_pdf
    _PDF_AVAILABLE = True
except ImportError:
    _PDF_AVAILABLE = False

SCORES_HISTORY_FILE = os.path.join(os.path.dirname(__file__), "scores_history.json")

def _load_scores_history():
    if os.path.exists(SCORES_HISTORY_FILE):
        with open(SCORES_HISTORY_FILE, "r") as f:
            return json.load(f)
    return {}

def render_score_delta(asset_name: str, current_total: int):
    """前日比のスコア変動を表示する"""
    history = _load_scores_history()
    if not history:
        return
    dates = sorted(history.keys(), reverse=True)
    prev_score = None
    for d in dates:
        s = history[d].get(asset_name)
        if s is not None:
            prev_score = s
            break
    if prev_score is None:
        return
    delta = current_total - prev_score
    if delta > 0:
        color, arrow = "#10b981", "&#9650;"
    elif delta < 0:
        color, arrow = "#ef4444", "&#9660;"
    else:
        color, arrow = "#94a3b8", "&#9644;"
    st.markdown(
        f'<div style="text-align:center; font-size:1.1em; font-weight:700; color:{color}; margin-top:-8px; margin-bottom:10px;">'
        f'{arrow} {delta:+d} from last record ({prev_score})'
        f'</div>',
        unsafe_allow_html=True
    )

def render_daily_score_tracker(asset_name: str):
    """scores_history.json からデイリースコア推移チャートを表示する"""
    history = _load_scores_history()
    if not history:
        return
    dates = sorted(history.keys())
    values = []
    valid_dates = []
    for d in dates:
        score = history[d].get(asset_name)
        if score is not None:
            valid_dates.append(d)
            values.append(score)
    if len(valid_dates) < 2:
        return
    fig_daily = go.Figure()
    fig_daily.add_trace(go.Scatter(
        x=valid_dates, y=values, mode='lines+markers',
        name=asset_name,
        line=dict(color='#2E7BE6', width=2),
        marker=dict(size=5),
        fill='tozeroy', fillcolor='rgba(46,123,230,0.05)'
    ))
    fig_daily.update_layout(
        yaxis=dict(range=[0, 1000], title="Score"),
        height=250,
        margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor='white',
        hovermode="x unified",
        clickmode='none',
        dragmode=False,
    )
    st.plotly_chart(fig_daily, use_container_width=True, config={"displayModeBar": False}, key=f"daily_tracker_{asset_name}")

APP_TITLE = "ROCKET-1000 — Launch Vehicle Scoring Platform"
st.set_page_config(page_title=APP_TITLE, page_icon="🚀", layout="wide")

# ---------------------------------------------------------------------------
# CSS — hide Streamlit chrome + inject shared styles
# ---------------------------------------------------------------------------
inject_css()
st.markdown("""
<style>
.block-container { padding-top: 1rem !important; }
header[data-testid="stHeader"] { display: none !important; }
footer { display: none !important; }
#MainMenu { display: none !important; }
.viewerBadge_container__r5tak { display: none !important; }
.styles_viewerBadge__CvC9N { display: none !important; }
[data-testid="stActionButtonIcon"] { display: none !important; }
[data-testid="manage-app-button"] { display: none !important; }
a[href*="github.com"] img { display: none !important; }
div[class*="viewerBadge"] { display: none !important; }
div[class*="StatusWidget"] { display: none !important; }
div[data-testid="stStatusWidget"] { display: none !important; }
iframe[title="streamlit_lottie.streamlit_lottie"] { display: none !important; }
.stDeployButton { display: none !important; }
div[class*="stToolbar"] { display: none !important; }
div.embeddedAppMetaInfoBar_container__DxxL1 { display: none !important; }
div[class*="embeddedAppMetaInfoBar"] { display: none !important; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "saved_rocket_data" not in st.session_state:
    st.session_state.saved_rocket_data = None
if "selected_company" not in st.session_state:
    st.session_state["selected_company"] = None
if "selected_rocket_detail" not in st.session_state:
    st.session_state["selected_rocket_detail"] = None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _score_color(score: float) -> str:
    if score >= 700:
        return "#10b981"
    if score >= 500:
        return "#2E7BE6"
    if score >= 300:
        return "#f59e0b"
    return "#ef4444"


def _border_color(score: float) -> str:
    if score >= 700:
        return "#10b981"
    if score >= 500:
        return "#2E7BE6"
    if score >= 300:
        return "#f59e0b"
    return "#ef4444"


def _fmt_cost(val):
    if val >= 1e9:
        return f"${val/1e9:.1f}B"
    if val >= 1e6:
        return f"${val/1e6:.0f}M"
    if val >= 1e3:
        return f"${val/1e3:.0f}K"
    return f"${val:.0f}"


def _fmt_mass(val):
    if val >= 1000:
        return f"{val/1000:.1f}t"
    return f"{val:.0f}kg"


def estimate_premium_rate(success_rate_pct, total_launches, consecutive, reusable_flag):
    """Estimate insurance premium rate based on rocket stats."""
    failure_rate = (100 - success_rate_pct) / 100
    base_rate = failure_rate * 1.75
    if total_launches < 5:
        base_rate += 0.10
    elif total_launches < 10:
        base_rate += 0.05
    elif total_launches < 20:
        base_rate += 0.02
    streak_discount = min(consecutive * 0.0005, 0.015)
    base_rate -= streak_discount
    if reusable_flag:
        if total_launches >= 50:
            base_rate *= 0.90
        else:
            base_rate *= 1.05
    return max(0.015, min(base_rate, 0.25))


COUNTRY_FLAG = {
    "USA": "US", "RUS": "RU", "CHN": "CN", "IND": "IN", "JPN": "JP",
    "FRA": "FR", "EU": "EU", "ISR": "IL", "KOR": "KR", "IRN": "IR",
    "BRA": "BR", "UKR": "UA", "GBR": "GB", "NZL": "NZ", "ITA": "IT",
    "ESP": "ES", "DEU": "DE", "TWN": "TW", "AUS": "AU",
}


def _country_label(code: str) -> str:
    if not code:
        return ""
    return code


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
with st.spinner("Fetching launcher data..."):
    all_scored = score_all_launchers()

if not all_scored:
    st.error("Could not load launcher data. The API may be rate-limited. Please try again in a few minutes.")
    st.stop()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_dash, tab_detail, tab_rank, tab_ins = st.tabs(["Dashboard", "Rocket Detail", "Rankings", "Insurance"])

# ===================================================================
# DASHBOARD TAB
# ===================================================================
with tab_dash:
    st.markdown(
        "<div style='font-size:1.5em; font-weight:900; color:#1e3a8a; margin-bottom:5px;'>"
        "ROCKET-1000</div>"
        "<p style='color:#64748b; margin-bottom:4px;'>"
        "Every launch vehicle scored on the same 0&ndash;1,000 scale across 5 dimensions: "
        "track record, reliability, payload, cost efficiency, and reusability.</p>"
        "<p style='color:#64748b; margin-bottom:20px;'>"
        "Compare rockets side by side like a health check. A higher score means the vehicle is in a stronger position.</p>",
        unsafe_allow_html=True,
    )

    # --- Sidebar filters ---
    with st.sidebar:
        st.markdown("### Filters")
        # Country filter
        all_countries = sorted(set(r.get("country_code", "") for r in all_scored if r.get("country_code")))
        selected_countries = st.multiselect("Country", all_countries, default=[], key="filter_country")
        # Reusable filter
        reuse_filter = st.radio("Reusability", ["All", "Reusable", "Expendable"], key="filter_reuse")
        # Active filter
        active_filter = st.radio("Status", ["All", "Active", "Retired"], key="filter_active")
        # Search box
        search_query = st.text_input("Search rockets", "", key="filter_search", placeholder="e.g. Falcon, Soyuz...")

    # Apply filters
    filtered = list(all_scored)
    if selected_countries:
        filtered = [r for r in filtered if r.get("country_code") in selected_countries]
    if reuse_filter == "Reusable":
        filtered = [r for r in filtered if r["reusable"]]
    elif reuse_filter == "Expendable":
        filtered = [r for r in filtered if not r["reusable"]]
    if active_filter == "Active":
        filtered = [r for r in filtered if r.get("active")]
    elif active_filter == "Retired":
        filtered = [r for r in filtered if not r.get("active")]
    if search_query:
        q = search_query.lower()
        filtered = [r for r in filtered if q in r["full_name"].lower() or q in r["name"].lower() or q in r.get("manufacturer_name", "").lower()]

    st.markdown(f"<p style='color:#94a3b8; font-size:0.85em;'>Showing {len(filtered)} of {len(all_scored)} rockets</p>", unsafe_allow_html=True)

    # --- Browse by Launch Provider ---
    companies = {}
    for r in filtered:
        family = r.get("family") or "Other"
        if family not in companies:
            companies[family] = []
        companies[family].append(r)

    company_order = sorted(companies.keys(), key=lambda c: max(r["total"] for r in companies[c]), reverse=True)

    st.markdown("<div class='section-title'>Browse by Launch Provider</div>", unsafe_allow_html=True)

    top_companies = company_order[:15]
    if top_companies:
        comp_cols = st.columns(min(len(top_companies), 5))
        for i, company in enumerate(top_companies):
            with comp_cols[i % 5]:
                if st.button(company, key=f"company_{company}", use_container_width=True):
                    st.session_state["selected_company"] = company
                    st.session_state["selected_rocket_detail"] = None

    selected_company = st.session_state.get("selected_company")
    if selected_company and selected_company in companies:
        st.markdown(f"<div style='font-size:1.1em; font-weight:700; color:#1e3a8a; margin:15px 0 10px;'>{selected_company} Rockets</div>", unsafe_allow_html=True)
        company_rockets = sorted(companies[selected_company], key=lambda r: r["total"], reverse=True)

        rocket_cols = st.columns(min(len(company_rockets), 4))
        for j, rocket in enumerate(company_rockets):
            with rocket_cols[j % 4]:
                score = int(rocket["total"])
                if st.button(f"\U0001f680 {rocket['name']}\n{score}/1000", key=f"rocket_btn_{selected_company}_{j}_{rocket['name']}", use_container_width=True):
                    st.session_state["selected_rocket_detail"] = rocket["name"]

        selected_rocket_name = st.session_state.get("selected_rocket_detail")
        if selected_rocket_name:
            detail = None
            for r in filtered:
                if r["name"] == selected_rocket_name:
                    detail = r
                    break
            if not detail:
                for r in all_scored:
                    if r["name"] == selected_rocket_name:
                        detail = r
                        break
            if detail:
                # Image + score side by side
                if detail.get("image_url"):
                    img_col, info_col = st.columns([1, 2])
                    with img_col:
                        st.image(detail["image_url"], width=250)
                    with info_col:
                        st.markdown(f"""
                        <div style="text-align:center; margin:10px 0;">
                            <div style="font-size:14px; letter-spacing:2px; color:#666;">TOTAL SCORE</div>
                            <div style="font-size:70px; font-weight:800; color:#2E7BE6; line-height:1;">
                                {int(detail['total'])}
                                <span style="font-size:28px; color:#BBB;">/ 1000</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="text-align:center; margin:10px 0;">
                        <div style="font-size:14px; letter-spacing:2px; color:#666;">TOTAL SCORE</div>
                        <div style="font-size:70px; font-weight:800; color:#2E7BE6; line-height:1;">
                            {int(detail['total'])}
                            <span style="font-size:28px; color:#BBB;">/ 1000</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                render_score_delta(detail['name'], int(detail['total']))

                cl_left, cl_right = st.columns([1.5, 1])
                with cl_left:
                    st.markdown("<div style='font-size:1.1em; font-weight:bold; color:#333; margin-bottom:5px;'>Intelligence Radar</div>", unsafe_allow_html=True)
                    fig_r = render_radar_chart(detail, None, AXES_LABELS)
                    st.plotly_chart(fig_r, use_container_width=True, config={"displayModeBar": False}, key=f"radar_browse_{selected_company}_{detail['name']}")
                with cl_right:
                    st.markdown("<div style='font-size:0.9em; font-weight:bold; color:#333; margin-bottom:15px; border-left:3px solid #2E7BE6; padding-left:8px;'>SCORE METRICS</div>", unsafe_allow_html=True)
                    for axis in AXES_LABELS:
                        v = detail["axes"][axis]
                        desc = LOGIC_DESC.get(axis, "")
                        st.markdown(f"""
                        <div style="background:#fff; padding:16px; border-radius:12px; margin-bottom:10px;
                            border:1px solid #e0e0e0; border-left:8px solid #2E7BE6; box-shadow:2px 2px 5px rgba(0,0,0,0.07);">
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                                <span style="font-size:1.3em; font-weight:800; color:#333;">{axis}</span>
                                <span style="font-size:1.7em; font-weight:900; color:#2E7BE6;">{int(v)}</span>
                            </div>
                            <p style="font-size:1em; color:#777; margin:0;">{desc}</p>
                        </div>""", unsafe_allow_html=True)

                st.markdown("---")

    # --- Top 10 / Bottom 10 ---
    top_col, bot_col = st.columns(2)
    with top_col:
        st.markdown(
            "<div style='font-size:1em; font-weight:700; color:#10b981; margin-bottom:10px;'>Top 10 Rockets</div>",
            unsafe_allow_html=True,
        )
        for s in filtered[:10]:
            score = s["total"]
            country = _country_label(s.get("country_code", ""))
            country_tag = f"<span style='font-size:0.75em; color:#94a3b8; margin-left:6px;'>{country}</span>" if country else ""
            st.markdown(
                f"""<div style="background:#f0fdf4; padding:8px 12px; border-radius:8px; margin-bottom:4px; display:flex; justify-content:space-between;">
                    <span style="font-weight:600;">{s['full_name']}{country_tag}</span>
                    <span style="font-weight:900; color:#10b981;">{int(score)}</span>
                </div>""",
                unsafe_allow_html=True,
            )
    with bot_col:
        st.markdown(
            "<div style='font-size:1em; font-weight:700; color:#ef4444; margin-bottom:10px;'>Bottom 10 Rockets</div>",
            unsafe_allow_html=True,
        )
        for s in filtered[-10:]:
            score = s["total"]
            country = _country_label(s.get("country_code", ""))
            country_tag = f"<span style='font-size:0.75em; color:#94a3b8; margin-left:6px;'>{country}</span>" if country else ""
            st.markdown(
                f"""<div style="background:#fef2f2; padding:8px 12px; border-radius:8px; margin-bottom:4px; display:flex; justify-content:space-between;">
                    <span style="font-weight:600;">{s['full_name']}{country_tag}</span>
                    <span style="font-weight:900; color:#ef4444;">{int(score)}</span>
                </div>""",
                unsafe_allow_html=True,
            )

    # --- All Rockets Grid ---
    st.markdown("<div class='section-title'>All Rockets</div>", unsafe_allow_html=True)

    cols = st.columns(3)
    for i, rocket in enumerate(filtered):
        score = rocket["total"]
        border = _border_color(score)
        country = _country_label(rocket.get("country_code", ""))
        country_tag = f"<span style='font-size:0.75em; color:#94a3b8; margin-left:4px;'>{country}</span>" if country else ""
        reuse_tag = "<span style='font-size:0.7em; background:#10b981; color:#fff; padding:1px 6px; border-radius:10px; margin-left:6px;'>Reusable</span>" if rocket["reusable"] else ""
        with cols[i % 3]:
            st.markdown(
                f"""<div style="background:#fff; border-radius:12px; padding:18px; margin-bottom:12px;
                border-left:4px solid {border}; box-shadow:0 2px 8px rgba(0,0,0,0.04);">
                <div style="font-size:0.95em; font-weight:700; color:#1e293b; margin:2px 0;">
                {rocket['full_name']}{country_tag}{reuse_tag}</div>
                <div style="display:flex; justify-content:space-between; align-items:baseline;">
                <span style="font-size:1.8em; font-weight:900; color:{border};">{int(score)}</span>
                <span style="font-size:0.8em; color:#94a3b8;">{rocket['total_launches']} launches</span>
                </div></div>""",
                unsafe_allow_html=True,
            )

# ===================================================================
# ROCKET DETAIL TAB
# ===================================================================
with tab_detail:
    rocket_names = [r["full_name"] for r in all_scored]
    search_query = st.text_input("Search rockets", "", placeholder="e.g. Falcon, Soyuz, Starship...", key="detail_search")
    if search_query:
        q = search_query.lower()
        rocket_names = [n for n in rocket_names if q in n.lower()]
        if not rocket_names:
            rocket_names = [r["full_name"] for r in all_scored]
    selected_name = st.selectbox("Select a rocket", rocket_names, key="rocket_select")
    selected = next((r for r in all_scored if r["full_name"] == selected_name), None)

    if selected:
        total = int(selected["total"])

        # --- Save / Clear / PDF / CSV buttons (matches FRS-1000 order) ---
        col_btn1, col_btn2, col_btn3, col_btn4, col_btn_rest = st.columns([1, 1, 1.5, 1.5, 5.5])
        with col_btn1:
            save_it = st.button("Save", key="btn_save")
        with col_btn2:
            clear_it = st.button("Clear", key="btn_clear")
        with col_btn3:
            # PDF export
            if _PDF_AVAILABLE:
                rocket_snapshot = {
                    "Total Launches": str(selected["total_launches"]),
                    "Success Rate": f"{selected['success_rate']}%",
                    "LEO Capacity": _fmt_mass(selected["leo_capacity"]) if selected["leo_capacity"] else "N/A",
                    "Cost / Launch": _fmt_cost(selected["launch_cost"]) if selected["launch_cost"] else "N/A",
                    "Reusable": "Yes" if selected["reusable"] else "No",
                    "Country": selected.get("country_code", "N/A"),
                }
                pdf_bytes = generate_pdf(selected, AXES_LABELS, LOGIC_DESC, rocket_snapshot)
                st.download_button("PDF", pdf_bytes, f"ROCKET1000_{selected['name'].replace(' ', '_')}.pdf", "application/pdf", key="btn_pdf_detail")
            else:
                st.button("PDF (installing...)", disabled=True, key="btn_pdf_detail")
        with col_btn4:
            # CSV export
            export_data = {
                "Rocket": [selected["full_name"]],
                "Total Score": [total],
                "Country": [selected.get("country_code", "")],
                "Reusable": [selected["reusable"]],
                "Total Launches": [selected["total_launches"]],
                "Success Rate (%)": [selected["success_rate"]],
                "LEO Capacity (kg)": [selected["leo_capacity"]],
                "Launch Cost ($)": [selected["launch_cost"]],
            }
            for axis in AXES_LABELS:
                export_data[axis] = [selected["axes"][axis]]
            csv_buf = io.StringIO()
            pd.DataFrame(export_data).to_csv(csv_buf, index=False)
            st.download_button("Excel", csv_buf.getvalue(), f"{selected['name']}_score.csv", "text/csv", key="btn_csv_detail")

        if save_it:
            st.session_state.saved_rocket_data = selected
            st.rerun()
        if clear_it:
            st.session_state.saved_rocket_data = None
            st.rerun()

        # --- Image + Total Score ---
        if selected.get("image_url"):
            img_col, score_col = st.columns([1, 2.5])
            with img_col:
                st.image(selected["image_url"], width=280)
            with score_col:
                st.markdown(f"""
                <div style="text-align:center; margin-top:4px; margin-bottom:10px;">
                    <div style="font-size:14px; letter-spacing:2px; color:#666;">TOTAL SCORE</div>
                    <div style="font-size:90px; font-weight:800; color:#2E7BE6; line-height:1;">
                        {total}
                        <span style="font-size:35px; color:#BBB;">/ 1000</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="text-align:center; margin-top:4px; margin-bottom:10px;">
                <div style="font-size:14px; letter-spacing:2px; color:#666;">TOTAL SCORE</div>
                <div style="font-size:90px; font-weight:800; color:#2E7BE6; line-height:1;">
                    {total}
                    <span style="font-size:35px; color:#BBB;">/ 1000</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        render_score_delta(selected['name'], total)

        # --- I. Radar + II. Score Metrics ---
        col_radar, col_axes = st.columns([1.5, 1])

        with col_radar:
            st.markdown(
                "<div style='font-size: 1.1em; font-weight: bold; color: #333; margin-top: -10px; margin-bottom: 5px;'>I. Intelligence Radar</div>",
                unsafe_allow_html=True,
            )
            fig = render_radar_chart(selected, st.session_state.saved_rocket_data, AXES_LABELS)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key="radar_detail")

        with col_axes:
            st.markdown(
                "<div style='font-size: 0.9em; font-weight: bold; color: #333; margin-top: -10px; margin-bottom: 15px; border-left: 3px solid #2E7BE6; padding-left: 8px;'>II. ANALYSIS SCORE METRICS</div>",
                unsafe_allow_html=True,
            )

            saved = st.session_state.saved_rocket_data
            for axis in AXES_LABELS:
                v1 = selected["axes"][axis]
                v2 = saved["axes"].get(axis, 0) if saved else None
                desc_text = LOGIC_DESC.get(axis, "")

                score_html = f'<span style="color: #2E7BE6;">{int(v1)}</span><span style="color:#bbb;font-size:0.5em;font-weight:600;"> /200</span>'
                if v2 is not None:
                    score_html += f' <span style="color: #ccc; font-size: 0.9em; font-weight:bold; margin: 0 6px;">vs</span> <span style="color: #F4A261;">{int(v2)}</span><span style="color:#bbb;font-size:0.5em;font-weight:600;"> /200</span>'

                st.markdown(
                    f"""
                    <div style="
                        background-color: #FFFFFF;
                        padding: 20px;
                        border-radius: 12px;
                        margin-bottom: 12px;
                        border: 1px solid #E0E0E0;
                        border-left: 8px solid #2E7BE6;
                        box-shadow: 2px 2px 5px rgba(0,0,0,0.07);
                    ">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                            <span style="font-size: 1.4em; font-weight: 800; color: #333333;">{axis}</span>
                            <span style="font-size: 1.9em; font-weight: 900; line-height: 1;">{score_html}</span>
                        </div>
                        <p style="font-size: 1.05em; color: #777777; margin: 0; line-height: 1.3; font-weight: 500;">{desc_text}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Why X? expanders
                with st.expander(f"Why {int(v1)}?", expanded=False):
                    if axis == "Track Record":
                        st.markdown("**Formula:** `(Successful Launches / Total Launches) x 200 x Confidence`\n\nConfidence = min(Total Launches / 10, 1.0). Rockets with fewer than 10 launches get penalized.\n\n**Source:** Launch Library 2 API")
                    elif axis == "Reliability Streak":
                        st.markdown("**Formula:** `Consecutive Successful Launches x 2 (capped at 200)`\n\n**Source:** Launch Library 2 API")
                    elif axis == "Payload Capacity":
                        st.markdown("**Formula:** `75% x (log2(LEO kg) / 15) x 200 + 25% x (log2(Thrust kN) / 17) x 200`\n\nPayload capacity (75%) and thrust power (25%), both on logarithmic scale. If only one data point is available, that component is used at 100%.\n\n**Source:** Launch Library 2 API")
                    elif axis == "Cost Efficiency":
                        st.markdown("**Formula:** `(5.5 - log10(Cost per kg)) x 75 (capped at 200)`\n\nLower cost per kilogram = higher score. Default 100 when cost data is unavailable.\n\n**Source:** Launch Library 2 API")
                    elif axis == "Reusability & Innovation":
                        st.markdown("**Formula:** `Base (100 if reusable, 50 if expendable) + Landing Success Rate x 100`\n\n**Source:** Launch Library 2 API")

        # --- III. Specs Snapshot ---
        st.markdown("<div class='section-title'>III. Specs Snapshot</div>", unsafe_allow_html=True)
        bs1, bs2, bs3, bs4 = st.columns(4)

        spec_items = [
            (bs1, "TOTAL LAUNCHES", str(selected["total_launches"])),
            (bs2, "SUCCESS RATE", f"{selected['success_rate']}%"),
            (bs3, "LEO CAPACITY", _fmt_mass(selected["leo_capacity"]) if selected["leo_capacity"] else "N/A"),
            (bs4, "COST / LAUNCH", _fmt_cost(selected["launch_cost"]) if selected["launch_cost"] else "N/A"),
        ]
        for col, label, value in spec_items:
            col.markdown(
                f"""
                <div style="background:#fff; padding:20px; border-radius:12px; text-align:center; border:1px solid #e2e8f0; box-shadow:2px 2px 5px rgba(0,0,0,0.04);">
                    <div style="font-size:0.7em; font-weight:700; color:#94a3b8; letter-spacing:1px;">{label}</div>
                    <div style="font-size:1.8em; font-weight:900; color:#2E7BE6; line-height:1.3;">{value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # --- Insurance Premium Estimator ---
        st.markdown("<div class='section-title'>III-B. Insurance Premium Estimator</div>", unsafe_allow_html=True)

        est_rate = estimate_premium_rate(
            selected["success_rate"],
            selected["total_launches"],
            selected.get("consecutive_successes", 0),
            selected["reusable"],
        )

        ins_col1, ins_col2 = st.columns([1, 2])
        with ins_col1:
            payload_value = st.number_input(
                "Payload Value ($ million)",
                min_value=1, max_value=2000, value=200, step=10,
                key="ins_payload_value",
            )
        with ins_col2:
            est_premium = payload_value * est_rate
            rate_color = "#10b981" if est_rate < 0.05 else "#f59e0b" if est_rate < 0.10 else "#ef4444"
            st.markdown(f"""
            <div style="background:#fff; padding:20px; border-radius:12px; border:1px solid #e2e8f0; box-shadow:2px 2px 5px rgba(0,0,0,0.04);">
                <div style="display:flex; justify-content:space-around; text-align:center;">
                    <div>
                        <div style="font-size:0.7em; font-weight:700; color:#94a3b8; letter-spacing:1px;">EST. PREMIUM RATE</div>
                        <div style="font-size:2.2em; font-weight:900; color:{rate_color};">{est_rate*100:.1f}%</div>
                    </div>
                    <div>
                        <div style="font-size:0.7em; font-weight:700; color:#94a3b8; letter-spacing:1px;">EST. PREMIUM</div>
                        <div style="font-size:2.2em; font-weight:900; color:#2E7BE6;">${est_premium:.1f}M</div>
                    </div>
                    <div>
                        <div style="font-size:0.7em; font-weight:700; color:#94a3b8; letter-spacing:1px;">PAYLOAD VALUE</div>
                        <div style="font-size:2.2em; font-weight:900; color:#1e293b;">${payload_value}M</div>
                    </div>
                </div>
            </div>
            <p style="font-size:0.75em; color:#94a3b8; margin-top:8px; text-align:center;">
                Estimate based on historical failure rate, launch count confidence, streak discount, and reusability factor. Actual premiums vary by mission, orbit, and market conditions.
            </p>
            """, unsafe_allow_html=True)

        # --- Description ---
        if selected["description"]:
            st.markdown("<div class='section-title'>Description</div>", unsafe_allow_html=True)
            st.markdown(
                f"<div class='card'><p>{selected['description']}</p></div>",
                unsafe_allow_html=True,
            )

        # --- IV. Score Comparison ---
        st.markdown("<div class='section-title'>IV. Score Comparison</div>", unsafe_allow_html=True)

        sc1, sc2, sc3 = st.columns(3)

        t1 = int(selected.get("total", 0))
        t_html = f'<span style="color:#2E7BE6;">{t1}</span>'
        saved = st.session_state.saved_rocket_data
        if saved:
            t2 = int(saved.get("total", 0))
            t_html += f' <span style="font-size:0.5em; color:#666;">vs</span> <span style="color:#F4A261;">{t2}</span>'
        sc1.markdown(
            f'<div class="card"><div style="font-size:11px; color:#999;">TOTAL SCORE</div>'
            f'<div style="font-size:22px; font-weight:900;">{t_html}</div></div>',
            unsafe_allow_html=True,
        )

        axes1 = selected.get("axes", {})
        best1 = max(axes1, key=axes1.get) if axes1 else "N/A"
        best1_val = int(axes1.get(best1, 0))
        sc2.markdown(
            f'<div class="card"><div style="font-size:11px; color:#999;">STRONGEST AXIS</div>'
            f'<div style="font-size:18px; font-weight:900;"><span style="color:#2E7BE6;">{best1} ({best1_val})</span></div></div>',
            unsafe_allow_html=True,
        )

        worst1 = min(axes1, key=axes1.get) if axes1 else "N/A"
        worst1_val = int(axes1.get(worst1, 0))
        sc3.markdown(
            f'<div class="card"><div style="font-size:11px; color:#999;">WEAKEST AXIS</div>'
            f'<div style="font-size:18px; font-weight:900;"><span style="color:#ef4444;">{worst1} ({worst1_val})</span></div></div>',
            unsafe_allow_html=True,
        )

        # --- V. Score History ---
        history = _load_scores_history()
        if history:
            rocket_full = selected["full_name"]
            dates = sorted(history.keys())
            hist_dates = []
            hist_scores = []
            for d in dates:
                s = history[d].get(rocket_full)
                if s is not None:
                    hist_dates.append(d)
                    hist_scores.append(s)
            if len(hist_dates) >= 1:
                st.markdown("<div class='section-title'>V. Score History</div>", unsafe_allow_html=True)
                fig_hist = go.Figure()
                fig_hist.add_trace(go.Scatter(
                    x=hist_dates, y=hist_scores,
                    mode="lines",
                    line=dict(color="#2E7BE6", width=2),
                    fill="tozeroy", fillcolor="rgba(46,123,230,0.05)",
                ))
                fig_hist.update_layout(
                    yaxis=dict(range=[0, 1000], title="Score"),
                    height=250,
                    margin=dict(l=0, r=0, t=10, b=0),
                    plot_bgcolor="white",
                    hovermode="x unified",
                    clickmode="none",
                    dragmode=False,
                )
                st.plotly_chart(fig_hist, use_container_width=True, config={"displayModeBar": False}, key="score_history_detail")

        # --- V-b. Daily Score Tracker ---
        st.markdown("<div class='section-title'>Daily Score Tracker</div>", unsafe_allow_html=True)
        render_daily_score_tracker(selected["full_name"])

        # --- VI. Latest News ---
        st.markdown("<div class='section-title'>VI. Latest News</div>", unsafe_allow_html=True)
        news = fetch_rocket_news(selected["name"], max_items=5)
        if news:
            for article in news:
                st.markdown(
                    f'<div style="padding:10px 0; border-bottom:1px solid #F0F0F0;">'
                    f'<a href="{article["url"]}" target="_blank" style="font-size:0.95em; font-weight:600; color:#1e3a8a; text-decoration:none;">{article["title"]}</a>'
                    f'<div style="font-size:0.8em; color:#999; margin-top:3px;">{article["source"]} · {article["date"]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No recent news available.")

# ===================================================================
# RANKINGS TAB
# ===================================================================
with tab_rank:
    st.markdown(
        "<div style='font-size:1.5em; font-weight:900; color:#1e3a8a; margin-bottom:20px;'>"
        "All Rockets Ranking</div>",
        unsafe_allow_html=True,
    )

    # Sort option
    sort_by = st.selectbox("Sort by", ["Total Score"] + AXES_LABELS, key="rank_sort")

    ranking_scores = list(filtered)
    if sort_by == "Total Score":
        ranking_scores.sort(key=lambda x: x["total"], reverse=True)
    else:
        ranking_scores.sort(key=lambda x: x["axes"].get(sort_by, 0), reverse=True)

    # CSV export for full ranking
    rank_export = []
    for idx, s in enumerate(ranking_scores, 1):
        row = {
            "Rank": idx,
            "Rocket": s["full_name"],
            "Total Score": int(s["total"]),
            "Country": s.get("country_code", ""),
            "Reusable": s["reusable"],
            "Active": s.get("active", False),
            "Total Launches": s["total_launches"],
            "Success Rate (%)": s["success_rate"],
        }
        for axis in AXES_LABELS:
            row[axis] = s["axes"].get(axis, 0)
        rank_export.append(row)
    csv_rank_buf = io.StringIO()
    pd.DataFrame(rank_export).to_csv(csv_rank_buf, index=False)
    st.download_button("Download Excel (All Rockets)", csv_rank_buf.getvalue(), "rocket_1000_rankings.csv", "text/csv", key="btn_csv_rank")

    # Render ranked cards
    for idx, s in enumerate(ranking_scores, 1):
        score = int(s["total"])
        bar_color = _border_color(score)
        country = _country_label(s.get("country_code", ""))
        country_tag = f"<span style='font-size:0.7em; color:#94a3b8; margin-left:6px;'>{country}</span>" if country else ""

        st.markdown(
            f"""
            <div style="display:flex; align-items:center; padding:14px 20px; background:#fff; border-radius:12px; margin-bottom:8px; border:1px solid #e2e8f0; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                <div style="font-size:1.4em; font-weight:900; color:#94a3b8; width:40px;">#{idx}</div>
                <div style="flex:1;">
                    <div style="font-size:1.05em; font-weight:700; color:#1e293b;">{s['full_name']}{country_tag}</div>
                    <span style="font-size:0.75em; background:#2E7BE6; color:#fff; padding:2px 8px; border-radius:20px;">{s['total_launches']} launches</span>
                    <span style="font-size:0.75em; background:{'#10b981' if s['reusable'] else '#94a3b8'}; color:#fff; padding:2px 8px; border-radius:20px; margin-left:4px;">
                        {"Reusable" if s['reusable'] else "Expendable"}
                    </span>
                    <span style="font-size:0.75em; background:{'#3b82f6' if s.get('active') else '#94a3b8'}; color:#fff; padding:2px 8px; border-radius:20px; margin-left:4px;">
                        {"Active" if s.get('active') else "Retired"}
                    </span>
                </div>
                <div style="text-align:right; min-width:80px;">
                    <div style="font-size:1.5em; font-weight:900; color:{bar_color};">{score}</div>
                    <div style="background:#f1f5f9; border-radius:4px; height:6px; width:80px; margin-top:4px;">
                        <div style="background:{bar_color}; height:6px; border-radius:4px; width:{score/10}%;"></div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # --- Score Distribution bar chart ---
    st.markdown("<div class='section-title'>Score Distribution</div>", unsafe_allow_html=True)

    bar_colors = []
    for s in ranking_scores:
        if s["total"] >= 700:
            bar_colors.append("#10b981")
        elif s["total"] >= 500:
            bar_colors.append("#2E7BE6")
        elif s["total"] >= 300:
            bar_colors.append("#f59e0b")
        else:
            bar_colors.append("#ef4444")

    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        x=[s["name"] for s in ranking_scores],
        y=[s["total"] for s in ranking_scores],
        marker_color=bar_colors,
        text=[int(s["total"]) for s in ranking_scores],
        textposition="outside",
    ))
    fig_bar.update_layout(
        yaxis=dict(range=[0, 1000], title="Score"),
        xaxis_tickangle=-45,
        height=500,
        margin=dict(l=0, r=0, t=10, b=150),
        plot_bgcolor="white",
        clickmode="none",
        dragmode=False,
    )
    st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False}, key="rank_score_dist")

    # --- Axis Breakdown stacked bar ---
    st.markdown("<div class='section-title'>Axis Breakdown</div>", unsafe_allow_html=True)

    axis_colors = ["#2E7BE6", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444"]
    fig_stack = go.Figure()
    for j, axis in enumerate(AXES_LABELS):
        fig_stack.add_trace(go.Bar(
            x=[s["name"] for s in ranking_scores],
            y=[s["axes"].get(axis, 0) for s in ranking_scores],
            name=axis,
            marker_color=axis_colors[j],
        ))
    fig_stack.update_layout(
        barmode="stack",
        yaxis=dict(title="Score"),
        xaxis_tickangle=-45,
        height=500,
        margin=dict(l=0, r=0, t=10, b=150),
        plot_bgcolor="white",
        clickmode="none",
        dragmode=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig_stack, use_container_width=True, config={"displayModeBar": False}, key="rank_axis_breakdown")

# ===================================================================
# INSURANCE TAB
# ===================================================================
with tab_ins:
    st.markdown(
        "<div style='font-size:1.5em; font-weight:900; color:#1e3a8a; margin-bottom:5px;'>"
        "Insurance Premium Estimator</div>"
        "<p style='color:#64748b; margin-bottom:20px;'>"
        "Estimate launch insurance premiums for all rockets based on failure rate, launch confidence, streak, and reusability.</p>",
        unsafe_allow_html=True,
    )

    ins_payload = st.number_input(
        "Payload Value ($ million)",
        min_value=1, max_value=2000, value=200, step=10,
        key="ins_tab_payload",
    )

    # Build insurance data for all rockets
    ins_data = []
    for r in all_scored:
        rate = estimate_premium_rate(
            r["success_rate"],
            r["total_launches"],
            r.get("consecutive_successes", 0),
            r["reusable"],
        )
        premium = ins_payload * rate
        ins_data.append({
            "rocket": r,
            "rate": rate,
            "premium": premium,
        })

    ins_data.sort(key=lambda x: x["rate"])

    # Summary cards
    lowest = ins_data[0]
    highest = ins_data[-1]
    avg_rate = sum(d["rate"] for d in ins_data) / len(ins_data)

    s1, s2, s3 = st.columns(3)
    s1.markdown(
        f"""<div style="background:#f0fdf4; padding:20px; border-radius:12px; text-align:center; border:1px solid #d1fae5;">
            <div style="font-size:0.7em; font-weight:700; color:#10b981; letter-spacing:1px;">LOWEST RATE</div>
            <div style="font-size:2em; font-weight:900; color:#10b981;">{lowest['rate']*100:.1f}%</div>
            <div style="font-size:0.85em; color:#64748b;">{lowest['rocket']['full_name']}</div>
        </div>""",
        unsafe_allow_html=True,
    )
    s2.markdown(
        f"""<div style="background:#fff; padding:20px; border-radius:12px; text-align:center; border:1px solid #e2e8f0;">
            <div style="font-size:0.7em; font-weight:700; color:#94a3b8; letter-spacing:1px;">AVERAGE RATE</div>
            <div style="font-size:2em; font-weight:900; color:#2E7BE6;">{avg_rate*100:.1f}%</div>
            <div style="font-size:0.85em; color:#64748b;">{len(ins_data)} rockets</div>
        </div>""",
        unsafe_allow_html=True,
    )
    s3.markdown(
        f"""<div style="background:#fef2f2; padding:20px; border-radius:12px; text-align:center; border:1px solid #fecaca;">
            <div style="font-size:0.7em; font-weight:700; color:#ef4444; letter-spacing:1px;">HIGHEST RATE</div>
            <div style="font-size:2em; font-weight:900; color:#ef4444;">{highest['rate']*100:.1f}%</div>
            <div style="font-size:0.85em; color:#64748b;">{highest['rocket']['full_name']}</div>
        </div>""",
        unsafe_allow_html=True,
    )

    st.markdown("<div class='section-title'>Premium Rate Ranking</div>", unsafe_allow_html=True)

    # CSV export
    ins_export = []
    for idx, d in enumerate(ins_data, 1):
        r = d["rocket"]
        ins_export.append({
            "Rank": idx,
            "Rocket": r["full_name"],
            "Premium Rate (%)": round(d["rate"] * 100, 2),
            f"Est. Premium ($M, payload ${ins_payload}M)": round(d["premium"], 2),
            "ROCKET-1000 Score": int(r["total"]),
            "Success Rate (%)": r["success_rate"],
            "Total Launches": r["total_launches"],
            "Consecutive Successes": r.get("consecutive_successes", 0),
            "Reusable": r["reusable"],
            "Country": r.get("country_code", ""),
        })
    csv_ins_buf = io.StringIO()
    pd.DataFrame(ins_export).to_csv(csv_ins_buf, index=False)
    st.download_button("Download Excel", csv_ins_buf.getvalue(), "rocket_insurance_estimates.csv", "text/csv", key="btn_csv_ins")

    # Ranked list
    for idx, d in enumerate(ins_data, 1):
        r = d["rocket"]
        rate = d["rate"]
        premium = d["premium"]
        rate_color = "#10b981" if rate < 0.05 else "#f59e0b" if rate < 0.10 else "#ef4444"
        country = r.get("country_code", "")
        country_tag = f"<span style='font-size:0.7em; color:#94a3b8; margin-left:6px;'>{country}</span>" if country else ""

        st.markdown(
            f"""
            <div style="display:flex; align-items:center; padding:14px 20px; background:#fff; border-radius:12px; margin-bottom:8px; border:1px solid #e2e8f0; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                <div style="font-size:1.4em; font-weight:900; color:#94a3b8; width:40px;">#{idx}</div>
                <div style="flex:1;">
                    <div style="font-size:1.05em; font-weight:700; color:#1e293b;">{r['full_name']}{country_tag}</div>
                    <span style="font-size:0.75em; background:#2E7BE6; color:#fff; padding:2px 8px; border-radius:20px;">{r['total_launches']} launches</span>
                    <span style="font-size:0.75em; background:{'#10b981' if r['reusable'] else '#94a3b8'}; color:#fff; padding:2px 8px; border-radius:20px; margin-left:4px;">
                        {"Reusable" if r['reusable'] else "Expendable"}
                    </span>
                    <span style="font-size:0.75em; color:#64748b; margin-left:8px;">Score: {int(r['total'])}</span>
                </div>
                <div style="text-align:right; min-width:160px;">
                    <div style="font-size:1.3em; font-weight:900; color:{rate_color};">{rate*100:.1f}%</div>
                    <div style="font-size:0.85em; color:#64748b;">Est. ${premium:.1f}M</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Rate distribution chart
    st.markdown("<div class='section-title'>Premium Rate Distribution</div>", unsafe_allow_html=True)
    rate_colors = ["#10b981" if d["rate"] < 0.05 else "#f59e0b" if d["rate"] < 0.10 else "#ef4444" for d in ins_data]
    fig_ins = go.Figure()
    fig_ins.add_trace(go.Bar(
        x=[d["rocket"]["name"] for d in ins_data],
        y=[d["rate"] * 100 for d in ins_data],
        marker_color=rate_colors,
        text=[f'{d["rate"]*100:.1f}%' for d in ins_data],
        textposition="outside",
    ))
    fig_ins.update_layout(
        yaxis=dict(title="Premium Rate (%)", range=[0, 30]),
        xaxis_tickangle=-45,
        height=500,
        margin=dict(l=0, r=0, t=10, b=150),
        plot_bgcolor="white",
        clickmode="none",
        dragmode=False,
    )
    st.plotly_chart(fig_ins, use_container_width=True, config={"displayModeBar": False}, key="ins_rate_dist")

    st.markdown(
        "<p style='text-align:center; color:#94a3b8; font-size:0.8em; margin-top:10px;'>"
        "Estimates based on historical failure rate, launch count confidence, streak discount, and reusability factor. "
        "Actual premiums vary by mission profile, orbit type, satellite value, and market conditions.</p>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Disclaimer
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown(
    "<p style='text-align:center; color:#999; font-size:12px;'>"
    "This tool is for informational purposes only. Scores are derived from publicly available launch data "
    "from the Launch Library 2 API. Not affiliated with any space agency or launch provider."
    "</p>",
    unsafe_allow_html=True,
)
