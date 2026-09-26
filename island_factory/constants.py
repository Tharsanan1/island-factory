"""Numbers and names for the v1 island. Change these to retune the game."""

from __future__ import annotations

WOOD, SAND, COPPER, IRON, GOLD = "wood", "sand", "copper", "iron", "gold"
RESOURCES = (WOOD, COPPER, IRON, GOLD)

ARM, BELT = "arm", "belt"
COPPER_EXT, IRON_EXT, GOLD_EXT = "copper_ext", "iron_ext", "gold_ext"
EXTRACTORS = (COPPER_EXT, IRON_EXT, GOLD_EXT)
DUMP, GENERATOR, BATTERY = "dump", "generator", "battery"
ARM_MK2, DUMP_MK2, BATTERY_MK2 = "arm_mk2", "dump_mk2", "battery_mk2"
UPGRADES = {ARM_MK2: ARM, DUMP_MK2: DUMP, BATTERY_MK2: BATTERY}

FOUNDATION, WALLS, STAIRS, DOME, THRONE = (
    "foundation",
    "walls",
    "stairs",
    "dome",
    "throne",
)
CASTLE_ORDER = (FOUNDATION, WALLS, STAIRS, DOME, THRONE)

WATER, GRASS = "water", "grass"
GROWN, CHOPPING, LOG, STUMP = "grown", "chopping", "log", "stump"

# Facing index: north, east, south, west. y grows downward.
DIRS = ((0, -1), (1, 0), (0, 1), (-1, 0))
DIR_NAMES = ("north", "east", "south", "west")

GRID_W, GRID_H = 48, 32
# Sand field on the east. (x, y, width, height)
SAND_RECT = (32, 14, 8, 6)
# Castle keep-out on the north shore.
CASTLE_RECT = (18, 4, 9, 9)
PADS = {
    "stockpile": (6, 24, 3, 2),
    "workshop": (16, 24, 4, 2),
    "toolpile": (26, 24, 3, 2),
}
# Belts deliver into this grass tile. It sits on the south lip of the stockpile.
STOCK_INPUT = (7, 26)
SOCKETS = {
    FOUNDATION: (22, 11),
    WALLS: (22, 6),
    STAIRS: (22, 13),
    DOME: (22, 7),
    THRONE: (22, 8),
}
TREES = (
    (4, 6), (7, 6), (10, 6), (13, 6),
    (5, 8), (8, 8), (12, 8),
    (4, 10), (7, 10), (11, 10), (14, 10),
    (6, 12), (9, 12), (13, 12),
    (4, 14), (8, 14), (11, 14),
    (5, 16), (10, 16), (14, 16),
)

GEN_WATTS = 10
GEN_BURN_SECONDS = 10.0
BATTERY_WS = 200
BATTERY_MK2_WS = 500
BELT_SECONDS = 0.5
ARM_SECONDS = 2.0
ARM_MK2_SECONDS = 1.0
EXTRACT_SECONDS = 1.0
CHOP_SECONDS = 1.5
REGROW_SECONDS = 100.0
DUMP_CAP = 20
DUMP_MK2_CAP = 40
DUMP_CLICK_SECONDS = 0.3
DUMP_SPILL_SECONDS = 1.0
TOOL_CAP = 6
QUEUE_CAP = 3
COPPER_GATE = 10
IRON_GATE = 10
QUEEN_SECONDS = 8.0

WATTS = {ARM: 2, COPPER_EXT: 3, IRON_EXT: 5, GOLD_EXT: 8}
ARM_MK2_WATTS = 4
DUMP_MK2_WATTS = 2

# tier 0 woodshed, 1 copper bins, 2 iron racks, 3 gold vault
CAPS = (
    {WOOD: 20, COPPER: 0, IRON: 0, GOLD: 0},
    {WOOD: 40, COPPER: 40, IRON: 0, GOLD: 0},
    {WOOD: 60, COPPER: 60, IRON: 40, GOLD: 0},
    {WOOD: 80, COPPER: 80, IRON: 60, GOLD: 40},
)

INTRO = "The Queen stays at sea until the castle can receive her. Raise it in gold."
WIN_LINE = "You kept the fire. I will stay."

NAMES = {
    WOOD: "Wood",
    SAND: "Sand",
    COPPER: "Copper",
    IRON: "Iron",
    GOLD: "Gold",
    ARM: "Arm",
    BELT: "Belt",
    COPPER_EXT: "Copper extractor",
    IRON_EXT: "Iron extractor",
    GOLD_EXT: "Gold extractor",
    DUMP: "Dump",
    GENERATOR: "Generator",
    BATTERY: "Battery",
    ARM_MK2: "Arm Mk2",
    DUMP_MK2: "Dump Mk2",
    BATTERY_MK2: "Battery Mk2",
    FOUNDATION: "Foundation",
    WALLS: "Walls",
    STAIRS: "Stairs",
    DOME: "Dome",
    THRONE: "Throne",
    "stockpile": "Stockpile",
    "workshop": "Workshop",
    "toolpile": "Tool pile",
}


def opposite(facing: int) -> int:
    return (facing + 2) % 4


def right_hand(facing: int) -> int:
    return (facing + 1) % 4


def facing_from(src: tuple[int, int], dst: tuple[int, int]) -> int | None:
    dx, dy = dst[0] - src[0], dst[1] - src[1]
    for index, (fx, fy) in enumerate(DIRS):
        if (fx, fy) == (dx, dy):
            return index
    return None
