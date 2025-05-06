# detect_deps.py  (Python ≥3.8)
import modulefinder, pathlib, importlib.util, json, sys

BASE_DIR = pathlib.Path(__file__).resolve().parent      # vote-system/
mf = modulefinder.ModuleFinder()

def safe_run(script: pathlib.Path):
    """loader 가 없는 모듈에서 터지는 문제를 우회"""
    try:
        mf.run_script(str(script))
    except AttributeError as e:
        # spec.loader 가 None 인 모듈이 있으면 그냥 스킵
        if "'NoneType' object has no attribute 'is_package'" in str(e):
            print(f"[skip] {script}  ({e})", file=sys.stderr)
        else:
            raise

for py in BASE_DIR.glob('**/*.py'):
    safe_run(py)

# ── 최상위 site-packages 모듈 집계 ────────────────────
top_level = {
    name.partition('.')[0]
    for name, mod in mf.modules.items()
    if mod.__file__ and 'site-packages' in mod.__file__
}

print(json.dumps(sorted(top_level), indent=2, ensure_ascii=False))


