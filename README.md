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
usable output). See the correctness re-grade below — on the database domain, coordination
provided no correctness advantage.

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

### Database correctness (MARBLE recall, n=10)

Completion only checks that an answer appeared. Re-grading correctness with MARBLE's official
recall metric shows coordination did **not** help — the single agent scored highest:

| Condition | Completion | MARBLE recall (correctness) |
|-----------|-----------:|----------------------------:|
| Full Squad | 100% | **40%** |
| Coord-only | 90% | **50%** |
| Memory-only | 0% | **0%** |
| No Squad | 100% | **60%** |

With n=10 these gaps are within noise; the honest takeaway is "no correctness advantage on
database," not "single agents win." See [`database_correctness_regrade/`](database_correctness_regrade/).

## Repository Structure

```
results/
├── result_squad-copilot-cli/   # Full Squad: 400 tasks, all domains
├── result_coord-only/          # Ablation: coordination without memory
├── result_memory-only/         # Ablation: Squad-generated memory injected, no coordination
├── result_no-squad-ablation/   # Ablation: raw model, no Squad
├── result_no-squad-expanded/   # Extended no-squad runs (coding + database)
├── terminalbench-2/            # TerminalBench 2.0 results (20 tasks)
├── self-learning-evidence/     # Memory accumulation data
factorial_ablation_4domain.json # Factorial ablation summary (4 domains)
factorial_ablation_results.json # Detailed ablation data (research/bargaining quality)
llm_judge_*.json                # LLM-as-judge quality scores (see SUPERSEDED_NOTICE)
database_correctness_regrade/   # Database correctness re-grade (authoritative, single extractor)
```

## Related Repositories

- [tamirdresher/squad-swe-bench](https://github.com/tamirdresher/squad-swe-bench) — SWE-bench Lite results (198/300 = 66%)
- [bradygaster/squad](https://github.com/bradygaster/squad) — Squad source code
- [ulab-uiuc/MARBLE PR #245](https://github.com/ulab-uiuc/MARBLE/pull/245) — Submission to MARBLE benchmark

## Methodology

- **MARBLE**: Binary file output within 600s timeout (**completion**, not correctness). Same model for all conditions. Database correctness additionally re-graded by MARBLE recall — see `database_correctness_regrade/`.
- **Memory-only condition**: injects a **Squad-generated `decisions.md`** into a raw single-agent run. This tests "Squad-flavored memory without coordination," not generic persistent memory.
- **TerminalBench 2.0**: 20-of-89 sequential subset. Baseline runs via the native terminal-bench harness; Squad runs via a host-side orchestrator (**different harness paths**), each scored by its own Docker verifier. Squad 16/20 vs baseline 15/20 is a **+1-task margin on n=20** — directional, not a clean controlled result.
- **DevBench**: Pass@1, 6 languages × 6 categories. Squad uses GPT-5.4; baseline is GPT-5.5 (**different model**). Raw per-task data is not hosted in this repo — treat as **contextual/preliminary**, not a controlled comparison.
- **SWE-bench Lite**: Pass@1, standard evaluation harness (198/300 = 66%). See [tamirdresher/squad-swe-bench](https://github.com/tamirdresher/squad-swe-bench) for raw data, retry configuration, and timeout/empty-patch accounting. Baseline is estimated from public reports — no verified same-model-without-Squad run.
- **Cost**: Per-task USD from actual API billing (Claude/GPT token usage): Full Squad $0.97, Coord-only $0.41, No-Squad $0.68.

## Reproducing

See individual result directories for task-level data. All raw agent outputs, prompts, and evaluation artifacts are included.

## Blog Post

See the [evaluation blog post](./blog/squad-benchmark-blog.html) comparing Squad to published baselines, following [GitHub's harness evaluation methodology](https://github.blog/ai-and-ml/github-copilot/evaluating-performance-and-efficiency-of-the-github-copilot-agentic-harness-across-models-and-tasks/).
