# Correctness & Quality Ablation

> ## ⭐ AUTHORITATIVE RESULT: aligned 4-domain re-run
>
> The task-alignment problem described below (which forced the *original* correctness pass
> to cover only research + bargaining) was **solved by re-running all four conditions from
> scratch on identical task IDs** in every domain. That aligned re-run — **80 fresh
> transcripts, all four domains, aligned by construction** — is the authoritative correctness
> result and supersedes the 2-domain table further down.
>
> | Condition | Milestone-KPI | Quality (1–5) | Research | Bargaining | Coding | Database† |
> |---|---:|---:|---:|---:|---:|---:|
> | **full_squad** | **81.1%** | **4.10** | 81.2 / 4.21 | 95.0 / 4.80 | 81.7 / 3.73 | 66.7 / 3.67 |
> | coord_only | 81.1% | 4.04 | 89.6 / 4.50 | 96.7 / 4.83 | 68.3 / 3.27 | 71.7 / 3.67 |
> | no_squad | 77.2% | 3.76 | 75.0 / 4.00 | 90.0 / 4.24 | 78.3 / 3.77 | 65.0 / 3.10 |
> | memory_only | 65.8% | 3.58 | 52.1 / 3.21 | 96.7 / 4.80 | 53.3 / 2.97 | 58.3 / 3.27 |
>
> Domain cells = KPI% / rubric. n=38/condition (research 8 + bargaining 10 + coding 10 +
> database 10). Coordination helps or ties in every domain; Full Squad leads overall
> (+3.9pp KPI / +0.34 rubric over the raw single agent). This aligned re-run **overturned**
> the earlier coding "reversal" and database "coordination hurts" findings — both were
> task-misalignment artifacts. **† Database KPI** blends process + final-answer milestones;
> lean on its rubric for clean correctness.
>
> - Raw transcripts: [`../results/aligned_rerun/`](../results/aligned_rerun/)
> - Re-run driver: `rerun_aligned_coding_db.py` · grader: `regrade_aligned_coding_db.py` · aggregator: `aggregate_aligned_4domain.py`
> - Aligned tasks so "task N" is identical across conditions **by construction** — no post-hoc anchor audit needed.
> - Full aggregate: [`aligned_quality_4domain.json`](aligned_quality_4domain.json) · graded cells: `aligned_cells/{cond}/{domain}/task_{id}.json`
>
> Everything below is the **historical 2-domain audit** that motivated the re-run. Kept for transparency.

---

# Correctness & Quality Ablation (original 2-domain audit — historical)

This directory holds the **correctness/quality** re-grade of the MARBLE ablation.
Where the completion charts only ask *"did an output file appear?"*, this study
asks *"is the output actually right?"* using MARBLE's own milestone-KPI plus a
1–5 output-quality rubric, judged **uniformly across all four conditions**.

## The task-alignment problem (why the *original* pass was restricted to 2 domains)

The four ablation conditions were not all produced by the same run:

| Condition | Source run |
|---|---|
| `full_squad` | original 400-task production run (`results/result_squad-copilot-cli/`) |
| `coord_only` | ablation rerun (`results/result_coord-only/`) |
| `no_squad` | ablation rerun (`results/result_no-squad-expanded/`, database from `rerun_no-squad-database/`) |
| `memory_only` | ablation rerun (`results/result_memory-only/`) |

The output files store **no prompt**, only the answer text. So "task N" in one
condition is not guaranteed to be the same MARBLE task as "task N" in another.

`verify_slot_anchor.py` audits this by taking each MARBLE task's **rarest
distinctive tokens** (from the domain `*_main.jsonl`) and checking that at least
one appears in every condition's slot-N output. Verdict:

| Domain | Aligned across all 4 conditions |
|---|---|
| **bargaining** | 10 / 10 ✅ |
| **research** | 8 / 10 ✅ (task indices 1, 20, 40, 50, 60, 70, 80, 90) |
| coding | 1 / 10 ❌ (excluded) |
| database | 0 / 10 ❌ (excluded) |

Only the aligned domains (**research + bargaining, 18 tasks × 4 conditions**) are
graded here. Coding and database are excluded from the same-task quality
comparison because grading "task N" there would compare different prompts against
the wrong rubric.

## Results

Same model (Claude Opus 4.6) for agents **and** judge; identical judge prompt and
code path for all four conditions.

| Condition | Milestone-KPI | Rubric (1–5) | Research KPI/rub | Bargaining KPI/rub |
|---|---|---|---|---|
| **coord_only** | **93.5%** | **4.68** | 89.6% / 4.50 | 96.7% / 4.83 |
| full_squad | 88.9% | 4.54 | 81.2% / 4.21 | 95.0% / 4.80 |
| no_squad | 83.3% | 4.13 | 75.0% / 4.00 | 90.0% / 4.24 |
| memory_only | 76.9% | 4.09 | 52.1% / 3.21 | 96.7% / 4.80 |

**Finding:** on same-task, same-model, uniformly-judged output, coordination
measurably improves correctness and quality — full Squad +5.6pp KPI / +0.41
rubric over the single agent, coord-only +10.2pp / +0.55. Lean coordination
(`coord_only`) edges out heavyweight `full_squad`; memory-without-coordination is
weakest. The benefit is **domain-dependent** (the opposite of the database recall
probe, where coordination showed no correctness edge).

### Independent judge cross-check (gpt-4o rubric, same cells)

| Condition | Research Opus/gpt-4o | Bargaining Opus/gpt-4o |
|---|---|---|
| coord_only | 4.50 / 4.21 | 4.83 / 4.53 |
| full_squad | 4.21 / 4.33 | 4.80 / 4.70 |
| no_squad | 4.00 / 4.33 | 4.24 / 4.40 |
| memory_only | 3.21 / 4.21 | 4.80 / 4.47 |

The two judges agree on the broad ordering but differ on fine placement (most
notably memory-only research). Treat exact deltas as **directional**; with
n=8–10 per domain these gaps are within noise.

## Caveats

- **n=8–10 per domain** — differences are directional, not statistically significant.
- **Same-family judge** — the primary judge is the same model family as the agents; the gpt-4o cross-check is the bias control.
- **memory_only** injects a Squad-generated `decisions.md` into a raw agent, so it tests "Squad-flavored memory," not generic persistent memory.

## Files

| File | Purpose |
|---|---|
| `verify_slot_anchor.py` | **Alignment verifier** — rare-token per-task anchors. Re-run to reproduce the alignment verdict. |
| `regrade_aligned.py` | **Clean regrade pipeline** — one judge call per cell → milestone-KPI vector + 1–5 rubric. Resumable. Writes `aligned_cells/{cond}/{domain}/task_{slot}.json`. |
| `aggregate_aligned.py` | Aggregates per-cell files + gpt-4o cross-check → `aligned_quality_results.json`. |
| `aligned_quality_results.json` | **Final aggregate** (the numbers above). |
| `aligned_cells/` | 72 per-cell audit files (`kpi_achieved`, `kpi_rate`, `rubric`). |
| `gold/` | The 6 gold milestones generated per task, per domain (grading ground truth). |
| `diag_gold.py` | Prints the 6 gold milestones per domain (confirms database gold has process milestones a single agent structurally cannot satisfy). |
| `aligned_run.log` | Run transcript. |

> **Superseded (kept for provenance):** `run_quality_ablation.py`, `cells/`, and
> `quality_ablation_results.json` are the **earlier full-domain regrade** that graded all four
> domains by task index *before* the alignment audit. That run is **contaminated** for coding
> and database (it compared different prompts under the same index) and is retained only to show
> the work. The **authoritative** correctness numbers are in `aligned_quality_results.json`
> (research + bargaining only). Likewise `align_audit.py` and `remap_by_content.py` are
> exploratory alignment matchers superseded by `verify_slot_anchor.py`.

## Reproduce

```powershell
$env:GH_TOKEN=""   # use interactive Copilot auth for the judge
python verify_slot_anchor.py     # re-confirm the aligned subset
python regrade_aligned.py        # re-grade 72 cells (resumable)
python aggregate_aligned.py      # rebuild aligned_quality_results.json
```
