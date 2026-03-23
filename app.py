# app.py
"""ROCKET-1000 — Launch Vehicle Scoring Platform."""
import pandas as pd
import plotly.express as px
import streamlit as st

from data_logic import AXES_LABELS, LOGIC_DESC, score_all_launchers
from ui_components import inject_css, render_radar_chart

APP_TITLE = "ROCKET-1000 — Launch Vehicle Scoring Platform"
st.set_page_config(page_title=APP_TITLE, layout="wide")
inject_css()


def _score_color(score: float) -> str:
    if score >= 700:
        return "#22C55E"
    if score >= 500:
        return "#2E7BE6"
    if score >= 300:
        return "#EAB308"
    return "#EF4444"


def _border_color(score: float) -> str:
    if score >= 700:
        return "#22C55E"
    if score >= 500:
        return "#2E7BE6"
    if score >= 300:
        return "#EAB308"
    return "#EF4444"


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

# ===== DASHBOARD TAB =====
with tab_dash:
    st.markdown(f"<h1 style='text-align:center; font-weight:900; margin-bottom:5px;'>{APP_TITLE}</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#666; margin-bottom:30px;'>Comprehensive scoring of launch vehicles based on track record, reliability, payload, cost, and reusability.</p>", unsafe_allow_html=True)

    cols = st.columns(3)
    for idx, rocket in enumerate(all_scored):
        col = cols[idx % 3]
        color = _border_color(rocket["total"])
        with col:
            st.markdown(f"""
                <div class="rocket-grid-card" style="border-left: 4px solid {color};">
                    <div class="rocket-grid-name">{rocket['full_name']}</div>
                    <div class="rocket-grid-launches">{rocket['total_launches']} launches</div>
                    <div class="rocket-grid-score" style="color: {color};">{rocket['total']}</div>
                </div>
            """, unsafe_allow_html=True)

# ===== ROCKET DETAIL TAB =====
with tab_detail:
    rocket_names = [r["full_name"] for r in all_scored]
    selected_name = st.selectbox("Select a rocket", rocket_names, key="rocket_select")
    selected = next((r for r in all_scored if r["full_name"] == selected_name), None)

    if selected:
        # Total score
        score_color = _score_color(selected["total"])
        st.markdown(f"""
            <div class="total-score-container">
                <div class="total-score-label">TOTAL SCORE</div>
                <div class="total-score-val" style="color: {score_color};">{selected['total']}</div>
            </div>
        """, unsafe_allow_html=True)

        # Radar chart + axis scores
        col_radar, col_axes = st.columns([3, 2])
        with col_radar:
            st.markdown('<div class="section-title">Score Profile</div>', unsafe_allow_html=True)

            # Compare selector
            compare_options = ["None"] + [r["full_name"] for r in all_scored if r["full_name"] != selected_name]
            compare_name = st.selectbox("Compare with", compare_options, key="compare_select")
            compare_data = None
            if compare_name != "None":
                compare_data = next((r for r in all_scored if r["full_name"] == compare_name), None)

            fig = render_radar_chart(selected, compare_data, AXES_LABELS)
            st.plotly_chart(fig, use_container_width=True, key="radar_chart")

        with col_axes:
            st.markdown('<div class="section-title">Score Breakdown</div>', unsafe_allow_html=True)
            for axis_name in AXES_LABELS:
                val = selected["axes"][axis_name]
                st.markdown(f"""
                    <div class="dna-card">
                        <div>
                            <div class="dna-label">{axis_name}</div>
                            <div style="font-size:11px; color:#999;">{LOGIC_DESC[axis_name]}</div>
                        </div>
                        <div class="dna-value">{val}</div>
                    </div>
                """, unsafe_allow_html=True)

        # Specs snapshot
        st.markdown('<div class="section-title">Specs Snapshot</div>', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Total Launches", selected["total_launches"])
        with c2:
            st.metric("Success Rate", f"{selected['success_rate']}%")
        with c3:
            leo_str = f"{selected['leo_capacity']:,.0f} kg" if selected["leo_capacity"] else "N/A"
            st.metric("LEO Capacity", leo_str)
        with c4:
            cost_str = f"${selected['launch_cost']:,.0f}" if selected["launch_cost"] else "N/A"
            st.metric("Cost / Launch", cost_str)

        # Additional specs
        st.markdown('<div class="section-title">Vehicle Specs</div>', unsafe_allow_html=True)
        s1, s2, s3, s4 = st.columns(4)
        with s1:
            length_str = f"{selected['length']} m" if selected.get("length") else "N/A"
            st.metric("Length", length_str)
        with s2:
            diam_str = f"{selected['diameter']} m" if selected.get("diameter") else "N/A"
            st.metric("Diameter", diam_str)
        with s3:
            mass_str = f"{selected['launch_mass']:,.0f} t" if selected.get("launch_mass") else "N/A"
            st.metric("Launch Mass", mass_str)
        with s4:
            st.metric("Reusable", "Yes" if selected["reusable"] else "No")

        # Description
        if selected["description"]:
            st.markdown('<div class="section-title">Description</div>', unsafe_allow_html=True)
            st.markdown(f"<div class='card'><p>{selected['description']}</p></div>", unsafe_allow_html=True)

        # Maiden flight
        if selected["maiden_flight"]:
            st.markdown(f"<p style='color:#999; font-size:13px; margin-top:10px;'>Maiden flight: {selected['maiden_flight']}</p>", unsafe_allow_html=True)

# ===== RANKINGS TAB =====
with tab_rank:
    st.markdown('<div class="section-title">All Rockets Ranked by Score</div>', unsafe_allow_html=True)

    # Rankings table
    rank_data = []
    for i, r in enumerate(all_scored, 1):
        rank_data.append({
            "Rank": i,
            "Rocket": r["full_name"],
            "Total Score": r["total"],
            "Track Record": r["axes"]["Track Record"],
            "Reliability": r["axes"]["Reliability Streak"],
            "Payload": r["axes"]["Payload Capacity"],
            "Cost Eff.": r["axes"]["Cost Efficiency"],
            "Reusability": r["axes"]["Reusability & Innovation"],
            "Launches": r["total_launches"],
            "Reusable": "Yes" if r["reusable"] else "No",
        })
    df_rank = pd.DataFrame(rank_data)
    st.dataframe(df_rank, use_container_width=True, hide_index=True, key="rankings_table")

    # Score distribution chart
    st.markdown('<div class="section-title">Score Distribution</div>', unsafe_allow_html=True)
    df_chart = pd.DataFrame({
        "Rocket": [r["full_name"] for r in all_scored],
        "Score": [r["total"] for r in all_scored],
    })
    colors = [_score_color(r["total"]) for r in all_scored]
    fig_bar = px.bar(
        df_chart,
        x="Rocket",
        y="Score",
        color="Score",
        color_continuous_scale=["#EF4444", "#EAB308", "#2E7BE6", "#22C55E"],
        range_color=[0, 1000],
    )
    fig_bar.update_layout(
        xaxis_tickangle=-45,
        height=500,
        margin=dict(b=150),
        showlegend=False,
    )
    st.plotly_chart(fig_bar, use_container_width=True, key="score_distribution")

# ---------------------------------------------------------------------------
# Disclaimer
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown(
    "<p style='text-align:center; color:#999; font-size:12px;'>"
    "This tool is for informational purposes only. Scores are derived from publicly available launch data. "
    "Not affiliated with any space agency or launch provider."
    "</p>",
    unsafe_allow_html=True,
)
