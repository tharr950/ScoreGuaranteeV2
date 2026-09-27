"""
1. Replaces the MySQL-based advisor lookup with a Redshift-only version
   (dw.students -> dw.parents.advisor_id -> dw.employees -> dw.users),
   since this app has never had live MySQL access set up.
2. Rebuilds the Overview tab: Missing Baseline Scores front-and-center,
   plus a Sales Tracking section (week/month trend, by-advisor
   breakdown, new sales) using the full qualifying-Premium population
   (Premium name match, >=20hrs, real revenue >0) — matching the
   already-established definition from the earlier Premium-vs-SG
   analysis, not narrowed to literal "Score Guarantee" naming.
"""
APP_PATH = "app.py"
with open(APP_PATH, "r") as f:
    content = f.read()

# ── 1. Replace MySQL advisor lookup with Redshift-only version ──────────
old_func = '''@st.cache_data(ttl=3600)
def load_premium_advisor_lookup(student_ids):
    """MySQL: advisor per student, restricted to the given student_ids
    (avoids a full unfiltered scan across every student in the system)."""
    if not student_ids:
        return pd.DataFrame(columns=["student_id", "advisor"])
    conn = get_mysql_connection()
    ids_str = ",".join(str(int(s)) for s in student_ids if pd.notna(s))
    query = f"""
    SELECT DISTINCT
        students.id AS student_id,
        CONCAT(advisors.first_name,' ',advisors.last_name) AS advisor
    FROM orbit_production.students
        JOIN orbit_production.parents p ON students.parent_id = p.id
        JOIN orbit_production.employees e1 ON e1.id = p.advisor_id
        JOIN orbit_production.users advisors ON e1.user_id = advisors.id
    WHERE students.id IN ({ids_str})
    """
    return pd.read_sql(query, conn)'''

new_func = '''@st.cache_data(ttl=3600)
def load_premium_advisor_lookup(student_ids):
    """Redshift: advisor per student, restricted to the given student_ids.
    Uses dw only — this app has never had live MySQL access configured."""
    if not student_ids:
        return pd.DataFrame(columns=["student_id", "advisor"])
    conn = get_redshift_connection()
    ids_str = ",".join(str(int(s)) for s in student_ids if pd.notna(s))
    query = f"""
    SELECT DISTINCT
        s.id AS student_id,
        adv_users.first_name||' '||adv_users.last_name AS advisor
    FROM dw.students s
        JOIN dw.parents p ON s.parent_id = p.id
        JOIN dw.employees adv_emp ON p.advisor_id = adv_emp.id
        JOIN dw.users adv_users ON adv_emp.user_id = adv_users.id
    WHERE s.id IN ({ids_str})
    """
    return pd.read_sql(query, conn)


@st.cache_data(ttl=3600)
def load_qualifying_premium_sales():
    """
    Full qualifying-Premium population for sales tracking: same
    definition established in the earlier Premium-vs-SG revenue
    analysis (name matches Premium, >=20 hours, real revenue > 0) —
    NOT narrowed to literal 'Score Guarantee' naming, since SG is a
    subset of this population, not a separate product.
    """
    conn = get_redshift_connection()
    query = """
    WITH qualifying AS (
        SELECT
            tp.id AS package_id, tp.student_id, tp.won_at, tp.name,
            tp.duration/60.0 AS package_hours,
            CASE WHEN tp.name ILIKE '%%Score Guarantee%%' THEN 1 ELSE 0 END AS is_sg
        FROM dw.tutor_packages tp
        WHERE tp.name ILIKE '%%Premium%%'
            AND tp.name NOT ILIKE '%%Transcript Adjustment%%'
            AND tp.status = 'won'
            AND tp.duration/60.0 >= 20
    )
    SELECT
        q.package_id, q.student_id, q.won_at, q.name, q.package_hours, q.is_sg,
        SUM(b.amount) AS net_revenue
    FROM qualifying q
        LEFT JOIN dw.bookings b ON b.item_type = 'TutorPackage' AND b.item_id = q.package_id
    GROUP BY q.package_id, q.student_id, q.won_at, q.name, q.package_hours, q.is_sg
    HAVING SUM(b.amount) > 0
    """
    df = pd.read_sql(query, conn)
    df["won_at"] = pd.to_datetime(df["won_at"], errors="coerce")
    df["net_revenue"] = pd.to_numeric(df["net_revenue"], errors="coerce").fillna(0)
    return df'''

if old_func in content:
    content = content.replace(old_func, new_func)
    print("Replaced MySQL advisor lookup with Redshift-only version, added load_qualifying_premium_sales()")
else:
    print("WARNING: old advisor function not found as expected — check manually")

# ── 2. Update the call site in Tab 3 (student_ids-based advisor merge) ──
old_call = '''    _pvp_df = load_premium_vs_sg_monthly()
    if selected_advisors:
        _pvp_student_ids = _pvp_df["student_id"].dropna().unique().tolist()
        _advisor_lookup = load_premium_advisor_lookup(_pvp_student_ids)
        _pvp_df = _pvp_df.merge(_advisor_lookup, on="student_id", how="left")
        _pvp_df = _pvp_df[_pvp_df["advisor"].isin(selected_advisors)]'''

new_call = '''    _pvp_df = load_premium_vs_sg_monthly()
    if selected_advisors:
        _pvp_student_ids = _pvp_df["student_id"].dropna().unique().tolist()
        _advisor_lookup = load_premium_advisor_lookup(_pvp_student_ids)
        _pvp_df = _pvp_df.merge(_advisor_lookup, on="student_id", how="left")
        _pvp_df = _pvp_df[_pvp_df["advisor"].isin(selected_advisors)]
'''
if old_call in content:
    content = content.replace(old_call, new_call.rstrip("\n") + "\n")
    print("Call site already compatible with new signature — no change needed beyond the function swap")

# ── 3. Remove the now-unused MySQL connection helper ─────────────────────
mysql_helper_marker = '''

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
if mysql_helper_marker in content:
    content = content.replace(mysql_helper_marker, "")
    print("Removed unused MySQL connection helper")

# ── 4. Insert new Overview tab content right after the existing tab1 header ──
tab1_marker = '    with tab1:\n        # ── New Student Alert'
new_overview_intro = '''    with tab1:
        # ── Missing Baseline Scores (front and center for advisors) ─────
        st.markdown(
            "<p class='section-label'>Action Needed</p>"
            "<p class='section-title'>Missing Baseline Scores</p>",
            unsafe_allow_html=True,
        )
        try:
            _mb_df = df_sg.copy()
            _mb_df["_no_baseline"] = _mb_df["starting_score"].isna() | _mb_df["starting_test_taken"].isna()
            _mb_missing = _mb_df[_mb_df["_no_baseline"]]
            mbm1, mbm2 = st.columns(2)
            mbm1.metric("Students Missing Baseline", len(_mb_missing))
            mbm2.metric("Total Score Guarantee Students", len(_mb_df))
            if len(_mb_missing) > 0:
                st.dataframe(
                    _mb_missing[["student", "advisor", "tutor", "won_at"]]
                    .rename(columns={"student": "Student", "advisor": "Advisor", "tutor": "Tutor", "won_at": "Won Date"})
                    .sort_values("Won Date", ascending=False),
                    hide_index=True, use_container_width=True,
                )
            else:
                st.success("All Score Guarantee students have a baseline score on file.")
        except Exception as e:
            st.error(f"Could not compute missing baselines: {e}")

        st.markdown("---")

        # ── Sales Tracking ───────────────────────────────────────────────
        st.markdown(
            "<p class='section-label'>Sales</p>"
            "<p class='section-title'>Score Guarantee — Eligible Premium Sales</p>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='color:#94a3b8; font-size:0.78rem;'>Includes any Premium-tier package "
            "of 20+ hours with real revenue collected — the full population eligible for the "
            "guarantee, not just packages explicitly named Score Guarantee.</p>",
            unsafe_allow_html=True,
        )
        try:
            _sales_df = load_qualifying_premium_sales()
            _sales_df["week"] = _sales_df["won_at"].dt.to_period("W-SAT").apply(lambda p: p.start_time)
            _sales_df["month"] = _sales_df["won_at"].dt.to_period("M").astype(str)

            _this_week = pd.Timestamp.now().to_period("W-SAT").start_time
            _last_week = _this_week - pd.Timedelta(days=7)
            _new_this_week = _sales_df[_sales_df["week"] == _this_week]
            _new_last_week = _sales_df[_sales_df["week"] == _last_week]

            sm1, sm2, sm3 = st.columns(3)
            sm1.metric("New Sales This Week", len(_new_this_week),
                        f"{len(_new_this_week) - len(_new_last_week):+d} vs last week")
            sm2.metric("Revenue This Week", f"${_new_this_week['net_revenue'].sum():,.0f}",
                        f"${_new_this_week['net_revenue'].sum() - _new_last_week['net_revenue'].sum():+,.0f} vs last week")
            sm3.metric("Total Qualifying Sales (all time)", len(_sales_df))

            st.markdown("")
            st.markdown("**Weekly Trend**")
            _weekly = _sales_df.groupby("week").agg(sales=("package_id", "count"), revenue=("net_revenue", "sum")).reset_index().sort_values("week")
            fig_weekly = go.Figure()
            fig_weekly.add_trace(go.Bar(x=_weekly["week"], y=_weekly["sales"], name="Sales Count", marker_color="#2563eb"))
            fig_weekly.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="DM Sans", color="#475569"),
                margin=dict(l=20, r=20, t=20, b=20),
                xaxis=dict(title="Week Of", gridcolor="rgba(226,232,240,0.8)"),
                yaxis=dict(title="Sales Count", gridcolor="rgba(226,232,240,0.8)"),
                height=300, showlegend=False,
            )
            st.plotly_chart(fig_weekly, use_container_width=True)

            st.markdown("**Monthly Trend**")
            _monthly = _sales_df.groupby("month").agg(sales=("package_id", "count"), revenue=("net_revenue", "sum")).reset_index().sort_values("month")
            fig_monthly = go.Figure()
            fig_monthly.add_trace(go.Bar(x=_monthly["month"], y=_monthly["sales"], name="Sales Count", marker_color="#8b5cf6"))
            fig_monthly.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="DM Sans", color="#475569"),
                margin=dict(l=20, r=20, t=20, b=20),
                xaxis=dict(title="Month", gridcolor="rgba(226,232,240,0.8)"),
                yaxis=dict(title="Sales Count", gridcolor="rgba(226,232,240,0.8)"),
                height=300, showlegend=False,
            )
            st.plotly_chart(fig_monthly, use_container_width=True)

            st.markdown("")
            st.markdown("**By Advisor**")
            _sales_student_ids = _sales_df["student_id"].dropna().unique().tolist()
            _sales_advisor_lookup = load_premium_advisor_lookup(_sales_student_ids)
            _sales_with_advisor = _sales_df.merge(_sales_advisor_lookup, on="student_id", how="left")
            _by_advisor = _sales_with_advisor.groupby("advisor").agg(
                sales=("package_id", "count"),
                revenue=("net_revenue", "sum"),
                sg_named=("is_sg", "sum"),
            ).reset_index().sort_values("revenue", ascending=False)
            _by_advisor = _by_advisor.rename(columns={
                "advisor": "Advisor", "sales": "Qualifying Sales",
                "revenue": "Revenue", "sg_named": "Explicitly Tagged SG",
            })
            _by_advisor["Revenue"] = _by_advisor["Revenue"].apply(lambda x: f"${x:,.0f}")
            st.dataframe(_by_advisor, hide_index=True, use_container_width=True)

        except Exception as e:
            st.error(f"Could not load sales tracking data: {e}")

        st.markdown("---")

        # ── New Student Alert'''

if tab1_marker in content:
    content = content.replace(tab1_marker, new_overview_intro, 1)
    print("Inserted new Overview tab content (Missing Baselines + Sales Tracking)")
else:
    print("WARNING: tab1 marker not found — Overview content NOT inserted, check manually")

with open(APP_PATH, "w") as f:
    f.write(content)

print("\nDone.")
