# FitFindr

> ### 👋 Start here
>
> **New to this repo? Read [RUNNING.md](RUNNING.md) first** — setup, every
> command, and what to do when something breaks.
>
> Once `python test.py` passes:
>
> ```bash
> python app.py listings --full -n 6      # read the data (Milestone 1)
> python app.py fields                    # what you can filter on
> python app.py ask 'vintage graphic tee under $30'
> ```
>
> All three tools are stubs, so that last command will do nothing useful yet.
> That's the starting position.
>
> **The rest of this file is your submission.** Fill it in as you go.

---

<!-- ─────────────────────────────────────────────────────────────────────────
     HOW TO USE THIS FILE

     This is your submission. Fill each section in as you finish the milestone
     it belongs to — don't leave it all to the end.

     Unit 3 asks for the first five sections. Unit 4 adds the five below them.
     Leave the unit 4 sections alone until then; they're here so you know
     what's coming.

     Everything is pasted as TEXT. No screenshots, no images, no video links.
     A typed block of output gets full credit; a picture of the same output
     gets none.
     ───────────────────────────────────────────────────────────────────────── -->

<!-- ═══════════════════════ UNIT 3 — THE BUILD ═══════════════════════ -->

## What This Does

FitFindr is a three-tool agent over a file of 40 secondhand clothing listings.
A user asks for something in plain language — "a vintage graphic tee under $30"
— and the agent searches the listings, works out what the item would go with
using the example wardrobe, and writes a short caption someone could post. If
nothing matches the query, it stops before calling the model and says what to
change instead of guessing.

---

## Tool Inventory

Query parsing happens before any tool runs, in `agent.py::parse_query`. It is
**regex-based, not model-based**: one pattern pulls out a price ceiling
(`under $30`, `below 30`, `$30`), another pulls out a size (`size M`), and the
rest becomes the description after filler words (`looking`, `for`, `a`, `the`,
`in`, `size`, …) are stripped. The stripping matters because search ANDs every
word — without it, "looking for a vintage graphic tee" would match nothing.

### `search_listings`

- **What it does:** Filters the 40 listings from `utils/data_loader.load_listings()` by price, size and keywords; no model call. Keywords are matched against the listing's `title` + `description` + `style_tags`, lowercased into one string, and **every** word in the description must appear in it (AND, not OR). Words match as substrings, so "tee" also matches "tees". Size is compared as whole tokens: the listing's size is split on whitespace and `/`, parenthetical notes like "(oversized)" are dropped, and the query size must equal one token case-insensitively — so "M" matches "S/M" and "M/L" but not "W30 L30". Survivors are sorted title-first (more query words in the title ranks higher) and capped at `config.SEARCH_RESULT_LIMIT` (10).
- **Inputs:** `description` (str or None — None/empty means no keyword filter), `size` (str or None — None means no size filter), `max_price` (float or None, inclusive — None means no price filter)
- **Returns:** `list[dict]` of up to 10 listing dicts, best match first, each with `id` (str), `title` (str), `description` (str), `category` (str), `style_tags` (list[str]), `size` (str), `condition` (str), `price` (float), `colors` (list[str]), `brand` (str or None), `platform` (str)
- **When it has nothing:** `[]` — an empty list, never None and never an exception (any error inside also returns `[]`). This is what the loop branches on.

### `suggest_outfit`

- **What it does:** Calls the model through `generate()` to suggest one or two outfits built around the new item. With a wardrobe, the prompt lists every owned piece (name, category, colors, style tags, notes) and asks the model to name them exactly; with an empty wardrobe it asks for general styling advice instead. Every listing field is guarded, since `brand` is None on most listings.
- **Inputs:** `new_item` (dict — a listing dict), `wardrobe` (dict with an `items` key holding a list of wardrobe-item dicts; may be empty)
- **Returns:** `str` — non-empty outfit suggestion text, under ~120 words. Whether the wardrobe was used is recorded by the loop in `session["wardrobe_used"]` (bool), not returned.
- **When it has nothing:** An empty wardrobe still returns general styling advice. If the model returns empty text or the call fails, it returns a fallback string that says it couldn't get outfit ideas (with the reason) and suggests pairing the item, by title, with neutral basics. Never None, never "".

### `create_fit_card`

- **What it does:** Calls the model through `generate()` to write a 2–4 sentence caption someone would actually post — mentions the item, its price and its platform once each, specific about the vibe, at most two hashtags.
- **Inputs:** `outfit` (str — the text from `suggest_outfit`), `new_item` (dict — a listing dict)
- **Returns:** `str` — the caption.
- **When it has nothing:** If `outfit` is empty or whitespace, or the model returns empty text or fails, it returns a short fallback caption naming the item: `New thrift find: the {title}. Already planning the first fit. 🛍️`. Never None, never "".

**Known limitation:** the two model-calling tools catch all errors including API
failures, so a bad key produces a fallback caption rather than surfacing the
error to the agent. Unit 4's error handling will need this changed.

> **Changed in unit 4 (Milestone 2):** both model-calling tools now re-raise
> `ModelUnavailable` instead of falling back, and `run_agent` catches it and
> stops with a message. Every other error still falls back as described above.
> `search_listings` now runs on the MCP server in `mcp_server.py`; its
> behaviour is unchanged.

---

## Planning Loop

**Branch rule:** If search_listings returns an empty list, put a message in the
session naming what the user could change — the size, the price ceiling, or the
wording — and stop. suggest_outfit is never called and session["fit_card"] stays
None. Otherwise take the first result, store it as session["selected_item"], and
continue to suggest_outfit and then create_fit_card.

**Where it lives:** `agent.py::run_agent`

**How the query is parsed:** Regex, not the model — `agent.py::parse_query` (see Tool Inventory).

**What moves through the session:** Each tool's result is written into the
session and read back out of it for the next call, rather than passed directly
from one call to the next — in order, `parsed` → `search_results` →
`selected_item` → `outfit_suggestion` and `wardrobe_used` → `fit_card`, with
`error` set instead when the search comes back empty. The loop runs one step per
pass and calls `trace.check_iterations()` on every pass, so it stops at
`config.MAX_ITERATIONS`.

---

## Sample Run

**The three tools, tested one at a time**

```
$ python -c "from tools import search_listings; print(search_listings('graphic tee', max_price=30))"
[{'id': 'lst_006', 'title': 'Graphic Tee — 2003 Tour Bootleg Style', 'description': 'Vintage-style bootleg tee with faded graphic. Slightly boxy fit. 100% cotton, soft and worn-in.', 'category': 'tops', 'style_tags': ['graphic tee', 'vintage', 'grunge', 'streetwear', 'band tee'], 'size': 'L', 'condition': 'good', 'price': 24.0, 'colors': ['black'], 'brand': None, 'platform': 'depop'}, {'id': 'lst_002', 'title': 'Y2K Baby Tee — Butterfly Print', 'description': 'Super cute early 2000s baby tee with butterfly graphic. Fitted crop length. Tag says medium but fits like a small.', 'category': 'tops', 'style_tags': ['y2k', 'vintage', 'graphic tee', 'cottagecore'], 'size': 'S/M', 'condition': 'excellent', 'price': 18.0, 'colors': ['white', 'pink', 'purple'], 'brand': None, 'platform': 'depop'}, {'id': 'lst_033', 'title': 'Vintage Band Tee — Faded Grey', 'description': 'Faded grey band-style tee with distressed graphic. Crew neck. Fits boxy. Well-loved but no holes or major damage.', 'category': 'tops', 'style_tags': ['vintage', 'grunge', 'band tee', 'graphic tee', 'streetwear'], 'size': 'L', 'condition': 'fair', 'price': 19.0, 'colors': ['grey', 'charcoal'], 'brand': None, 'platform': 'depop'}, {'id': 'lst_017', 'title': 'Mesh Long-Sleeve Top — Black', 'description': 'Sheer black mesh long-sleeve. Great for layering under a graphic tee or over a bralette. Stretchy material, fits true to size.', 'category': 'tops', 'style_tags': ['y2k', 'grunge', 'goth', 'layering'], 'size': 'S/M', 'condition': 'excellent', 'price': 15.0, 'colors': ['black'], 'brand': None, 'platform': 'depop'}]
```

```
$ python -c "from tools import suggest_outfit; from utils.data_loader import get_example_wardrobe, load_listings; print(suggest_outfit(load_listings()[0], get_example_wardrobe()))"
Outfit One:
Pair your vintage Levi's 501 jeans with the white ribbed tank top tucked in. Layer the oversized grey crewneck sweatshirt over top, letting the hem peek out. Slip into the chunky white sneakers and add the black crossbody bag for an effortless streetwear look.

Outfit Two:
Style the vintage Levi's 501 jeans with the black cropped zip hoodie. Throw on the vintage black denim jacket for a cool double-denim moment. Finish the outfit with the black combat boots and the black crossbody bag for a grungy, everyday vibe.
```

```
$ python -c "from tools import create_fit_card; from utils.data_loader import load_listings; print(create_fit_card('jeans and white sneakers', load_listings()[0]))"
Scored these vintage Levi's 501 jeans on Depop for just $38 and they are the ultimate everyday staple. That medium wash and broken-in knee fading give off the most effortless 90s streetwear vibe. Just throwing them on with crisp white sneakers and I'm out the door. #vintagelevis #denimstyle
```

**One full query**

```
$ python app.py ask 'vintage graphic tee under $30'

  Found:    Graphic Tee — 2003 Tour Bootleg Style — $24.0 on depop

  Outfit:   Outfit One: Skate Grunge
Pair the graphic tee with your baggy straight-leg jeans, worn with the brown leather belt. Add the black cropped zip hoodie layered underneath for an edgy look, and lace up your black combat boots. Finish with the black crossbody bag.

Outfit Two: Contrast Casual
Tuck the graphic tee into your wide-leg khaki trousers, styled with the brown leather belt. Throw on the slightly cropped vintage black denim jacket over top. Complete the outfit with your chunky white sneakers and the black crossbody bag for an effortless streetwear vibe.

  Fit card: Scored this perfectly faded 2003 tour bootleg graphic tee on Depop for just $24. It has that ultimate worn-in grunge feel that’s so hard to find. Can’t wait to style it for both skate days and casual street fits. #depopfinds #vintagestyle

2 model calls this session, 691 prompt + 178 output tokens
```

**The empty-search branch**

```
$ python app.py ask 'designer ballgown size XXS under $5'

  Nothing matched "designer ballgown" in size XXS at $5 or less. To find something: try a size other than XXS, or leave size out; raise the price ceiling above $5; use fewer or broader words — every word in the description has to match.

0 model calls this session
```

---

## How I Used AI

**1.** I gave Claude Code a spec saying suggest_outfit should return
{"text", "wardrobe_used"}, while also telling it not to change the stub
signatures. It caught the contradiction — the stub returns -> str, and returning
a dict would make `app.py` print a raw dict repr instead of the suggestion text.
I kept the stub's -> str and moved wardrobe_used into session["wardrobe_used"]
instead, which turned out better than what I'd asked for: criterion 3 is about
inspectable state, and that's one more thing I can check in the session.

**2.** My search requires every word in the query to appear in a listing, which
Claude Code pointed out would break the starter's own example query — "looking
for a vintage graphic tee under $30" finds nothing, because no listing contains
"looking" or "for". It added filler-word stripping to the regex parser before
the AND-match. I kept that, and wrote the parsing approach into my Tool
Inventory, since the README asks which method I chose.

<!-- ═══════════════════════ UNIT 4 — THE TEST ═══════════════════════

     Don't fill these in during unit 3.
     ═══════════════════════════════════════════════════════════════════ -->

---

## Run Log — Before

<!-- Five criteria, five tries each, in this exact format.

     Five, because your criteria are written out of five. Mark each try PASS
     or FAIL, count the passes, and read that count against your target — a
     row targeting 4 of 5 with three PASS cells is MISSED (3/5).

     `python run_eval.py --label before` runs everything and writes the table
     into results/. Paste it here and fill in the verdicts. -->

Results file: [`results/run_2026-10-14_1949_before.md`](results/run_2026-10-14_1949_before.md), produced by
`run_eval.py::main`, which calls `agent.py::run_agent` once per try with the
cache off. PASS and FAIL were marked by applying each criterion's rule to that
file, as written down below the table. `python score_run.py results/<file>.md`
applies the same rules and prints the marks.

| Criterion | Target | Try 1 | Try 2 | Try 3 | Try 4 | Try 5 | Verdict |
|---|---|---|---|---|---|---|---|
| 1. Matching query completes all three tools with a fit card | 4 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 2. Impossible query stops before `suggest_outfit` with a message naming what to change | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 3. `session["selected_item"]` is the item passed to `suggest_outfit` | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 4. Same query ×3, cache off: no two fit cards identical text | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 5. A matching run makes ≤ 2 model calls | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |

**How each try was marked**

1. `vintage graphic tee under $30`. PASS if the session has no `error` and has a non-empty `fit_card`.
2. `designer ballgown size XXS under $5`. PASS if `error` is set, the message names a size, price-ceiling or wording change, and the trace has no `suggest_outfit` step.
3. `90s track jacket in size M`. PASS if the `selected_item = …` id in the search step's trace note equals the `item=…` id in the `suggest_outfit` step's inputs.
4. `denim jacket under $50`, listed three times in `scenarios.py` (runs A, B, C). Attempt *i* is try *i* of A, B and C. PASS if all three have a fit card and no two are identical strings.
5. `platform sneakers size 8`. PASS if the run completed and the `done` trace step reports ≤ 2 model calls (`session["model_calls"]`).

**Real output, try 1 of each criterion.** Each block comes from
`agent.py::run_agent` (trace steps from `trace.step`; fit cards from
`tools.py::create_fit_card`), as recorded in the results file.

*Criterion 1:* trace, then the fit card

```
[1] parse_query (regex)
      in:  vintage graphic tee under $30
      out: {'description': 'vintage graphic tee', 'size': None, 'max_price': 30.0}
[2] search_listings (via MCP)
      in:  {'description': 'vintage graphic tee', 'size': None, 'max_price': 30.0}
      out: 3 items: Graphic Tee — 2003 Tour Bootleg Style, Vintage Band Tee — Faded Grey, Y2K Baby Tee — Butterfly Print
      →    branch: 3 found, selected_item = lst_006
[3] suggest_outfit
      in:  item=lst_006, wardrobe_items=10
      out: Outfit One: Streetwear Grunge Pair the graphic tee with your baggy straight-leg jeans in dark blue. Add the bl…
[4] create_fit_card
      in:  item=lst_006, outfit=511 chars
      out: Scored this washed black 2003 tour bootleg tee on Depop for just $24, and the worn-in grunge vibe is unreal. S…
[5] done
      →    4 passes, 2 model calls this run (cache hits not counted)
```

```
Scored this washed black 2003 tour bootleg tee on Depop for just $24, and the worn-in grunge vibe is unreal. Styled it two ways, from baggy denim streetwear to edgy khaki contrast casual. Can't wait to live in this boxy fit all season. #depopfinds #grungefashion
```

*Criterion 2:* trace, then `session["error"]`

```
[1] parse_query (regex)
      in:  designer ballgown size XXS under $5
      out: {'description': 'designer ballgown', 'size': 'XXS', 'max_price': 5.0}
[2] search_listings (via MCP)
      in:  {'description': 'designer ballgown', 'size': 'XXS', 'max_price': 5.0}
      out: [] (empty)
      →    branch: empty, stopping before suggest_outfit
[3] done
      →    2 passes, 0 model calls this run (cache hits not counted), stopped early
```

```
Nothing matched "designer ballgown" in size XXS at $5 or less. To find something: try a size other than XXS, or leave size out; raise the price ceiling above $5; use fewer or broader words — every word in the description has to match.
```

*Criterion 3:* trace (`selected_item = lst_004` in step 2, `item=lst_004` going into step 3)

```
[1] parse_query (regex)
      in:  90s track jacket in size M
      out: {'description': '90s track jacket', 'size': 'M', 'max_price': None}
[2] search_listings (via MCP)
      in:  {'description': '90s track jacket', 'size': 'M', 'max_price': None}
      out: 1 items: 90s Track Jacket — Navy/White Stripe
      →    branch: 1 found, selected_item = lst_004
[3] suggest_outfit
      in:  item=lst_004, wardrobe_items=10
      out: Outfit 1: Streetwear Casual Pair the Champion track jacket with the white ribbed tank top as your base layer. …
[4] create_fit_card
      in:  item=lst_004, outfit=594 chars
      out: Scored this vintage 90s Champion track jacket on Poshmark for just $45 and I'm obsessed. It's the ultimate lig…
[5] done
      →    4 passes, 2 model calls this run (cache hits not counted)
```

*Criterion 4:* attempt 1, the three fit cards from runs A, B and C

```
A: Scored this vintage Wrangler cropped denim jacket on Poshmark for just $42 and it’s the ultimate blank canvas for custom patches. The structured shoulders look so good styled up for effortless streetwear or thrown over wide-leg trousers. #DenimStyle #PoshmarkFind

B: Scored this vintage Wrangler cropped denim jacket on Poshmark for just $42 and it has the best structured shoulders. It’s a total blank canvas, making it so easy to style for effortless streetwear looks or clean minimal fits. 

#WranglerStyle #ThriftFinds

C: Scored this vintage Wrangler cropped denim jacket on Poshmark for just $42 and it has the best structured shoulders. It’s a total blank canvas, making it so easy to style for effortless streetwear or casual neutral fits. Can't wait to live in this light wash staple all season long. #denimjacket #poshfinds
```

*Criterion 5:* trace (the `done` step reports the model calls)

```
[1] parse_query (regex)
      in:  platform sneakers size 8
      out: {'description': 'platform sneakers', 'size': '8', 'max_price': None}
[2] search_listings (via MCP)
      in:  {'description': 'platform sneakers', 'size': '8', 'max_price': None}
      out: 1 items: Platform Sneakers — White Chunky Sole
      →    branch: 1 found, selected_item = lst_019
[3] suggest_outfit
      in:  item=lst_019, wardrobe_items=10
      out: Outfit One: Embrace the Y2K streetwear vibe. Pair the platform sneakers with your baggy straight-leg jeans, da…
[4] create_fit_card
      in:  item=lst_019, outfit=539 chars
      out: Scored these Y2K white chunky platform sneakers on Poshmark for just $48, and the late-90s streetwear energy i…
[5] done
      →    4 passes, 2 model calls this run (cache hits not counted)
```

---

## Verdicts and Diagnoses

<!-- MET or MISSED per criterion against LAST UNIT's target, plus a sentence on
     how you decided.

     Then, for every miss: which of the four places it happened — a tool, the
     loop's branch, the session, or the model's output — AND the mechanism.

     Not a diagnosis:  "The fit card was bad."
     A diagnosis:      "The fit card criterion missed on 2 of 5 items. Both had
                        an empty brand field. My prompt puts the brand in the
                        first sentence, so the card opened with a blank and read
                        like a fragment. The tool worked; the prompt assumed a
                        field that isn't always there."

     Look for a pattern. Three misses on the same tool is one problem, not
     three. -->

| # | Criterion | Target | Verdict | How I decided |
|---|---|---|---|---|
| 1 | Matching query completes with a fit card | 4 of 5 | MET (5/5) | All five tries had no `error` and a non-empty `fit_card` |
| 2 | Impossible query stops before `suggest_outfit`, names what to change | 5 of 5 | MET (5/5) | All five stopped at the search step, with no `suggest_outfit` in the trace, and the message names size, price ceiling and wording |
| 3 | `selected_item` is the item passed to `suggest_outfit` | 5 of 5 | MET (5/5) | `lst_004` selected and `lst_004` received, in all five traces |
| 4 | Same query ×3: no two fit cards identical | 5 of 5 | MET (5/5) | No identical strings in any attempt. **But see the revision below** |
| 4 (revised) | Same query ×3: no two fit cards share their first three words | 5 of 5 | **MISSED (1/5)** | Only attempt 5 had three different openers. Scored on the same before-run data by `score_run.py` |
| 5 | Matching run makes ≤ 2 model calls | 5 of 5 | MET (5/5) | The `done` step reported exactly 2 in all five |

**Diagnoses**

**I missed nothing as originally written, and that says more about my targets
than about my agent.** Taking the criteria one at a time:

- **Criterion 1 was too easy, and its reason was never tested.** I gave it 4 of
  5 because "some phrasings will miss". But the scenario used one phrasing, and
  the search step is deterministic, so all five tries searched the same thing
  and got the same three tees. Only a model failure could have failed a try. It
  also counts *any* fit card as a pass, even for the wrong item. In unit 3,
  `search_listings('graphic tee')` returned a mesh long-sleeve top because its
  description mentions a graphic tee, and criterion 1 would have passed that. I'd
  tighten it to five *different* phrasings of matching queries, where the
  selected item's category also has to match what was asked for.
- **Criterion 3 passes by construction.** `run_agent` passes
  `session["selected_item"]` straight into `suggest_outfit`, so the trace
  comparison can only fail if I break that line. That's the honest answer to
  "why 5 of 5". It's still worth keeping as a regression check, but it was never
  at risk. A tighter version would check what reached the model, e.g. that
  `suggest_outfit`'s prompt contains the selected item's title.
- **Criteria 2 and 5 are deterministic and should be 5 of 5.** The branch is an
  `if` on an empty list, and the call count is fixed by the loop's shape. Both
  met their targets for the reasons I gave in unit 3.
- **Criterion 4 measured the wrong thing, so I revised it** (in `criteria.md`,
  under the original). At temperature 0.9, two byte-identical captions are close
  to impossible, so "no two identical" could only fail if the cache was on. The
  revised version asks whether the captions *read* differently, and it misses.

**The miss: criterion 4 (revised), 1 of 5. Where: the model's output, caused by
the prompt in `tools.py::create_fit_card`.** The tool worked: every run returned
a caption that mentions the item, price and platform. The problem is the
prompt's instruction to "mention the item, its price and the platform once
each". The single sentence that fits all three is a purchase announcement,
"Scored this \<item\> on \<platform\> for $\<price\>". Nothing in the prompt says
how to open, so the model leads with that sentence. Temperature 0.9 varies the
adjective after "Scored this" but not the opening.

**It's a pattern, not a fluke.** It isn't specific to the denim jacket: 25 of
the 35 fit cards across *every* scenario open with "Scored" (21 of them with
"Scored this"). So it's one problem with one cause, the prompt, not three
separate misses.
---

## Loop Trace

<!-- One full run, printed step by step, with the MCP call visible in it.

     `python app.py ask '...' --trace` once you've added the trace.step()
     calls in Milestone 2.

     Worth pasting BOTH the happy path and the empty-search path. The empty
     one should be visibly shorter, because it stops. If your two traces are
     the same length, your branch isn't working — and this is the fastest way
     anyone will ever find that out. -->

**Happy path**

```
$ AI201_CACHE=0 python app.py ask 'vintage graphic tee under $30' --trace
[1] parse_query (regex)
      in:  vintage graphic tee under $30
      out: {'description': 'vintage graphic tee', 'size': None, 'max_price': 30.0}
[2] search_listings (via MCP)
      in:  {'description': 'vintage graphic tee', 'size': None, 'max_price': 30.0}
      out: 3 items: Graphic Tee — 2003 Tour Bootleg Style, Vintage Band Tee — Faded Grey, Y2K Baby Tee — Butterfly Print
      →    branch: 3 found, selected_item = lst_006
[3] suggest_outfit
      in:  item=lst_006, wardrobe_items=10
      out: Outfit one leans into classic grunge streetwear. Pair the graphic tee with your baggy straight-leg jeans, dark…
[4] create_fit_card
      in:  item=lst_006, outfit=590 chars
      out: Scored this vintage-style bootleg graphic tee on Depop for just $24, and the worn-in black cotton is pure grun…
[5] done
      →    4 passes, 2 model calls this run (cache hits not counted)

  Found:    Graphic Tee — 2003 Tour Bootleg Style — $24.0 on depop

  Outfit:   Outfit one leans into classic grunge streetwear. Pair the graphic tee with your baggy straight-leg jeans, dark wash. Layer your vintage black denim jacket on top for extra texture, and lace up your black combat boots. Finish the look with your black crossbody bag.

Outfit two plays with contrasting proportions and earth tones. Tuck the graphic tee into your wide-leg khaki trousers, secured with the brown leather belt. Throw your oversized grey crewneck sweatshirt over your shoulders for a casual layered effect, and step into your chunky white sneakers to complete the streetwear vibe.

  Fit card: Scored this vintage-style bootleg graphic tee on Depop for just $24, and the worn-in black cotton is pure grunge streetwear perfection. It’s got that boxy fit that looks unreal paired with baggy denim or dressed up with trousers. #thriftfind #streetwear

2 model calls this session, 691 prompt + 170 output tokens
```

**Empty search**

```
$ python app.py ask 'designer ballgown size XXS under $5' --trace
[1] parse_query (regex)
      in:  designer ballgown size XXS under $5
      out: {'description': 'designer ballgown', 'size': 'XXS', 'max_price': 5.0}
[2] search_listings (via MCP)
      in:  {'description': 'designer ballgown', 'size': 'XXS', 'max_price': 5.0}
      out: [] (empty)
      →    branch: empty, stopping before suggest_outfit
[3] done
      →    2 passes, 0 model calls this run (cache hits not counted), stopped early

  Nothing matched "designer ballgown" in size XXS at $5 or less. To find something: try a size other than XXS, or leave size out; raise the price ceiling above $5; use fewer or broader words — every word in the description has to match.

0 model calls this session
```

The empty-search trace is three steps against five, and there's no
`suggest_outfit` step in it: the branch stops the loop.

**On the MCP move:** <!-- what changed in your code, and whether anything
behaved differently afterwards. If the rewire didn't work, say exactly where it
broke — the error text and the last thing that worked. That earns the point in
full. -->

`search_listings` is registered in `mcp_server.py` with a description written
for a caller who can't see the code: the units, the size-token rule, and the
empty case (`[]`, never null). In `agent.py::run_agent`, the direct
`search_listings(...)` call became `call_tool("search_listings", {...})`.
Nothing behaved differently afterwards. Before rewiring I called it both ways on
three inputs: a match, a no-match, and a listing with a brand. All three came
back identical, including `[]` for no match and `None` for a missing brand
(JSON `null` comes back as `None`). One new way to fail came with it: the
server process might not start. `run_agent` now catches `MCPError` for that. I
forced it by pointing the client at a server file that doesn't exist, and it
stopped with: *"The listings search couldn't be reached, so nothing was
searched. Try the same query again; if it keeps failing, run `python
mcp_server.py` to see why the search server won't start."*

### Failure modes, triggered on purpose

| Failure | How I triggered it | Before a handler | What the agent says now |
|---|---|---|---|
| Empty search | `python app.py ask 'sequined opera cape size XXS under $3'` | Already handled by the unit 3 branch | *Nothing matched "sequined opera cape" in size XXS at $3 or less. To find something: try a size other than XXS, or leave size out; raise the price ceiling above $3; use fewer or broader words — every word in the description has to match.* |
| Empty wardrobe | `python app.py ask 'denim jacket under $50' --empty-wardrobe` | Already handled: `suggest_outfit` asks for general advice | General advice that names no owned pieces: *"…pair this light wash cropped Wrangler jacket with high-waisted black cargo pants or baggy wide-leg trousers…"*, then a normal fit card. `wardrobe_used` is False. |
| Model unavailable | Bad key for one command only: `GEMINI_API_KEY=<key with last char changed> python app.py ask 'platform sneakers size 8'` (an uncached query). The env var overrides `.env`, so the real key was never edited. | **Silent.** No crash, but the run looked successful. The outfit text said *"Couldn't get outfit ideas (The model rejected your API key…)"*, the fit card was the generic fallback *"New thrift find: the Platform Sneakers — White Chunky Sole. Already planning the first fit. 🛍️"*, and `session["error"]` stayed `None`. | *The search worked — it found the Platform Sneakers — White Chunky Sole ($48.0 on poshmark) — but the AI model couldn't be reached, so there's no outfit or fit card. The model rejected your API key. Check GEMINI_API_KEY in your .env file, or create a fresh key at aistudio.google.com. If you just changed your key, put it back; otherwise wait a minute and ask again.* |

The model-unavailable handler: `suggest_outfit` and `create_fit_card` re-raise
`ModelUnavailable`, and `run_agent` catches it, writes the message above into
`session["error"]` and stops, so `fit_card` stays `None`.



---

## The Improvement

<!-- What you changed, why your diagnosis pointed at it, and the after-run in
     the same table format. One change, measured properly.

     `python run_eval.py --label after` -->

**What I changed:** One prompt, in `tools.py::create_fit_card`. I added one
instruction and left everything else alone:

```diff
         "specific about the vibe. "
+        "Don't open with how or where you got it — no "
+        "'Scored', 'Just scored', 'Found', 'Snagged' or 'Copped' — and keep the "
+        "price and platform out of the first sentence. Open with the vibe, the "
+        "outfit, or a moment you'd wear it in. "
         "At most two hashtags. Return only the caption."
```

No other code, scenario, or setting changed between the two runs.

**Which failure it was meant to fix:** Criterion 4 (revised), 1 of 5. The
diagnosis put the miss in the model's output, caused by the prompt: asking for
item, price and platform made "Scored this \<item\> on \<platform\> for
$\<price\>" the obvious first sentence, and 25 of 35 cards opened with
"Scored". So the change targets the opening sentence directly.

### Run Log — After

Results file: [`results/run_2026-10-14_1956_after.md`](results/run_2026-10-14_1956_after.md), produced by
`run_eval.py::main` with the same eight scenarios, five tries each, cache off.
Marked by `score_run.py` with the same rules as the before run.

| Criterion | Target | Try 1 | Try 2 | Try 3 | Try 4 | Try 5 | Verdict |
|---|---|---|---|---|---|---|---|
| 1. Matching query completes all three tools with a fit card | 4 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 2. Impossible query stops before `suggest_outfit` with a message naming what to change | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 3. `session["selected_item"]` is the item passed to `suggest_outfit` | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 4. Same query ×3, cache off: no two fit cards identical text | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 4 (revised). Same query ×3: no two fit cards share their first three words | 5 of 5 | PASS | PASS | PASS | PASS | FAIL | **MISSED (4/5)** |
| 5. A matching run makes ≤ 2 model calls | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |

**Side by side**

| Criterion | Before | After |
|---|---|---|
| 1 | MET (5/5) | MET (5/5) |
| 2 | MET (5/5) | MET (5/5) |
| 3 | MET (5/5) | MET (5/5) |
| 4 (original) | MET (5/5) | MET (5/5) |
| 4 (revised) | MISSED (1/5) | MISSED (4/5) |
| 5 | MET (5/5) | MET (5/5) |
| Fit cards opening with "Scored" / "Just scored" | 25 of 35 | 0 of 35 |
| Fit cards missing the price or the platform | 0 of 35 | 0 of 35 |

**Did it help, and how do I know:** It helped, but it didn't fix the problem,
and the revised criterion is still missed. It went from 1 of 5 to 4 of 5 on the
same scenarios and the same scoring rule. "Scored" disappeared completely, and
no card lost its price or platform. But the after run found a new default:
**12 of 35 cards open with "Nothing beats"**, and "Channeling major/peak" opens
another 10. Attempt 5 failed because all three cards opened "Nothing beats the":

```
A: Nothing beats the structured shoulders on this Wrangler cropped denim jacket for nailing that effortless streetwear aesthetic. I grabbed it on Poshmark for $42 and it's already the ultimate blank canvas for my weekend double denim fits. #denimjacket #poshmarkfinds
B: Nothing beats the structured shoulders on this vintage Wrangler denim jacket for throwing over an oversized crewneck. Grabbed it on Poshmark for $42 and it's practically begging for a high-low streetwear moment with some khaki trousers and combat boots. #denimstyle #poshmarkfinds
C: Nothing beats the structured shoulders on this vintage Wrangler denim jacket for throwing together a high-contrast double denim look. I grabbed it on Poshmark for $42 and it's basically the ultimate blank canvas for customizing. Going to live in this all through streetwear season. #denimstyle #poshfinds
```

Attempt 1, for comparison, had three different openers:

```
A: The ultimate vintage streetwear vibe unlocked with this cropped Wrangler denim jacket. It's giving major structured-shoulder energy and is the blank canvas my closet needed. Grabbed it on Poshmark for $42 and honestly can't wait to style it two ways. #DenimStyle #PoshmarkFinds
B: The ultimate light wash Wrangler cropped denim jacket is giving effortless vintage streetwear energy. Grabbed it on Poshmark for just $42, and it's basically a blank canvas waiting for some pins. Already planning to wear it with dark denim and chunky sneakers on heavy rotation. #denimjacket #streetwear
C: Nothing beats that effortless 90s streetwear vibe when you throw on the ultimate cropped Wrangler jacket over a black zip hoodie and khaki trousers. This light wash beauty was an absolute steal at $42 on Poshmark. Ready to customize it or just wear it on repeat all season long. #denimstyle #streetwear
```

So the change worked on the symptom I named and missed the cause. Banning one
opener just moved the model to its next most likely one. The prompt still never
gives the model a *reason* to open differently from one run to the next. The
prompt's other instruction, keeping the price and platform out of the first
sentence, was followed in 33 of 35 cards. The attempt 5 cards also show how
narrow the new default is: they share their first eight words, "Nothing beats
the structured shoulders on this", which comes almost straight from the
listing's description. So the first three words understate how alike they are.

---

## What's Still Broken

<!-- For each criterion still missed: what you'd do, and why you stopped where
     you did. "I ran out of time" is fine if it's true. Pretending nothing is
     left is not. -->

**Criterion 4 (revised): MISSED, 4 of 5 after the fix.** The next thing I'd
try is giving each run a different opening angle chosen in code: for example,
pick one of "the outfit", "a place you'd wear it", "the texture or fit", or
"what it replaces in your closet" at random and put it in the prompt. Then the
variety comes from the input rather than from hoping the model samples away
from its favourite phrase. Banning more phrases ("Nothing beats", "Channeling")
would just repeat what I already did: the model would find its next default. I
stopped here because the brief allows one change per run, and making a second
one would leave me unable to tell which change did what.

**Criteria that pass but shouldn't be trusted yet.** These aren't misses, but
the Verdicts section explains why they passed easily:

- **Criterion 1** used one phrasing on a deterministic search, so its own
  reason ("some phrasings will miss") was never tested. It also passes a fit
  card for the wrong item. `search_listings('graphic tee')` still returns the
  mesh long-sleeve top, because substring matching hits "graphic tee" in its
  description. I'd test five different phrasings and check the selected item's
  category.
- **Criterion 3** passes by construction. I'd check what reached the model
  (the item title in `suggest_outfit`'s prompt), not just what the session
  handed over.

**Other known gaps:**

- **`wardrobe_used` doesn't reflect what happened.** It's set from whether the
  wardrobe has items, not from whether the model actually used them. Now that a
  bad key stops the run, the case where it was misleading (a fallback outfit
  with `wardrobe_used=True`) only happens if the model returns empty text.
- **Only `ModelUnavailable` is surfaced.** Running out of rate-limit retries
  raises a `RuntimeError` inside `generate()`, and the tools still turn that into
  a fallback outfit or caption. The run would look complete. I didn't trigger
  this, because it needs the per-minute quota exhausted for five retries in a
  row.

<!-- ═════════════════════════════════════════════════════════════════════

     SUBMISSION CHECKLIST — unit 3

       [ ] criteria.md has five numbered criteria, each with a target
       [ ] Each criterion has a reason underneath it
       [ ] All five unit 3 sections above have real content
       [ ] Tool Inventory: all three tools, inputs WITH TYPES, a specific
           return value, and the empty case
       [ ] Planning Loop names the branch rule and agent.py::run_agent
       [ ] Sample Run: one full query plus the three per-tool tests, as text
       [ ] At least four new commits
       [ ] Repository URL submitted — WRITE IT DOWN, you submit the same one
           next unit

     SUBMISSION CHECKLIST — unit 4

       [ ] mcp_server.py exists with one tool registered
           (or a written record of exactly where the rewire broke)
       [ ] Run Log — Before, five criteria, five tries each
       [ ] Real output pasted underneath, naming file and function
       [ ] A verdict on every criterion
       [ ] A diagnosis for every miss, naming a place AND a mechanism
       [ ] Loop Trace, with the MCP call visible in it
       [ ] All three failure modes triggered and handled
       [ ] One improvement, with Run Log — After in the same format
       [ ] What's Still Broken
       [ ] At least four new commits
       [ ] The SAME repository URL as last unit

     Do not delete and recreate this repository. Your commit history is what
     shows your criteria existed before your results did.
     ═════════════════════════════════════════════════════════════════════ -->

---

📖 **How to run this project: [RUNNING.md](RUNNING.md)**
