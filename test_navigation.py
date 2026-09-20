import ast
from pathlib import Path

PAGES = {
    "main.html": "Environmental Exposure",
    "clinical-outreach.html": "Clinical Outreach &amp; Vulnerability Management",
    "clinical-parameter-assessment.html": "Clinical Parameter Assessment",
}

for filename, active_label in PAGES.items():
    html = Path(filename).read_text(encoding="utf-8")
    assert html.count('aria-current="page"') == 1, filename
    assert active_label in html, filename
    for linked_page in PAGES:
        assert f'href="{linked_page}"' in html, f"{filename} missing {linked_page}"

print("Navigation check passed for all three pages.")

tree = ast.parse(Path("main.py").read_text(encoding="utf-8"))
allowlist = next(
    ast.literal_eval(node.value)
    for node in tree.body
    if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == "FRONTEND_FILES" for target in node.targets)
)
assert set(PAGES) <= allowlist
assert {"styles.css", "dashboard.js"} <= allowlist
assert "environmental.csv" not in allowlist
print("Frontend file allowlist check passed.")
