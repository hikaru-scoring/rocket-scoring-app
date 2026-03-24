"""Methodology page — accessed via Streamlit sidebar navigation."""
import streamlit as st

st.markdown("""
<div style="text-align:center; margin:20px 0 30px;">
    <div style="font-size:2.5em; font-weight:900; color:#2E7BE6; letter-spacing:-1px;">ROCKET-1000</div>
    <div style="font-size:1.2em; color:#64748b;">Scoring Methodology</div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
### What is ROCKET-1000?

ROCKET-1000 is a multi-dimensional scoring framework that evaluates every launch vehicle on the **same 0 to 1,000 scale**.
Each rocket is scored across **5 axes**, each worth a maximum of **200 points**.

This is not a recommendation to use or invest in any launch provider. It is a screening and comparison tool.
""")

st.markdown("---")

m1, m2 = st.columns(2)
with m1:
    st.markdown("""
    #### 1. Track Record (200 pts)
    **What:** Historical launch success rate, adjusted for confidence.

    **Formula:** `(Successful / Total) x 200 x Confidence`

    Confidence = min(Total Launches / 10, 1.0). Rockets with fewer than 10 launches are penalized to prevent a rocket with 2/2 successes from outscoring one with 190/200.

    ---

    #### 2. Reliability Streak (200 pts)
    **What:** Current run of consecutive successful launches.

    **Formula:** `Consecutive Successes x 2 (capped at 200)`

    100 consecutive successes = perfect score. A single failure resets this to zero.

    ---

    #### 3. Payload Capacity (200 pts)
    **What:** Payload to LEO (75%) combined with thrust power (25%).

    **Formula:** `0.75 x (log2(LEO kg) / 15) x 200 + 0.25 x (log2(Thrust kN) / 17) x 200`

    Both use logarithmic scale so heavy-lift rockets don't make everything else look like zero. If LEO data is missing, GTO x 2 is used as a proxy. If only one data point is available, that component is used at 100%.
    """)
with m2:
    st.markdown("""
    #### 4. Cost Efficiency (200 pts)
    **What:** Cost per kilogram to orbit.

    **Formula:** `(5.5 - log10(cost/kg)) x 75 (capped at 200)`

    Lower cost per kg = higher score. When cost data is unavailable (common for older rockets), a neutral score of 100 is assigned.

    ---

    #### 5. Reusability & Innovation (200 pts)
    **What:** Landing capability and reuse track record.

    **Formula:** `Base + Landing Success Rate x 100`

    - Reusable rockets start at 100 points
    - Expendable rockets start at 50 points
    - Landing success rate adds up to 100 bonus points

    A fully reusable rocket with 100% landing success = 200 points.

    ---

    #### Insurance Premium Estimator
    **What:** Estimated launch insurance premium rate.

    **Formula:** `Failure Rate x 1.75 + Confidence Adjustment - Streak Discount x Reusability Factor`

    - Low launch count (< 5): +10% surcharge
    - Consecutive success streak: up to -1.5% discount
    - Proven reusable (50+ launches): 10% discount
    - Range: 1.5% (floor) to 25% (ceiling)
    """)

st.markdown("---")

st.markdown("""
### Data Source

All launch data comes from the **Launch Library 2 API** (thespacedevs.com), which aggregates information from official space agency records and public sources.

Only rockets with **at least 1 launch** are scored.

### Limitations

- **Cost data** is missing for many rockets, resulting in a neutral 100/200 score
- **New rockets** with few launches receive a confidence penalty on Track Record
- **Landing data** may not capture all attempted recoveries
- **Insurance estimates** are approximations based on historical failure rates, not actual market pricing
- Scores update when the API data updates (cached for 1 hour)
""")
