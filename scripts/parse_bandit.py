import json, sys

with open(sys.argv[1]) as f:
    d = json.load(f)

results = d.get("results", [])
metrics = d.get("metrics", {})
totals = metrics.get("_totals", {})

print("HIGH:", int(totals.get("SEVERITY.HIGH", 0)))
print("MEDIUM:", int(totals.get("SEVERITY.MEDIUM", 0)))
print("LOW:", int(totals.get("SEVERITY.LOW", 0)))
print("---")
for r in results:
    fname = r["filename"].split("src")[-1].lstrip("/").lstrip("\\")
    print(r["issue_severity"], r["test_id"], fname, r["line_number"], r["issue_text"][:70])
