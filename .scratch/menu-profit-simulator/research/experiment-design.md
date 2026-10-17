# Research: restaurant experiment design practice

Ticket: `issues/05-restaurant-experiment-design-research.md`. Date: 2026-10-17.
Scope: facts, formulas, caveats only. This does not design the Experiment backlog.

Verification legend: **[V]** = read in the primary source (or its first-party landing page) this session. **[S]** = confirmed only from a search-result abstract/snippet, not read in full. **[U]** = unverified, stated from general knowledge; do not rely on it without checking.

## Headline caveat

There is almost no high-trust, peer-reviewed literature on randomized price or menu experiments in a *single* restaurant at its own volumes. The designs below come from (a) online-marketplace switchback statistics, (b) sequential-testing statistics from clinical trials and online A/B testing, and (c) a handful of small restaurant/cafeteria field studies run at institutional restaurants. The simulator should present all of it as "borrowed method, restaurant-specific parameters are assumptions".

## 1. Switchback (time-split) designs and carryover

**Source:** Bojinov, Simchi-Levi, Zhao, "Design and Analysis of Switchback Experiments", *Management Science* 69(7), 2023, 3759-3777. arXiv: https://arxiv.org/abs/2009.00148 (v4 HTML: https://arxiv.org/html/2009.00148v4).

- Setting: one experimental unit is exposed to a randomly chosen treatment each period; outcome measured; repeat. Precision depends on the *number of assignments (periods)*, not the number of transactions inside them. [V, abstract; S for the "precision is a function of the number of assignments" wording via HBS Working Knowledge summary]
- **m-carryover definition (Assumption 2.1):** there is a fixed, known m such that the outcome in period t depends only on the treatments assigned in periods t-m through t; treatments before t-m do not affect Y_t. [V, v4 HTML]
- **Other assumptions:** non-anticipating outcomes (the outcome at t does not depend on future assignments); bounded outcomes |Y_t| <= B; a non-degenerate-variance condition. [V]
- **Optimal design (Theorem 3.3, as extracted):** assign by fair coin (q = 1/2) at the randomization points; for T = nm with n >= 4, the optimal randomization points are {1, 2m+1, 3m+1, ..., (n-2)m+1}, i.e. blocks of roughly length m after an initial block of length 2m; when m = 0 randomize every period. [V via page extraction by a summarizing model; the exact index set and the n >= 4 condition should be re-checked against the PDF before being coded.]
- **Estimator:** Horvitz-Thompson estimator over periods t = m+1..T; periods without m prior periods of history are excluded from the estimand. [V, same caveat]
- **Misspecified m:** using a lag p >= m stays unbiased; p < m is biased for the order-m effect. Asymptotic normality is stated, and exact randomization p-values plus a finite-population CLT for conservative tests/CIs are provided. [V, v4 HTML and abstract]
- **Practical guidance on choosing m:** the extraction found no data-driven method; m comes from domain knowledge. [V for "not data-driven" only as far as the 100k of 228k characters read; the second half of the paper was not read.]
- A first extraction pass of the PDF claimed "discard the first m periods of each block". The v4 HTML contradicted that (no discarding; the estimand just starts at m+1). Treat the "discard" claim as wrong unless confirmed in the PDF. Flagging because the two extractions disagreed.

**Industry corroboration (company engineering blog, lower trust than the paper):** DoorDash describes switchback as randomizing region-by-time units to reduce dependence between buckets, and notes carryover as the main drawback. [S, search snippet only; URL not read in full. Candidates surfaced: careersatdoordash.com `?p=11043`, `?p=6696`.] A washout period is a common mitigation but its length is a judgement call. [S]

**Restaurant caveats (my reading, not from a source):**
- Carryover plausibly operates through guests, not the kitchen: regulars see a changed price/menu on one day and behave differently on the next visit. Restaurants have repeat customers, so m is not 0 even for daily blocks; no source quantifies m for restaurants. [U]
- A single restaurant has very few independent units, so the number of time blocks, not covers, drives power (see section 5).
- Day-of-week and season are strong confounders, so blocks need balancing/stratifying by day-of-week (Kohavi, section 5).

## 2. Menu-design tests

All items here are small observational/field studies, not definitive effect sizes for a generic restaurant.

| Topic | Source | Reported finding | Verification and caveats |
|---|---|---|---|
| Descriptive labels | Wansink, Painter, van Ittersum, "Descriptive menu labels' effect on sales", *Cornell Hotel & Restaurant Administration Quarterly* 42(6), 2001, 68 | Six-week field study in a faculty cafeteria; items with descriptive labels sold 27% more than items without; higher perceived quality/value | [S]. **Integrity caveat:** first author Brian Wansink was found by a Cornell committee to have committed academic misconduct (misreported data, problematic statistics, poor documentation); 13+ papers retracted by late 2018 (Retraction Watch: https://retractionwatch.com/2018/09/19/jama-journals-retract-six-papers-by-food-marketing-researcher-brian-wansink). I did **not** confirm whether this specific 2001 paper was retracted or corrected. Do not cite 27% as a prior without checking. |
| Price format (no $ sign) | Yang, Kimes, Sessarego, "$ or Dollars: Effects of Menu-price Formats on Restaurant Checks", Cornell Center for Hospitality Research report (c. 2009) | Lunch at St. Andrew's (Culinary Institute of America); numerals-only menus averaged about $5.55 (about 8%) higher checks than $-sign or written-out prices | [S] (Cornell eCommons: https://ecommons.cornell.edu/bitstream/1813/72131/1/Kimes14_Menu_price.pdf, fetch returned HTTP 429). Sample size, randomization method and p-values **not verified**. Institutional restaurant; a later replication is not known to me. A non-peer-reviewed center report. |
| Decoy / asymmetric dominance | Huber, Payne, Puto, *Journal of Consumer Research* 9(1), 1982, 90-98, doi:10.1086/208899 | Adding an asymmetrically dominated option can raise the share of the option that dominates it (violates regularity) | [S]. Lab choice experiments, not restaurant sales. Effect sizes do not transfer to menu revenue; replication in the field is mixed in the later literature, which I did not review. [U] |
| Placement / anchoring on menus | none found | No primary field source located for item placement or price-anchor position effects on a restaurant menu | Gap. Popular-press and consultancy claims surfaced in search (e.g. olveraadvisors.com) were excluded as non-primary. |

Design implication that is source-grounded: menu-presentation effects are small-to-moderate, measured as shifts in item mix or check size, so their outcome variance is the check-level variance in section 5, not a conversion rate.

## 3. Portion-size tests

- **Rolls, Morris, Roe 2002**, *American Journal of Clinical Nutrition* (PubMed 12450884): 51 adults, lunch once a week for 4 weeks, macaroni and cheese ad libitum at 500, 625, 750 or 1000 g; energy intake was 30% higher at the largest vs the smallest portion. [S, PubMed snippet/search abstract; the PubMed page itself returned a cookie wall.] Lab setting.
- **Diliberti, Bordi, Conklin, Roe, Rolls 2004**, *Obesity Research* 12(3), 562-568: cafeteria-style restaurant; pasta entree 248 g standard vs 377 g large; the large portion raised entree intake 43% and whole-meal intake 25%; no difference in ratings of portion appropriateness. [S] (https://pure.psu.edu/en/publications/increased-portion-size-leads-to-increased-energy-intake-in-a-rest/)
- **Gap and caveat:** both are consumption/health studies. They show people eat more when served more; they say nothing about pricing the larger portion, margin, waste, repeat visits or satisfaction, which are what the simulator's portion experiments would care about. No primary source found for portion-down ("shrinkflation") tests in restaurants or for guest reaction to smaller portions at the same price. Cost of the extra food and plate waste must come from the simulator's own recipe data.

## 4. Sequential testing, stopping boundaries

- **Peeking inflates error.** Johari, Pekelis, Walsh, "Always Valid Inference: Bringing Sequential Analysis to A/B Testing", arXiv:1512.04922 (later *Operations Research* 2022). Quote: "Even with 10,000 samples ... Type I error can easily increase fivefold." [V, ar5iv extraction]
- **Always-valid p-values via the mixture SPRT (mSPRT):** stop the first time the mixture likelihood ratio Lambda_n >= 1/alpha. Mixing-distribution variance should match the expected effect-size variance; the paper reports that misspecifying it by about one order of magnitude cost under 5% average power. Limitations stated: results are derived for a single stream while A/B tests have two; the binary-data CLT approximation is only approximately valid for small alpha; adaptive allocation is future work. [V, ar5iv extraction; second half of page not read]
- **Group sequential boundaries (fixed number of planned looks):** Pocock (1977, *Biometrika* 64, 191-199) uses a constant nominal significance level at each look; O'Brien and Fleming (1979, *Biometrics* 35, 549-556) uses very strict early boundaries that relax toward the final look, with the overall size close to that of a single fixed-sample test. [S for both, via search abstracts.] Numeric per-look levels for given K: **not verified** (I recall roughly 0.0158 per look for Pocock with 5 looks and alpha = 0.05; this is [U]). Get them from Jennison and Turnbull, *Group Sequential Methods with Applications to Clinical Trials* (2000) or a validated library before use.
- **Applicability caveat:** these procedures assume independent observations in a stream. Switchback data are time-block aggregates with possible carryover and serial correlation, so the nominal guarantees are not automatic; Bojinov et al.'s randomization-based p-values are the design-matched inference there. Combining switchback with sequential boundaries is not covered by any source I read. [gap]
- **Auto-abort in practice:** Kohavi et al. recommend near-real-time analysis with auto-abort when the treatment is significantly underperforming, ramping exposure up in steps (their example 0.1% -> 0.5% -> 2.5% -> 10% -> 50%). [V, Kohavi, Longbotham, Sommerfield, Henne, "Controlled experiments on the web: survey and practical guide", *Data Mining and Knowledge Discovery* 18, 2009, 140-181, doi:10.1007/s10618-008-0114-1; PDF read at https://www.exp-platform.com/Documents/GuideControlledExperiments.pdf.] Ramping is natural online but not available for a physical price on a menu board; a restaurant analogue (e.g. one daypart first) is my inference, not sourced.

## 5. Sample size, duration, restaurant volumes

**Formula (sourced).** Kohavi et al. (2009), section 3.2: at 95% confidence and 90% power, total sample size n = (4 r sigma / Delta)^2, where r = number of variants (about equal sized), sigma = standard deviation of the overall evaluation criterion (OEC), Delta = minimum difference to detect. They note the factor 4 may overestimate by about 25% for large n. [V] For r = 2 this is n_total = 64 sigma^2/Delta^2, i.e. 32 sigma^2/Delta^2 per arm. Note: the widely quoted "16 sigma^2/Delta^2 per arm" is the 80%-power version; I did not verify that variant in a source, so use the paper's 90% form.
- Their worked example confirms the arithmetic: 4*2*30/(3.75*0.05) squared is about 1.64 million users. [V]
- Variance reduction: use lower-variance OECs (counts or binary instead of revenue) and analyze only exposed users. [V]
- **Duration:** run at least a week or two, then in whole-week multiples, because of day-of-week effects; for primacy/newness effects some experiments "need to be run for multiple weeks". [V, sections 5.2.5 and 3.]

**Illustration of the order of magnitude (my arithmetic, assumed inputs, not sourced).** Mean check $30, check standard deviation $15, minimum detectable lift 3% ($0.90), 50/50 split: per arm n = 32 * 15^2 / 0.9^2 = about 8,900 checks, about 17,800 total. At a hypothetical 600 checks a week, that is about 30 weeks. Two takeaways for the planner: (1) small percentage lifts on average check are infeasible in a single restaurant within a quarter unless the effect is large or the metric is lower-variance; (2) this treats checks as independent, but in a switchback the independent units are the time blocks, so the effective n is smaller still (Bojinov et al.: precision depends on the number of assignments). No source gives restaurant-specific check standard deviations; the simulator should take sigma from its synthetic data and label it an assumption.

## 6. Guardrail metrics

- **Concept:** Kohavi, Tang, Xu, *Trustworthy Online Controlled Experiments* (Cambridge University Press, 2020) distinguishes *organizational guardrails* (protect the business) from *trust-related guardrails* (flag violated assumptions, e.g. sample ratio mismatch). [S: Cambridge chapter landing page found by search; the page fetch returned HTTP 500 and the book text was not read.] Any specific thresholds I might quote (e.g. an SRM p-value cutoff) are **[U]**.
- **Source-grounded rule of thumb:** guardrails/auto-abort act on a statistically significant degradation of the OEC or key metrics, as in Kohavi et al. 2009 (section 4 above).
- **Restaurant-specific guardrail lists (covers, average check, satisfaction, waste, margin, staff load):** no primary source found that defines thresholds for restaurants. The ticket's examples are sensible candidates, but the thresholds are not evidence-based; the simulator should present them as policy choices. Portion-test evidence (section 3) offers no satisfaction-vs-price data.
- Because guardrail metrics are many, repeated testing multiplies false alarms; multiplicity adjustment is addressed in the mSPRT paper's extension to multiple hypotheses ("extends to multiple hypothesis testing in the sequential setting" [S]). Not read in detail.

## 7. What could not be verified (consolidated)

1. Exact index set of the optimal switchback design and whether any periods are dropped: re-check Theorem 3.3 in the PDF. Two extractions disagreed on discarding.
2. Whether the Wansink 2001 descriptive-labels paper is retracted/corrected; the 27% figure is not safe to use as a prior.
3. Sample size, test details and randomization of Yang, Kimes, Sessarego (8%); eCommons fetch rate-limited.
4. Full abstracts of Rolls 2002 and Diliberti 2004 (read only via search snippets and a university repository summary); and of Huber et al. 1982.
5. Numeric per-look boundaries for Pocock and O'Brien-Fleming; no source read.
6. Any numeric guardrail threshold (SRM cutoff, acceptable covers or check drop); Kohavi et al. 2020 book not read.
7. Restaurant-specific carryover length m, check-level variance, and menu placement/anchoring effects: no primary source found.
8. DoorDash engineering pages seen only as search snippets.

## Source list

- Bojinov, Simchi-Levi, Zhao (2023), Management Science 69(7):3759-3777. https://arxiv.org/abs/2009.00148
- Johari, Pekelis, Walsh. Always Valid Inference. https://arxiv.org/abs/1512.04922
- Kohavi, Longbotham, Sommerfield, Henne (2009), DMKD 18:140-181. https://www.exp-platform.com/Documents/GuideControlledExperiments.pdf
- Kohavi, Tang, Xu (2020), Trustworthy Online Controlled Experiments, Cambridge UP (chapter 21 landing page found; not read).
- Pocock (1977), Biometrika 64:191-199. O'Brien and Fleming (1979), Biometrics 35:549-556. (abstracts only)
- Wansink, Painter, van Ittersum (2001), CHRAQ 42(6):68. Retraction Watch on Wansink, 2018-09-19.
- Yang, Kimes, Sessarego, Cornell CHR report. https://ecommons.cornell.edu/bitstream/1813/72131/1/Kimes14_Menu_price.pdf
- Huber, Payne, Puto (1982), JCR 9(1):90-98. doi:10.1086/208899
- Rolls, Morris, Roe (2002), AJCN. PubMed 12450884. Diliberti et al. (2004), Obesity Research 12(3):562-568.
