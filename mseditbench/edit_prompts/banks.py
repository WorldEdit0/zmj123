"""Per-task value banks. These are deterministic, hand-curated alternatives
used to instantiate the templates in tasks.py.

Curate / extend these lists before running generate.py at scale; each pulls
N samples per video, so list length × video count drives total prompt count.
"""

from __future__ import annotations


# T1 dynamic replacements: people / animals / animated entities.
T1_DYNAMIC_TARGETS = [
    "an old man with a long white beard, wearing a brown robe",
    "a young child about ten years old with curly black hair, wearing a school uniform",
    "an astronaut in a full white space suit with the visor down",
    "a knight in shining medieval armor with a red plume",
    "a robot with a chrome humanoid body and glowing blue eyes",
    "a pirate captain with a tricorn hat, eye patch, and red coat",
    "a bride in a white wedding gown with long veil",
    "a clown with rainbow hair, white face paint, and a polka-dot suit",
    "a small border collie puppy with a blue collar",
    "a female barista with short silver hair and a black apron",
]

# Backward-compatible alias for older generation code.
T1_TARGETS = T1_DYNAMIC_TARGETS

T1_STATIC_REPLACEMENTS = [
    "a clear double-walled glass mug",
    "a pale gray porcelain clay lump",
    "a bright yellow sunflower bouquet",
    "a blue-backed deck of cards",
    "a tall clear glass mixing pitcher",
    "a black marble gavel",
    "a dark walnut balloon basket",
    "a square black slate serving plate",
]

# T2 (attribute_kind, old_value templates, new_value list). Keep categories
# broad: color, material, clothing type, hairstyle, and accessories.
T2_ATTRIBUTES = [
    ("color", ["original clothing color"], ["a deep maroon apron", "a teal jacket", "a coral tank top", "a navy-blue suit"]),
    ("material", ["original fabric"], ["a black leather jacket", "a dark denim apron", "a sheer lace shawl", "a cream cashmere cardigan"]),
    ("clothing_type", ["original garment"], ["a sleeveless skate jersey", "a short-sleeved chef jacket", "a white medical scrub top", "a white dinner jacket"]),
    ("hairstyle", ["original hairstyle"], ["a sleek high updo", "a short blunt bob haircut", "a long loose ponytail", "loose shoulder-length hair"]),
    ("accessory", ["original accessory"], ["round wire-rimmed glasses", "a tall white pleated chef hat", "a chunky gold chain", "a red collar with a silver tag"]),
]

# T3 global style only. Lighting-only edits live in T7.
T3_STYLES = [
    "pixel art style",
    "Makoto Shinkai style",
    "Hayao Miyazaki style",
    "JoJo manga style",
    "cyberpunk style",
    "traditional Chinese ink-wash painting style",
    "oil painting style",
    "American comic-book style",
    "3D realistic animation style",
    "stop-motion clay animation style",
]

# T4 add/delete operations.
#
# Schema: (op, new_object_or_None, conditions_dict)
#   op:        "add" | "delete"
#   conditions:
#     object_kind: "static" | "dynamic"
#     match_any:  old object/entity substrings for delete
#     anchor_any: anchor substrings for add
T4_OPS = [
    ("add", "a small brass desk bell",       {"object_kind": "static", "anchor_any": ["counter", "table", "desk", "cup"]}),
    ("add", "a folded blue towel",           {"object_kind": "static", "anchor_any": ["table", "exam table", "bench"]}),
    ("add", "a small red seal stamp",        {"object_kind": "static", "anchor_any": ["ink", "paper", "desk"]}),
    ("add", "a stainless steel water bottle", {"object_kind": "static", "anchor_any": ["floor", "mat", "table"]}),
    ("delete", None,                          {"object_kind": "static", "match_any": ["cup", "pitcher", "tool", "deck", "gavel", "cone", "mat", "bottle"]}),
    ("delete", None,                          {"object_kind": "static", "match_any": ["surfboard", "snowboard", "rod", "wrench", "watch", "plate", "tongs"]}),
    ("add", "a small calm dog",              {"object_kind": "dynamic", "anchor_any": ["table", "mat", "dock", "campfire", "case"]}),
    ("add", "a quiet assistant standing nearby", {"object_kind": "dynamic", "anchor_any": ["bench", "furnace", "truck", "basket", "bar"]}),
    ("delete", None,                          {"object_kind": "dynamic", "match_any": ["person", "character", "dog", "puppy", "poodle"]}),
]

# T6 cinematic re-shoot
T6_FRAMINGS = ["extreme close-up", "wide establishing shot", "low-angle medium shot", "overhead shot", "dutch-angle medium shot"]
T6_CAMERA_MOVES = ["slow dolly-in", "slow dolly-out", "left-to-right pan", "smooth tilt-up", "handheld follow"]

# T7 global lighting only.
T7_LIGHTING = [
    "warm dusk window light",
    "neon cocktail-bar lighting in pink and teal",
    "misty pre-dawn blue light",
    "deep midnight light with faint practical sources",
    "aurora-colored sky glow",
    "weak indoor bulb light",
    "flickering campfire light",
    "candlelight as the dominant illumination",
    "cool fluorescent overhead light",
    "golden-hour sunset light",
    "moonlit blue night light",
    "small handheld work-light beam",
]

# T8 global background replacements. The production T8 prompts are hand-written
# in runs/edit_prompts_v2_10s/T8.json; this bank is only for future generation
# experiments.
T8_BACKGROUNDS = [
    "a sunlit mountain valley with distant pine ridges",
    "a bright tropical beach with pale sand and turquoise water",
    "a quiet redwood forest clearing with mossy ground",
    "a clean white marble sculpture gallery",
    "a misty alpine meadow full of wildflowers",
    "a glass greenhouse surrounded by dense jungle leaves",
    "an ancient stone amphitheater at sunset",
    "a sleek futuristic theater with dark chrome walls",
    "a moonlit desert oasis with low palms",
    "a gothic library lined with tall arched bookshelves",
]
