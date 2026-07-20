| Claim | REFUTED/SURVIVES | exact escape |
|-------|------------------|--------------|
| C1 bijection | **REFUTED** | `report_filenames()` = non-recursive `_REPORTS.glob("*retrospective*.md")`. Add e.g. `docs/_archive/reports/pending/2026-07-21-retrospective.md` (or top-level name **without** substring `retrospective`, e.g. `2026-07-21-5plus1.md`). File never enters the set → `test_every_retrospective_report_is_indexed` stays green while unindexed. (Bonus: not a real bijection — reverse only checks linked basenames containing `"retrospective"`; `_LINK_RE` `[\w./-]+` also misses many real MD link forms.) |
| C2 non-recurring drift | **REFUTED** | One edit: under `## 🟡`, keep a finished ID as an open row and keep summary `**N**` in lockstep — e.g. add `| **B3** | ✅ 완료 (#1131) | … |` and set `| 🟡 착수 가능 | **3** … |`. Counts still match; `_현재 없음._` unused; 착수 순서 can list **B3** (it is "open"). Ledger lies; all 5 tests pass. Same class: put decision work only in 🟡 while 🔴 stays 0/empty. |

Unencoded invariant: **semantic open-ness** (ID not ✅-done; 🔴 decision not parked in 🟡) — count bijection alone is observer-green.
