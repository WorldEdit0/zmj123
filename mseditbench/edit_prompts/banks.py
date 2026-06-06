"""Per-task value banks. These are deterministic, hand-curated alternatives
used to instantiate the templates in tasks.py.

Curate / extend these lists before running generate.py at scale; each pulls
N samples per video, so list length × video count drives total prompt count.
"""

from __future__ import annotations


# T1 character replacements — keep gender-balanced, all "human"
T1_TARGETS = [
    "an old man with a long white beard, wearing a brown robe",
    "a young child about ten years old with curly black hair, wearing a school uniform",
    "an astronaut in a full white space suit with the visor down",
    "a knight in shining medieval armor with a red plume",
    "a robot with a chrome humanoid body and glowing blue eyes",
    "a pirate captain with a tricorn hat, eye patch, and red coat",
    "a bride in a white wedding gown with long veil",
    "a clown with rainbow hair, white face paint, and a polka-dot suit",
]

# T2 (attribute_kind, old_value templates, new_value list)
T2_ATTRIBUTES = [
    ("hair color", ["original hair"], ["bright pink hair", "platinum white hair", "deep red hair", "neon green hair"]),
    ("jacket color", ["original jacket"], ["a bright yellow jacket", "an electric blue jacket", "a black leather jacket"]),
    ("shirt color", ["original shirt"], ["a tie-dye shirt", "a striped black-and-white shirt", "a pure white shirt"]),
    ("glasses",     ["no glasses"],     ["round gold-rimmed glasses", "thick black-rimmed glasses", "mirrored aviator sunglasses"]),
    ("hat",         ["no hat"],         ["a red baseball cap", "a wide-brimmed straw hat", "a knit beanie"]),
]

# T3 global style / lighting
T3_STYLES = [
    "1990s VHS camcorder footage with chromatic noise",
    "stop-motion clay animation",
    "anime cel-shaded with bold black outlines",
    "oil painting with visible brush strokes",
    "film noir black-and-white with deep shadows",
    "underwater lighting with caustic ripples",
    "midday neon-lit cyberpunk street",
    "warm golden-hour sunset lighting throughout",
    "cold blue moonlit night scene",
    "infrared thermal-camera view",
]

# T4 object operations.
#
# Schema: (op, new_object_or_None, conditions_dict)
#   op:        "replace" | "add" | "remove"
#   conditions:
#     match_any: list[str]   any substring (lowercased) must appear in some key_object
#                            of the video for the op to be applicable
# generate.py filters to applicable ops first, then samples up to N per video,
# so adding more options only widens coverage — it never starves other ops.
T4_OPS = [
    # ── coffee / drink containers ───────────────────────────────────────────
    ("replace", "a tall iced lemonade in a clear glass",   {"match_any": ["coffee cup", "coffee mug", "ceramic cup", "espresso"]}),
    ("replace", "a steaming bowl of green matcha",         {"match_any": ["coffee cup", "coffee mug", "ceramic cup", "espresso"]}),
    ("replace", "a glass of red wine",                     {"match_any": ["coffee cup", "coffee mug", "espresso", "wine glass"]}),
    ("replace", "a small clay teapot",                     {"match_any": ["coffee cup", "coffee mug", "ceramic cup"]}),

    # ── writing / hand tools ────────────────────────────────────────────────
    ("replace", "a quill pen with an ink well",            {"match_any": ["fountain pen", "pen", "blue marker"]}),
    ("replace", "a thick black marker",                    {"match_any": ["highlighter", "fountain pen"]}),
    ("replace", "a pair of bronze garden shears",          {"match_any": ["scissors"]}),
    ("replace", "a vintage wooden ruler",                  {"match_any": ["highlighter", "blue marker"]}),

    # ── kitchen / mechanic tools ────────────────────────────────────────────
    ("replace", "a meat cleaver",                          {"match_any": ["chef's knife", "knife"]}),
    ("replace", "a bright orange power drill",             {"match_any": ["wrench"]}),
    ("replace", "a copper saucepan",                       {"match_any": ["iron skillet", "skillet"]}),
    ("replace", "a fresh yellow lemon",                    {"match_any": ["red tomato", "tomato"]}),
    ("replace", "a green avocado cut in half",             {"match_any": ["red tomato", "tomato"]}),

    # ── digital devices ─────────────────────────────────────────────────────
    ("replace", "a chunky 1995-style flip phone",          {"match_any": ["smartphone", "phone"]}),
    ("replace", "a vintage rotary dial telephone",         {"match_any": ["smartphone", "phone"]}),
    ("replace", "an old beige CRT monitor",                {"match_any": ["computer monitor", "laptop"]}),
    ("replace", "a vintage typewriter",                    {"match_any": ["laptop"]}),
    ("replace", "an antique brass microphone on a stand",  {"match_any": ["studio microphone", "microphone"]}),

    # ── reading material ────────────────────────────────────────────────────
    ("replace", "a rolled-up parchment scroll",            {"match_any": ["paperback book", "open textbook", "hardcover book", "open notebook", "sheet music"]}),
    ("replace", "an oversized magazine with a glossy cover", {"match_any": ["paperback book", "hardcover book"]}),

    # ── outdoor / props ────────────────────────────────────────────────────
    ("replace", "a small white starfish",                  {"match_any": ["seashell"]}),
    ("replace", "a polished smooth black pebble",          {"match_any": ["seashell"]}),
    ("replace", "a yellow flower-patterned parasol",       {"match_any": ["red umbrella", "umbrella"]}),
    ("replace", "a heavy black kettlebell",                {"match_any": ["dumbbell"]}),
    ("replace", "a tall green succulent in a terracotta pot", {"match_any": ["small green plant", "green plant"]}),
    ("replace", "a dried branch with autumn leaves",       {"match_any": ["wooden stick", "walking stick"]}),

    # ── add: small object placed on a flat surface ─────────────────────────
    ("add", "a small black domestic cat curled up",        {"anchor_any": ["counter", "table", "desk", "tablecloth", "bedsheet", "mat", "platform"]}),
    ("add", "a fresh bouquet of red roses in a vase",      {"anchor_any": ["counter", "table", "desk", "tablecloth"]}),
    ("add", "a brass desk bell",                           {"anchor_any": ["counter", "table", "desk"]}),
    ("add", "a glowing candle in a glass holder",          {"anchor_any": ["counter", "table", "tablecloth", "desk"]}),
    ("add", "a small pile of orange autumn leaves",        {"anchor_any": ["sand", "soil", "path"]}),

    # ── add: thing on a wall or vertical surface ───────────────────────────
    ("add", "a vintage round wall clock",                  {"anchor_any": ["wall", "shelf", "mirror"]}),
    ("add", "a small framed family photograph",            {"anchor_any": ["wall", "shelf", "bookshelf", "mirror"]}),
    ("add", "a string of warm yellow fairy lights",        {"anchor_any": ["wall", "shelf", "bookshelf", "skyline", "alley"]}),

    # ── remove ─────────────────────────────────────────────────────────────
    ("remove", None,                                       {"match_any": ["coffee cup", "coffee mug", "ceramic cup", "espresso", "wine glass"]}),
    ("remove", None,                                       {"match_any": ["smartphone", "phone"]}),
    ("remove", None,                                       {"match_any": ["scattered papers", "papers"]}),
    ("remove", None,                                       {"match_any": ["red umbrella", "umbrella"]}),
    ("remove", None,                                       {"match_any": ["sheet music", "music sheet", "metronome"]}),
    ("remove", None,                                       {"match_any": ["highlighter", "blue marker", "fountain pen"]}),
]

# T6 cinematic re-shoot
T6_FRAMINGS = ["extreme close-up", "wide establishing shot", "low-angle medium shot", "overhead shot", "dutch-angle medium shot"]
T6_CAMERA_MOVES = ["slow dolly-in", "slow dolly-out", "left-to-right pan", "smooth tilt-up", "handheld follow"]

# T7 transitions
T7_TRANSITIONS = [
    "smooth crossfade", "slow cross-dissolve", "white flash", "iris-out",
    "rotational wipe", "match-cut on motion",
]
