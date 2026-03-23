# app.py
"""ROCKET-1000 — Launch Vehicle Scoring Platform."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data_logic import AXES_LABELS, LOGIC_DESC, score_all_launchers
from ui_components import inject_css, render_radar_chart

APP_TITLE = "ROCKET-1000 — Launch Vehicle Scoring Platform"
st.set_page_config(page_title=APP_TITLE, layout="wide")

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
tab_dash, tab_detail, tab_rank = st.tabs(["Dashboard", "Rocket Detail", "Rankings"])

# ===================================================================
# DASHBOARD TAB
# ===================================================================
with tab_dash:
    st.markdown(
        "<div style='font-size:1.5em; font-weight:900; color:#1e3a8a; margin-bottom:5px;'>"
        "ROCKET-1000 — Launch Vehicle Scoring Platform</div>"
        "<p style='color:#64748b; margin-bottom:20px;'>"
        "Comprehensive scoring of launch vehicles based on track record, reliability, payload, cost, and reusability.</p>",
        unsafe_allow_html=True,
    )

    # --- Top 10 / Bottom 10 ---
    top_col, bot_col = st.columns(2)
    with top_col:
        st.markdown(
            "<div style='font-size:1em; font-weight:700; color:#10b981; margin-bottom:10px;'>Top 10 Rockets</div>",
            unsafe_allow_html=True,
        )
        for s in all_scored[:10]:
            score = s["total"]
            st.markdown(
                f"""<div style="background:#f0fdf4; padding:8px 12px; border-radius:8px; margin-bottom:4px; display:flex; justify-content:space-between;">
                    <span style="font-weight:600;">{s['full_name']}</span>
                    <span style="font-weight:900; color:#10b981;">{int(score)}</span>
                </div>""",
                unsafe_allow_html=True,
            )
    with bot_col:
        st.markdown(
            "<div style='font-size:1em; font-weight:700; color:#ef4444; margin-bottom:10px;'>Bottom 10 Rockets</div>",
            unsafe_allow_html=True,
        )
        for s in all_scored[-10:]:
            score = s["total"]
            st.markdown(
                f"""<div style="background:#fef2f2; padding:8px 12px; border-radius:8px; margin-bottom:4px; display:flex; justify-content:space-between;">
                    <span style="font-weight:600;">{s['full_name']}</span>
                    <span style="font-weight:900; color:#ef4444;">{int(score)}</span>
                </div>""",
                unsafe_allow_html=True,
            )

    # --- All Rockets Grid ---
    st.markdown("<div class='section-title'>All Rockets</div>", unsafe_allow_html=True)

    cols = st.columns(3)
    for i, rocket in enumerate(all_scored):
        score = rocket["total"]
        border = _border_color(score)
        with cols[i % 3]:
            st.markdown(
                f"""<div style="background:#fff; border-radius:12px; padding:18px; margin-bottom:12px;
                border-left:4px solid {border}; box-shadow:0 2px 8px rgba(0,0,0,0.04);">
                <div style="font-size:0.95em; font-weight:700; color:#1e293b; margin:2px 0;">
                {rocket['full_name']}</div>
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
    selected_name = st.selectbox("Select a rocket", rocket_names, key="rocket_select")
    selected = next((r for r in all_scored if r["full_name"] == selected_name), None)

    if selected:
        total = int(selected["total"])

        # --- Save / Clear buttons ---
        col_btn1, col_btn2, col_btn_rest = st.columns([1, 1, 8])
        with col_btn1:
            save_it = st.button("Save", key="btn_save")
        with col_btn2:
            clear_it = st.button("Clear", key="btn_clear")

        if save_it:
            st.session_state.saved_rocket_data = selected
            st.rerun()
        if clear_it:
            st.session_state.saved_rocket_data = None
            st.rerun()

        # --- Total Score ---
        st.markdown(f"""
        <div style="text-align:center; margin-top:4px; margin-bottom:10px;">
            <div style="font-size:14px; letter-spacing:2px; color:#666;">TOTAL SCORE</div>
            <div style="font-size:90px; font-weight:800; color:#2E7BE6; line-height:1;">
                {total}
                <span style="font-size:35px; color:#BBB;">/ 1000</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

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

                score_html = f'<span style="color: #2E7BE6;">{int(v1)}</span>'
                if v2 is not None:
                    score_html += f' <span style="color: #ccc; font-size: 0.9em; font-weight:bold; margin: 0 6px;">vs</span> <span style="color: #F4A261;">{int(v2)}</span>'

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
                        st.markdown("**Formula:** `(Successful Launches / Total Launches) x 200`\n\n**Source:** Launch Library 2 API")
                    elif axis == "Reliability Streak":
                        st.markdown("**Formula:** `Consecutive Successful Launches x 2 (capped at 200)`\n\n**Source:** Launch Library 2 API")
                    elif axis == "Payload Capacity":
                        st.markdown("**Formula:** `LEO Capacity / 150 (capped at 200)`\n\n**Source:** Launch Library 2 API")
                    elif axis == "Cost Efficiency":
                        st.markdown("**Formula:** `200 - (Cost per kg / 50) (capped at 200)`\n\n**Source:** Launch Library 2 API")
                    elif axis == "Reusability & Innovation":
                        st.markdown("**Formula:** `Base (100 if reusable, 50 if not) + Landing Success Rate x 100`\n\n**Source:** Launch Library 2 API")

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

    ranking_scores = list(all_scored)  # copy to avoid mutating original
    if sort_by == "Total Score":
        ranking_scores.sort(key=lambda x: x["total"], reverse=True)
    else:
        ranking_scores.sort(key=lambda x: x["axes"].get(sort_by, 0), reverse=True)

    # Render ranked cards (matching GOV-1000 style)
    for idx, s in enumerate(ranking_scores, 1):
        score = int(s["total"])
        bar_color = _border_color(score)

        st.markdown(
            f"""
            <div style="display:flex; align-items:center; padding:14px 20px; background:#fff; border-radius:12px; margin-bottom:8px; border:1px solid #e2e8f0; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                <div style="font-size:1.4em; font-weight:900; color:#94a3b8; width:40px;">#{idx}</div>
                <div style="flex:1;">
                    <div style="font-size:1.05em; font-weight:700; color:#1e293b;">{s['full_name']}</div>
                    <span style="font-size:0.75em; background:#2E7BE6; color:#fff; padding:2px 8px; border-radius:20px;">{s['total_launches']} launches</span>
                </div>
                <div style="text-align:right; margin-right:15px; font-size:0.85em; color:#94a3b8;">
                    {"Reusable" if s['reusable'] else "Expendable"}
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
