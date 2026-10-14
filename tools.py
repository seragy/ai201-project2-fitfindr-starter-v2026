"""
The three FitFindr tools.

Each one is a standalone function you can call and test on its own, before any
of them are wired into the loop. Build and test them one at a time — three
untested tools joined by a loop is one problem that looks like six, because you
can't tell which layer is lying to you.

    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)             → str
    create_fit_card(outfit, new_item)              → str

All three are stubs right now. They run and they do nothing — that's the
starting position and it's deliberate.

⚠️ Before you write any of them, fill in the **Tool Inventory** section of your
README (Milestone 2). Four lines per tool: what it does, each input with its
type, exactly what it returns, and what it returns when it has nothing to give.
That last line is what your loop branches on. "Returns a list" earns nothing —
the description has to say what is *in* the list.
"""

import re

import config
from generate import generate
from utils.data_loader import load_listings


# ── shared helpers ────────────────────────────────────────────────────────────

def _size_tokens(size: str | None) -> set[str]:
    """
    Break a listing's size into whole, lowercase tokens.

    Parenthetical notes are dropped, then the rest is split on whitespace and
    "/":  "S/M" → {"s", "m"},  "W30 L30" → {"w30", "l30"},
    "XL (oversized)" → {"xl"},  "US 8.5" → {"us", "8.5"}.
    """
    if not size:
        return set()
    without_notes = re.sub(r"\([^)]*\)", " ", size)
    return {token for token in re.split(r"[\s/]+", without_notes.lower()) if token}


def _describe_item(item: dict) -> str:
    """A listing as prompt text. Every field is guarded — brand is often None."""
    item = item or {}
    colors = ", ".join(item.get("colors") or []) or "not listed"
    tags = ", ".join(item.get("style_tags") or []) or "not listed"
    return (
        f"{item.get('title') or 'Untitled item'}\n"
        f"Category: {item.get('category') or 'unknown'}; "
        f"size {item.get('size') or 'unknown'}; "
        f"condition {item.get('condition') or 'unknown'}; "
        f"brand: {item.get('brand') or 'no brand listed'}\n"
        f"Price: ${item.get('price')} on {item.get('platform') or 'an unknown platform'}\n"
        f"Colors: {colors}\n"
        f"Style: {tags}\n"
        f"Description: {item.get('description') or ''}"
    )


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the listings data for items matching a description, and optionally a
    size and a price ceiling.

    This is the tool that doesn't call the model, which makes it the easiest one
    to test and the one to move onto MCP in unit 4.

    Args:
        description: keywords describing what the user wants
                     (e.g. "vintage graphic tee").
        size:        a size string to filter by, or None to skip size filtering.
                     Match case-insensitively — "M" should match "S/M".

                     ⚠️ Read the sizes in the data before you reach for a plain
                     substring test. `"s" in "us 9"` is True, and so is
                     `"l" in "xl"`. A filter that returns shoes when someone
                     asked for a small top reads like a broken search, and it
                     will quietly cost you in unit 4 when you test criterion 1.
                     What counts as a size match is part of your spec — decide
                     it and write it into your Tool Inventory.
        max_price:   maximum price, inclusive, or None to skip price filtering.

    Returns:
        A list of matching listing dicts, best match first.
        **Returns an empty list when nothing matches — an empty list, not None,
        and not an exception.** Your loop branches on this.

    Each listing dict has these fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand (str or None), platform

    Note that `brand` is None for most listings. That is deliberate and
    realistic — thrift listings often have no brand. If something you write
    assumes a brand is always there, you will find out in unit 4.

    TODO:
        1. Load every listing with load_listings().
        2. Filter by max_price and by size, when each is provided.
        3. Score what's left by keyword overlap with `description`.
        4. Drop anything scoring zero.
        5. Sort by score, highest first, and return the listing dicts —
           at most config.SEARCH_RESULT_LIMIT of them.

    Test it from a terminal before you move on:
        python -c "from tools import search_listings; print(search_listings('graphic tee', max_price=30))"
    """
    try:
        words = (description or "").lower().split()
        wanted_size = size.strip().lower() if size and size.strip() else None

        scored = []
        for listing in load_listings():
            price = listing.get("price")
            if max_price is not None and (price is None or price > max_price):
                continue

            if wanted_size is not None and wanted_size not in _size_tokens(listing.get("size")):
                continue

            searchable = " ".join([
                listing.get("title") or "",
                listing.get("description") or "",
                *(listing.get("style_tags") or []),
            ]).lower()
            if not all(word in searchable for word in words):
                continue

            # Every survivor matched every word, so rank by how many of them
            # are in the title — a title hit is the stronger signal.
            title = (listing.get("title") or "").lower()
            scored.append((sum(word in title for word in words), listing))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [listing for _, listing in scored[:config.SEARCH_RESULT_LIMIT]]
    except Exception:  # noqa: BLE001 — the loop branches on [], never on a crash
        return []


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest one or two outfits.

    This one calls the model, through `generate()`. You don't need to think
    about rate limits — the adapter handles pacing for you.

    Args:
        new_item: a listing dict — the item the user is considering.
        wardrobe: a wardrobe dict with an 'items' key holding a list of items.
                  **It may be empty.** Handle that.

    Returns:
        A non-empty string with outfit suggestions.
        With an empty wardrobe, return general styling advice rather than
        raising or returning "". Unit 4 has you trigger the empty wardrobe on
        purpose, so decide now what it should do.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If it is, ask the model for general styling ideas for this item.
        3. If it isn't, format the wardrobe items into the prompt and ask for
           specific combinations naming pieces the user already owns.
        4. Return the model's response.

    Test it from a terminal before you move on:
        python -c "from tools import suggest_outfit; from utils.data_loader import get_example_wardrobe, load_listings; print(suggest_outfit(load_listings()[0], get_example_wardrobe()))"
    """
    title = (new_item or {}).get("title") or "this piece"
    owned = (wardrobe or {}).get("items") or []

    if owned:
        lines = []
        for piece in owned:
            colors = ", ".join(piece.get("colors") or [])
            tags = ", ".join(piece.get("style_tags") or [])
            notes = f" — {piece['notes']}" if piece.get("notes") else ""
            lines.append(
                f"- {piece.get('name') or 'unnamed item'} "
                f"({piece.get('category') or 'unknown'}; colors: {colors}; style: {tags}){notes}"
            )
        prompt = (
            f"Item the user is thinking of buying:\n{_describe_item(new_item)}\n\n"
            f"What they already own:\n" + "\n".join(lines) + "\n\n"
            "Suggest one or two complete outfits built around the new item. "
            "Name the owned pieces exactly as listed. Keep it under 120 words."
        )
    else:
        prompt = (
            f"Item the user is thinking of buying:\n{_describe_item(new_item)}\n\n"
            "They haven't saved any wardrobe items yet. Give one or two general "
            "outfit ideas for this item — what kinds of pieces, colors and shoes "
            "pair well. Keep it under 120 words."
        )

    system = "You are a practical thrift-fashion stylist. Plain text, no markdown headings."

    try:
        text = generate(prompt, system=system).strip()
    except Exception as exc:  # noqa: BLE001 — keep the reason, don't crash the run
        text = ""
        reason = str(exc)
    else:
        reason = "the model returned nothing"

    if text:
        return text

    return (
        f"Couldn't get outfit ideas ({reason}). As a starting point, wear "
        f"the {title} with simple basics in neutral colors and let it be "
        f"the focus."
    )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Write a short caption someone would actually post about the find.

    This calls the model too.

    Args:
        outfit:   the outfit suggestion string from suggest_outfit().
        new_item: the listing dict for the item.

    Returns:
        A two-to-four sentence caption.
        If `outfit` is empty or whitespace, return a descriptive message rather
        than raising.

    The caption should read like a real post rather than a product description,
    mention the item and its price and platform once each, and be specific about
    the vibe.

    It should also come out **differently for different inputs**. If you run
    this three times on the same item and get three word-for-word identical
    strings, it's one of two things, and both are near the top of `config.py`:

        • CACHE_ENABLED — the adapter handed back an answer it already had
        • TEMPERATURE   — at 0.0 the model gives the same words every time

    TODO:
        1. Guard against an empty or whitespace-only `outfit`.
        2. Build a prompt with the item details and the outfit.
        3. Call generate() and return the response.

    Test it from a terminal before you move on:
        python -c "from tools import create_fit_card; from utils.data_loader import load_listings; print(create_fit_card('jeans and white sneakers', load_listings()[0]))"
    """
    item = new_item or {}
    title = item.get("title") or "this thrift find"
    fallback = f"New thrift find: the {title}. Already planning the first fit. 🛍️"

    if not (outfit or "").strip():
        return fallback

    prompt = (
        f"The find:\n{_describe_item(item)}\n\n"
        f"How it'll be styled:\n{outfit}\n\n"
        "Write a 2-4 sentence caption someone would actually post about this "
        "find. Mention the item, its price and the platform once each, and be "
        "specific about the vibe. At most two hashtags. Return only the caption."
    )
    system = "You write short, casual social captions. No preamble, no quotes around the caption."

    try:
        caption = generate(prompt, system=system).strip()
    except Exception:  # noqa: BLE001 — a caption is never worth a crash
        caption = ""

    return caption or fallback
