#!/usr/bin/env python3
"""Extract the full Zork I map into scene definitions.

Parses the ZIL dungeon for every room and its text (LDESC, or the M-LOOK text in
its action routine), dedupes by display name (Maze x15 -> 1, etc.), assigns a
music region, and MERGES any hand-authored scenes from opening.yaml (so the
polished opening keeps its prompts/anchors). Output: zork1/scenes/zork1.yaml.

    python scripts/extract_scenes.py
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "sources" / "zork1"
DUNGEON = SRC / "1dungeon.zil"
ACTIONS = SRC / "1actions.zil"
OPENING = ROOT / "zork1" / "scenes" / "opening.yaml"
OUT = ROOT / "zork1" / "scenes" / "zork1.yaml"

REGION_SETS = {
    "above_ground": {
        "West of House", "North of House", "South of House", "Behind House", "Kitchen",
        "Living Room", "Attic", "Forest", "Forest Path", "Up a Tree", "Clearing",
        "Canyon View", "Rocky Ledge", "Canyon Bottom", "End of Rainbow", "On the Rainbow",
        "Aragain Falls", "White Cliffs Beach", "Sandy Beach", "Shore", "Frigid River",
        "Stone Barrow",
    },
    "peril": {"The Troll Room", "Cyclops Room", "Treasure Room"},
    "wonder": {"Temple", "Altar", "Egyptian Room", "Dome Room", "Torch Room", "Gallery",
               "Atlantis Room", "Engravings Cave"},
    "dread": {"Entrance to Hades", "Land of the Dead"},
}


def region_of(desc):
    for region, names in REGION_SETS.items():
        if desc in names:
            return region
    return "underground"


def slugify(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def clean(s):
    s = s.replace("|", " ").replace("\\", " ")
    s = re.sub(r"\s*:\s*\.", ".", s)  # strip dynamic object-list placeholders ("you can see: .")
    return " ".join(s.split())


def parse_rooms(text):
    rooms = []
    for m in re.finditer(r"<ROOM\s+([A-Z0-9-]+)(.*?)(?=\n<(?:ROOM|OBJECT)\b|\Z)", text, re.S):
        name, body = m.group(1), m.group(2)
        d = re.search(r'\(DESC\s+"([^"]*)"', body)
        ld = re.search(r'\(LDESC\s+"([^"]*)"', body)
        act = re.search(r"\(ACTION\s+([A-Z0-9-]+)", body)
        rooms.append({
            "name": name,
            "desc": d.group(1) if d else None,
            "ldesc": clean(ld.group(1)) if ld else None,
            "action": act.group(1) if act else None,
        })
    return rooms


def parse_action_descs(text):
    """Best-effort: the M-LOOK branch text of each action routine (room descriptions)."""
    out = {}
    for m in re.finditer(r"<ROUTINE\s+([A-Z0-9-]+)\b(.*?)(?=\n<ROUTINE\b|\Z)", text, re.S):
        rname, body = m.group(1), m.group(2)
        i = body.find("M-LOOK")
        if i < 0:
            continue
        span = body[i:]
        nxt = span.find("(<EQUAL? .RARG", 6)  # stop at the next RARG branch (e.g. M-END)
        if nxt > 0:
            span = span[:nxt]
        strings = re.findall(r'"([^"]*)"', span)
        desc = clean(" ".join(strings))
        if desc:
            out[rname] = desc
    return out


def main():
    rooms = parse_rooms(DUNGEON.read_text())
    actions = parse_action_descs(ACTIONS.read_text())
    opening = {s["id"]: s for s in yaml.safe_load(OPENING.read_text())["scenes"]}

    scenes = []
    seen = {}  # desc -> index in scenes
    for r in rooms:
        desc = r["desc"]
        if not desc:
            continue
        if desc in seen:
            scenes[seen[desc]]["rooms"].append(r["name"])
            continue
        seen[desc] = len(scenes)

        if desc in opening:  # keep the hand-authored opening scene verbatim
            entry = dict(opening[desc])
            entry.setdefault("rooms", [r["name"]])
            scenes.append(entry)
            continue

        text = r["ldesc"] or actions.get(r["action"] or "", "") or ""
        scenes.append({
            "id": desc,
            "room": r["name"],
            "rooms": [r["name"]],
            "slug": slugify(desc),
            "region": region_of(desc),
            "anchors": [],
            "scene_description": text,
            "scene_core": text,
        })

    doc = {"game": "zork1", "default_region": "above_ground", "start_room": "West of House", "scenes": scenes}
    OUT.write_text(yaml.safe_dump(doc, sort_keys=False, default_flow_style=False, width=90, allow_unicode=True))

    from collections import Counter
    regions = Counter(s["region"] for s in scenes)
    missing = [s["id"] for s in scenes if not s.get("scene_description")]
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(scenes)} unique scenes")
    print("regions:", dict(regions))
    print("scenes with NO text (need manual):", missing or "none")


if __name__ == "__main__":
    main()
