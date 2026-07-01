# Squad Benchmark Results

Public repository containing all raw benchmark data for evaluating [Squad](https://github.com/bradygaster/squad) — a multi-agent coordination layer for GitHub Copilot CLI.

## Benchmarks

| Benchmark | Tasks | Squad | Baseline (no Squad) | Δ | Controlled? |
|-----------|-------|-------|---------------------|---|-------------|
| **MARBLE** (ACL 2025) | 400 (+160 ablation) | 100% | 60% | +40pp | ✅ Same model |
| **DevBench** | 1,800 | 53.1% | 43.5%† | +9.6pp | ⚠️ Different model |
| **SWE-bench Lite** | 300 | 66% | ~48%‡ | +18pp | ⚠️ Estimated baseline |
| **TerminalBench 2.0** | 20 | 80% | 75% | +5pp | ✅ Same model |

† DevBench: Squad uses GPT-5.4; baseline is GPT-5.5 (different model).
‡ SWE-bench Lite: Baseline estimated from public reports. No same-model-without-Squad run.

## Controlled Ablation (MARBLE)

Factorial ablation: same model (Claude Opus 4.6), same tasks, same metric.
4 domains × 4 conditions × 10 tasks = 160 task-runs.

| Condition | Coding | Research | Bargaining | Database | **Average** |
|-----------|--------|----------|------------|----------|-------------|
| Full Squad | 100% | 100% | 100% | 100% | **100%** |
| Coord-only | 100% | 90% | 90% | 90% | **92.5%** |
| Memory-only | 40% | 70% | 60% | 25% | **48.75%** |
| No Squad | 90% | 80% | 70% | 0% | **60%** |

## Repository Structure

```
results/
├── result_full-squad/          # 400 tasks, all domains
├── result_coord-only/          # Ablation: coordination without memory
├── result_memory-only/         # Ablation: memory without coordination
├── result_no-squad-ablation/   # Ablation: raw model, no Squad
├── result_no-squad-expanded/   # Extended no-squad runs (coding + database)
├── terminalbench-2/            # TerminalBench 2.0 results (20 tasks)
├── self-learning-evidence/     # Memory accumulation data
factorial_ablation_4domain.json # Factorial ablation summary (4 domains)
factorial_ablation_results.json # Detailed ablation data
llm_judge_*.json                # LLM-as-judge quality scores
```

## Related Repositories

- [tamirdresher/squad-swe-bench](https://github.com/tamirdresher/squad-swe-bench) — SWE-bench Lite results (198/300 = 66%)
- [bradygaster/squad](https://github.com/bradygaster/squad) — Squad source code
- [ulab-uiuc/MARBLE PR #245](https://github.com/ulab-uiuc/MARBLE/pull/245) — Submission to MARBLE benchmark

## Methodology

- **MARBLE**: Binary file output within 600s timeout. Same model for all conditions.
- **TerminalBench 2.0**: Tasks run via Harbor (baseline) and host-side Squad. Same model (Claude Opus 4.6).
- **DevBench**: Pass@1, 6 languages × 6 categories. Results from Brady Gaster's evaluation.
- **SWE-bench Lite**: Pass@1, standard evaluation harness. Results from Squad v0.9.6.
- **Cost**: All costs from actual API billing (Claude/GPT token usage).

## Reproducing

See individual result directories for task-level data. All raw agent outputs, prompts, and evaluation artifacts are included.

## Blog Post

See the [evaluation blog post](./blog/squad-benchmark-blog.html) comparing Squad to published baselines, following [GitHub's harness evaluation methodology](https://github.blog/ai-and-ml/github-copilot/evaluating-performance-and-efficiency-of-the-github-copilot-agentic-harness-across-models-and-tasks/).
