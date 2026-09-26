"""Workshop jobs. Costs are paid when the job is ordered."""

from __future__ import annotations

from dataclasses import dataclass

from island_factory.constants import (
    ARM,
    ARM_MK2,
    BATTERY,
    BATTERY_MK2,
    BELT,
    COPPER,
    COPPER_EXT,
    DOME,
    DUMP,
    DUMP_MK2,
    FOUNDATION,
    GENERATOR,
    GOLD,
    GOLD_EXT,
    IRON,
    IRON_EXT,
    STAIRS,
    THRONE,
    WALLS,
    WOOD,
)


@dataclass(frozen=True)
class Recipe:
    id: str
    name: str
    cost: dict[str, int]
    seconds: float
    tool_kind: str | None = None
    charges: int = 1
    stock_tier: int | None = None


def _add(recipe: Recipe) -> Recipe:
    RECIPES[recipe.id] = recipe
    return recipe


RECIPES: dict[str, Recipe] = {}

_add(Recipe("belt", "Belt spool", {WOOD: 2}, 3, tool_kind=BELT, charges=8))
_add(Recipe("generator", "Generator", {WOOD: 8}, 6, tool_kind=GENERATOR))
_add(Recipe("battery", "Battery", {WOOD: 6}, 5, tool_kind=BATTERY))
_add(Recipe("dump", "Dump", {WOOD: 4}, 4, tool_kind=DUMP))
_add(Recipe("arm", "Arm", {WOOD: 8}, 8, tool_kind=ARM))
_add(Recipe("copper_ext", "Copper extractor", {WOOD: 10}, 10, tool_kind=COPPER_EXT))
_add(Recipe("copper_bins", "Copper bins", {WOOD: 12}, 6, stock_tier=1))

_add(Recipe("iron_ext", "Iron extractor", {COPPER: 24}, 12, tool_kind=IRON_EXT))
_add(Recipe("iron_racks", "Iron racks", {COPPER: 20}, 8, stock_tier=2))
_add(Recipe("arm_mk2", "Arm Mk2", {COPPER: 16, IRON: 8}, 10, tool_kind=ARM_MK2))
_add(Recipe("dump_mk2", "Dump Mk2", {COPPER: 12, IRON: 10}, 8, tool_kind=DUMP_MK2))

_add(Recipe("gold_vault", "Gold vault", {IRON: 24}, 10, stock_tier=3))
_add(Recipe("gold_ext", "Gold extractor", {COPPER: 40, IRON: 36}, 20, tool_kind=GOLD_EXT))
_add(Recipe("battery_mk2", "Battery Mk2", {IRON: 12}, 8, tool_kind=BATTERY_MK2))

_add(Recipe("foundation", "Foundation", {GOLD: 6}, 15, tool_kind=FOUNDATION))
_add(Recipe("walls", "Walls", {GOLD: 8}, 20, tool_kind=WALLS))
_add(Recipe("stairs", "Stairs", {GOLD: 8}, 20, tool_kind=STAIRS))
_add(Recipe("dome", "Dome", {GOLD: 12}, 25, tool_kind=DOME))
_add(Recipe("throne", "Throne", {GOLD: 40}, 30, tool_kind=THRONE))


def cost_text(cost: dict[str, int]) -> str:
    return ", ".join(f"{amount} {name}" for name, amount in cost.items())
