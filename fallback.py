"""Rule-based recommendations used when Gemini is not configured or fails (Activity 5.4).

Every function returns the SAME raw schema Gemini is asked to produce, so the result goes
through the same normalisation / validation / link-building code as an AI answer.
"""
from typing import Optional

from PIL import Image

from models import HomeBudgetInput, JewelryBudgetInput, PartyBudgetInput

SPENDABLE = 0.92  # keep ~8% of the budget unallocated as a safety buffer


# ----------------------------------------------------------------------------- home
_HOME_CATALOG = {
    "lighting": ("LED panel / batten light", "Energy-efficient 4000K-6500K LED fixture for {rooms}", "LED panel light", 0.22),
    "ceiling_fans": ("5-star ceiling fan (1200 mm)", "Energy-saving fan with good air delivery for {rooms}", "5 star ceiling fan 1200mm", 0.28),
    "furniture": ("Engineered-wood furniture piece", "Accent chair, storage unit or side table for {rooms}", "engineered wood furniture", 0.30),
    "dining_tables": ("Dining table set", "Compact wooden dining table with chairs", "dining table set 4 seater", 0.20),
}


def home_plan(inp: HomeBudgetInput) -> dict:
    qty = {
        "lighting": inp.num_lights, "ceiling_fans": inp.num_fans,
        "furniture": inp.num_furniture, "dining_tables": inp.num_dining_tables,
    }
    active = {k: q for k, q in qty.items() if q > 0}
    total_weight = sum(_HOME_CATALOG[k][3] for k in active)
    rooms = ", ".join(
        name for name, on in (("living room", inp.has_living_room), ("kitchen", inp.has_kitchen),
                              ("bedroom", inp.has_bedroom)) if on
    ) or "your home"
    breakdown = []
    for cat, q in active.items():
        name, desc, terms, weight = _HOME_CATALOG[cat]
        share = inp.total_budget * SPENDABLE * weight / total_weight
        breakdown.append({
            "category": cat,
            "items": [{"name": name, "description": desc.format(rooms=rooms),
                       "estimated_price": round(share / q, 2), "quantity": q, "search_terms": terms}],
        })
    return {
        "budget_breakdown": breakdown,
        "additional_suggestions": [
            "Compare the same product across Amazon, Flipkart and IKEA before buying.",
            "Watch for festival sales (Diwali, Republic Day) on fans and lighting.",
            "Buy essentials first and add decor pieces later if the budget allows.",
        ],
    }


# ----------------------------------------------------------------------------- party
def party_plan(inp: PartyBudgetInput) -> dict:
    at_home = "home" in (inp.venue_type or "").lower()
    weights = {}
    if not at_home:
        weights["venue"] = 0.25
    if inp.needs_catering:
        weights["catering"] = 0.45
    if inp.needs_decoration:
        weights["decoration"] = 0.20
    if inp.needs_entertainment:
        weights["entertainment"] = 0.15
    weights["contingency"] = 0.08
    total_weight = sum(weights.values())
    party = inp.party_type.strip().lower()

    def share(cat: str) -> float:
        return inp.total_budget * SPENDABLE * weights[cat] / total_weight

    builders = {
        "venue": lambda: {"name": f"{inp.venue_type or 'Banquet hall'} booking",
                          "description": f"Venue for a {party} party with {inp.num_guests} guests",
                          "estimated_price": round(share("venue"), 2), "quantity": 1,
                          "search_terms": f"party hall for {inp.num_guests} guests"},
        "catering": lambda: {"name": "Food and beverages (per guest)",
                             "description": f"Catering for {inp.num_guests} guests, about "
                                            f"₹{share('catering') / inp.num_guests:,.0f} per head",
                             "estimated_price": round(share("catering") / inp.num_guests, 2),
                             "quantity": inp.num_guests, "search_terms": f"{party} party catering"},
        "decoration": lambda: {"name": f"{party.title()} decoration package",
                               "description": "Balloons, lights, backdrop and table styling",
                               "estimated_price": round(share("decoration"), 2), "quantity": 1,
                               "search_terms": f"{party} party decoration kit"},
        "entertainment": lambda: {"name": "Music and games",
                                  "description": "DJ or speaker rental, playlist and party games",
                                  "estimated_price": round(share("entertainment"), 2), "quantity": 1,
                                  "search_terms": "party speaker and games"},
        "contingency": lambda: {"name": "Buffer for unexpected costs",
                                "description": "Extra ice, disposables, tips or last-minute items",
                                "estimated_price": round(share("contingency"), 2), "quantity": 1,
                                "search_terms": "party disposable plates cups"},
    }
    breakdown = [{"category": c, "items": [builders[c]()]} for c in weights]
    venues = []
    if not at_home:
        venues.append({"name": "Local banquet or community hall", "type": inp.venue_type or "banquet",
                       "capacity": inp.num_guests, "estimated_cost": round(share("venue"), 2),
                       "search_terms": f"party hall for {inp.num_guests} guests"})
    return {
        "budget_breakdown": breakdown,
        "venue_suggestions": venues,
        "additional_suggestions": [
            "Ask caterers for per-plate quotes and confirm what is included.",
            "Book the venue and caterer at least two weeks ahead for better rates.",
            "Keep the buffer untouched until the day before the event.",
        ],
    }


# ----------------------------------------------------------------------------- jewelry
_DEFAULT_SET = [
    ("earrings", "Studs or drops that suit the occasion", "earrings", 0.35),
    ("necklace", "Pendant or short necklace that sits well with your neckline", "pendant necklace", 0.40),
    ("bracelet", "Slim bracelet or a pair of bangles", "bracelet", 0.25),
]
_OCCASION_SETS = {
    "wedding": [("necklace set", "Kundan or polki-style necklace set with matching earrings", "kundan necklace set", 0.50),
                ("bangles", "Set of stone-studded or gold-plated bangles", "bridal bangles set", 0.30),
                ("maang tikka", "Traditional forehead piece to complete the look", "maang tikka", 0.20)],
    "engagement": [("ring", "Solitaire-style or halo ring", "solitaire ring", 0.55),
                   ("earrings", "Sparkling studs", "diamond look stud earrings", 0.25),
                   ("pendant", "Delicate pendant with chain", "pendant with chain", 0.20)],
    "festival": [("jhumka earrings", "Traditional jhumkas in gold or oxidised finish", "jhumka earrings", 0.35),
                 ("necklace", "Temple or choker-style necklace", "temple jewellery necklace", 0.40),
                 ("bangles", "Matching bangles", "traditional bangles set", 0.25)],
    "office": [("stud earrings", "Minimal studs for daily wear", "minimal stud earrings", 0.35),
               ("chain and pendant", "Fine chain with a small pendant", "delicate chain pendant", 0.40),
               ("watch or bracelet", "Slim bracelet or watch", "slim bracelet women", 0.25)],
}


def dominant_colors(image_path: str, n: int = 3) -> list[str]:
    palette = {
        "black": (20, 20, 20), "white": (240, 240, 240), "grey": (128, 128, 128), "red": (200, 30, 40),
        "maroon": (110, 20, 35), "orange": (240, 140, 30), "yellow": (240, 210, 50), "green": (40, 150, 70),
        "teal": (0, 128, 128), "blue": (40, 80, 200), "navy": (20, 30, 90), "purple": (120, 50, 160),
        "pink": (240, 130, 170), "brown": (120, 75, 40), "beige": (220, 200, 165),
    }
    with Image.open(image_path) as im:
        quant = im.convert("RGB").resize((64, 64)).quantize(colors=n)
        pal = quant.getpalette() or []
        counts = sorted(quant.getcolors() or [], reverse=True)
    names: list[str] = []
    for _, idx in counts:
        rgb = pal[idx * 3: idx * 3 + 3]
        if len(rgb) < 3:
            continue
        name = min(palette, key=lambda k: sum((a - b) ** 2 for a, b in zip(palette[k], rgb)))
        if name not in names:
            names.append(name)
    return names


def jewelry_plan(inp: JewelryBudgetInput, image_path: Optional[str] = None) -> dict:
    occasion = inp.occasion.lower()
    items = next((v for k, v in _OCCASION_SETS.items() if k in occasion), _DEFAULT_SET)
    style = (inp.preferences or "").strip()[:60] or "classic"
    recs = [{"item_type": t, "description": d, "style": style,
             "estimated_price": round(inp.total_budget * SPENDABLE * w, 2), "search_terms": q}
            for t, d, q, w in items]
    result = {
        "jewelry_recommendations": recs,
        "styling_tips": [
            "Pick one statement piece and keep the others simple.",
            "Match metal tones (gold with warm colours, silver with cool colours).",
            "Check the outfit neckline before choosing a necklace.",
        ],
    }
    if image_path:
        try:
            colors = dominant_colors(image_path)
        except Exception:  # unreadable image should never break the fallback
            colors = []
        result["outfit_analysis"] = {"colors": colors, "style": "not analysed in demo mode", "formality": "unknown"}
    return result
