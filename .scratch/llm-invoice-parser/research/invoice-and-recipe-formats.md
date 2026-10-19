# Research: what supplier invoices and written recipes look like in text

Ticket: `../issues/01-invoice-and-recipe-formats.md`. Researched 2026-10-19.

## How to read this note

- Source quality is uneven. Primary or government sources are USDA/Child Nutrition documents for recipes and yields. For invoices I found **no distributor-owned documentation** (Sysco, US Foods and others do not publish invoice layouts that I could reach). Invoice claims therefore rest on software-vendor help pages and blogs. Those are **secondary** and are tagged `[secondary]`.
- Every claim has a URL. Anything I could not confirm by reading the page is tagged `UNVERIFIED`.
- "Common / rare" labels are **my judgment** from how often a feature shows up across the sources, not measured frequencies. No source gives a prevalence figure. Treat them as UNVERIFIED as frequencies.
- Section 6 examples are **constructed by me**. They are not real documents and no real supplier's layout is being reproduced.

## 1. Pack-size notation

Findings:

- Descriptions embed the pack configuration inside the product name, for example "6/10#", "4/1 GAL", "4/5 LB". Form is `count/size`. A $42.50 price on "chicken breast 4/5 LB" is per case (20 lb total), not per pound. `[secondary]` https://imagetotable.ai/blog/food-distributor-invoice-line-item-extraction-errors
- `#10` is a can-size code, not "number of pounds". A #10 can is stated as about 105-110 oz by one source `[secondary]` https://jochamp.com/discovering-food-can-sizes/ and as "No. 10 can (108 oz)" by the USDA Food Buying Guide (primary) https://foodbuyingguide.fns.usda.gov/Content/TablesFBG/USDA_FBG_Appendix_B.pdf . Other codes listed: #5 (28-32 oz), #303 (18-20 oz), #300 (15 oz), #12 (120-125 oz) `[secondary]` https://jochamp.com/discovering-food-can-sizes/ . Net contents vary by product (liquid vs solid), so a table lookup is only approximate.
- The same size is written several ways across vendors: "50 LB", "50 lbs", "50#". `[secondary]` (search summary of the same imagetotable page and similar; not confirmed by direct quote) https://imagetotable.ai/blog/food-distributor-invoice-line-item-extraction-errors . Note `6/10#` (pounds sign after) versus `6/#10` (can size, hash before) are different things, and an LLM can confuse them. This pitfall is my inference from the two notations; no source says it.
- Pack count can be larger than one level, for example `2/5 LB` or `12/32 OZ`. UNVERIFIED that nested (three-level) notations such as `4/6/1 LB` occur; I did not find a source.

Judgment: `count/size UNIT` is **common** on broadline and dry-goods invoices. Pack text living inside the description (not in its own column) is common `[secondary]`.

## 2. Catch-weight items

- Ordered in cases (nominal weight), received and billed by actual weight in pounds. Example from a guide: PO of 50 cases at about 60 lb/case at $6.20/lb, invoice "2,972 pounds billed at $6.20 per pound". `[secondary]` https://invoicedataextraction.com/blog/catch-weight-invoice-reconciliation
- Invoice lines can show both ordered and received weight, for example "Qty Ord: 40 LB", "Qty Rec'd: 38.7 LB", "$3.87/lb"; the bill uses received weight (38.7 x 3.87 = 149.77), and a naive extractor may take the ordered figure. `[secondary]` https://imagetotable.ai/blog/food-distributor-invoice-line-item-extraction-errors
- Mechanism of nominal versus actual weight is described in https://softwareconnect.com/learn/catch-weight-management/ `[secondary]` (seen only as a search result; not fetched, UNVERIFIED in detail).

Judgment: **common for meat, poultry, seafood, some cheese** lines. For this project the right unit cost is price per lb times received lb, divided by lb; the ordered case count must not be used as the quantity. Rare in produce and dry goods.

## 3. Units of measure and abbreviations

- Common invoice UOM codes: CS (case), EA (each), LB (pound). `[secondary]` https://help.truecommerce.com/en/articles/11470672-unit-of-measures-uoms (search summary only; page not fetched).
- Split case: a line can be sold as individual units out of a case. Distributor EDI files carry a split flag (Sysco: a column value greater than 0; US Foods: a "~EA~" pattern) per Restaurant365 documentation. `[secondary]` https://docs.restaurant365.com/docs/split-unit-of-measure . That page gives no price examples, so how case and split prices compare is UNVERIFIED. Note this describes EDI files, not printed text.
- Produce is sold by count or bunch inside a case ("24 ct", "24 bunch"). `[secondary]` from procurement price sheets surfaced in search, for example https://media.cobbk12.org/media/WWWCobb/medialib/freshproduceandeggs-b1928_taba.a4fe8446904.pdf (not read in full; UNVERIFIED beyond the search summary). Maps naturally onto this project's `head`, `each`, `doz`.
- Product names are inconsistent across suppliers ("onion green iceless", "green onion bunch", "scallion" for one ingredient). `[secondary]` https://imagetotable.ai/blog/food-distributor-invoice-line-item-extraction-errors . So ingredient matching to `ingredients.name` is a real task, not just unit parsing.
- Government abbreviation list (DLA subsistence abbreviations) could not be fetched (HTTP 403). UNVERIFIED: https://www.dla.mil/Portals/104/Documents/TroopSupport/Subsistence/DoingBusiness/techops/abbrev_20JUL21.pdf

Units the simulator already uses (lb, qt, gal, oz, each, doz, head) cover most of the above. Likely **missing** from that list (my inference, from the sources above): fl oz, pint, cup, tbsp, tsp, bunch, count-per-case, kg/g/L (metric imports), case and pack as non-convertible. Volume-to-weight conversion is not possible without a density, see section 5.

## 4. Case price versus unit price, fees, credits, substitutions, back-orders

- Case price versus unit price: the price column is per the invoice UOM (case, each, or lb), not always per pound. See the $42.50 example above. `[secondary]` https://imagetotable.ai/blog/food-distributor-invoice-line-item-extraction-errors . Units-per-case information is needed to derive a per-unit cost.
- Off-invoice allowances and deductions (pickup allowance, prompt-pay discount, volume incentive) appear as separate lines below products, so "the invoice total does not equal the sum of product line totals". `[secondary]` same imagetotable page.
- Fuel surcharge: printed just below the line-item detail, on invoices from distributors that apply one. `[secondary]` https://necs.com/mods_KB/mod1501.htm (search summary; not fetched, UNVERIFIED in detail). Restaurants have disputed Sysco's fuel surcharge: https://www.law360.co.uk/articles/924671 (headline only; not read).
- Deposits: beverage invoices carry deposits as their own lines (example format quoted in a search summary: "Bottle deposit - 6 x $0.05 = $0.30") `[secondary]`, from https://beancount.io/blog/2026/09/08/bottle-bills-beverage-retailers-container-deposits-handling-fees-redemption-guide (not fetched, UNVERIFIED). A Florida statute is reported to require keg deposits and returns credits to be shown separately on invoices (https://www.myfloridahouse.gov/Statutes/2017/0561.4205/, fetch redirected away, UNVERIFIED). State rules differ.
- Credits: credit memos are separate documents or negative lines that reference an invoice number. A general-business source (not restaurant-specific) says credit memos reference the PO, bill of lading and prior invoice number: https://www.up.com/suppliers/existing/order-inv/invoice-prep/partial-shipments `[not restaurant-specific]`.
- Substitutions and shorts: receivers annotate by hand, for example "Subbed 85/15 for 80/20", crossed-out quantities. That information is not in the printed text and "standard extraction cannot reliably connect" it to a line. `[secondary]` https://imagetotable.ai/blog/food-distributor-invoice-line-item-extraction-errors . For text-only input this means a substitution may appear only as a different product description on the line, or as a note line. Back-order specifics (an "ordered 3, shipped 2, B/O 1" style line) are plausible but I found **no source**: UNVERIFIED. Partial shipments are reported to get a separate invoice per delivery (https://www.up.com/suppliers/existing/order-inv/invoice-prep/partial-shipments, not restaurant-specific).

Judgment on prevalence (UNVERIFIED as frequencies):

| Feature | Judgment |
|---|---|
| `count/size` pack text, price per case | common |
| Per-lb price on protein lines (catch weight) | common |
| Fuel surcharge / delivery fee line | common |
| Credit lines, shorts, out-of-stock lines | common but varied layout |
| Deposits (kegs, bottles) | common on beverage only, rare elsewhere |
| Substitution as a visible text note | occasional |
| Allowances / rebates / prompt-pay discounts | occasional |
| Split-case (EA from a case) | occasional |
| Nested pack notation | rare, UNVERIFIED |

## 5. Recipe quantity styles, yield and trim

Primary sources are USDA Child Nutrition documents (school and summer-meal programs). They are institutional, large-batch and unusually rigorous; a bistro's written recipes will be looser. That gap is **UNVERIFIED** (I found no source on restaurant recipe style).

- A standardized recipe has ingredient, weight, measure columns, yield, servings and serving size. Best practice: "measure all liquid ingredients by volume and measure all non-liquid ingredients by weight". USDA recipes list both weight and measure because not all sites have scales. https://theicn.org/cicn/resources/159/basic-food-prep-skills/109844/how-to-read-a-standardized-recipe.pdf
- Quantities in that document appear as mixed units and Unicode fractions: "5 lb", "3 qt ½ cup", "3 lb 6 oz", "1 gal 2 ¼ qt", "6 lb 10 oz" with "(1 No. 10 can)" in parentheses, and "sliced ¼”" in the ingredient text. Same URL. So compound quantities (`3 lb 6 oz`, `1 gal 2 qt`) and can-size mentions occur even in tidy recipes.
- Fractions and mixed numbers also occur as "93/8 cups" (a PDF-extraction rendering of 9 3/8), "1/2 inch", "1/4 cup", and decimal conversions like "5 lb 10 oz = 5.62 lb". https://foodbuyingguide.fns.usda.gov/Content/TablesFBG/USDA_FBG_Appendix_B.pdf . The garbled "93/8" is a live reminder that text exports can break fraction formatting.
- Yield and trim: AP (as purchased) versus EP (edible portion). Yield % = EP / AP x 100; EP cost per lb = AP cost / yield. https://psu.pb.unizin.org/hmd329/chapter/ch7/ `[secondary summary via search; page returned 403]`. Primary example from USDA: 1 lb of whole fresh watermelon yields 0.61 lb diced, so buying for 2 lb diced needs 2 / 0.61 = 3.28 lb (round up to 3.5 lb); broccoli yield 0.81; apples 0.78. https://foodbuyingguide.fns.usda.gov/Content/TablesFBG/USDA_FBG_Appendix_B.pdf
- Cooking loss is also a yield: ground beef (no more than 15% fat) 1 lb raw gives 0.75 lb cooked, drained. Same USDA appendix.
- Rule from USDA: if the recipe uses the ingredient in the same form it was purchased (for example cooked diced chicken bought as cooked diced chicken), no yield adjustment applies. Same appendix.
- "To taste", "as needed", ranges ("2-3 cloves"), "pinch": the USDA documents I read do **not** use them (they are standardized for consistency), so I found no primary source. They are common in restaurant and home recipes in my experience, but that is UNVERIFIED here. The ICN document mentions "taste preferences" only in a different context.
- Ranges and counts appear in USDA yield tables as item counts ("125-138 count apples"), which is a size spec, not a recipe quantity range.

Implication (my inference): the simulator has no waste or yield model, and `qty_per_serving` is a single number in one unit. A recipe line given as AP versus EP, or as volume, cannot be stored faithfully without either a stated convention (for example store EP quantity and price in AP terms with a yield flag) or a flag for the reviewer.

## 6. Constructed examples (NOT real documents)

All text below is **made up by me** to illustrate the notations above. Suppliers, items and prices are fictional.

### 6a. Constructed broadline-style invoice text

```
INVOICE 100482   WEEK OF 2026-03-02
QTY UOM PACK/SIZE  DESCRIPTION               PRICE    EXT
 2  CS  6/#10      TOMATO WHOLE PEELED       24.50    49.00
 1  CS  4/1 GAL    OIL CANOLA FRY            38.90    38.90
 1  CS  40 LB      FLOUR AP UNBLEACHED       21.75    21.75
 2  CS  4/5 LB     CHICKEN BREAST BNLS       42.50    85.00
    CW  38.7 LB    BEEF CHUCK GRND 80/20     3.87/LB 149.77
 3  EA             LETTUCE ROMAINE 24CT      (split) 1.60 4.80
 1  CS  24/12 OZ   WATER SPARKLING           17.00    17.00
    ** FUEL SURCHARGE                                  6.00
    -- CREDIT  SHORT 1 CS FLOUR (OOS)               -21.75
```

What it exercises: three pack notations, a catch-weight line, a split-case line, a fee line, a negative line.

### 6b. Constructed small-vendor invoice (free text)

```
Valley Greens - delivered Tue
Romaine hearts   2 cases @ 36.00 (12 ct each)
Lemons 115ct     1 cs  41.25
Basil            5 lb  @ 9.00/lb
Subbed: arugula 4 lb for baby spinach 4 lb (same price)
Backordered: shallots 10 lb, will ship Thu
Total due 169.25
```

What it exercises: no columns, price basis stated inline, a substitution note, a back-order note, no pack code.

### 6c. Constructed beverage invoice lines

```
KEG 1/2 BBL  PALE ALE         158.00
KEG DEPOSIT  1 x 30.00         30.00
CS 24/12 OZ  LAGER            31.20
BOTTLE DEPOSIT 24 x 0.05       1.20
CREDIT EMPTY KEG (1)         -30.00
```

### 6d. Constructed recipe text, varied styles

```
Tomato soup (makes 2 gal)
 1 No. 10 can whole peeled tomatoes (6 lb 10 oz)
 2 1/2 lb onions, peeled and diced        (AP 3 lb)
 3-4 cloves garlic
 1 1/2 qt stock
 1/2 cup cream, optional
 salt and white pepper, to taste
 olive oil as needed
Portion: 8 oz
```

What it exercises: mixed fractions, a can-size reference with a weight, an AP versus EP note, a range, "optional", "to taste", "as needed", portion size separate from yield.

## 7. Scope implications for the design ticket (my recommendations; for later decision)

- **Likely in scope as common:** `count/size UNIT` packs, `#10` and other can codes (via a small lookup, flagged as approximate), per-lb catch-weight lines, case versus each versus lb price basis, fee and credit lines recognized and excluded from ingredient costs, product-name matching to existing `ingredient_id`.
- **In scope with a flag:** substitutions and back-orders as text notes, deposits (not an ingredient cost), ranges and "to taste" lines (stage with a reason, do not invent a quantity), volume-to-weight (needs a density the schema lacks).
- **Out of scope, say so under Limitations:** handwritten annotations (not in text), EDI formats, nested or unusual pack notation, yield and trim modelling (the simulator has none), metric-only invoices.
- The eval generator should be told which messiness types are grounded in sources (Sections 1-5) versus guessed.

## Not verified

- No distributor-owned (Sysco, US Foods, etc.) invoice documentation; no real invoice sample seen.
- No frequency data for any feature.
- Restaurant (as opposed to school-program) recipe styles, including "to taste" and ranges.
- Back-order line formatting; nested pack notation; the DLA abbreviation list (403); the Florida deposit statute (redirected); PSU recipe-costing chapter (403, used only through a search summary); US Foods and Sysco column conventions beyond the R365 EDI note.
