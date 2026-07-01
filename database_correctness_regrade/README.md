# Database domain — completion fix + correctness re-grade

This folder documents a correction to the database domain of the 4-domain factorial ablation.

## What was wrong

The original ablation reported the **no-Squad (single agent) database completion rate as 0%**.
That figure was based on placeholder result files (`task_10`…`task_90`, ~339 bytes each,
`"NO-FILE-OUTPUT"` stubs) that were never populated with real runs. Only `task_1` had a
genuine run. The "database requires coordination / 0% without Squad" claim was therefore an
artifact of missing data, not a real effect.

## What we did

1. **Re-ran all 10 no-Squad database tasks from scratch** using raw Copilot CLI
   (`copilot --yolo --autopilot`, no `--agent squad`), same model (claude-opus-4.6),
   600s+ budget. Every task produced a substantive root-cause diagnosis (4.3–7.1 KB).
   → **Completion: 0% → 100% (10/10).** Real outputs are in
   `../results/result_no-squad-expanded/database/task_*.json`.

2. **Re-graded correctness for all four conditions** on the 10-task database subset using
   MARBLE's official recall metric: `recall = |gold ∩ selected| / |gold|`, averaged over
   tasks. Root-cause labels the agent *selected* were extracted by an LLM judge
   (`judge_pertask.py`), scored against ground truth in
   `multiagentbench/database/database_main.jsonl` (`.task.root_causes`).
   Two independent judge passes (batched-snippet and per-task full-output) produced
   **identical** scores.

## Corrected numbers (database, n=10)

| Condition   | Completion | MARBLE recall (correctness) |
|-------------|-----------:|----------------------------:|
| Full Squad  | 100%       | **40%** |
| Coord-only  | 90%        | **50%** |
| Memory-only | 0%         | **0%**  |
| No Squad    | **100%**   | **60%** |

**Finding:** On database root-cause diagnosis, coordination did **not** improve correctness —
the raw single agent scored the highest recall. Multi-agent configs repeatedly "converged" on
the obvious high-signal causes (large inserts, full-table scans) and missed subtler ones
(e.g. `REDUNDANT_INDEX`). With n=10 these gaps are within noise, so the honest takeaway is
"coordination provides no correctness advantage here" — the opposite of the fabricated 0%.

## Extraction consistency (important)

**All four conditions were graded by the identical LLM extractor** — the same
`judge_pertask.py` code path, the same prompt, the same 7000-char truncation, the same
`claude-opus-4.6` judge. No condition was graded differently from another. The published
numbers in `judge_results.json` (Full Squad 40%, Coord-only 50%, Memory-only 0%, No-Squad 60%)
all come from this single uniform pass. `no_squad`, `coord_only`, and `full_squad` are graded
inside one loop (`for cond in ["full_squad","coord_only","no_squad"]`); `memory_only` produced
no output at all (all runs empty), so its recall is 0 by definition, not by a different grader.

`grade_nosquad_database.py` is a **superseded regex cross-check** that was written earlier and
only inspects the no-Squad outputs. It is **not** the source of any published number and is
retained solely for auditability. Do not treat it as a second grading method for the comparison.

**Treat the correctness gap as a hypothesis, not a conclusion.** n=10, label extraction is
imperfect, and the gaps are within noise. The defensible claim is "coordination provided no
correctness advantage on database in this small regrade," not "single agents are better."

## Memory-only caveat

The `memory_only` condition injects a **Squad-generated `decisions.md`** into an otherwise raw
single-agent run. It therefore tests "Squad-flavored accumulated memory without coordination,"
**not** generic persistent memory. Read the memory-only results with that scope in mind.

## Files

- `extract_judge_input.py` — isolates each condition/task output for judging → `judge_input.json`
- `judge_pertask.py` — **authoritative** per-task LLM judge (all conditions); writes `judge_results.json`
- `grade_nosquad_database.py` — **SUPERSEDED** regex cross-check (no-Squad only), kept for audit; not a published source
- `judge_input.json` — the exact snippets fed to the judge
- `judge_results.json` — per-task predictions, gold labels, and recall per condition

Judge model: claude-opus-4.6 via Copilot CLI (documented, deterministic file-output judge).
