# Validation strategy

Type: grilling
Status: open
Blocked by:

## Question

How does the build prove the simulator is right and honest? Decide: unit tests for the formulas (break-even drop, break-even elasticity, cost-shock flow, substitution allocation, price-cut cannibalization); what is checked against the hidden ground truth (e.g. share of items whose true elasticity falls inside the low-to-high band; whether the band-range profit change covers the truth-based change; whether simulated experiments recover the truth); where those checks run (tests vs notebook) and how results are shown in the README as limits rather than boasts; pass/fail thresholds, if any; and how the validation file is kept from leaking into the simulator.
