"""The island, with no drawing in it.

Ten times a second is plenty, but the rules are written in seconds, so any
small dt is fine. Belts hold one item. A full next tile refuses it, and that
refusal is what stops the machines upstream.
"""

from __future__ import annotations

from dataclasses import dataclass

from island_factory.constants import (
    ARM,
    ARM_MK2,
    ARM_MK2_SECONDS,
    ARM_MK2_WATTS,
    ARM_SECONDS,
    BATTERY,
    BATTERY_MK2,
    BATTERY_MK2_WS,
    BATTERY_WS,
    BELT,
    BELT_SECONDS,
    CAPS,
    CASTLE_ORDER,
    CASTLE_RECT,
    CHOP_SECONDS,
    CHOPPING,
    COPPER,
    COPPER_EXT,
    COPPER_GATE,
    DIRS,
    DIR_NAMES,
    DUMP,
    DUMP_CAP,
    DUMP_CLICK_SECONDS,
    DUMP_MK2,
    DUMP_MK2_CAP,
    DUMP_MK2_WATTS,
    DUMP_SPILL_SECONDS,
    EXTRACT_SECONDS,
    EXTRACTORS,
    GENERATOR,
    GEN_BURN_SECONDS,
    GEN_WATTS,
    GOLD,
    GOLD_EXT,
    GRASS,
    GROWN,
    GRID_H,
    GRID_W,
    INTRO,
    IRON,
    IRON_EXT,
    IRON_GATE,
    LOG,
    NAMES,
    PADS,
    QUEEN_SECONDS,
    QUEUE_CAP,
    REGROW_SECONDS,
    SAND,
    SAND_RECT,
    SOCKETS,
    STOCK_INPUT,
    STUMP,
    TOOL_CAP,
    TREES,
    UPGRADES,
    WATER,
    WATTS,
    WIN_LINE,
    WOOD,
    opposite,
    right_hand,
)
from island_factory.recipes import RECIPES, Recipe


@dataclass
class Tool:
    kind: str
    charges: int = 1
    tier: int = 1
    waste: int = 0


@dataclass
class Machine:
    id: int
    kind: str
    x: int
    y: int
    facing: int = 1
    tier: int = 1
    paused: bool = False
    lit: bool = False
    belt_item: str | None = None
    belt_progress: float = 0.0
    sand_in: str | None = None
    sand_out: str | None = None
    metal_out: str | None = None
    work: float = 0.0
    sand_seen: int = 0
    waste: int = 0
    spill: float = 0.0
    hand_t: float = 0.0
    burn: float = 0.0


@dataclass
class Tree:
    x: int
    y: int
    state: str = GROWN
    timer: float = 0.0


@dataclass
class Stock:
    wood: int = 0
    copper: int = 0
    iron: int = 0
    gold: int = 0
    tier: int = 0

    def cap(self, resource: str) -> int:
        return CAPS[self.tier][resource]

    def get(self, resource: str) -> int:
        return getattr(self, resource)

    def add(self, resource: str, amount: int) -> int:
        room = self.cap(resource) - self.get(resource)
        if room <= 0 or amount <= 0:
            return 0
        take = min(amount, room)
        setattr(self, resource, self.get(resource) + take)
        return take

    def can_pay(self, cost: dict[str, int]) -> bool:
        return all(self.get(name) >= amount for name, amount in cost.items())

    def pay(self, cost: dict[str, int]) -> None:
        for name, amount in cost.items():
            setattr(self, name, self.get(name) - amount)


class Game:
    def __init__(self) -> None:
        self.time = 0.0
        self.stock = Stock()
        self.tools: list[Tool] = []
        self.queue: list[str] = []
        self.craft_t = 0.0
        self.machines: dict[tuple[int, int], Machine] = {}
        self.trees: dict[tuple[int, int], Tree] = {}
        self.pads: dict[tuple[int, int], str] = {}
        self.terrain: list[list[str]] = []
        self.scar: dict[tuple[int, int], int] = {}
        self.reserved: set[tuple[int, int]] = set()
        self.castle_tiles: set[tuple[int, int]] = set()
        self.placed_castle: set[str] = set()
        self.next_id = 1
        self.lifetime_copper = 0
        self.lifetime_iron = 0
        self.lifetime_gold = 0
        self.supply = 0.0
        self.demand = 0
        self.brownout = False
        self.battery_ws = 0.0
        self.battery_cap = 0
        self.queen_t = 0.0
        self.won = False
        self.held_dump: tuple[int, int] | None = None
        self._build_world()

    def _build_world(self) -> None:
        self.terrain = []
        for y in range(GRID_H):
            row = []
            for x in range(GRID_W):
                if x < 2 or y < 2 or x >= GRID_W - 2 or y >= GRID_H - 2:
                    row.append(WATER)
                else:
                    row.append(GRASS)
            self.terrain.append(row)
        sx, sy, sw, sh = SAND_RECT
        for y in range(sy, sy + sh):
            for x in range(sx, sx + sw):
                self.terrain[y][x] = SAND
        cx, cy, cw, ch = CASTLE_RECT
        self.castle_tiles = {(x, y) for x in range(cx, cx + cw) for y in range(cy, cy + ch)}
        self.reserved = set(self.castle_tiles)
        self.reserved.update(SOCKETS.values())
        self.reserved.add(STOCK_INPUT)
        for name, (x, y, w, h) in PADS.items():
            for ty in range(y, y + h):
                for tx in range(x, x + w):
                    self.pads[(tx, ty)] = name
                    self.reserved.add((tx, ty))
        for x, y in TREES:
            self.trees[(x, y)] = Tree(x, y)

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < GRID_W and 0 <= y < GRID_H

    def tick(self, dt: float) -> None:
        if dt <= 0:
            return
        self.time += dt
        self._tick_trees(dt)
        self._tick_workshop(dt)
        self._tick_power(dt)
        if not self.brownout:
            self._tick_arms(dt)
            self._tick_extractors(dt)
            self._tick_dumps(dt)
            self._push_outputs()
            self._tick_belts(dt)
        self._manual_dump(dt)
        self._tick_queen(dt)

    # --- trees and stock -------------------------------------------------

    def start_chop(self, x: int, y: int) -> str | None:
        tree = self.trees.get((x, y))
        if tree is None or tree.state != GROWN:
            return "That tree has no wood ready."
        tree.state = CHOPPING
        tree.timer = 0.0
        return None

    def give_log(self, x: int, y: int) -> str | None:
        tree = self.trees.get((x, y))
        if tree is None or tree.state != LOG:
            return "There is no log there."
        if self.stock.add(WOOD, 1) != 1:
            return "The stockpile cannot hold more wood."
        tree.state = STUMP
        tree.timer = 0.0
        return None

    def _tick_trees(self, dt: float) -> None:
        for tree in self.trees.values():
            if tree.state == CHOPPING:
                tree.timer += dt
                if tree.timer >= CHOP_SECONDS:
                    tree.state = LOG
                    tree.timer = 0.0
            elif tree.state == STUMP:
                tree.timer += dt
                if tree.timer >= REGROW_SECONDS:
                    tree.state = GROWN
                    tree.timer = 0.0

    # --- workshop --------------------------------------------------------

    def visible_recipes(self) -> list[Recipe]:
        ids = ["belt", "generator", "battery", "dump", "arm", "copper_ext"]
        if self.stock.tier < 1 and "copper_bins" not in self.queue:
            ids.append("copper_bins")
        if self.lifetime_copper >= COPPER_GATE:
            ids.append("iron_ext")
            if self.stock.tier < 2 and "iron_racks" not in self.queue:
                ids.append("iron_racks")
            ids.extend(["arm_mk2", "dump_mk2"])
        if self.lifetime_iron >= IRON_GATE:
            if self.stock.tier < 3 and "gold_vault" not in self.queue:
                ids.append("gold_vault")
            ids.extend(["gold_ext", "battery_mk2"])
            if self.stock.tier >= 3:
                for piece in CASTLE_ORDER:
                    if piece in self.placed_castle or self._holding(piece):
                        continue
                    ids.append(piece)
                    break
        return [RECIPES[rid] for rid in ids]

    def _holding(self, kind: str) -> bool:
        if any(tool.kind == kind for tool in self.tools):
            return True
        return any(RECIPES[rid].tool_kind == kind for rid in self.queue)

    def enqueue(self, recipe_id: str) -> str | None:
        recipe = RECIPES.get(recipe_id)
        if recipe is None or recipe_id not in {item.id for item in self.visible_recipes()}:
            return "That job is not open yet."
        if len(self.queue) >= QUEUE_CAP:
            return "The workshop already has three jobs."
        if not self.stock.can_pay(recipe.cost):
            return "Not enough in the stockpile."
        pending = sum(1 for rid in self.queue if RECIPES[rid].tool_kind)
        if recipe.tool_kind and len(self.tools) + pending >= TOOL_CAP:
            return "The tool pile is full."
        self.stock.pay(recipe.cost)
        self.queue.append(recipe_id)
        return None

    def _tick_workshop(self, dt: float) -> None:
        if not self.queue:
            self.craft_t = 0.0
            return
        recipe = RECIPES[self.queue[0]]
        if recipe.tool_kind and len(self.tools) >= TOOL_CAP:
            return
        self.craft_t += dt
        if self.craft_t < recipe.seconds:
            return
        self.craft_t = 0.0
        self.queue.pop(0)
        if recipe.stock_tier is not None:
            self.stock.tier = max(self.stock.tier, recipe.stock_tier)
            return
        assert recipe.tool_kind is not None
        self.tools.append(Tool(kind=recipe.tool_kind, charges=recipe.charges))

    # --- placement -------------------------------------------------------

    def can_place(self, tool_index: int, x: int, y: int, facing: int) -> bool:
        if not 0 <= tool_index < len(self.tools):
            return False
        tool = self.tools[tool_index]
        if tool.kind == BELT:
            return (
                self.in_bounds(x, y)
                and not self._blocked(x, y)
                and self.terrain[y][x] == GRASS
            )
        if tool.kind in UPGRADES:
            machine = self.machines.get((x, y))
            expect = UPGRADES[tool.kind]
            return machine is not None and machine.kind == expect and machine.tier < 2
        if tool.kind in CASTLE_ORDER:
            if SOCKETS[tool.kind] != (x, y):
                return False
            for piece in CASTLE_ORDER:
                if piece not in self.placed_castle:
                    return piece == tool.kind
            return False
        return self._machine_error(tool.kind, x, y, facing) is None

    def place(self, tool_index: int, x: int, y: int, facing: int) -> str | None:
        if not 0 <= tool_index < len(self.tools):
            return "Nothing in hand."
        tool = self.tools[tool_index]
        if tool.kind == BELT:
            return self._place_belt(tool_index, x, y, facing)
        if tool.kind in UPGRADES:
            return self._apply_upgrade(tool_index, x, y)
        if tool.kind in CASTLE_ORDER:
            return self._place_castle(tool_index, x, y)
        error = self._machine_error(tool.kind, x, y, facing)
        if error:
            return error
        machine = self._add_machine(tool.kind, x, y, facing, tool.tier)
        machine.waste = tool.waste
        if machine.kind == GENERATOR:
            machine.lit = False
        del self.tools[tool_index]
        return None

    def _place_belt(self, tool_index: int, x: int, y: int, facing: int) -> str | None:
        if self._blocked(x, y) or self.terrain[y][x] != GRASS:
            return "Belts sit on open grass."
        self._add_machine(BELT, x, y, facing, 1)
        tool = self.tools[tool_index]
        tool.charges -= 1
        if tool.charges <= 0:
            del self.tools[tool_index]
        return None

    def _apply_upgrade(self, tool_index: int, x: int, y: int) -> str | None:
        machine = self.machines.get((x, y))
        kind = self.tools[tool_index].kind
        expect = UPGRADES[kind]
        if machine is None or machine.kind != expect:
            return f"Drop that onto a {NAMES[expect].lower()}."
        if machine.tier >= 2:
            return "That one is already improved."
        machine.tier = 2
        del self.tools[tool_index]
        return None

    def _place_castle(self, tool_index: int, x: int, y: int) -> str | None:
        kind = self.tools[tool_index].kind
        if SOCKETS[kind] != (x, y):
            return "That piece has its own mark on the castle."
        for piece in CASTLE_ORDER:
            if piece not in self.placed_castle:
                if piece != kind:
                    return "The castle is built in order."
                break
        self.placed_castle.add(kind)
        del self.tools[tool_index]
        if kind == CASTLE_ORDER[-1]:
            self.queen_t = 0.001
        return None

    def _machine_error(
        self,
        kind: str,
        x: int,
        y: int,
        facing: int,
        ignore: tuple[int, int] | None = None,
    ) -> str | None:
        if not self.in_bounds(x, y) or self._blocked(x, y, ignore) or self.terrain[y][x] != GRASS:
            return "That does not fit there."
        if kind == ARM:
            dx, dy = DIRS[facing]
            tx, ty = x + dx, y + dy
            if not self.in_bounds(tx, ty) or self.terrain[ty][tx] != SAND:
                return "The arm has to face a sand tile."
        return None

    def _blocked(self, x: int, y: int, ignore: tuple[int, int] | None = None) -> bool:
        if not self.in_bounds(x, y):
            return True
        if self.terrain[y][x] == WATER:
            return True
        key = (x, y)
        if key in self.reserved or key in self.trees:
            return True
        return key in self.machines and key != ignore

    def _add_machine(self, kind: str, x: int, y: int, facing: int, tier: int) -> Machine:
        machine = Machine(id=self.next_id, kind=kind, x=x, y=y, facing=facing % 4, tier=tier)
        self.next_id += 1
        self.machines[(x, y)] = machine
        return machine

    def move_machine(self, x: int, y: int, nx: int, ny: int, facing: int) -> str | None:
        machine = self.machines.get((x, y))
        if machine is None:
            return "Nothing there."
        facing %= 4
        if (nx, ny) == (x, y):
            if machine.kind != BELT:
                error = self._machine_error(machine.kind, x, y, facing, ignore=(x, y))
                if error:
                    return error
            machine.facing = facing
            return None
        if machine.kind == BELT and machine.belt_item:
            return "Take the item off the belt first."
        if machine.sand_in or machine.sand_out or machine.metal_out:
            return "That machine is still holding sand."
        del self.machines[(x, y)]
        error = (
            self._place_blocked_belt(nx, ny)
            if machine.kind == BELT
            else self._machine_error(machine.kind, nx, ny, facing)
        )
        if error:
            self.machines[(x, y)] = machine
            return error
        machine.x, machine.y, machine.facing = nx, ny, facing
        self.machines[(nx, ny)] = machine
        return None

    def _place_blocked_belt(self, x: int, y: int) -> str | None:
        if self._blocked(x, y) or self.terrain[y][x] != GRASS:
            return "Belts sit on open grass."
        return None

    def pickup(self, x: int, y: int) -> str | None:
        machine = self.machines.get((x, y))
        if machine is None:
            return "Nothing there."
        if machine.kind == BELT:
            return self._pickup_belt(machine)
        if machine.belt_item or machine.sand_in or machine.sand_out or machine.metal_out:
            return "It is still holding something."
        if len(self.tools) >= TOOL_CAP:
            return "The tool pile is full."
        self.tools.append(Tool(kind=machine.kind, charges=1, tier=machine.tier, waste=machine.waste))
        del self.machines[(x, y)]
        return None

    def _pickup_belt(self, machine: Machine) -> str | None:
        if machine.belt_item:
            return "Take the item off the belt first."
        for tool in self.tools:
            if tool.kind == BELT and tool.charges < 8:
                tool.charges += 1
                del self.machines[(machine.x, machine.y)]
                return None
        if len(self.tools) >= TOOL_CAP:
            return "The tool pile is full."
        self.tools.append(Tool(kind=BELT, charges=1))
        del self.machines[(machine.x, machine.y)]
        return None

    def click_machine(self, x: int, y: int) -> str | None:
        machine = self.machines.get((x, y))
        if machine is None or machine.kind == BELT:
            return "Nothing to switch."
        if machine.kind == GENERATOR:
            machine.lit = not machine.lit
            return None
        machine.paused = not machine.paused
        return None

    # --- simulation ------------------------------------------------------

    def watts_of(self, machine: Machine) -> int:
        if machine.paused:
            return 0
        if machine.kind == ARM:
            return ARM_MK2_WATTS if machine.tier >= 2 else WATTS[ARM]
        if machine.kind == DUMP:
            return DUMP_MK2_WATTS if machine.tier >= 2 else 0
        return WATTS.get(machine.kind, 0)

    def battery_capacity(self) -> int:
        total = 0
        for machine in self.machines.values():
            if machine.kind == BATTERY:
                total += BATTERY_MK2_WS if machine.tier >= 2 else BATTERY_WS
        return total

    def _tick_power(self, dt: float) -> None:
        gen_seconds = 0.0
        for machine in self.machines.values():
            if machine.kind != GENERATOR or not machine.lit:
                continue
            left = dt
            while left > 1e-9 and self.stock.wood > 0:
                need = GEN_BURN_SECONDS - machine.burn
                if need <= 1e-9:
                    machine.burn = 0.0
                    self.stock.wood -= 1
                    continue
                step = min(left, need)
                machine.burn += step
                gen_seconds += step
                left -= step
                if machine.burn >= GEN_BURN_SECONDS - 1e-9:
                    machine.burn = 0.0
                    self.stock.wood -= 1
        gen_energy = GEN_WATTS * gen_seconds
        demand_w = sum(self.watts_of(machine) for machine in self.machines.values())
        demand_energy = demand_w * dt
        cap = self.battery_capacity()
        self.battery_ws = min(self.battery_ws, float(cap))
        if gen_energy + self.battery_ws + 1e-6 >= demand_energy:
            short = demand_energy - gen_energy
            if short > 0:
                self.battery_ws -= short
            else:
                self.battery_ws = min(float(cap), self.battery_ws + (gen_energy - demand_energy))
            self.brownout = False
        else:
            self.battery_ws = 0.0
            self.brownout = demand_w > 0
        self.supply = gen_energy / dt if dt else 0.0
        self.demand = demand_w
        self.battery_cap = cap

    def _tick_arms(self, dt: float) -> None:
        for machine in self.machines.values():
            if machine.kind != ARM or machine.paused:
                continue
            machine.work += dt
            interval = ARM_MK2_SECONDS if machine.tier >= 2 else ARM_SECONDS
            if machine.work < interval:
                continue
            dx, dy = DIRS[opposite(machine.facing)]
            dest = self.machines.get((machine.x + dx, machine.y + dy))
            if dest is None or dest.kind != BELT or dest.belt_item is not None:
                continue
            sx, sy = machine.x + DIRS[machine.facing][0], machine.y + DIRS[machine.facing][1]
            if not self.in_bounds(sx, sy) or self.terrain[sy][sx] != SAND:
                continue
            dest.belt_item = SAND
            dest.belt_progress = 0.0
            machine.work = 0.0
            self.scar[(sx, sy)] = self.scar.get((sx, sy), 0) + 1

    def _tick_extractors(self, dt: float) -> None:
        for machine in self.machines.values():
            if machine.kind not in EXTRACTORS or machine.paused or machine.sand_in is None:
                continue
            metal = self._next_metal(machine)
            if machine.sand_out is not None:
                continue
            if metal and machine.metal_out is not None:
                continue
            machine.work += dt
            if machine.work < EXTRACT_SECONDS:
                continue
            machine.work = 0.0
            machine.sand_seen += 1
            machine.sand_in = None
            machine.sand_out = SAND
            if metal:
                machine.metal_out = metal
                if metal == COPPER:
                    self.lifetime_copper += 1
                elif metal == IRON:
                    self.lifetime_iron += 1
                elif metal == GOLD:
                    self.lifetime_gold += 1

    def _next_metal(self, machine: Machine) -> str | None:
        count = machine.sand_seen + 1
        if machine.kind == COPPER_EXT:
            return COPPER
        if machine.kind == IRON_EXT:
            return IRON if count % 2 == 0 else None
        if machine.kind == GOLD_EXT:
            return GOLD if count % 4 == 0 else None
        return None

    def _tick_dumps(self, dt: float) -> None:
        for machine in self.machines.values():
            if machine.kind != DUMP or machine.tier < 2 or machine.paused or machine.waste <= 0:
                continue
            machine.spill += dt
            while machine.spill >= DUMP_SPILL_SECONDS and machine.waste > 0:
                machine.spill -= DUMP_SPILL_SECONDS
                machine.waste -= 1

    def _manual_dump(self, dt: float) -> None:
        if self.held_dump is None:
            return
        machine = self.machines.get(self.held_dump)
        if machine is None or machine.kind != DUMP or machine.waste <= 0:
            return
        machine.hand_t += dt
        while machine.hand_t >= DUMP_CLICK_SECONDS and machine.waste > 0:
            machine.hand_t -= DUMP_CLICK_SECONDS
            machine.waste -= 1

    def _push_outputs(self) -> None:
        for machine in list(self.machines.values()):
            if machine.kind not in EXTRACTORS:
                continue
            self._push_port(machine, machine.facing, "sand_out")
            self._push_port(machine, right_hand(machine.facing), "metal_out")

    def _push_port(self, machine: Machine, facing: int, attr: str) -> None:
        item = getattr(machine, attr)
        if item is None:
            return
        dx, dy = DIRS[facing]
        nx, ny = machine.x + dx, machine.y + dy
        if (nx, ny) == STOCK_INPUT and item != SAND:
            if self._accept_stock(item):
                setattr(machine, attr, None)
            return
        dest = self.machines.get((nx, ny))
        if dest is None:
            return
        if dest.kind == BELT and dest.belt_item is None:
            dest.belt_item = item
            dest.belt_progress = 0.0
            setattr(machine, attr, None)
            return
        if dest.kind == DUMP and item == SAND and dest.waste < self.dump_cap(dest):
            dest.waste += 1
            setattr(machine, attr, None)

    def _tick_belts(self, dt: float) -> None:
        ready: list[Machine] = []
        for machine in self.machines.values():
            if machine.kind != BELT or machine.belt_item is None:
                continue
            machine.belt_progress = min(1.0, machine.belt_progress + dt / BELT_SECONDS)
            if machine.belt_progress >= 1.0:
                ready.append(machine)
        occupied = {
            (machine.x, machine.y)
            for machine in self.machines.values()
            if machine.kind == BELT and machine.belt_item is not None
        }
        claimed: set[tuple[int, int]] = set()
        for machine in ready:
            dx, dy = DIRS[machine.facing]
            nx, ny = machine.x + dx, machine.y + dy
            if self._deliver_belt(machine, nx, ny, occupied, claimed):
                machine.belt_item = None
                machine.belt_progress = 0.0

    def _deliver_belt(
        self,
        belt: Machine,
        nx: int,
        ny: int,
        occupied: set[tuple[int, int]],
        claimed: set[tuple[int, int]],
    ) -> bool:
        if (nx, ny) in claimed:
            return False
        if (nx, ny) == STOCK_INPUT:
            if self._accept_stock(belt.belt_item):
                claimed.add((nx, ny))
                return True
            return False
        dest = self.machines.get((nx, ny))
        if dest is None:
            return False
        if dest.kind == BELT:
            if (nx, ny) in occupied:
                return False
            dest.belt_item = belt.belt_item
            dest.belt_progress = 0.0
            occupied.add((nx, ny))
            claimed.add((nx, ny))
            return True
        if dest.kind == DUMP:
            if belt.belt_item != SAND or dest.waste >= self.dump_cap(dest):
                return False
            dest.waste += 1
            claimed.add((nx, ny))
            return True
        if dest.kind in EXTRACTORS:
            return self._deliver_extractor(belt, dest, claimed)
        return False

    def _deliver_extractor(
        self,
        belt: Machine,
        dest: Machine,
        claimed: set[tuple[int, int]],
    ) -> bool:
        ix = dest.x + DIRS[opposite(dest.facing)][0]
        iy = dest.y + DIRS[opposite(dest.facing)][1]
        if (belt.x, belt.y) != (ix, iy) or belt.belt_item != SAND:
            return False
        if dest.paused:
            if dest.sand_out is not None:
                return False
            dest.sand_out = SAND
            claimed.add((dest.x, dest.y))
            return True
        if dest.sand_in is not None:
            return False
        dest.sand_in = SAND
        claimed.add((dest.x, dest.y))
        return True

    def _accept_stock(self, item: str | None) -> bool:
        if item not in (COPPER, IRON, GOLD):
            return False
        return self.stock.add(item, 1) == 1

    def dump_cap(self, machine: Machine) -> int:
        return DUMP_MK2_CAP if machine.tier >= 2 else DUMP_CAP

    def _tick_queen(self, dt: float) -> None:
        if self.queen_t <= 0 or self.won:
            return
        self.queen_t += dt / QUEEN_SECONDS
        if self.queen_t >= 1:
            self.queen_t = 1
            self.won = True

    # --- words for the window --------------------------------------------

    def hint(self) -> str:
        if self.won:
            return WIN_LINE
        if self.queen_t > 0:
            return "A boat is at the north shore."
        generators = [m for m in self.machines.values() if m.kind == GENERATOR]
        if not generators:
            return "Chop a western tree, drag the log to the stockpile, and craft a generator."
        if not any(machine.lit for machine in generators):
            return "Click the generator to light it. It burns wood from the stockpile."
        if self.stock.tier < 1:
            return "Craft the copper bins, or the stockpile will refuse the metal."
        if not any(machine.kind == COPPER_EXT for machine in self.machines.values()):
            return "Face an arm into the sand. Sand leaves its back, copper leaves the extractor's right side."
        if self.lifetime_copper < COPPER_GATE:
            return "Belt the copper into the bright tile on the stockpile. Hold a full dump to empty it."
        if not any(machine.kind == IRON_EXT for machine in self.machines.values()):
            return "Set an iron extractor on the sand belt, between the copper extractor and the dump."
        if self.stock.tier < 2:
            return "Craft the iron racks so iron has a place to rest."
        if self.lifetime_iron < IRON_GATE:
            return "Let the iron flow. Pause copper once the later machines are paid for."
        if self.stock.tier < 3:
            return "Craft the gold vault. Gold has nowhere else to sit."
        if not any(machine.kind == GOLD_EXT for machine in self.machines.values()):
            return "Set the gold extractor between iron and the dump. Its bars are for the castle."
        for piece in CASTLE_ORDER:
            if piece not in self.placed_castle:
                return f"Craft the {NAMES[piece].lower()} and set it on its mark."
        return INTRO

    def hover_label(self, x: int, y: int) -> str:
        if not self.in_bounds(x, y):
            return ""
        if (x, y) == STOCK_INPUT:
            return "Stockpile input"
        if (x, y) in SOCKETS.values():
            for name, pos in SOCKETS.items():
                if pos == (x, y):
                    state = "set" if name in self.placed_castle else "open"
                    return f"{NAMES[name]} mark, {state}"
        pad = self.pads.get((x, y))
        if pad:
            return NAMES[pad]
        machine = self.machines.get((x, y))
        if machine:
            return self.machine_label(machine)
        tree = self.trees.get((x, y))
        if tree:
            return {
                GROWN: "Tree",
                CHOPPING: "Chopping",
                LOG: "Log, drag it to the stockpile",
                STUMP: "Stump, growing back",
            }[tree.state]
        if self.terrain[y][x] == SAND:
            return "Sand"
        if self.terrain[y][x] == WATER:
            return "Sea"
        return "Grass"

    def machine_label(self, machine: Machine) -> str:
        name = NAMES[machine.kind]
        if machine.tier >= 2 and machine.kind in (ARM, DUMP, BATTERY):
            name += " Mk2"
        if machine.kind == GENERATOR:
            return name + (" lit" if machine.lit else " dark")
        if machine.paused:
            return name + ", paused"
        if machine.kind == DUMP:
            return f"{name}, {machine.waste}/{self.dump_cap(machine)}"
        if machine.kind in EXTRACTORS or machine.kind == ARM:
            return f"{name}, facing {DIR_NAMES[machine.facing]}"
        if machine.kind == BELT:
            carried = NAMES.get(machine.belt_item or "", "empty")
            return f"Belt {DIR_NAMES[machine.facing]}, {carried}"
        return name

    def tool_label(self, tool: Tool) -> str:
        if tool.kind == BELT:
            return f"Belt ×{tool.charges}"
        if tool.tier >= 2 and tool.kind in (ARM, DUMP, BATTERY):
            return NAMES[tool.kind] + " Mk2"
        return NAMES.get(tool.kind, tool.kind)

    def blurb(self, kind: str) -> str:
        return BLURBS.get(kind, "")


BLURBS = {
    BELT: "Drag a path over grass. Items travel the way the belt faces.",
    ARM: "Face it into sand. A belt on the back catches what it pulls.",
    COPPER_EXT: "Sand enters the back and leaves the front. Copper leaves on the right.",
    IRON_EXT: "Set it on the sand's path. Every second lump drops an iron bar to the right.",
    GOLD_EXT: "Set it after iron. Every fourth lump drops gold. Pause it when the vault is full.",
    DUMP: "Drag it to a new tile. The sand comes with it. Hold still on it to heave sand into the sea.",
    GENERATOR: "Place it, then click it. A lit fire burns one log every ten seconds.",
    BATTERY: "Stores spare watts and gives them back when a fire goes out.",
    ARM_MK2: "Drop onto an arm. It pulls twice as fast and draws more watts.",
    DUMP_MK2: "Drop onto the dump. It empties itself and draws a little power.",
    BATTERY_MK2: "Drop onto a battery. A bigger store for a missed chop.",
    "foundation": "Drag it onto the low mark in the ghost castle.",
    "walls": "Drag it onto the wall mark.",
    "stairs": "Drag it onto the stair mark, just south of the castle.",
    "dome": "Drag it onto the dome mark.",
    "throne": "The last piece. The Queen comes ashore when it is set.",
}
