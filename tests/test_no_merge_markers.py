from pathlib import Path


def test_repo_has_no_merge_conflict_markers():
    markers = ("<<<<<<< ", "=======", ">>>>>>> ")
    root = Path(__file__).resolve().parents[1]
    bad = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".db", ".pdf", ".xlsx", ".ttf"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for idx, line in enumerate(text.splitlines(), start=1):
            if line.startswith(markers):
                bad.append(f"{path.relative_to(root)}:{idx}")
    assert not bad, "merge conflict markers found:\n" + "\n".join(bad)
