"""
Fixes two bugs:
1. Notes/legend were sharing the SAME GitHub files as the other SG
   dashboard. Gives this dashboard its own separate files.
2. load_premium_advisor_lookup() had no WHERE filter, causing a full
   scan across every student in the system. Restricts it to only the
   student_ids that actually appear in the Premium/SG revenue data.
"""
import re

APP_PATH = "app.py"
with open(APP_PATH, "r") as f:
    content = f.read()

changes = []

# ── Fix 1: separate notes/legend file paths ──────────────────────────────
replacements = [
    ('"data/score_guarantee_notes.csv"', '"data/score_guarantee_v2_notes.csv"'),
    ('"data/score_guarantee_legend.csv"', '"data/score_guarantee_v2_legend.csv"'),
]
for old, new in replacements:
    count = content.count(old)
    if count > 0:
        content = content.replace(old, new)
        changes.append(f"Replaced {count}x: {old} -> {new}")

# ── Fix 2: filter the advisor lookup query to relevant student_ids only ──
old_func = '''@st.cache_data(ttl=3600)
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
    return pd.read_sql(query, conn)'''

new_func = '''@st.cache_data(ttl=3600)
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

if old_func in content:
    content = content.replace(old_func, new_func)
    changes.append("Fixed load_premium_advisor_lookup: now takes student_ids and filters the query")
else:
    changes.append("WARNING: load_premium_advisor_lookup function not found as expected — check manually")

# Update the call site to pass student_ids
old_call = '''    _pvp_df = load_premium_vs_sg_monthly()
    if selected_advisors:
        _advisor_lookup = load_premium_advisor_lookup()
        _pvp_df = _pvp_df.merge(_advisor_lookup, on="student_id", how="left")
        _pvp_df = _pvp_df[_pvp_df["advisor"].isin(selected_advisors)]'''

new_call = '''    _pvp_df = load_premium_vs_sg_monthly()
    if selected_advisors:
        _pvp_student_ids = _pvp_df["student_id"].dropna().unique().tolist()
        _advisor_lookup = load_premium_advisor_lookup(_pvp_student_ids)
        _pvp_df = _pvp_df.merge(_advisor_lookup, on="student_id", how="left")
        _pvp_df = _pvp_df[_pvp_df["advisor"].isin(selected_advisors)]'''

if old_call in content:
    content = content.replace(old_call, new_call)
    changes.append("Updated call site to pass student_ids to load_premium_advisor_lookup")
else:
    changes.append("WARNING: call site not found as expected — check manually")

with open(APP_PATH, "w") as f:
    f.write(content)

print("\n".join(changes))
