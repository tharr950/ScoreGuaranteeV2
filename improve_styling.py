"""
Replaces the current minimal CSS block with a fuller, more polished
theme: subtle background tint, card-style containers, better spacing,
accent colors, and nicer buttons/inputs — so it reads as a designed
site rather than plain black-on-white.
"""
APP_PATH = "app.py"
with open(APP_PATH, "r") as f:
    content = f.read()

old_css_start = "# ── Custom CSS ────────────────────────────────────────────────────────────\nst.markdown(\"\"\""
old_css_end = "\"\"\", unsafe_allow_html=True)"

start_idx = content.index(old_css_start)
end_idx = content.index(old_css_end, start_idx) + len(old_css_end)
old_block = content[start_idx:end_idx]

new_block = '''# ── Custom CSS ────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@400;600;700&family=DM+Sans:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

.stApp {
    background: linear-gradient(180deg, #f7f9fc 0%, #ffffff 300px);
}

[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1px solid #e5e9f0;
}

h1, h2, h3 { font-family: 'Source Serif 4', serif !important; color: #1e293b !important; }

[data-testid="metric-container"] {
    background: #ffffff;
    border: 1px solid #e5e9f0;
    border-radius: 12px;
    padding: 18px 22px;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}
[data-testid="metric-container"] label {
    color: #64748b !important; font-size: 0.72rem !important;
    letter-spacing: 0.1em; text-transform: uppercase; font-weight: 600;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #0f172a !important; font-size: 1.9rem !important;
    font-family: 'Source Serif 4', serif !important;
}

[data-testid="stDataFrame"] {
    border: 1px solid #e5e9f0;
    border-radius: 10px;
    overflow: hidden;
}

[data-testid="stExpander"] {
    border: 1px solid #e5e9f0 !important;
    border-radius: 10px !important;
    background: #ffffff;
}

.stButton > button {
    background: #2563eb;
    color: white;
    border-radius: 8px;
    border: none;
    font-weight: 500;
    padding: 0.5rem 1.25rem;
}
.stButton > button:hover {
    background: #1d4ed8;
    color: white;
}

.stTextInput input, .stMultiSelect [data-baseweb="select"] {
    border-radius: 8px !important;
    border: 1px solid #d6dbe3 !important;
}

hr { border-color: #e5e9f0 !important; }

.section-label {
    font-family: 'DM Sans', sans-serif; font-size: 0.7rem; font-weight: 600;
    letter-spacing: 0.15em; text-transform: uppercase; color: #94a3b8; margin-bottom: 4px;
}
.section-title {
    font-family: 'Source Serif 4', serif; font-size: 1.7rem;
    color: #0f172a; margin-bottom: 18px;
}

[data-baseweb="tab-list"] {
    gap: 4px;
    background: #f1f5f9;
    padding: 4px;
    border-radius: 10px;
}
[data-baseweb="tab"] {
    border-radius: 8px !important;
    font-weight: 500;
    color: #64748b;
}
[aria-selected="true"][data-baseweb="tab"] {
    background: white !important;
    color: #0f172a !important;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
}

#MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)'''

if old_block in content:
    content = content.replace(old_block, new_block)
    with open(APP_PATH, "w") as f:
        f.write(content)
    print("Replaced CSS block with fuller theme")
else:
    print("WARNING: old CSS block not found exactly as expected — no changes made, check manually")
