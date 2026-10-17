# Restaurant experiment design practice

Type: research
Status: resolved
Blocked by:

## Question

What do high-trust sources say about running price and menu experiments in a single-location (or few-location) restaurant: switchback / time-split designs and carryover effects, menu-design tests (placement, descriptions, anchoring), portion-size tests, sample-size and duration needs given weekly volumes, and typical guardrail metrics and stop rules (e.g. covers, average check, satisfaction, waste, sequential testing boundaries)? Capture sources, formulas and caveats; do not design our backlog (that belongs to the Experiment backlog ticket).

## Answer

Findings are on the throwaway branch `research/experiment-design` (commit 7d38222, not pushed), file `.scratch/menu-profit-simulator/research/experiment-design.md`. The branch lives in the worktree `.claude/worktrees/agent-a678cdd8d3a615432`.

Gist:
- Switchback: precision depends on the number of time blocks, not covers. Carryover is modelled as m periods (Bojinov, Simchi-Levi, Zhao 2023). No source gives a restaurant-specific m.
- Menu-design and portion evidence is thin: small cafeteria/institutional studies, consumption only. The largest effect cited comes from a researcher found to have committed misconduct. Treat it as weak.
- Sample size: n = (4rσ/Δ)² per arm (Kohavi et al. 2009); run whole weeks. Illustration with assumed inputs: detecting a 3% lift in average check at ~600 checks/week takes ~30 weeks. Small lifts at one restaurant are near-infeasible, which matters for how the backlog scores feasibility.
- Stop rules: peeking at fixed-horizon p-values inflates Type I error (Johari et al.); always-valid (mSPRT) or group-sequential boundaries are the options. No source combines them with switchback data.
- Guardrails: no restaurant-specific thresholds exist in primary sources; they are policy choices for the backlog ticket.

Caveats: many claims rest on search abstracts only; the file's section 7 lists eight unverified items (including Theorem 3.3 of the switchback paper, and whether the 27% label study was retracted). Re-check these before the spec cites them.
