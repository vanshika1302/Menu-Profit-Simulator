# Elasticity benchmarks for restaurant menu items

Type: research
Status: resolved
Blocked by:

## Question

What do high-trust primary sources (academic papers, industry studies) report for own-price elasticity of restaurant / food-service demand, at menu-item and category level, and what range is defensible for low / medium / high bands? Also: any evidence on substitution or cross-item effects within a menu, and the typical gap between item-level and restaurant-level elasticity. Capture sources, figures, and caveats; do not decide the bands (that belongs to the Simulation model ticket).

## Answer

Findings are on the throwaway branch `research/elasticity-benchmarks` (commit b07495f, not pushed), file `.scratch/menu-profit-simulator/research/elasticity-benchmarks.md`, in the worktree `.claude/worktrees/agent-acae1044e4b0755b8`. Bands were deliberately not decided here.

Gist:
- Pooled food-away-from-home own-price elasticity: mean -0.81, range -0.23 to -1.76 (N=13; Andreyeva, Long & Brownell 2010, verified in the paper's table).
- Large split by service level: USDA ERS ERR-139 gives limited-service -0.13, other FAFH -0.43, full-service -1.96 (verified in the PDF). UK evidence (Law et al. 2022): fast food about -0.7, restaurants about -1.0 to -1.5 (read via a fetch summary, not the tables). Sit-down is more elastic than quick-service in both, but magnitudes differ widely, so bands likely need to depend on service level and concept (ticket 01).
- Item-level own-price evidence is thin: abstracts only (Kiefer et al. 1994, Noone & Cachia 2020), so no item-level coefficients are quoted.
- Substitution evidence is category-level and imprecise; no clean within-menu substitution rate was found, so the substitution share has to remain a user-set assumption.
- No primary source quantifies the item-level vs restaurant-level gap. Treat as an evidence gap.

Caveats: a "1.2 to 2.3" restaurant figure came from an untraced trade-page snippet and is not used; Richards/Jekanowski et al. 2001 and Noone & Cachia coefficients were unverified. Best follow-up: the Noone & Cachia full text.
