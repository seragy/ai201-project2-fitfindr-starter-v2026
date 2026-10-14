"""Score a run_eval results file against criteria.md, one rule per criterion."""
import re
import sys

text = open(sys.argv[1], encoding="utf-8").read()
body = text.split("## What actually happened", 1)[1]

# scenario name -> list of try blocks
scenarios = {}
for chunk in re.split(r"^### ", body, flags=re.M)[1:]:
    name, rest = chunk.split("\n", 1)
    tries = re.split(r"^\*\*Try \d+\*\*", rest, flags=re.M)[1:]
    scenarios[name.strip()] = tries


def fit_card(block):
    m = re.search(r"Fit card:\n\n```\n(.*?)\n```", block, re.S)
    return m.group(1) if m else None


def stopped(block):
    return "- stopped early: yes" in block


def model_calls(block):
    m = re.search(r"(\d+) model calls this run", block)
    return int(m.group(1)) if m else None


def crit1(b):
    ok = not stopped(b) and bool((fit_card(b) or "").strip()) and "Crashed" not in b
    return ok, "completed with fit card" if ok else "no fit card"


def crit2(b):
    msg = re.search(r"- stopped early: yes — (.*)", b)
    names_change = bool(msg) and any(k in msg.group(1) for k in ("price ceiling", "size", "words"))
    no_suggest = "] suggest_outfit" not in b
    ok = bool(msg) and names_change and no_suggest
    return ok, f"stopped={bool(msg)}, names change={names_change}, suggest_outfit skipped={no_suggest}"


def crit3(b):
    sel = re.search(r"selected_item = (lst_\d+)", b)
    got = re.search(r"\] suggest_outfit\n\s+in:\s+item=(lst_\d+)", b)
    ok = bool(sel and got and sel.group(1) == got.group(1))
    return ok, f"selected {sel and sel.group(1)} → suggest_outfit got {got and got.group(1)}"


def crit5(b):
    n = model_calls(b)
    ok = not stopped(b) and n is not None and n <= 2
    return ok, f"{n} model calls"


rows = {}
for name, rule, number in [
    ("matching query completes", crit1, 1),
    ("impossible query stops early", crit2, 2),
    ("selected item reaches suggest_outfit", crit3, 3),
    ("model calls per matching run", crit5, 5),
]:
    rows[number] = [rule(b) for b in scenarios[name]]

a, b_, c = (scenarios[f"fit card variety run {x}"] for x in "ABC")
rows[4] = []
for i in range(len(a)):
    cards = [fit_card(t[i]) for t in (a, b_, c)]
    ok = all(cards) and len(set(cards)) == 3
    rows[4].append((ok, f"{sum(1 for x in cards if x)} cards, {len(set(x for x in cards if x))} distinct"))

# Criterion 4 as revised in unit 4: no two of the three cards share their
# first three words (lowercased, punctuation stripped).
def opener(card):
    return tuple(re.sub(r"[^a-z0-9' ]", "", card.lower()).split()[:3])

rows["4r"] = []
for i in range(len(a)):
    cards = [fit_card(t[i]) for t in (a, b_, c)]
    openers = [opener(x) for x in cards if x]
    ok = len(openers) == 3 and len(set(openers)) == 3
    rows["4r"].append((ok, " | ".join(" ".join(o) for o in openers)))

targets = {1: 4, 2: 5, 3: 5, 4: 5, "4r": 5, 5: 5}
for n in [1, 2, 3, 4, "4r", 5]:
    passes = sum(ok for ok, _ in rows[n])
    verdict = "MET" if passes >= targets[n] else "MISSED"
    print(f"{n}: {' '.join('PASS' if ok else 'FAIL' for ok, _ in rows[n])}  -> {verdict} ({passes}/5)")
    for i, (ok, why) in enumerate(rows[n], 1):
        print(f"     try {i}: {why}")
