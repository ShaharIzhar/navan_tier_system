"""Generate a first draft of docs/business-logic.excalidraw. The committed file has since been edited by hand in Excalidraw, so do not regenerate over it (Navan Growth Intelligence business logic)."""
import json
import random
import sys

random.seed(7)
els = []
_id = 0

# Palette (fill, stroke)
DET = ("#e7ebff", "#3c4fe0")      # deterministic rules
AI = ("#efe6ff", "#6b3fc8")       # AI
HUMAN = ("#dff5e8", "#18794e")    # human
DATA = ("#f1f3f6", "#4a5263")     # data / outcome
WARN = ("#fff4d6", "#a15c00")     # notes / caveats
RED = ("#fde8e6", "#c2352b")      # Review Now / stop
TIER = ("#ffffff", "#1b1f27")


def nid(prefix):
    global _id
    _id += 1
    return f"{prefix}{_id}"


def base(kind, x, y, w, h, stroke, fill, **kw):
    e = {
        "id": nid(kind[:2]), "type": kind, "x": x, "y": y, "width": w, "height": h, "angle": 0,
        "strokeColor": stroke, "backgroundColor": fill, "fillStyle": "solid", "strokeWidth": 2,
        "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None,
        "roundness": {"type": 3} if kind in ("rectangle", "diamond") else None,
        "seed": random.randint(1, 2**31), "version": 1, "versionNonce": random.randint(1, 2**31),
        "isDeleted": False, "boundElements": [], "updated": 1762646400000, "link": None, "locked": False,
    }
    e.update(kw)
    return e


def text_dims(s, size):
    lines = s.split("\n")
    return max(len(l) for l in lines) * size * 0.55, len(lines) * size * 1.25


def label(container, s, size=16, color=None):
    w, h = text_dims(s, size)
    t = base("text", container["x"] + (container["width"] - w) / 2, container["y"] + (container["height"] - h) / 2,
             w, h, color or container["strokeColor"], "transparent",
             text=s, fontSize=size, fontFamily=1, textAlign="center", verticalAlign="middle",
             containerId=container["id"], originalText=s, lineHeight=1.25, autoResize=True)
    t["roundness"] = None
    container["boundElements"].append({"type": "text", "id": t["id"]})
    els.append(t)
    return t


def box(x, y, w, h, s, colors, size=16, kind="rectangle", dashed=False):
    fill, stroke = colors
    e = base(kind, x, y, w, h, stroke, fill, strokeStyle="dashed" if dashed else "solid")
    els.append(e)
    label(e, s, size, color="#1b1f27")
    return e


def diamond(x, y, w, h, s, colors=DET, size=15):
    return box(x, y, w, h, s, colors, size, kind="diamond")


def free_text(x, y, s, size=16, color="#1b1f27"):
    w, h = text_dims(s, size)
    t = base("text", x, y, w, h, color, "transparent", text=s, fontSize=size, fontFamily=1,
             textAlign="left", verticalAlign="top", containerId=None, originalText=s, lineHeight=1.25,
             autoResize=True)
    t["roundness"] = None
    els.append(t)
    return t


def anchor(e, side):
    x, y, w, h = e["x"], e["y"], e["width"], e["height"]
    return {"top": (x + w / 2, y), "bottom": (x + w / 2, y + h), "left": (x, y + h / 2),
            "right": (x + w, y + h / 2)}[side]


def arrow(a, b, sa="bottom", sb="top", text=None, color="#4a5263", dashed=False, via=None):
    x1, y1 = anchor(a, sa)
    x2, y2 = anchor(b, sb)
    pts = [[0, 0]]
    for vx, vy in (via or []):
        pts.append([vx - x1, vy - y1])
    pts.append([x2 - x1, y2 - y1])
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    e = base("arrow", x1, y1, max(xs) - min(xs), max(ys) - min(ys), color, "transparent",
             points=pts, lastCommittedPoint=None, startArrowhead=None, endArrowhead="arrow",
             startBinding={"elementId": a["id"], "focus": 0, "gap": 4},
             endBinding={"elementId": b["id"], "focus": 0, "gap": 4},
             strokeStyle="dashed" if dashed else "solid", elbowed=False)
    e["roundness"] = {"type": 2}
    els.append(e)
    a["boundElements"].append({"type": "arrow", "id": e["id"]})
    b["boundElements"].append({"type": "arrow", "id": e["id"]})
    if text:
        # label at the midpoint of the first segment
        mx = x1 + pts[1][0] / 2 if len(pts) > 2 else x1 + (x2 - x1) / 2
        my = y1 + pts[1][1] / 2 if len(pts) > 2 else y1 + (y2 - y1) / 2
        w, h = text_dims(text, 14)
        t = base("text", mx - w / 2, my - h / 2, w, h, color, "transparent", text=text, fontSize=14,
                 fontFamily=1, textAlign="center", verticalAlign="middle", containerId=e["id"],
                 originalText=text, lineHeight=1.25, autoResize=True)
        t["roundness"] = None
        e["boundElements"].append({"type": "text", "id": t["id"]})
        els.append(t)
    return e


def frame_label(x, y, w, h, title, color):
    e = base("rectangle", x, y, w, h, color, "transparent", strokeStyle="dashed", strokeWidth=1)
    e["roundness"] = {"type": 3}
    els.append(e)
    free_text(x + 16, y + 12, title, 20, color)


# ---------------------------------------------------------------------------
# Simple version: one main flow, side notes only where a business decision lives.
free_text(40, -120, "Navan Growth Intelligence: business logic", 34)
free_text(40, -70, "AI researches · fixed rules decide · people approve tier changes", 18, "#4a5263")

lx, ly = 1060, -120
for i, (name, c) in enumerate([("Rule (code)", DET), ("AI", AI), ("Person", HUMAN), ("Note", WARN)]):
    box(lx + i * 140, ly, 125, 40, name, c, 14)

X, W = 300, 460          # main column
NX, NW = 820, 440        # notes column

signup = box(X, 0, W, 70, "Company signs up\nname · domain · reported GBV · employees", DATA)
base_ = box(X, 120, W, 120,
            "Baseline tier (Navan rules)\nGBV ≥ $500K → Tier 1\nGBV ≥ $100K or 150+ employees → Tier 2\nelse Tier 3", DET)
n1 = box(NX, 120, NW, 120,
         "• headcount unknown → provisional Tier 3\n• invalid GBV → no tier (never $0)\n• research headcount never silently\n   replaces the dataset value", WARN, 14)

research = box(X, 290, W, 110,
               "AI research (Claude Haiku + web search)\nStandard: industry, locations, employees,\nfunding, hiring\nDeep Research: all 8 fields (on request, once)", AI, 15)
n2 = box(NX, 290, NW, 110,
         "Input is name + domain only.\nNever sees reported GBV or Day 30 data.\nAI never changes a tier.", WARN, 14)

valid = box(X, 450, W, 110,
            "Checks (code, not AI)\n• citations must come from the actual search\n• ranges (51-200) aren't exact numbers\n• older than 18 months → stale", DET, 15)
n3 = box(NX, 450, NW, 110,
         "Failed or malformed run → shown as failed,\nnothing invented. Rules keep working.\nMissing info ≠ \"doesn't travel\".", WARN, 14)

flags = box(X, 610, W, 150,
            "Flags (a company can have several)\nTier Mismatch · Data Conflict ·\nGrowth Opportunity · Travel Potential ·\nInsufficient Evidence", DET, 15)
n4 = box(NX, 610, NW, 150,
         "• Conflict is material when headcounts\n   straddle 150 and GBV < $100K\n• Travel needs a source saying staff travel;\n   local driving doesn't count\n• Growth is never proof of travel spend", WARN, 14)

d_mm = diamond(X + 80, 810, W - 160, 120, "Tier Mismatch?")
attn = box(40, 840, 220, 90, "Attention only\nReview Suggested\nor Monitor", DATA, 15)

prop = box(X, 980, W, 100,
           "Tier proposal (needs a person)\nrule correction or evidence override\nnot raised again if already open or rejected", DET, 15)

review = box(X, 1130, W, 90, "Human review (PR-style)\nAI judge gives a one-line why (advisory)", HUMAN, 15)
appr = box(X - 200, 1270, 240, 80, "Approve\ntier changes, original kept", HUMAN, 14)
rej = box(X + 110, 1270, 240, 80, "Reject\nreason required", HUMAN, 14)
info = box(X + 420, 1270, 240, 80, "Comment only\nproposal stays open", HUMAN, 14)

manual = box(40, 610, 220, 150, "Manual correction\nedit a value\n→ rules rerun\ninstantly, no AI", HUMAN, 15)

day30 = box(NX + 40, 840, 400, 110,
            "Day 30 activity arrives\ntravelers · bookings · trend\n(update or remove anytime, logged)", DATA, 15)
d30 = box(NX + 40, 990, 400, 150,
          "Day 30 rules\n15+ travelers, or 40+ bookings growing 25%+\n→ Tier 3 can be proposed for Tier 2\n40+ travelers on Tier 2 → proposed Tier 1\nAlways an override, at most one tier up", DET, 14)
n5 = box(NX + 40, 1180, 400, 70, "Bookings aren't dollars.\nThe Day 0 assessment is never edited.", WARN, 14)

arrow(signup, base_)
arrow(base_, research)
arrow(research, valid)
arrow(valid, flags)
arrow(flags, d_mm)
arrow(d_mm, attn, "left", "right", "no")
arrow(d_mm, prop, "bottom", "top", "yes")
arrow(prop, review)
arrow(review, appr, "bottom", "top")
arrow(review, rej, "bottom", "top")
arrow(review, info, "bottom", "top")
arrow(manual, flags, "right", "left", dashed=True)
arrow(day30, d30)
arrow(d30, prop, "left", "right", "material", color=RED[1])

doc = {
    "type": "excalidraw",
    "version": 2,
    "source": "https://excalidraw.com",
    "elements": els,
    "appState": {"gridSize": 20, "viewBackgroundColor": "#ffffff"},
    "files": {},
}
out = sys.argv[1]
with open(out, "w") as f:
    json.dump(doc, f, indent=1, ensure_ascii=False)
print(f"wrote {out}: {len(els)} elements")
