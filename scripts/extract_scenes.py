#!/usr/bin/env python3
"""Extract a game's full map into scene definitions.

Parses the ZIL dungeon for every room and its text (LDESC, or the M-LOOK text in
its action routine), dedupes by display name (Maze x15 -> 1, etc.), assigns a
music region, and MERGES any hand-authored scenes from the game's opening.yaml
(so a polished opening keeps its prompts/anchors). Output: <game>/scenes/<game>.yaml.

    python scripts/extract_scenes.py                # zork1 (default)
    python scripts/extract_scenes.py --game zork2
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# Per-game config. `regions` maps a room display-name to its music region; rooms
# not listed fall back to `region_default`. `default_region` is the doc-level
# fallback the runtime uses when a scene/room has no region at all (NOT the same
# as region_default — for zork1 the overworld is the doc default but unmatched
# interior rooms are "underground"). `opening` (optional) is a hand-authored
# scenes file merged verbatim by display-name.
GAMES = {
    "zork1": {
        "src": "sources/zork1",
        "dungeon": "1dungeon.zil",
        "actions": "1actions.zil",
        "opening": "zork1/scenes/opening.yaml",
        "out": "zork1/scenes/zork1.yaml",
        "default_region": "above_ground",
        "region_default": "underground",
        "start_room": "West of House",
        "scene_anchors": {},  # zork1 attaches anchors via opening.yaml only
        "regions": {
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
        },
    },
    "zork2": {
        "src": "sources/zork2",
        "dungeon": "2dungeon.zil",
        "actions": "2actions.zil",
        "opening": "zork2/scenes/opening.yaml",  # optional; merged only if present
        "out": "zork2/scenes/zork2.yaml",
        # Zork II ("The Wizard of Frobozz") is almost entirely underground; the
        # barrow/gardens are the only open-air notes, so the doc fallback is the
        # cavern theme. The four music moods map onto its set-pieces:
        #   above_ground = the barrow threshold + the open-air formal gardens
        #   peril        = the volcano, the dragon, Cerberus, the carousel trap
        #   wonder       = the Wizard's domain + the marvellous Bank of Zork
        #   dread        = the misty maze, the crypt, the dank cells
        "default_region": "underground",
        "region_default": "underground",
        "start_room": "Inside the Barrow",
        # Attach recurring-entity anchors (anchors.yaml) to the clean LDESC scenes
        # that feature them, without rewriting their faithful room text. Scenes that
        # are hand-authored in opening.yaml carry their own anchors instead.
        "scene_anchors": {
            "Dragon Room": ["dragon"],
            "Dragon's Lair": ["dragon"],
            "Cerberus Room": ["cerberus"],
            "Menhir Room": ["menhir"],
            "Formal Garden": ["unicorn", "princess"],
            "North End of Garden": ["unicorn"],
            "Topiary": ["unicorn"],
            "Aquarium Room": ["sea-serpent"],
            "Wizard's Workroom": ["wizard-of-frobozz"],
            "Wizard's Workshop": ["wizard-of-frobozz"],
            "Posts Room": ["robot"],
        },
        "regions": {
            "above_ground": {
                "Inside the Barrow", "Formal Garden", "North End of Garden", "Topiary",
                "Gazebo", "Stone Bridge",
            },
            "peril": {
                "Dragon Room", "Dragon's Lair", "Cerberus Room", "Guarded Room", "Carousel Room",
                "Menhir Room", "Lava Room", "Lava Tube", "Volcano Bottom", "Volcano Core",
                "Volcano View", "Volcano Near Small Ledge", "Volcano Near Wide Ledge",
                "Volcano by Viewing Ledge", "Narrow Ledge", "Wide Ledge",
            },
            "wonder": {
                "Wizard's Quarters", "Wizard's Workroom", "Wizard's Workshop", "Aquarium Room",
                "Pearl Room", "Marble Hall", "Bank Entrance", "Safety Depository", "Vault",
                "East Viewing Room", "West Viewing Room", "East Teller's Room", "West Teller's Room",
                "Chairman's Office", "Riddle Room", "Pentagram Room", "Circular Room",
                "Fresco Room", "Library", "Tea Room",
            },
            "dread": {
                "Crypt", "Crypt Anteroom", "Room of Black Mist", "Room of Blue Mist",
                "Room of Red Mist", "Room of White Mist", "Murky Room", "Dreary Room",
                "Dusty Room", "Dingy Closet", "Cool Room", "Cobwebby Corridor", "Dark Tunnel",
                "Kennel", "Ice Room",
            },
        },
    },
    "zork3": {
        "src": "sources/zork3",
        "dungeon": ["3dungeon.zil", "3actions.zil"],  # ZIII splits room defs across both
        "actions": "3actions.zil",
        "opening": "zork3/scenes/opening.yaml",  # optional; merged only if present
        "out": "zork3/scenes/zork3.yaml",
        # Zork III ("The Dungeon Master") is wholly subterranean and the most
        # melancholy of the trilogy; the lake/cliff/ocean are its only "open" notes.
        "default_region": "underground",
        "region_default": "underground",
        "start_room": "Endless Stair",
        "scene_anchors": {
            "Land of Shadow": ["hooded-figure"],
            "Dungeon Entrance": ["guardians-of-zork"],
            "Parapet": ["guardians-of-zork"],
            "Treasury of Zork": ["dungeon-master"],
        },
        "regions": {
            "above_ground": {
                "Lake Shore", "On the Lake", "Western Shore", "Southern Shore",
                "Aqueduct View", "Cliff Base", "Cliff", "Cliff Ledge", "Flathead Ocean",
            },
            "peril": {
                "Land of Shadow", "Dungeon Entrance", "Narrow Corridor", "North Corridor",
                "South Corridor", "East Corridor", "West Corridor", "Parapet", "Prison Cell",
                "Great Door",
            },
            "wonder": {
                "Crystal Grotto", "Royal Hall", "Jewel Room", "Technology Museum",
                "Museum Entrance", "Scenic Vista", "Inside Mirror", "Beam Room",
                "Engravings Room", "Button Room", "Treasury of Zork", "Royal Puzzle Entrance",
                "Room in a Puzzle", "Side Room",
            },
            "dread": {
                "Creepy Crawl", "Dark Place", "Foggy Room", "Damp Passage", "Dead End",
                "Tight Squeeze", "Drafty Room", "Machine Room", "Sacrificial Altar",
            },
        },
    },
}


def region_of(desc, regions, region_default):
    for region, names in regions.items():
        if desc in names:
            return region
    return region_default


def slugify(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def clean(s):
    s = s.replace("|", " ").replace("\\", " ")
    s = re.sub(r"\s*:\s*\.", ".", s)  # strip dynamic object-list placeholders ("you can see: .")
    s = " ".join(s.split())
    # Drop a runtime list-intro left dangling once its object list was stripped,
    # e.g. "...On the ground below you can see." (otherwise narrated as nonsense).
    s = re.sub(r"\s*[^.]*\byou can see\s*\.\s*$", "", s).strip()
    return s


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
    ap = argparse.ArgumentParser(description="Extract a game's map into scene definitions.")
    ap.add_argument("--game", default="zork1", choices=sorted(GAMES),
                    help="which game's ZIL to extract (default: zork1)")
    args = ap.parse_args()
    cfg = GAMES[args.game]

    src = ROOT / cfg["src"]
    # Room definitions can span multiple ZIL files (Zork III splits them across
    # 3dungeon.zil + 3actions.zil); accept a str or a list of filenames for both.
    dungeon_files = cfg["dungeon"] if isinstance(cfg["dungeon"], list) else [cfg["dungeon"]]
    action_files = cfg["actions"] if isinstance(cfg["actions"], list) else [cfg["actions"]]
    out = ROOT / cfg["out"]
    region_default = cfg["region_default"]
    regions = cfg["regions"]
    scene_anchors = cfg.get("scene_anchors", {})

    opening = {}
    if cfg.get("opening"):
        opening_path = ROOT / cfg["opening"]
        if opening_path.exists():  # keep the merge optional per game
            opening = {s["id"]: s for s in yaml.safe_load(opening_path.read_text())["scenes"]}

    rooms = []
    for df in dungeon_files:
        rooms += parse_rooms((src / df).read_text())
    action_descs = {}
    for af in action_files:
        action_descs.update(parse_action_descs((src / af).read_text()))

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

        text = r["ldesc"] or action_descs.get(r["action"] or "", "") or ""
        scenes.append({
            "id": desc,
            "room": r["name"],
            "rooms": [r["name"]],
            "slug": slugify(desc),
            "region": region_of(desc, regions, region_default),
            "anchors": scene_anchors.get(desc, []),
            "scene_description": text,
            "scene_core": text,
        })

    doc = {"game": args.game, "default_region": cfg["default_region"],
           "start_room": cfg["start_room"], "scenes": scenes}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(doc, sort_keys=False, default_flow_style=False, width=90, allow_unicode=True))

    from collections import Counter
    regions_count = Counter(s["region"] for s in scenes)
    missing = [s["id"] for s in scenes if not s.get("scene_description")]
    print(f"Wrote {out.relative_to(ROOT)}: {len(scenes)} unique scenes")
    print("regions:", dict(regions_count))
    print("scenes with NO text (need manual):", missing or "none")


if __name__ == "__main__":
    main()
