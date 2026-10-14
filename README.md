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

| Criterion | Target | Try 1 | Try 2 | Try 3 | Try 4 | Try 5 | Verdict |
|---|---|---|---|---|---|---|---|
| 1.  |  |  |  |  |  |  |  |
| 2.  |  |  |  |  |  |  |  |
| 3.  |  |  |  |  |  |  |  |
| 4.  |  |  |  |  |  |  |  |
| 5.  |  |  |  |  |  |  |  |

**Real output from one try**, pasted as text, naming the file and function
that produced it:

```

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
| 1 |  |  |  |  |
| 2 |  |  |  |  |
| 3 |  |  |  |  |
| 4 |  |  |  |  |
| 5 |  |  |  |  |

**Diagnoses**



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

```

**Empty search**

```

```

**On the MCP move:** <!-- what changed in your code, and whether anything
behaved differently afterwards. If the rewire didn't work, say exactly where it
broke — the error text and the last thing that worked. That earns the point in
full. -->



---

## The Improvement

<!-- What you changed, why your diagnosis pointed at it, and the after-run in
     the same table format. One change, measured properly.

     `python run_eval.py --label after` -->

**What I changed:**

**Which failure it was meant to fix:**

### Run Log — After

| Criterion | Target | Try 1 | Try 2 | Try 3 | Try 4 | Try 5 | Verdict |
|---|---|---|---|---|---|---|---|
| 1.  |  |  |  |  |  |  |  |
| 2.  |  |  |  |  |  |  |  |
| 3.  |  |  |  |  |  |  |  |
| 4.  |  |  |  |  |  |  |  |
| 5.  |  |  |  |  |  |  |  |

**Did it help, and how do I know:**

<!-- If it made things worse, say that. Honestly reported, that earns full
     credit and is more interesting than one that worked. -->



---

## What's Still Broken

<!-- For each criterion still missed: what you'd do, and why you stopped where
     you did. "I ran out of time" is fine if it's true. Pretending nothing is
     left is not. -->



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
