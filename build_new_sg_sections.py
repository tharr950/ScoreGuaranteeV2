"""
Appends four new sections to app.py:
  1. Refund Revenue
  2. Reached Goal — First Test
  3. Reached Goal — After Awarded Hours
  4. Guarantee vs. Other Premium Revenue (with monthly trend chart)

Adds an advisor filter that applies to all of the above plus notes it
should be threaded through the existing compliance table too.

Also adds a MySQL connection helper and removes the orphaned
'# PAGE — FULL ROSTER' marker at the end of the file.
"""
import re

APP_PATH = "app.py"

with open(APP_PATH, "r") as f:
    content = f.read()

# ── 1. Add MySQL connection helper right after get_redshift_connection ──
mysql_helper = '''

# ── MySQL connection (advisor lookups for Premium comparison) ────────────
def get_mysql_connection():
    import mysql.connector
    creds = st.secrets["mysql"]
    if "mysql_conn" not in st.session_state:
        st.session_state.mysql_conn = mysql.connector.connect(
            host=creds["host"], user=creds["user"], password=creds["password"],
            charset="utf8mb4", auth_plugin="mysql_native_password",
        )
    return st.session_state.mysql_conn
'''

redshift_marker = "# ── Redshift connection ──────────────────────────────────────────────────\ndef get_redshift_connection():"
if redshift_marker in content:
    idx = content.index(redshift_marker)
    end_of_func = content.index("\n\n", content.index("return", idx))
    content = content[:end_of_func] + mysql_helper + content[end_of_func:]
    print("Added MySQL connection helper")
else:
    print("WARNING: redshift connection marker not found — MySQL helper NOT added, add manually")

# ── 2. New data loader functions ─────────────────────────────────────────
new_loaders = '''

@st.cache_data(ttl=3600)
def load_sg_bookings_and_refunds():
    """All booking-level rows for SG packages: net revenue + real refunds."""
    conn = get_redshift_connection()
    query = """
    WITH sg_packages AS (
        SELECT id AS package_id, student_id, won_at
        FROM dw.tutor_packages
        WHERE name ILIKE '%%Score Guarantee%%'
    )
    SELECT
        sg.package_id, sg.student_id, sg.won_at,
        b.amount, b.booked_at
    FROM sg_packages sg
        LEFT JOIN dw.bookings b ON b.item_type = 'TutorPackage' AND b.item_id = sg.package_id
    """
    df = pd.read_sql(query, conn)
    df["won_at"] = pd.to_datetime(df["won_at"], errors="coerce")
    df["booked_at"] = pd.to_datetime(df["booked_at"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=3600)
def load_awarded_hours():
    """
    Detects 'awarded' (free) follow-up packages: a later package for the
    same SG student, real hours, $0 net revenue, excluding Transcript
    Adjustment lines. All via Redshift (dw.tutor_packages/bookings/line_items).
    """
    conn = get_redshift_connection()
    query = """
    WITH sg_packages AS (
        SELECT id AS sg_package_id, student_id, won_at AS sg_won_at
        FROM dw.tutor_packages
        WHERE name ILIKE '%%Score Guarantee%%'
    ),
    candidate_followups AS (
        SELECT
            sg.sg_package_id, sg.student_id, sg.sg_won_at,
            tp.id AS package_id, tp.won_at, tp.duration/60.0 AS package_hours, tp.name
        FROM sg_packages sg
            JOIN dw.tutor_packages tp
                ON tp.student_id = sg.student_id
                AND tp.won_at > sg.sg_won_at
                AND tp.id != sg.sg_package_id
        WHERE tp.name NOT ILIKE '%%Transcript Adjustment%%'
            AND tp.name NOT ILIKE '%%Score Guarantee%%'
    ),
    followup_revenue AS (
        SELECT
            cf.sg_package_id, cf.student_id, cf.package_id, cf.won_at,
            cf.package_hours, cf.name,
            SUM(b.amount) AS net_revenue
        FROM candidate_followups cf
            LEFT JOIN dw.bookings b ON b.item_type = 'TutorPackage' AND b.item_id = cf.package_id
        GROUP BY cf.sg_package_id, cf.student_id, cf.package_id, cf.won_at, cf.package_hours, cf.name
    )
    SELECT * FROM followup_revenue
    WHERE package_hours > 0 AND (net_revenue = 0 OR net_revenue IS NULL)
    """
    df = pd.read_sql(query, conn)
    df["won_at"] = pd.to_datetime(df["won_at"], errors="coerce")
    return df


@st.cache_data(ttl=3600)
def load_premium_vs_sg_monthly():
    """
    Monthly net revenue for SG packages vs. all other Premium packages,
    for the Guarantee-vs-Premium comparison chart.
    """
    conn = get_redshift_connection()
    query = """
    WITH premium_packages AS (
        SELECT tp.id AS package_id, tp.student_id, tp.won_at, tp.name,
            CASE WHEN tp.name ILIKE '%%Score Guarantee%%' THEN 1 ELSE 0 END AS is_sg
        FROM dw.tutor_packages tp
        WHERE tp.name ILIKE '%%Premium%%'
            AND tp.name NOT ILIKE '%%Transcript Adjustment%%'
            AND tp.status = 'won'
    )
    SELECT
        pp.package_id, pp.student_id, pp.won_at, pp.is_sg,
        SUM(b.amount) AS net_revenue
    FROM premium_packages pp
        LEFT JOIN dw.bookings b ON b.item_type = 'TutorPackage' AND b.item_id = pp.package_id
    GROUP BY pp.package_id, pp.student_id, pp.won_at, pp.is_sg
    """
    df = pd.read_sql(query, conn)
    df["won_at"] = pd.to_datetime(df["won_at"], errors="coerce")
    df["net_revenue"] = pd.to_numeric(df["net_revenue"], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=3600)
def load_premium_advisor_lookup():
    """MySQL: advisor per student, for attributing Premium-vs-SG revenue by advisor."""
    conn = get_mysql_connection()
    query = """
    SELECT DISTINCT
        students.id AS student_id,
        CONCAT(advisors.first_name,' ',advisors.last_name) AS advisor
    FROM orbit_production.students
        JOIN orbit_production.parents p ON students.parent_id = p.id
        JOIN orbit_production.employees e1 ON e1.id = p.advisor_id
        JOIN orbit_production.users advisors ON e1.user_id = advisors.id
    """
    return pd.read_sql(query, conn)
'''

# Insert new loaders right after load_sg_legend / save_sg_legend block, before the try/except data-load section
data_load_marker = "# ── Load data ─────────────────────────────────────────────────────────────\ntry:"
if data_load_marker in content:
    idx = content.index(data_load_marker)
    content = content[:idx] + new_loaders.strip("\n") + "\n\n" + content[idx:]
    print("Added new data loader functions")
else:
    print("WARNING: '# ── Load data' marker not found — loaders NOT inserted, add manually")

# ── 3. Remove orphaned Full Roster marker ────────────────────────────────
orphan_marker = "\n\n# ══════════════════════════════════════════════════════════════════════════\n# PAGE — FULL ROSTER\n# ══════════════════════════════════════════════════════════════════════════"
if orphan_marker in content:
    content = content.replace(orphan_marker, "")
    print("Removed orphaned Full Roster marker")
else:
    print("Orphaned marker not found (may already be clean) — skipping")

# ── 4. New UI sections, appended at the end ──────────────────────────────
new_sections = '''

# ══════════════════════════════════════════════════════════════════════════
# NEW SECTIONS — Refunds, Goal Attainment, Guarantee vs Premium Revenue
# ══════════════════════════════════════════════════════════════════════════

st.markdown("---")
st.markdown(
    "<p class='section-label'>Advisor Filter</p>"
    "<p class='section-title'>Filter Everything Below by Advisor</p>",
    unsafe_allow_html=True,
)

_all_advisors = sorted(df_sg["advisor"].dropna().unique().tolist()) if "advisor" in df_sg.columns else []
selected_advisors = st.multiselect(
    "Advisor (leave blank to show all)",
    _all_advisors,
    default=[],
    key="new_sections_advisor_filter",
)

def _filter_by_advisor(df, advisor_col="advisor"):
    if selected_advisors and advisor_col in df.columns:
        return df[df[advisor_col].isin(selected_advisors)]
    return df

_sg_students_filtered = _filter_by_advisor(df_sg)
_sg_student_ids_filtered = set(_sg_students_filtered["student_id"].dropna().astype(int).tolist())

# ── Refund Revenue ────────────────────────────────────────────────────────
st.markdown("")
st.markdown(
    "<p class='section-label'>Revenue</p>"
    "<p class='section-title'>Refund Revenue</p>",
    unsafe_allow_html=True,
)

try:
    _bookings_df = load_sg_bookings_and_refunds()
    _bookings_df = _bookings_df[_bookings_df["student_id"].isin(_sg_student_ids_filtered)]
    _refund_rows = _bookings_df[_bookings_df["amount"] < 0]
    _total_refunded = abs(_refund_rows["amount"].sum())
    _net_revenue_all = _bookings_df["amount"].sum()

    rf1, rf2, rf3 = st.columns(3)
    rf1.metric("Total Refunded", f"${_total_refunded:,.2f}")
    rf2.metric("Refund Transactions", f"{len(_refund_rows)}")
    rf3.metric("Net SG Revenue (after refunds)", f"${_net_revenue_all:,.2f}")

    if len(_refund_rows) > 0:
        with st.expander("View refund transactions", expanded=False):
            _refund_display = _refund_rows.merge(
                df_sg[["student_id", "student", "advisor"]], on="student_id", how="left"
            )
            st.dataframe(
                _refund_display[["student", "advisor", "package_id", "amount", "booked_at"]]
                .rename(columns={"amount": "Refund Amount", "booked_at": "Date", "package_id": "Package ID"})
                .sort_values("Date", ascending=False),
                hide_index=True, use_container_width=True,
            )
except Exception as e:
    st.error(f"Could not load refund data: {e}")

# ── Goal Attainment: First Test & After Awarded Hours ─────────────────────
st.markdown("")
st.markdown(
    "<p class='section-label'>Outcomes</p>"
    "<p class='section-title'>Goal Attainment</p>",
    unsafe_allow_html=True,
)

try:
    _awarded_df = load_awarded_hours()
    _awarded_by_student = (
        _awarded_df.groupby("student_id")["won_at"].min().reset_index().rename(columns={"won_at": "awarded_at"})
    )

    def _calc_target(score, test_type):
        if pd.isna(score):
            return np.nan
        if test_type == "SAT":
            return score + 150 if score < 1350 else 1500
        return score + 2 if score < 29 else 31

    SAT_TYPES = ["SAT", "Digital SAT"]
    ACT_TYPES = ["ACT", "Digital ACT"]

    _goal_rows = []
    for _, sg_row in _sg_students_filtered.iterrows():
        sid = sg_row["student_id"]
        stu_exams = df_sg_exams[df_sg_exams["student_id"] == sid].copy()
        if stu_exams.empty:
            continue
        stu_exams["exam_date"] = pd.to_datetime(stu_exams["exam_date"], errors="coerce")
        before_all = stu_exams[stu_exams["before_or_after_tutoring"] == "before"].sort_values("exam_date", ascending=False)
        if before_all.empty:
            continue
        baseline = before_all.iloc[0]["score"]
        test_type = "SAT" if baseline > 100 else "ACT"
        target = _calc_target(baseline, test_type)
        type_filter = SAT_TYPES if test_type == "SAT" else ACT_TYPES

        typed_after = stu_exams[
            stu_exams["exam_type"].isin(type_filter) & (stu_exams["before_or_after_tutoring"] == "after")
        ].sort_values("exam_date")
        if typed_after.empty:
            continue

        first_score = typed_after.iloc[0]["score"]
        row = {
            "student_id": sid, "student": sg_row.get("student"), "advisor": sg_row.get("advisor"),
            "test_type": test_type, "baseline": baseline, "target": target,
            "first_test_score": first_score, "reached_goal_first_test": first_score >= target,
        }

        aw = _awarded_by_student[_awarded_by_student["student_id"] == sid]
        if len(aw) > 0:
            awarded_at = aw.iloc[0]["awarded_at"]
            after_award = typed_after[typed_after["exam_date"] > awarded_at]
            row["awarded_hours"] = True
            if len(after_award) > 0:
                second_score = after_award.iloc[0]["score"]
                row["second_test_score"] = second_score
                row["reached_goal_after_award"] = second_score >= target
        else:
            row["awarded_hours"] = False

        _goal_rows.append(row)

    _goal_df = pd.DataFrame(_goal_rows)

    if len(_goal_df) > 0:
        gm1, gm2, gm3 = st.columns(3)
        _n_first = len(_goal_df)
        _reached_first = int(_goal_df["reached_goal_first_test"].sum())
        gm1.metric("Reached Goal — First Test", f"{_reached_first} of {_n_first}",
                    f"{_reached_first/_n_first*100:.0f}%" if _n_first > 0 else None)

        _with_award = _goal_df[_goal_df.get("awarded_hours", False) == True] if "awarded_hours" in _goal_df.columns else pd.DataFrame()
        _n_award = len(_with_award)
        gm2.metric("Students Awarded Extra Hours", f"{_n_award}")

        if _n_award > 0 and "reached_goal_after_award" in _with_award.columns:
            _has_second = _with_award["second_test_score"].notna().sum() if "second_test_score" in _with_award.columns else 0
            _reached_second = int(_with_award["reached_goal_after_award"].fillna(False).sum())
            gm3.metric("Reached Goal — After Award", f"{_reached_second} of {_has_second}",
                        f"{_reached_second/_has_second*100:.0f}%" if _has_second > 0 else None)

        with st.expander("View student-level goal detail", expanded=False):
            _display_cols = ["student", "advisor", "test_type", "baseline", "target",
                              "first_test_score", "reached_goal_first_test",
                              "awarded_hours", "second_test_score", "reached_goal_after_award"]
            _display_cols = [c for c in _display_cols if c in _goal_df.columns]
            st.dataframe(_goal_df[_display_cols], hide_index=True, use_container_width=True)
    else:
        st.info("No students with usable baseline + post-tutoring test data for this filter.")

except Exception as e:
    st.error(f"Could not compute goal attainment: {e}")

# ── Guarantee vs Other Premium Revenue ────────────────────────────────────
st.markdown("")
st.markdown(
    "<p class='section-label'>Revenue Comparison</p>"
    "<p class='section-title'>Guarantee vs. Other Premium Revenue</p>",
    unsafe_allow_html=True,
)

try:
    _pvp_df = load_premium_vs_sg_monthly()
    if selected_advisors:
        _advisor_lookup = load_premium_advisor_lookup()
        _pvp_df = _pvp_df.merge(_advisor_lookup, on="student_id", how="left")
        _pvp_df = _pvp_df[_pvp_df["advisor"].isin(selected_advisors)]

    _pvp_df["month"] = _pvp_df["won_at"].dt.to_period("M").astype(str)
    _monthly = _pvp_df.groupby(["month", "is_sg"])["net_revenue"].sum().reset_index()
    _monthly_pivot = _monthly.pivot(index="month", columns="is_sg", values="net_revenue").fillna(0)
    _monthly_pivot.columns = ["Other Premium Revenue" if c == 0 else "Guarantee Revenue" for c in _monthly_pivot.columns]
    _monthly_pivot = _monthly_pivot.reset_index().sort_values("month")

    pv1, pv2 = st.columns(2)
    pv1.metric("Total Guarantee Revenue", f"${_pvp_df[_pvp_df['is_sg']==1]['net_revenue'].sum():,.2f}")
    pv2.metric("Total Other Premium Revenue", f"${_pvp_df[_pvp_df['is_sg']==0]['net_revenue'].sum():,.2f}")

    fig_pvp = go.Figure()
    fig_pvp.add_trace(go.Scatter(
        x=_monthly_pivot["month"], y=_monthly_pivot["Guarantee Revenue"],
        name="Guarantee Revenue", mode="lines+markers", marker_color="#2563eb",
    ))
    fig_pvp.add_trace(go.Scatter(
        x=_monthly_pivot["month"], y=_monthly_pivot["Other Premium Revenue"],
        name="Other Premium Revenue", mode="lines+markers", marker_color="#94a3b8",
        yaxis="y2",
    ))
    fig_pvp.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans", color="#475569"),
        legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"),
        margin=dict(l=40, r=40, t=40, b=40),
        xaxis=dict(title="Month", gridcolor="rgba(226,232,240,0.8)"),
        yaxis=dict(title="Guarantee Revenue ($)", gridcolor="rgba(226,232,240,0.8)"),
        yaxis2=dict(title="Other Premium Revenue ($)", overlaying="y", side="right"),
        height=420,
    )
    st.plotly_chart(fig_pvp, use_container_width=True)
    st.markdown(
        "<p style='color:#94a3b8; font-size:0.75rem;'>Guarantee Revenue plotted against the left axis, "
        "Other Premium Revenue against the right axis (different scales — Guarantee volume is much smaller).</p>",
        unsafe_allow_html=True,
    )
except Exception as e:
    st.error(f"Could not build revenue comparison: {e}")
'''

content = content.rstrip("\n") + "\n" + new_sections
with open(APP_PATH, "w") as f:
    f.write(content)

print("\nAppended all four new sections to app.py")
