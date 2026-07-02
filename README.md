# Squad Benchmark Results

Public repository containing all raw benchmark data for evaluating [Squad](https://github.com/bradygaster/squad) — a multi-agent coordination layer for GitHub Copilot CLI.

## Benchmarks

| Benchmark | Tasks | Squad | Baseline (no Squad) | Δ | Controlled? |
|-----------|-------|-------|---------------------|---|-------------|
| **MARBLE** ablation (ACL 2025) | 160 | 100% | 85% (same model) | **+15pp** | ✅ Controlled |
| **MARBLE** full run | 400 | 99.25% | ~45% (gpt-4o-mini, paper) | n/a* | ⚠️ Diff model/metric |
| **DevBench** | 1,800 | 53.1% | 43.5%† | +9.6pp* | ⚠️ Different model |
| **SWE-bench Lite** | 300 | 66% | ~48%‡ | +18pp* | ⚠️ Estimated baseline |
| **TerminalBench 2.0** | 20 | 80% | 75% | +5pp* | ⚠️ Same model, diff harness (n=20, +1 task) |

\* **Directional, not controlled.** Only the MARBLE ablation row isolates the coordination layer (same model, same 160 tasks). The MARBLE full-run 99.25% is the 400-task completion headline; its ~45% comparator is the paper's different-model/different-metric result, so no clean Δ is claimed. The other rows use different models, estimated baselines, or different harness paths.

† DevBench: Squad uses GPT-5.4; baseline is GPT-5.5 (different model). Raw per-task data not hosted here — contextual only.
‡ SWE-bench Lite: Baseline estimated from public reports. No same-model-without-Squad run. Retry/timeout accounting in [squad-swe-bench](https://github.com/tamirdresher/squad-swe-bench).

MARBLE Squad/baseline figures above are the **completion** metric (did the condition produce
usable output). See the correctness re-grade below — on same-task, same-model, uniformly-judged
output, coordination helps or ties in every domain.

## Controlled Ablation (MARBLE)

Factorial ablation: same model (Claude Opus 4.6), same tasks. The ablation metric is
**completion** (output produced within the 600s budget). 4 domains × 4 conditions × 10 tasks
= 160 task-runs.

| Condition | Coding | Research | Bargaining | Database | **Average** |
|-----------|--------|----------|------------|----------|-------------|
| Full Squad | 100% | 100% | 100% | 100% | **100%** |
| Coord-only | 100% | 90% | 90% | 90% | **92.5%** |
| Memory-only | 40% | 70% | 60% | 0% | **42.5%** |
| No Squad | 90% | 80% | 70% | 100% | **85%** |

> **Correction (database):** the no-Squad database completion was previously listed as **0%**,
> based on unpopulated placeholder files. All 10 tasks were re-run and every one produced a
> substantive diagnosis → **100%**. Memory-only database is 0% (all runs timed out/produced no
> output). Details and the raw re-runs: [`database_correctness_regrade/`](database_correctness_regrade/).

### Database correctness — superseded

> An earlier probe graded database correctness on transcripts that turned out **not to be task-aligned**
> across conditions (full-Squad came from the 400-task production run; others from separate reruns), and
> used a different recall extractor. It reported "coordination provided no correctness advantage on
> database (single agent 60% vs Squad 40%)." That finding was a **measurement artifact** and is superseded
> by the aligned 4-domain re-run below, where the coordinated conditions match or beat the single agent on
> database. The old probe data remains in [`database_correctness_regrade/`](database_correctness_regrade/)
> for transparency but should not be cited.

## Correctness & quality (all four domains, aligned by construction)

Completion only checks that an answer appeared — not whether it is **right**. To grade correctness/quality
across all four domains cleanly, we **re-ran all four conditions from scratch on the identical task IDs**
(1, 10, 20, …, 90) in every domain — 80 fresh transcripts — so "task N" is the same MARBLE task in every
condition **by construction** (no post-hoc alignment audit needed). We then graded all 80 with one identical
judge (Claude Opus 4.6) and one identical prompt: MARBLE's milestone-KPI (fraction of gold milestones
achieved) plus a 1–5 output-quality rubric.

| Condition | Milestone-KPI | Quality (1–5) | Research | Bargaining | Coding | Database† |
|-----------|--------------:|--------------:|---------:|-----------:|-------:|----------:|
| **Full Squad** (coord + memory) | **81.1%** | **4.10** | 81.2 / 4.21 | 95.0 / 4.80 | 81.7 / 3.73 | 66.7 / 3.67 |
| Coord-only | 81.1% | 4.04 | 89.6 / 4.50 | 96.7 / 4.83 | 68.3 / 3.27 | 71.7 / 3.67 |
| No Squad (single agent) | 77.2% | 3.76 | 75.0 / 4.00 | 90.0 / 4.24 | 78.3 / 3.77 | 65.0 / 3.10 |
| Memory-only | 65.8% | 3.58 | 52.1 / 3.21 | 96.7 / 4.80 | 53.3 / 2.97 | 58.3 / 3.27 |

Each domain cell = Milestone-KPI% / quality rubric (1–5). n per condition = 38 (research 8 + bargaining 10 +
coding 10 + database 10). On same-task, same-model, uniformly-judged output, **coordination helps or ties in
every domain**. Full Squad leads overall (+3.9pp KPI / +0.34 rubric over the raw single agent), with coord-only
essentially tied. This aligned re-run also **overturns two earlier artifact-driven findings**: the coding
"reversal" is gone (Full Squad coding 81.7% now leads no-Squad 78.3%), and the database "coordination hurts"
claim is refuted (coordinated conditions now ≥ single agent). Memory-without-coordination is consistently the
weakest condition. An independent gpt-4o rubric cross-check on research/bargaining agrees on the broad ordering
but differs on fine placement — treat exact deltas as **directional** (n=8–10 per domain).

> **† Database caveat:** the database gold blends diagnostic-process milestones (which `pg_stat_*` views to
> query) with a final root-cause answer, so its KPI reads partly as process-adherence — lean on the 1–5 rubric
> for the clean correctness signal there.

Raw re-runs: [`results/aligned_rerun/`](results/aligned_rerun/). Scripts, gold milestones, and per-cell grades:
[`quality_ablation/`](quality_ablation/).

## Repository Structure

```
results/
├── result_squad-copilot-cli/   # Full Squad: 400 tasks, all domains
├── result_coord-only/          # Ablation: coordination without memory
├── result_memory-only/         # Ablation: Squad-generated memory injected, no coordination
├── result_no-squad-ablation/   # Ablation: raw model, no Squad
├── result_no-squad-expanded/   # Extended no-squad runs (coding + database)
├── aligned_rerun/              # Aligned 4-domain correctness re-run (80 fresh transcripts, same task IDs)
├── terminalbench-2/            # TerminalBench 2.0 results (20 tasks)
├── self-learning-evidence/     # Memory accumulation data
factorial_ablation_4domain.json # Factorial ablation summary (4 domains)
factorial_ablation_results.json # Detailed ablation data (research/bargaining quality)
llm_judge_*.json                # LLM-as-judge quality scores (see SUPERSEDED_NOTICE)
database_correctness_regrade/   # Database correctness probe (SUPERSEDED — see aligned re-run)
quality_ablation/               # Correctness & quality re-grade, all 4 domains (aligned by construction)
```

## Related Repositories

- [tamirdresher/squad-swe-bench](https://github.com/tamirdresher/squad-swe-bench) — SWE-bench Lite results (198/300 = 66%)
- [bradygaster/squad](https://github.com/bradygaster/squad) — Squad source code
- [ulab-uiuc/MARBLE PR #245](https://github.com/ulab-uiuc/MARBLE/pull/245) — Submission to MARBLE benchmark

## Methodology

- **MARBLE**: Binary file output within 600s timeout (**completion**, not correctness). Same model for all conditions.
- **MARBLE correctness/quality (all 4 domains)**: milestone-KPI + 1–5 rubric, one identical judge (Claude Opus 4.6) and prompt across all four conditions. All four conditions were **re-run from scratch on the identical task IDs** in every domain (research, bargaining, coding, database), so tasks are aligned by construction. Raw re-runs in `results/aligned_rerun/`; independent gpt-4o cross-check on research/bargaining included. See `quality_ablation/`. The earlier `database_correctness_regrade/` probe is superseded (task-misaligned).
- **Memory-only condition**: injects a **Squad-generated `decisions.md`** into a raw single-agent run. This tests "Squad-flavored memory without coordination," not generic persistent memory.
- **TerminalBench 2.0**: 20-of-89 sequential subset. Baseline runs via the native terminal-bench harness; Squad runs via a host-side orchestrator (**different harness paths**), each scored by its own Docker verifier. Squad 16/20 vs baseline 15/20 is a **+1-task margin on n=20** — directional, not a clean controlled result.
- **DevBench**: Pass@1, 6 languages × 6 categories. Squad uses GPT-5.4; baseline is GPT-5.5 (**different model**). Raw per-task data is not hosted in this repo — treat as **contextual/preliminary**, not a controlled comparison.
- **SWE-bench Lite**: Pass@1, standard evaluation harness (198/300 = 66%). See [tamirdresher/squad-swe-bench](https://github.com/tamirdresher/squad-swe-bench) for raw data, retry configuration, and timeout/empty-patch accounting. Baseline is estimated from public reports — no verified same-model-without-Squad run.
- **Cost**: Per-task USD from actual API billing (Claude/GPT token usage): Full Squad $0.97, Coord-only $0.41, No-Squad $0.68.

## Reproducing

See individual result directories for task-level data. All raw agent outputs, prompts, and evaluation artifacts are included.

## Blog Post

See the [evaluation blog post](./blog/squad-benchmark-blog.html) comparing Squad to published baselines, following [GitHub's harness evaluation methodology](https://github.blog/ai-and-ml/github-copilot/evaluating-performance-and-efficiency-of-the-github-copilot-agentic-harness-across-models-and-tasks/).
