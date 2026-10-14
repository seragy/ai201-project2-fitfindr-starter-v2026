"""
The FitFindr planning loop.

This is the file that makes FitFindr an agent rather than a script. It decides
which tool to run next based on what the last one returned.

If your loop calls all three tools no matter what comes back, you have a list
of function calls. A loop looks at the last result before it picks the next
step. **That branch is the graded part of this unit.**

Build and test your three tools in `tools.py` first. Then come here.

    python agent.py          runs both example paths below
"""

import re

import config
import generate
import trace
from tools import suggest_outfit, create_fit_card
from mcp_client import MCPError, call_tool
from generate import ModelUnavailable


# ── session state ─────────────────────────────────────────────────────────────

def new_session(query: str, wardrobe: dict) -> dict:
    """
    A fresh session for one user interaction.

    The session is the single source of truth for a run. Every tool result goes
    in here, and the next tool reads it back out.

    You could pass values straight from one call to the next. It would work,
    and you would not be able to test it — you can't print a variable you have
    already overwritten. Going through the session is what makes the state
    visible, and unit 4 has you write a criterion about exactly that.

    Add fields if you need them.
    """
    return {
        "query": query,              # what the user typed
        "parsed": {},                # description / size / max_price you pulled out of it
        "search_results": [],        # everything search_listings returned
        "selected_item": None,       # the one you chose — goes into suggest_outfit
        "wardrobe": wardrobe,        # the user's wardrobe
        "outfit_suggestion": None,   # what suggest_outfit returned
        "wardrobe_used": None,       # whether the outfit drew on owned pieces
        "fit_card": None,            # what create_fit_card returned
        "error": None,               # set when the run ended early
        "model_calls": 0,            # model requests this run made (cache hits excluded)
    }


# ── query parsing ─────────────────────────────────────────────────────────────
#
# Regex, not the model: the query shapes are simple, and parsing for free keeps
# both model calls for the tools that need them.

_PRICE = re.compile(
    r"(?:under|below|less than|max|up to|<)\s*\$?\s*(\d+(?:\.\d+)?)|\$\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_SIZE = re.compile(r"\bsize\s+([a-z0-9./]+)", re.IGNORECASE)

# search_listings ANDs every word, so conversational filler has to go or
# "looking for a vintage tee" would match nothing.
_FILLER = {
    "a", "an", "the", "i", "im", "i'm", "me", "my", "for", "in", "with", "and",
    "looking", "want", "need", "find", "show", "some", "something", "please",
    "under", "below", "size",
}


def parse_query(query: str) -> dict:
    """Pull description, size and max_price out of plain language."""
    text = query or ""

    max_price = None
    price_match = _PRICE.search(text)
    if price_match:
        max_price = float(price_match.group(1) or price_match.group(2))
        text = text[:price_match.start()] + " " + text[price_match.end():]

    size = None
    size_match = _SIZE.search(text)
    if size_match:
        size = size_match.group(1).rstrip(".")
        text = text[:size_match.start()] + " " + text[size_match.end():]

    words = [w for w in re.findall(r"[a-z0-9']+", text.lower()) if w not in _FILLER]
    return {"description": " ".join(words), "size": size, "max_price": max_price}


def _no_results_message(parsed: dict) -> str:
    """Say what was searched and which of the three knobs the user can turn."""
    wanted = [f'"{parsed["description"]}"' if parsed["description"] else "anything"]
    changes = []
    if parsed["size"]:
        wanted.append(f"in size {parsed['size']}")
        changes.append(f"try a size other than {parsed['size']}, or leave size out")
    if parsed["max_price"] is not None:
        wanted.append(f"at ${parsed['max_price']:g} or less")
        changes.append(f"raise the price ceiling above ${parsed['max_price']:g}")
    if parsed["description"]:
        changes.append("use fewer or broader words — every word in the description has to match")
    if not changes:
        changes.append("describe the item differently")
    return f"Nothing matched {' '.join(wanted)}. To find something: " + "; ".join(changes) + "."


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Run the loop once and return the finished session.

    Args:
        query:    what the user asked for, in plain language
                  (e.g. "vintage graphic tee under $30, size M").
        wardrobe: a wardrobe dict — get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py.

    Returns:
        The session dict. **Check session["error"] first** — if it isn't None,
        the run ended early and the later fields will still be None.

    ─────────────────────────────────────────────────────────────────────────
    TODO — build this, following the branch rule you wrote in Milestone 2.

      1. Start a session with new_session().

      2. Count the times round the loop, and call trace.check_iterations(count)
         on each one before you go again. It raises when the count passes
         MAX_ITERATIONS in config.py — see trace.py.

      3. Parse the query into a description, a size, and a max_price. Regex,
         string splitting, or asking the model are all fine — say which you
         chose in your README. Put the result in session["parsed"].

      4. Call search_listings() with what you parsed.
         Put the results in session["search_results"].

         ⚠️ THIS IS THE BRANCH. If nothing came back:
              - put a message in session["error"] saying what the user could
                change — "No results" is not that message
              - return the session
              - do NOT call suggest_outfit with nothing

      5. Choose an item — the first result is fine. Put it in
         session["selected_item"].

      6. Call suggest_outfit() with the selected item and the wardrobe.
         Put the result in session["outfit_suggestion"].

      7. Call create_fit_card() with the outfit and the item.
         Put the result in session["fit_card"].

      8. Return the session.

    ─────────────────────────────────────────────────────────────────────────
    IN UNIT 4 you come back and add two things:

      • Trace calls. One per step. `trace.step("search_listings", inputs=...,
        returned=...)` — see trace.py. Your README needs the output.

      • A handler for ModelUnavailable, so a bad key produces a message rather
        than a stack trace. The import is already at the top of this file.
    """
    session = new_session(query, wardrobe)
    calls_before = generate.call_count()

    # Each pass does one step and picks the next from what is now in the
    # session. Every tool reads its inputs out of the session, never from the
    # previous call's return value.
    step = "parse"
    count = 0
    while step != "done":
        count += 1
        trace.check_iterations(count)

        if step == "parse":
            session["parsed"] = parse_query(session["query"])
            trace.step("parse_query (regex)", inputs=session["query"],
                       returned=str(session["parsed"]))
            step = "search"

        elif step == "search":
            parsed = session["parsed"]
            arguments = {
                "description": parsed["description"],
                "size": parsed["size"],
                "max_price": parsed["max_price"],
            }
            # search_listings runs on the MCP server (mcp_server.py), not in-process.
            try:
                session["search_results"] = call_tool("search_listings", arguments)
            except MCPError as exc:
                session["error"] = (
                    "The listings search couldn't be reached, so nothing was searched. "
                    "Try the same query again; if it keeps failing, run "
                    "`python mcp_server.py` to see why the search server won't start."
                )
                trace.step("search_listings (via MCP)", inputs=str(arguments),
                           returned=str(exc).splitlines()[0], note="MCP call failed, stopping")
                step = "done"
                continue

            if not session["search_results"]:
                # The branch: nothing to style, so stop before suggest_outfit.
                session["error"] = _no_results_message(session["parsed"])
                trace.step("search_listings (via MCP)", inputs=str(arguments),
                           returned=session["search_results"],
                           note="branch: empty, stopping before suggest_outfit")
                step = "done"
            else:
                session["selected_item"] = session["search_results"][0]
                trace.step("search_listings (via MCP)", inputs=str(arguments),
                           returned=session["search_results"],
                           note=f"branch: {len(session['search_results'])} found, "
                                f"selected_item = {session['selected_item']['id']}")
                step = "suggest"

        elif step == "suggest":
            session["wardrobe_used"] = bool((session["wardrobe"] or {}).get("items"))
            try:
                session["outfit_suggestion"] = suggest_outfit(
                    session["selected_item"], session["wardrobe"]
                )
            except ModelUnavailable as exc:
                session["error"] = _model_unavailable_message(session, exc)
                trace.step("suggest_outfit", inputs=session["selected_item"],
                           returned=str(exc), note="model unavailable, stopping")
                step = "done"
                continue
            trace.step("suggest_outfit",
                       inputs=f"item={session['selected_item']['id']}, "
                              f"wardrobe_items={len((session['wardrobe'] or {}).get('items') or [])}",
                       returned=session["outfit_suggestion"])
            step = "fit_card"

        elif step == "fit_card":
            try:
                session["fit_card"] = create_fit_card(
                    session["outfit_suggestion"], session["selected_item"]
                )
            except ModelUnavailable as exc:
                session["error"] = _model_unavailable_message(session, exc)
                trace.step("create_fit_card", inputs=session["selected_item"],
                           returned=str(exc), note="model unavailable, stopping")
                step = "done"
                continue
            trace.step("create_fit_card",
                       inputs=f"item={session['selected_item']['id']}, "
                              f"outfit={len(session['outfit_suggestion'])} chars",
                       returned=session["fit_card"])
            step = "done"

    session["model_calls"] = generate.call_count() - calls_before
    trace.step("done", note=f"{count} passes, {session['model_calls']} model calls this run (cache hits not counted)"
               + (", stopped early" if session["error"] else ""))
    return session


def _model_unavailable_message(session: dict, exc: Exception) -> str:
    """Name what broke, keep what did work, and say what to try."""
    item = session["selected_item"] or {}
    return (
        f"The search worked — it found the {item.get('title', 'item')} "
        f"(${item.get('price')} on {item.get('platform')}) — but the AI model "
        f"couldn't be reached, so there's no outfit or fit card. {exc} "
        f"If you just changed your key, put it back; otherwise wait a minute and "
        f"ask again."
    )


# ── running it directly ───────────────────────────────────────────────────────

def _show(session: dict) -> None:
    if session["error"]:
        print(f"  stopped: {session['error']}")
        print(f"  fit_card is {session['fit_card']!r} — it should still be None here")
        return

    item = session["selected_item"] or {}
    print(f"  found:    {item.get('title')} — ${item.get('price')} on {item.get('platform')}")
    print(f"  outfit:   {session['outfit_suggestion']}")
    print(f"  fit card: {session['fit_card']}")


if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== A query the data can match ===")
    _show(run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    ))

    print("\n=== A query it can't ===")
    _show(run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    ))

    print(
        "\nThe second one should stop before the fit card. If both paths look "
        "the same,\nthe branch isn't doing anything yet."
    )
