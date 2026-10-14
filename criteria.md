# Acceptance criteria — FitFindr

Five criteria that say what "working" means for this agent, written in unit 3
**before** any results existed.

An acceptance criterion names a target: a number, a count, a rate, or something
a person could plainly observe. *"The agent handles errors"* is an opinion.
*"When search returns nothing, the agent stops before calling the second tool,
in 5 of 5 tries"* is a criterion.

Under each one, write a sentence or two on **why that target** and not a
stricter one. A reason that says something about your tools, your loop, or the
data earns credit; *"80% seemed reasonable"* does not.

> Missing your own targets next unit costs you nothing. Setting a target so
> easy you can't miss it does.

**Two are written for you. You write three.**

---

1. Given a query that matches at least one listing, the agent completes all
   three tool calls and returns a fit card — in at least 4 of 5 tries.

**Why this target:** My search is a plain keyword match where every word in the
query has to appear in the listing's title, description or style_tags. Some
phrasings will miss even when a suitable item exists in the file, so I left room
for one of five to come back empty and stop early rather than completing.

2. Given a query that matches no listings, the agent stops before calling
   suggest_outfit and returns a message naming what to change — 5 of 5 tries.

**Why this target:** The branch is an `if` on an empty list in my own code, not
a model decision. Nothing about it varies between runs, so anything less than
5 of 5 would mean the branch is wrong rather than unlucky.

3. The item stored in session["selected_item"] is the same item passed to
   suggest_outfit — in 5 of 5 runs.

**Why this target:** This step is plain Python moving a value in and out of a
dictionary — no model call, no randomness. If it works once it works every time,
so anything less than 5 of 5 would mean a real bug rather than normal variation.
A looser target would be one I couldn't miss.

4. Running the same query three times with the cache off, no two fit cards are
   identical text — in 5 of 5 attempts.

**Why this target:** TEMPERATURE is 0.9, so the model is sampling rather than
picking the most likely wording every time. I ran this three times and got three
different captions with different outfit pairings each time. I set 5 of 5 rather
than 4 of 5 because at this temperature an identical repeat would mean something
is wrong — the cache is on, or the temperature setting isn't taking effect —
rather than normal variation.

> **Revised in unit 4:** Running the same query three times with the cache off,
> no two of the three fit cards open with the same first three words — in 5 of
> 5 attempts.
>
> **Why revised:** "Identical text" measured the wrong thing. In the before run
> it passed 5 of 5, but 25 of the 35 fit cards opened with "Scored", and in 4
> of the 5 attempts at least two of the three cards opened with the same three
> words ("scored this vintage" three times in attempt 1). Two captions that
> differ by one adjective still counted as different. The criterion exists
> because a caption that reads like a template isn't a caption, and the old
> version couldn't see a template. The new version can. The target stays 5 of 5.

5. A run that finds at least one listing makes no more than 2 model calls —
   in 5 of 5 runs.

**Why this target:** My loop calls the model exactly twice on the happy path,
once in suggest_outfit and once in create_fit_card. Search uses no model at all.
That count is fixed by the structure of my loop, not by anything the model
decides, so a third call would mean the loop ran a step twice or failed to stop
— the runaway-loop failure, which is the one I most want to catch.

---

<!-- ─────────────────────────────────────────────────────────────────────────
     UNIT 4 — read this before you change anything above.

     If a criterion turns out to be BROKEN rather than merely unmet, you can
     revise it, and that earns credit. But never delete or edit the original
     line. Add the revision underneath it, like this:

         ## 4. Something about the fit card

         The fit card is different every time.

         **Why this target:** ...

         > **Revised in unit 4:** For 5 different items, the 5 fit cards share
         > no opening sentence.
         >
         > **Why revised:** "different" wasn't checkable — two cards that
         > differed by one word still counted. The new version is something I
         > can actually score.

     That's a revision because the criterion couldn't be MEASURED.

     Lowering a target because you missed it is not a revision, and it costs
     you the point:

         ✗ "I said the empty search stops it 5 of 5 times, but I got 3 of 5,
            so 3 of 5 is more realistic."

     A number you missed stays where it is, gets diagnosed, and gets a fix
     attempted. That's where the points are.
     ───────────────────────────────────────────────────────────────────────── -->
