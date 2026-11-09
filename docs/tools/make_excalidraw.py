"""Generate docs/business-logic.excalidraw (Navan Growth Intelligence business logic)."""
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
free_text(40, -110, "Navan Growth Intelligence: business logic", 34)
free_text(40, -60, "AI researches and interprets · fixed rules evaluate · humans approve tier changes", 18, "#4a5263")

# ---- Legend ----------------------------------------------------------------
lx, ly = 2140, -120
free_text(lx, ly, "Legend", 18)
for i, (name, c) in enumerate([("Deterministic rule", DET), ("AI (LLM + web search)", AI),
                                ("Human decision", HUMAN), ("Data / outcome", DATA),
                                ("Caveat / note", WARN)]):
    box(lx + (i % 3) * 190, ly + 30 + (i // 3) * 60, 175, 45, name, c, 14)

# ---- Column 1: signup + baseline tier rules --------------------------------
frame_label(20, 0, 640, 1460, "1 · Baseline tier (Navan's rules)", DET[1])
signup = box(120, 60, 420, 90, "Company signs up\nname · domain · reported GBV · employee estimate", DATA)
d_valid = diamond(200, 200, 260, 120, "GBV valid?")
no_tier = box(480, 222, 160, 76, "No tier\ndata-quality issue\n(never $0)", RED, 13)
d_t1 = diamond(200, 360, 260, 120, "GBV ≥ $500K?")
t1 = box(500, 390, 130, 60, "Tier 1", TIER, 18)
d_t2g = diamond(200, 530, 260, 120, "GBV ≥ $100K?")
t2a = box(500, 560, 130, 60, "Tier 2", TIER, 18)
d_known = diamond(200, 700, 260, 120, "Employee count\nknown?")
t3p = box(470, 730, 170, 70, "Tier 3\nprovisional", TIER, 16)
d_150 = diamond(200, 870, 260, 120, "Employees\n≥ 150?")
t2b = box(500, 900, 130, 60, "Tier 2", TIER, 18)
t3 = box(265, 1050, 130, 60, "Tier 3", TIER, 18)
note1 = box(60, 1160, 560, 120,
            "Three tiers kept separately:\n• original (dataset) tier, never changes\n• rules tier (this calculation)\n• applied tier, changes only on approval",
            WARN, 15)
note1b = box(60, 1300, 560, 120,
             "Research headcount never silently replaces the\nenrichment value. If they disagree, it becomes a\nconflict for a human to resolve.",
             WARN, 15)

arrow(signup, d_valid)
arrow(d_valid, no_tier, "right", "left", "no")
arrow(d_valid, d_t1, text="yes")
arrow(d_t1, t1, "right", "left", "yes")
arrow(d_t1, d_t2g, text="no")
arrow(d_t2g, t2a, "right", "left", "yes")
arrow(d_t2g, d_known, text="no")
arrow(d_known, t3p, "right", "left", "no")
arrow(d_known, d_150, text="yes")
arrow(d_150, t2b, "right", "left", "yes")
arrow(d_150, t3, text="no")

# ---- Column 2: research → flags → proposal → review ------------------------
frame_label(700, 0, 820, 2210, "2 · Research, flags and review (signup / Day 0)", AI[1])
research = box(860, 60, 500, 90, "AI standard research\nClaude Haiku + web search · name + domain only\n8 fields · cached · ~$0.04", AI, 15)
validate = box(860, 200, 500, 120,
               "Validation (code, not AI)\n• JSON schema, 1 repair retry\n• drop URLs search didn't return\n• bands ≠ exact headcounts · stale > 18 mo",
               DET, 14)
d_ok = diamond(980, 370, 260, 110, "Research ok?")
failed = box(1280, 385, 220, 80, "Run marked failed\nerror shown\nnothing invented", RED, 14)
signals = box(860, 530, 500, 90, "Structured signals\nheadcounts by source · direct travel (scope)\ngrowth · field coverage", DET, 15)

flags_y = 670
free_text(870, flags_y, "Reason flags (a company can have several)", 18, DET[1])
f_conf = box(720, flags_y + 40, 380, 85, "Data Conflict\nmaterial if headcounts straddle 150\nAND GBV < $100K", DET, 14)
f_trav = box(1120, flags_y + 40, 380, 85, "Travel Potential\njob ads say staff travel · 2+ sources = strong\nlocal driving / home visits don't count", DET, 13)
f_grow = box(720, flags_y + 140, 380, 85, "Growth Opportunity\n2+ independent growth signals\ngrowth ≠ proof of higher GBV", DET, 14)
f_ins = box(1120, flags_y + 140, 380, 85, "Insufficient Evidence\nkey fact missing\nmissing ≠ \"no travel\"", DET, 14)
f_mis = box(920, flags_y + 240, 380, 85, "Tier Mismatch\nevidence points to a different tier", RED, 15)

d_mis = diamond(980, 1060, 260, 120, "Tier Mismatch?")
attention = box(720, 1230, 360, 150,
                "Attention only (no tier change)\nReview Suggested: moderate signal\nMonitor: weak signal\nNo action: nothing found\nTier 1 travel = info only",
                DATA, 14)
proposal = box(1120, 1230, 380, 150,
               "Tier proposal\n• rule correction: rules give\n   another tier\n• override: evidence beats rules\n   (at most 1 tier, needs consensus)",
               DET, 14)
d_dup = diamond(1180, 1430, 260, 130, "Already open or\nrejected with the\nsame evidence?", DET, 13)
suppressed = box(1240, 1700, 260, 70, "Not raised again\n(link to existing)", DATA, 14)
queue = box(880, 1600, 320, 90, "Review Now queue\nordered: impact → evidence\n→ actionability", RED, 14)
d_review = diamond(910, 1740, 260, 130, "Human review\n(PR-style)", HUMAN, 16)
approve = box(720, 1930, 220, 110, "Approve\ntier changes in prototype\noriginal tier kept", HUMAN, 14)
reject = box(960, 1930, 200, 110, "Reject\ntier unchanged\nreason required", HUMAN, 14)
info = box(1180, 1930, 220, 110, "Request more info\nproposal stays open", HUMAN, 14)
enrich = box(1180, 2090, 320, 100, "Manual value or Deep Research\nmanual: rules rerun, 0 AI calls\ndeep: only after confirm", HUMAN, 14)

arrow(signup, research, "right", "left", via=[(700, 105)])
arrow(research, validate)
arrow(validate, d_ok)
arrow(d_ok, failed, "right", "left", "no")
arrow(d_ok, signals, text="yes")
arrow(failed, signals, "bottom", "right", via=[(1390, 575)], dashed=True)
arrow(signals, f_conf, "bottom", "top", via=[(1110, 650), (910, 650)])
arrow(f_mis, d_mis)
arrow(d_mis, attention, "left", "top", "no", via=[(900, 1120)])
arrow(d_mis, proposal, "right", "top", "yes", via=[(1310, 1120)])
arrow(proposal, d_dup)
arrow(d_dup, suppressed, "bottom", "top", "yes")
arrow(d_dup, queue, "left", "top", "no", via=[(1040, 1495)])
arrow(queue, d_review)
arrow(d_review, approve, "left", "top", via=[(830, 1805)])
arrow(d_review, reject, "bottom", "top")
arrow(d_review, info, "right", "top", via=[(1290, 1805)])
arrow(info, enrich)
arrow(enrich, signals, "right", "right", "rules only", dashed=True, color=HUMAN[1], via=[(1535, 2140), (1535, 575)])
# baseline feeds signals
arrow(t3, signals, "right", "left", "rules tier", dashed=True, color=DET[1], via=[(680, 1080), (680, 575)])

# ---- Column 3: Day 30 -------------------------------------------------------
frame_label(1560, 300, 1020, 1230, "3 · Day 30 reassessment (after signup)", HUMAN[1])
d30 = box(1840, 370, 460, 90, "Day 30 activity received\ntravelers · bookings · trend\n(locked away until now)", DATA, 15)
d_mat = diamond(1880, 520, 380, 160, "Material activity?\n≥15 travelers, or\n≥40 bookings & +25%", DET, 14)
weak = box(2300, 545, 260, 110, "Not material\nweak / declining → \"weakens\"\ngrowing → Review Suggested", DATA, 14)
d_tier = diamond(2000, 740, 300, 140, "Current tier?", DET, 15)
o_t3 = box(1640, 950, 220, 100, "Tier 3 →\noverride to Tier 2", RED, 15)
d_40 = diamond(2160, 930, 300, 150, "Tier 2 with\n≥ 40 travelers?", DET, 14)
o_t1 = box(2200, 1140, 220, 100, "Tier 2 →\noverride to Tier 1", RED, 15)
consist = box(1880, 1140, 300, 100, "Tier 1, or Tier 2 below 40\nconsistent → Travel Potential\n(no proposal)", DATA, 13)
note30 = box(1620, 1290, 900, 200,
             "Rules for Day 30\n• the Day 0 assessment is never edited; a new assessment is compared with it\n• bookings are not dollars: never converted into a GBV estimate\n• proposals are always \"evidence-based overrides\", at most one tier up\n• 30 days may not represent a year · missing activity ≠ zero travel",
             WARN, 15)

arrow(d30, d_mat)
arrow(d_mat, weak, "right", "left", "no")
arrow(d_mat, d_tier, "bottom", "top", "yes")
arrow(d_tier, o_t3, "left", "top", "T3", via=[(1750, 810)])
arrow(d_tier, d_40, "right", "top", "T1 or T2", via=[(2310, 810)])
arrow(d_40, o_t1, "bottom", "top", "yes")
arrow(d_40, consist, "left", "top", "no", via=[(2030, 1005)])
arrow(o_t3, queue, "left", "right", "new proposal", dashed=True, color=RED[1], via=[(1600, 1000), (1600, 1645)])
arrow(o_t1, queue, "bottom", "right", dashed=True, color=RED[1], via=[(2310, 1270), (1600, 1270), (1600, 1645)])

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
