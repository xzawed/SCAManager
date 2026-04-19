import json

with open("coverage.json") as f:
    d = json.load(f)

files = d["files"]
low = []
all_files = []
for path, info in files.items():
    pct = info["summary"]["percent_covered"]
    short = path.replace("\\", "/")
    short = short.split("SCAManager/")[-1] if "SCAManager/" in short else short
    miss = info["summary"]["missing_lines"]
    all_files.append((pct, short, miss))

all_files.sort()
print("--- ALL MODULES (sorted by coverage) ---")
for pct, path, miss in all_files:
    flag = " ⚠" if pct < 80 else ""
    print(f"{pct:5.1f}%  {path}  (missing {miss}){flag}")

print()
total = d["totals"]
print(f"TOTAL: {total['percent_covered']:.1f}%  ({total['covered_lines']}/{total['num_statements']} lines)")
