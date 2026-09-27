"""
Restructures app.py into 3 tabs: Overview, Student Data, Financial Data.

Uses anchor-text search (not hardcoded line numbers) to find boundaries,
since prior edits have shifted line numbers. Streamlit tabs execute all
their code every rerun regardless of which tab is visible, so wrapping
existing sequential code in `with tabX:` blocks is safe as long as the
original top-to-bottom order is preserved — which this does.
"""
APP_PATH = "app.py"
with open(APP_PATH, "r") as f:
    lines = f.readlines()

def find_line(anchor, start=0):
    for i in range(start, len(lines)):
        if anchor in lines[i]:
            return i
    raise ValueError(f"Anchor not found: {anchor!r}")

def indent_range(start, end, spaces=4):
    """Indent lines[start:end] (end exclusive) by `spaces`, skipping blank lines."""
    pad = " " * spaces
    for i in range(start, end):
        if lines[i].strip() != "":
            lines[i] = pad + lines[i]

# ── Find anchors ──────────────────────────────────────────────────────────
if_empty_idx = find_line("if df_sg.empty:")
else_idx = find_line("else:", if_empty_idx)

tab1_start = find_line("# ── New Student Alert", else_idx)
tab1_end = find_line("# ── Apply test type overrides directly to sg", tab1_start)

tab2_start = find_line("# ── Compliance summary metrics", tab1_end)
# Tab 2 ends right where the appended new-sections divider begins.
# Use the unique banner comment from the appended block (NOT a bare
# st.markdown("---") — that string also appears earlier, inside the
# Student Detail Drilldown section, and matching the wrong one there
# is what broke the previous attempt).
banner_idx = find_line("NEW SECTIONS — Refunds, Goal Attainment", tab2_start)
# The divider (st.markdown("---")) sits a few lines before the banner;
# walk backward to find it so Tab 2 ends right before it.
tab2_end = banner_idx
for i in range(banner_idx, tab2_start, -1):
    if 'st.markdown("---")' in lines[i]:
        tab2_end = i
        break

tab3_start = tab2_end  # the divider itself starts the financial section
tab3_end = len(lines)

print(f"if/else: {if_empty_idx+1}/{else_idx+1}")
print(f"Tab 1 (Overview): lines {tab1_start+1}-{tab1_end}")
print(f"Unwrapped computation: lines {tab1_end+1}-{tab2_start}")
print(f"Tab 2 (Student Data): lines {tab2_start+1}-{tab2_end}")
print(f"Tab 3 (Financial Data): lines {tab3_start+1}-{tab3_end}")

# ── Apply indentation to each tab's content (deepest ranges first, so
#    earlier line indices don't shift before we use them) ─────────────────
indent_range(tab3_start, tab3_end, spaces=4)      # top-level -> inside with tab3:
indent_range(tab2_start, tab2_end, spaces=4)      # already at 4 -> 8 (inside else: + tab2)
indent_range(tab1_start, tab1_end, spaces=4)      # already at 4 -> 8 (inside else: + tab1)

# ── Insert `with tabX:` headers (insert from bottom to top so earlier
#    indices stay valid) ────────────────────────────────────────────────
lines.insert(tab3_start, "with tab3:\n")
lines.insert(tab2_start, "    with tab2:\n")
lines.insert(tab1_start, "    with tab1:\n")

# ── Insert tab creation before the if/else, and wrap the warning branch ──
warning_line_idx = find_line("Score guarantee data not available", if_empty_idx)
lines[warning_line_idx] = "    with tab1:\n        " + lines[warning_line_idx].strip() + "\n"

tabs_setup = (
    'tab1, tab2, tab3 = st.tabs(["📋 Overview", "🎓 Student Data", "💰 Financial Data"])\n\n'
)
lines.insert(if_empty_idx, tabs_setup)

with open(APP_PATH, "w") as f:
    f.writelines(lines)

print("\nDone — wrote tabs into app.py")
