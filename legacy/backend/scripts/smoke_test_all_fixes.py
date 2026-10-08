"""
Full smoke test suite covering all G-01 to G-05 gap fixes.
Run from backend directory.
"""
import subprocess, sys, os
from pathlib import Path

# Fix Windows console encoding for Unicode emojis
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Resolve project paths accurately regardless of current working directory
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
ROOT = BACKEND_DIR.parent
VENV_PYTHON = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"

results = {}


def run(label, cmd, cwd=None, expect_in_output=None, expect_exit_0=True):
    proc = subprocess.run(
        cmd, shell=True, capture_output=True, text=True,
        cwd=cwd or str(BACKEND_DIR)
    )
    ok = True
    if expect_exit_0 and proc.returncode != 0:
        ok = False
    if expect_in_output:
        for s in (expect_in_output if isinstance(expect_in_output, list) else [expect_in_output]):
            if s not in proc.stdout:
                ok = False
    results[label] = "✅ PASS" if ok else f"❌ FAIL (exit={proc.returncode})\n{proc.stderr[:300]}"
    status_icon = "[PASS]" if sys.stdout.encoding != "utf-8" else ("✅" if ok else "❌")
    print(f"{status_icon} {label}")
    if not ok:
        print(f"   stdout: {proc.stdout[:200]}")
        print(f"   stderr: {proc.stderr[:200]}")
    return ok


# G-01: venv
run("G-01 venv: packages importable",
    f'"{VENV_PYTHON}" -c "import fastapi, chromadb, networkx; print(\'OK\')"',
    expect_in_output="OK")

# G-02: auth middleware
run("G-02 auth: middleware importable",
    f'"{VENV_PYTHON}" -c "import sys; sys.path.insert(0, \'.\'); from middleware.auth import APIKeyMiddleware; print(\'OK\')"',
    cwd=str(BACKEND_DIR), expect_in_output="OK")

# G-03: vision module
run("G-03 vision: module importable",
    f'"{VENV_PYTHON}" -c "import sys; sys.path.insert(0, \'.\'); from routers.vision import is_image; print(is_image(\'x.png\'))"',
    cwd=str(BACKEND_DIR), expect_in_output="True")

# G-04: chromadb version
run("G-04 chromadb: version >= 0.5",
    f'"{VENV_PYTHON}" -c "import chromadb; v=chromadb.__version__; parts=[int(x) for x in v.split(\'.\')[:2]]; assert parts[0] > 0 or parts[1] >= 5; print(\'OK\')"',
    expect_in_output="OK")

# G-05: graphml roundtrip
run("G-05 graphml: roundtrip ok",
    f'"{VENV_PYTHON}" -c "import networkx as nx, tempfile, os; G=nx.DiGraph(); G.add_node(\'A\'); t=tempfile.mktemp(\'.graphml\'); nx.write_graphml(G,t); G2=nx.read_graphml(t).to_directed(); assert G2.number_of_nodes()==1; os.remove(t); print(\'OK\')"',
    expect_in_output="OK")

# Summary
print("\n" + "=" * 50)
print("SMOKE TEST RESULTS")
print("=" * 50)
for label, status in results.items():
    print(f"  {status}  — {label}")
passed = sum(1 for s in results.values() if "PASS" in s)
print(f"\n{passed}/{len(results)} PASSED")
print("SMOKE_TEST_COMPLETE")

# Write status file to root
with open(str(ROOT / "FINAL_STATUS.md"), "w", encoding="utf-8") as f:
    f.write("# Final Gap Closure Status\n\n")
    f.write(f"Run at: {__import__('datetime').datetime.now()}\n\n")
    for label, status in results.items():
        f.write(f"- {status} — {label}\n")
    f.write(f"\n**{passed}/{len(results)} PASSED**\n")
