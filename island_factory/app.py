"""The window. The island rules live in game.py; this file only shows them."""

from __future__ import annotations

import os
from pathlib import Path

import pygame

from island_factory.constants import (
    ARM,
    BATTERY,
    BELT,
    COPPER,
    COPPER_EXT,
    DIRS,
    DIR_NAMES,
    DOME,
    DUMP,
    EXTRACTORS,
    FOUNDATION,
    GENERATOR,
    GOLD,
    GOLD_EXT,
    GROWN,
    GRID_H,
    GRID_W,
    INTRO,
    IRON,
    IRON_EXT,
    LOG,
    NAMES,
    RESOURCES,
    SAND,
    SOCKETS,
    STAIRS,
    STOCK_INPUT,
    STUMP,
    THRONE,
    WALLS,
    WATER,
    WIN_LINE,
    WOOD,
    CHOPPING,
    facing_from,
    opposite,
    right_hand,
)
from island_factory.game import Game
from island_factory.recipes import RECIPES, cost_text

TILE = 32
PANEL_W = 330

WATER_C = (18, 58, 86)
SHORE_C = (36, 92, 118)
GRASS_C = (62, 104, 64)
GRASS_B = (52, 90, 56)
SAND_C = (214, 184, 128)
SAND_DARK = (132, 100, 64)
INK = (236, 230, 218)
DIM = (176, 170, 156)
PANEL = (24, 28, 32)
PANEL_2 = (36, 42, 48)
SELECT = (240, 208, 120)
BAD = (186, 78, 68)
GOOD = (110, 176, 114)

MACHINE_COLOR = {
    "arm": (48, 64, 82),
    "belt": (62, 60, 72),
    "copper_ext": (120, 72, 48),
    "iron_ext": (78, 84, 92),
    "gold_ext": (120, 96, 48),
    "dump": (52, 50, 58),
    "generator": (96, 52, 46),
    "battery": (36, 96, 86),
}
ITEM_COLOR = {
    SAND: (196, 164, 104),
    COPPER: (204, 122, 72),
    IRON: (186, 192, 198),
    GOLD: (232, 196, 92),
    WOOD: (164, 112, 62),
}
METAL_OF = {COPPER_EXT: COPPER, IRON_EXT: IRON, GOLD_EXT: GOLD}


def lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))  # type: ignore[return-value]


def wrap(text: str, font: pygame.font.Font, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = word if not current else f"{current} {word}"
        if font.size(trial)[0] <= width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def step_toward(src: tuple[int, int], dst: tuple[int, int]) -> tuple[int, int]:
    x, y = src
    dx, dy = dst[0] - x, dst[1] - y
    if dx == 0 and dy == 0:
        return src
    if abs(dx) >= abs(dy):
        return x + (1 if dx > 0 else -1), y
    return x, y + (1 if dy > 0 else -1)


class App:
    def __init__(self) -> None:
        pygame.init()
        self.game = Game()
        self.win_w, self.win_h = 1440, 900
        self.screen = pygame.display.set_mode((self.win_w, self.win_h), pygame.RESIZABLE)
        pygame.display.set_caption("Island Factory")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("helveticaneue", 16)
        self.small = pygame.font.SysFont("helveticaneue", 13)
        self.large = pygame.font.SysFont("helveticaneue", 26)
        self.zoom = 1.0
        self.cam_x = 0.0
        self.cam_y = 0.0
        self.fit_camera()
        self.armed: int | None = None
        self.was_armed = False
        self.facing = 1
        self.intro = True
        self.toast = ""
        self.toast_t = 0.0
        self.speed = 1
        self.recipe_scroll = 0
        self.recipe_height = 0
        self.slots: list[pygame.Rect] = []
        self.recipes: list[tuple[pygame.Rect, str]] = []
        self.rot_l = pygame.Rect(0, 0, 0, 0)
        self.rot_r = pygame.Rect(0, 0, 0, 0)
        self.speeds: list[tuple[pygame.Rect, int]] = []
        self.stock_drop = pygame.Rect(0, 0, 0, 0)
        self.tool_drop = pygame.Rect(0, 0, 0, 0)
        self.recipe_clip = pygame.Rect(0, 0, 0, 0)
        self.press: tuple[int, int] | None = None
        self.press_kind: str | None = None
        self.press_payload: tuple[int, int] | None = None
        self.dragged = False
        self.belt_last: tuple[int, int] | None = None
        self.log_from: tuple[int, int] | None = None
        self.move_from: tuple[int, int] | None = None
        self.right_press: tuple[int, int] | None = None
        self.panning = False
        self.dump_tile: tuple[int, int] | None = None
        self.dump_hold = 0.0
        self.hover = ""
        self.job_y = 300
        self.running = True

    def fit_camera(self) -> None:
        view_w = max(200, self.win_w - PANEL_W)
        map_w = GRID_W * TILE
        map_h = GRID_H * TILE
        self.zoom = min(view_w / map_w, self.win_h / map_h) * 0.94
        self.cam_x = (map_w - view_w / self.zoom) / 2
        self.cam_y = (map_h - self.win_h / self.zoom) / 2

    def run(self) -> None:
        while self.running:
            dt = min(self.clock.tick(60) / 1000.0, 0.05)
            self.step(dt)
            pygame.display.flip()
        pygame.quit()

    def step(self, dt: float) -> None:
        self.layout()
        self.handle_events()
        self._keys(dt)
        self._dump_hold(dt)
        self.game.tick(dt * self.speed)
        if self.toast_t > 0:
            self.toast_t = max(0.0, self.toast_t - dt)
        self.draw()

    def layout(self) -> None:
        panel_x = self.win_w - PANEL_W
        armed = self.armed is not None and self.armed < len(self.game.tools)
        self.slots = []
        self.recipes = []
        self.speeds = []
        self.stock_drop = pygame.Rect(panel_x + 12, 118, PANEL_W - 24, 20)
        slot_y = 214
        for index in range(6):
            rect = pygame.Rect(panel_x + 16 + (index % 3) * 102, slot_y + (index // 3) * 36, 96, 32)
            self.slots.append(rect)
        self.tool_drop = pygame.Rect(panel_x + 12, 196, PANEL_W - 24, 92)
        if armed:
            self.rot_l = pygame.Rect(panel_x + 16, 352, 40, 28)
            self.rot_r = pygame.Rect(panel_x + 62, 352, 40, 28)
            job_y = 390
        else:
            self.rot_l = pygame.Rect(0, 0, 0, 0)
            self.rot_r = pygame.Rect(0, 0, 0, 0)
            job_y = 300
        self.job_y = job_y
        clip_top = job_y + 52
        clip_bottom = self.win_h - 168
        self.recipe_clip = pygame.Rect(panel_x + 8, clip_top, PANEL_W - 16, max(40, clip_bottom - clip_top))
        visible = self.game.visible_recipes()
        self.recipe_height = len(visible) * 48
        limit = max(0, self.recipe_height - self.recipe_clip.height)
        self.recipe_scroll = min(self.recipe_scroll, limit)
        row_y = clip_top - self.recipe_scroll
        for recipe in visible:
            rect = pygame.Rect(panel_x + 16, row_y, PANEL_W - 40, 44)
            if rect.bottom > clip_top and rect.top < clip_bottom:
                self.recipes.append((rect, recipe.id))
            row_y += 48
        for index, speed in enumerate((1, 2, 4)):
            rect = pygame.Rect(panel_x + 16 + index * 102, self.win_h - 42, 96, 26)
            self.speeds.append((rect, speed))

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.VIDEORESIZE:
                self.win_w = max(1100, event.w)
                self.win_h = max(700, event.h)
                self.screen = pygame.display.set_mode((self.win_w, self.win_h), pygame.RESIZABLE)
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._cancel()
            elif event.type == pygame.MOUSEWHEEL:
                self._wheel(event.y)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                self.right_press = event.pos
                self.panning = False
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 3:
                if not self.panning:
                    self._cancel()
                self.right_press = None
                self.panning = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._down(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self._up(event.pos)
            elif event.type == pygame.MOUSEMOTION:
                self._move(event.pos, event.buttons, event.rel)
        mouse = pygame.mouse.get_pos()
        tile = self.screen_to_tile(*mouse)
        self.hover = self.game.hover_label(*tile) if tile else ""

    def _cancel(self) -> None:
        self.intro = False
        self.armed = None
        self.belt_last = None
        self.log_from = None
        self.move_from = None
        self.press_kind = None
        self.dump_tile = None
        self.game.held_dump = None

    def _down(self, pos: tuple[int, int]) -> None:
        if self.intro:
            self.intro = False
            return
        self.press = pos
        self.dragged = False
        slot = self._slot_at(pos)
        if slot is not None:
            self.press_kind = "slot"
            self.press_payload = (slot, 0)
            self.was_armed = self.armed == slot
            self.armed = slot
            return
        if self.rot_l.collidepoint(pos):
            self.facing = (self.facing - 1) % 4
            self.press_kind = "ui"
            return
        if self.rot_r.collidepoint(pos):
            self.facing = (self.facing + 1) % 4
            self.press_kind = "ui"
            return
        for rect, speed in self.speeds:
            if rect.collidepoint(pos):
                self.speed = speed
                self.press_kind = "ui"
                return
        for rect, recipe_id in self.recipes:
            if rect.collidepoint(pos) and self.recipe_clip.collidepoint(pos):
                error = self.game.enqueue(recipe_id)
                if error:
                    self._toast(error)
                self.press_kind = "ui"
                return
        tile = self.screen_to_tile(*pos)
        tree = self.game.trees.get(tile) if tile else None
        if tree is not None and tree.state == LOG:
            self.press_kind = "log"
            self.log_from = tile
            return
        if tree is not None and tree.state == GROWN:
            self.press_kind = "tree"
            self.press_payload = tile
            return
        if self.armed is not None and tile is not None:
            self.press_kind = "place"
            self.press_payload = tile
            if self._armed_kind() == BELT:
                self._begin_belt(tile)
            return
        if tile is not None and tile in self.game.machines:
            self.press_kind = "machine"
            self.move_from = tile
            self.press_payload = tile
            self.facing = self.game.machines[tile].facing
            if self.game.machines[tile].kind == DUMP:
                self.dump_tile = tile
                self.dump_hold = 0.0
            return
        self.press_kind = "world"

    def _up(self, pos: tuple[int, int]) -> None:
        kind = self.press_kind
        if kind == "slot":
            if self.dragged:
                tile = self.screen_to_tile(*pos)
                if tile is not None:
                    self._place_armed(tile)
            elif self.was_armed:
                self.armed = None
        elif kind == "log" and self.log_from is not None:
            if self._over_stock(pos):
                error = self.game.give_log(*self.log_from)
                if error:
                    self._toast(error)
            self.log_from = None
        elif kind == "tree" and self.press_payload is not None and not self.dragged:
            error = self.game.start_chop(*self.press_payload)
            if error:
                self._toast(error)
        elif kind == "place":
            if self._armed_kind() != BELT:
                tile = self.screen_to_tile(*pos)
                if tile is not None:
                    self._place_armed(tile)
            self.belt_last = None
        elif kind == "machine" and self.move_from is not None:
            self._release_machine(pos)
        self.press_kind = None
        self.press = None
        self.dump_tile = None
        self.game.held_dump = None
        self.move_from = None

    def _release_machine(self, pos: tuple[int, int]) -> None:
        assert self.move_from is not None
        if self.dragged:
            self.game.held_dump = None
        elif self.dump_tile is not None and self.dump_hold > 0.18:
            return
        if not self.dragged:
            error = self.game.click_machine(*self.move_from)
            if error:
                self._toast(error)
            return
        if self._over_tools(pos):
            error = self.game.pickup(*self.move_from)
            if error:
                self._toast(error)
            return
        tile = self.screen_to_tile(*pos)
        if tile is None:
            return
        error = self.game.move_machine(self.move_from[0], self.move_from[1], tile[0], tile[1], self.facing)
        if error:
            self._toast(error)

    def _move(self, pos: tuple[int, int], buttons: tuple[int, ...], rel: tuple[int, int]) -> None:
        if buttons[2] and self.right_press is not None:
            if abs(pos[0] - self.right_press[0]) + abs(pos[1] - self.right_press[1]) > 4:
                self.panning = True
            self.cam_x -= rel[0] / self.zoom
            self.cam_y -= rel[1] / self.zoom
            self.clamp_camera()
        if self.press is not None:
            if abs(pos[0] - self.press[0]) + abs(pos[1] - self.press[1]) > 6:
                self.dragged = True
                self.game.held_dump = None
            if self.press_kind == "place" and self.belt_last is not None and self._armed_kind() == BELT:
                tile = self.screen_to_tile(*pos)
                if tile is not None:
                    self._extend_belt(tile)

    def _wheel(self, direction: int) -> None:
        mouse = pygame.mouse.get_pos()
        if mouse[0] >= self.win_w - PANEL_W:
            self.recipe_scroll = max(0, self.recipe_scroll - direction * 36)
            return
        old = self.zoom
        self.zoom *= 1.1 if direction > 0 else 1 / 1.1
        self.zoom = min(2.8, max(0.35, self.zoom))
        world_x = mouse[0] / old + self.cam_x
        world_y = mouse[1] / old + self.cam_y
        self.cam_x = world_x - mouse[0] / self.zoom
        self.cam_y = world_y - mouse[1] / self.zoom
        self.clamp_camera()

    def _keys(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        step = 520 * dt / self.zoom
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.cam_x -= step
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.cam_x += step
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            self.cam_y -= step
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            self.cam_y += step
        self.clamp_camera()

    def _dump_hold(self, dt: float) -> None:
        if self.dragged or self.press_kind != "machine" or self.dump_tile is None:
            self.game.held_dump = None
            return
        self.dump_hold += dt
        if self.dump_hold > 0.18:
            self.game.held_dump = self.dump_tile

    def clamp_camera(self) -> None:
        view_w = max(200, self.win_w - PANEL_W)
        map_w = GRID_W * TILE
        map_h = GRID_H * TILE
        max_x = map_w - view_w / self.zoom
        max_y = map_h - self.win_h / self.zoom
        if max_x < 0:
            self.cam_x = max_x / 2
        else:
            self.cam_x = min(max(self.cam_x, -48), max_x + 48)
        if max_y < 0:
            self.cam_y = max_y / 2
        else:
            self.cam_y = min(max(self.cam_y, -48), max_y + 48)

    def _toast(self, text: str) -> None:
        self.toast = text
        self.toast_t = 2.4

    def _armed_kind(self) -> str | None:
        if self.armed is None or self.armed >= len(self.game.tools):
            return None
        return self.game.tools[self.armed].kind

    def _slot_at(self, pos: tuple[int, int]) -> int | None:
        for index, rect in enumerate(self.slots):
            if rect.collidepoint(pos) and index < len(self.game.tools):
                return index
        return None

    def _over_stock(self, pos: tuple[int, int]) -> bool:
        if self.stock_drop.collidepoint(pos):
            return True
        tile = self.screen_to_tile(*pos)
        return tile is not None and self.game.pads.get(tile) == "stockpile"

    def _over_tools(self, pos: tuple[int, int]) -> bool:
        if self.tool_drop.collidepoint(pos):
            return True
        tile = self.screen_to_tile(*pos)
        return tile is not None and self.game.pads.get(tile) == "toolpile"

    def _place_armed(self, tile: tuple[int, int], facing: int | None = None) -> str | None:
        if self.armed is None or self.armed >= len(self.game.tools):
            self.armed = None
            return "Nothing in hand."
        tool = self.game.tools[self.armed]
        error = self.game.place(self.armed, tile[0], tile[1], self.facing if facing is None else facing)
        if tool not in self.game.tools:
            self.armed = None
            self.belt_last = None
        if error:
            self._toast(error)
        return error

    def _begin_belt(self, tile: tuple[int, int]) -> None:
        error = self._place_armed(tile, facing=self.facing)
        if error is None and tile in self.game.machines:
            self.belt_last = tile

    def _extend_belt(self, target: tuple[int, int]) -> None:
        guard = 0
        while self.belt_last is not None and self.belt_last != target and guard < 64:
            guard += 1
            nxt = step_toward(self.belt_last, target)
            facing = facing_from(self.belt_last, nxt)
            if facing is None or self.armed is None:
                self.belt_last = None
                break
            previous = self.game.machines.get(self.belt_last)
            if previous is not None and previous.kind == BELT:
                previous.facing = facing
            error = self._place_armed(nxt, facing=facing)
            if error is not None or nxt not in self.game.machines:
                self.belt_last = None
                break
            self.belt_last = nxt

    def screen_to_tile(self, sx: int, sy: int) -> tuple[int, int] | None:
        if sx >= self.win_w - PANEL_W:
            return None
        wx = sx / self.zoom + self.cam_x
        wy = sy / self.zoom + self.cam_y
        tx, ty = int(wx // TILE), int(wy // TILE)
        if not self.game.in_bounds(tx, ty):
            return None
        return tx, ty

    def tile_origin(self, x: int, y: int) -> tuple[float, float]:
        return (x * TILE - self.cam_x) * self.zoom, (y * TILE - self.cam_y) * self.zoom

    def draw(self) -> None:
        self.screen.fill(WATER_C)
        self._draw_world()
        self._draw_panel()

    def _draw_world(self) -> None:
        game = self.game
        size = max(1, int(TILE * self.zoom))
        for y in range(GRID_H):
            for x in range(GRID_W):
                ox, oy = self.tile_origin(x, y)
                if ox > self.win_w - PANEL_W or oy > self.win_h or ox + size < 0 or oy + size < 0:
                    continue
                rect = pygame.Rect(int(ox), int(oy), size, size)
                self.screen.fill(self._tile_color(x, y), rect)
        self._draw_castle(size)
        self._draw_pads(size)
        self._mark_input(size)
        carried = self._carried_machine()
        for machine in game.machines.values():
            if machine.kind == BELT and machine is not carried:
                self._draw_machine(machine, size)
        for machine in game.machines.values():
            if machine.kind != BELT and machine is not carried:
                self._draw_machine(machine, size)
        for tree in game.trees.values():
            self._draw_tree(tree, size)
        self._draw_ghost(size)
        self._draw_queen(size)
        if self.intro:
            self._draw_intro()
        if game.won:
            self._banner(WIN_LINE)

    def _tile_color(self, x: int, y: int) -> tuple[int, int, int]:
        terrain = self.game.terrain[y][x]
        if terrain == WATER:
            for dx, dy in DIRS:
                nx, ny = x + dx, y + dy
                if self.game.in_bounds(nx, ny) and self.game.terrain[ny][nx] != WATER:
                    return SHORE_C
            return WATER_C
        if terrain == SAND:
            scar = min(self.game.scar.get((x, y), 0), 16) / 16
            return lerp(SAND_C, SAND_DARK, scar)
        return GRASS_B if (x + y) % 2 else GRASS_C

    def _draw_castle(self, size: int) -> None:
        placed = self.game.placed_castle
        for x, y in self.game.castle_tiles:
            ox, oy = self.tile_origin(x, y)
            rect = pygame.Rect(int(ox) + 2, int(oy) + 2, max(1, size - 4), max(1, size - 4))
            if FOUNDATION in placed:
                shade = (168, 132, 64) if WALLS in placed and self._on_castle_edge(x, y) else (146, 114, 58)
                self.screen.fill(shade, rect)
            else:
                pygame.draw.rect(self.screen, (120, 100, 62), rect, 1)
        if DOME in placed:
            self._draw_dome(size)
        if THRONE in placed:
            self._blob(SOCKETS[THRONE], size, (232, 196, 92), 0.28)
        if STAIRS in placed:
            sx, sy = SOCKETS[STAIRS]
            ox, oy = self.tile_origin(sx, sy)
            self.screen.fill((186, 150, 78), pygame.Rect(int(ox) + 4, int(oy) + 4, max(1, size - 8), max(1, size - 8)))
        for name, (x, y) in SOCKETS.items():
            if name in placed:
                continue
            ox, oy = self.tile_origin(x, y)
            pygame.draw.circle(
                self.screen,
                SELECT,
                (int(ox + size / 2), int(oy + size / 2)),
                max(2, int(size * 0.12)),
                1,
            )

    def _on_castle_edge(self, x: int, y: int) -> bool:
        return (x, y) in self.game.castle_tiles and (
            (x - 1, y) not in self.game.castle_tiles or (x + 1, y) not in self.game.castle_tiles
            or (x, y - 1) not in self.game.castle_tiles or (x, y + 1) not in self.game.castle_tiles
        )

    def _draw_dome(self, size: int) -> None:
        x, y = SOCKETS[DOME]
        ox, oy = self.tile_origin(x, y)
        pygame.draw.circle(
            self.screen,
            (212, 170, 78),
            (int(ox + size / 2), int(oy + size / 2)),
            max(4, int(size * 0.55)),
        )

    def _draw_pads(self, size: int) -> None:
        colors = {"stockpile": (122, 88, 64), "workshop": (64, 78, 102), "toolpile": (96, 76, 62)}
        for (x, y), name in self.game.pads.items():
            ox, oy = self.tile_origin(x, y)
            self.screen.fill(colors[name], pygame.Rect(int(ox), int(oy), size, size))
        if self.zoom >= 0.55:
            for name, (x, y, w, h) in (
                ("Stockpile", (6, 24, 3, 2)),
                ("Workshop", (16, 24, 4, 2)),
                ("Tool pile", (26, 24, 3, 2)),
            ):
                ox, oy = self.tile_origin(x, y)
                label = self.small.render(name, True, INK)
                self.screen.blit(label, (ox + 4, oy + 4))

    def _mark_input(self, size: int) -> None:
        x, y = STOCK_INPUT
        ox, oy = self.tile_origin(x, y)
        rect = pygame.Rect(int(ox) + 3, int(oy) + 3, max(1, size - 6), max(1, size - 6))
        pygame.draw.rect(self.screen, SELECT, rect, 2)

    def _draw_tree(self, tree, size: int) -> None:
        ox, oy = self.tile_origin(tree.x, tree.y)
        cx, cy = int(ox + size / 2), int(oy + size / 2)
        if tree.state == STUMP:
            grow = tree.timer / 100
            pygame.draw.ellipse(self.screen, (112, 80, 50), pygame.Rect(cx - size // 5, cy, size // 2, size // 5))
            if grow > 0.15:
                pygame.draw.circle(self.screen, (70, 130, 64), (cx, cy - int(size * 0.1)), max(2, int(size * 0.12 * grow)))
            return
        if tree.state == LOG:
            pygame.draw.ellipse(self.screen, (112, 80, 50), pygame.Rect(cx - size // 5, cy, size // 2, size // 5))
            pygame.draw.rect(self.screen, (164, 112, 62), pygame.Rect(cx - size // 3, cy - size // 8, int(size * 0.7), max(3, size // 6)))
            return
        radius = int(size * 0.34)
        if tree.state == CHOPPING:
            radius = max(3, int(radius * (1 - tree.timer / 1.5)))
        pygame.draw.rect(self.screen, (96, 68, 42), pygame.Rect(cx - 2, cy, 4, size // 4))
        pygame.draw.circle(self.screen, (24, 92, 48), (cx, cy - size // 8), radius)

    def _carried_machine(self):
        if self.press_kind == "machine" and self.dragged and self.move_from is not None:
            return self.game.machines.get(self.move_from)
        return None

    def _draw_machine(self, machine, size: int, at: tuple[int, int] | None = None) -> None:
        ox, oy = self.tile_origin(*(at or (machine.x, machine.y)))
        rect = pygame.Rect(int(ox) + 1, int(oy) + 1, max(1, size - 2), max(1, size - 2))
        color = MACHINE_COLOR.get(machine.kind, (80, 80, 80))
        if machine.kind == GENERATOR and machine.lit:
            color = (214, 108, 48)
        if machine.paused or (self.game.brownout and self.game.watts_of(machine) > 0):
            color = lerp(color, (20, 20, 24), 0.45)
        self.screen.fill(color, rect)
        if machine.kind == BELT:
            self._arrow(machine.facing, ox, oy, size, DIM)
            if machine.belt_item:
                ix, iy = self._item_point(machine, ox, oy, size)
                pygame.draw.circle(self.screen, ITEM_COLOR.get(machine.belt_item, INK), (int(ix), int(iy)), max(2, size // 7))
            return
        if machine.kind == ARM:
            self._arrow(machine.facing, ox, oy, size, SELECT)
        if machine.kind in EXTRACTORS:
            self._port(opposite(machine.facing), ox, oy, size, (70, 60, 52))
            self._port(machine.facing, ox, oy, size, SAND_C)
            metal = METAL_OF[machine.kind]
            self._port(right_hand(machine.facing), ox, oy, size, ITEM_COLOR[metal])
            self._center_text(METAL_LETTER[machine.kind], ox, oy, size)
        if machine.kind == DUMP:
            frac = machine.waste / self.game.dump_cap(machine)
            inner = pygame.Rect(int(ox) + 4, int(oy) + 4, max(1, size - 8), max(1, int((size - 8) * frac)))
            self.screen.fill(SAND_DARK, inner)
        if machine.kind == BATTERY and self.game.battery_cap:
            frac = self.game.battery_ws / self.game.battery_cap
            inner_h = max(1, int((size - 8) * frac))
            self.screen.fill(GOOD, pygame.Rect(int(ox) + 4, int(oy) + size - 4 - inner_h, max(1, size - 8), inner_h))
        if machine.paused:
            pygame.draw.line(self.screen, INK, (ox + 4, oy + 4), (ox + size - 4, oy + size - 4), 1)

    def _port(self, facing: int, ox: float, oy: float, size: int, color: tuple[int, int, int]) -> None:
        thickness = max(3, size // 7)
        if facing == 0:
            rect = pygame.Rect(int(ox + size * 0.28), int(oy) + 1, int(size * 0.44), thickness)
        elif facing == 1:
            rect = pygame.Rect(int(ox + size - thickness - 1), int(oy + size * 0.28), thickness, int(size * 0.44))
        elif facing == 2:
            rect = pygame.Rect(int(ox + size * 0.28), int(oy + size - thickness - 1), int(size * 0.44), thickness)
        else:
            rect = pygame.Rect(int(ox) + 1, int(oy + size * 0.28), thickness, int(size * 0.44))
        self.screen.fill(color, rect)

    def _arrow(self, facing: int, ox: float, oy: float, size: int, color: tuple[int, int, int]) -> None:
        cx, cy = ox + size / 2, oy + size / 2
        dx, dy = DIRS[facing]
        tip = (cx + dx * size * 0.28, cy + dy * size * 0.28)
        left = (cx - dy * size * 0.16 - dx * size * 0.08, cy + dx * size * 0.16 - dy * size * 0.08)
        right = (cx + dy * size * 0.16 - dx * size * 0.08, cy - dx * size * 0.16 - dy * size * 0.08)
        pygame.draw.polygon(self.screen, color, [tip, left, right])

    def _item_point(self, machine, ox: float, oy: float, size: int) -> tuple[float, float]:
        dx, dy = DIRS[machine.facing]
        span = 0.32 * machine.belt_progress - 0.16
        return ox + size / 2 + dx * size * span, oy + size / 2 + dy * size * span

    def _center_text(self, text: str, ox: float, oy: float, size: int) -> None:
        label = self.small.render(text, True, INK)
        self.screen.blit(label, (ox + size / 2 - label.get_width() / 2, oy + size / 2 - label.get_height() / 2))

    def _blob(self, tile: tuple[int, int], size: int, color: tuple[int, int, int], scale: float) -> None:
        ox, oy = self.tile_origin(*tile)
        pygame.draw.circle(self.screen, color, (int(ox + size / 2), int(oy + size / 2)), max(3, int(size * scale)))

    def _draw_ghost(self, size: int) -> None:
        mouse = pygame.mouse.get_pos()
        if self.log_from is not None:
            pygame.draw.rect(self.screen, ITEM_COLOR[WOOD], pygame.Rect(mouse[0] - 10, mouse[1] - 6, 22, 10))
            return
        carried = self._carried_machine()
        tile = self.screen_to_tile(*mouse)
        if carried is not None and tile is not None:
            self._draw_machine(carried, size, at=tile)
            return
        if self.armed is None or tile is None:
            return
        ok = self.game.can_place(self.armed, tile[0], tile[1], self.facing)
        self._outline(tile, size, GOOD if ok else BAD)

    def _outline(self, tile: tuple[int, int], size: int, color: tuple[int, int, int]) -> None:
        ox, oy = self.tile_origin(*tile)
        pygame.draw.rect(self.screen, color, pygame.Rect(int(ox) + 1, int(oy) + 1, max(1, size - 2), max(1, size - 2)), 2)

    def _draw_queen(self, size: int) -> None:
        if self.game.queen_t <= 0:
            return
        t = min(1.0, self.game.queen_t)
        sx, sy = 22 + 0.5, 2 + 0.5
        ex, ey = SOCKETS[THRONE][0] + 0.5, SOCKETS[THRONE][1] + 0.5
        wx = (sx + (ex - sx) * t) * TILE
        wy = (sy + (ey - sy) * t) * TILE
        px = (wx - self.cam_x) * self.zoom
        py = (wy - self.cam_y) * self.zoom
        pygame.draw.circle(self.screen, (236, 214, 170), (int(px), int(py)), max(4, size // 5))
        pygame.draw.polygon(
            self.screen,
            SELECT,
            [(px - 6, py - size * 0.18), (px + 6, py - size * 0.18), (px, py - size * 0.38)],
        )

    def _draw_intro(self) -> None:
        view_w = self.win_w - PANEL_W
        box = pygame.Rect(view_w // 2 - 280, self.win_h // 2 - 70, 560, 140)
        surface = pygame.Surface(box.size, pygame.SRCALPHA)
        surface.fill((16, 22, 28, 210))
        self.screen.blit(surface, box.topleft)
        lines = wrap(INTRO, self.font, box.width - 40)
        y = box.y + 28
        for line in lines:
            label = self.font.render(line, True, INK)
            self.screen.blit(label, (box.centerx - label.get_width() / 2, y))
            y += 24
        hint = self.small.render("Click to begin", True, SELECT)
        self.screen.blit(hint, (box.centerx - hint.get_width() / 2, box.bottom - 32))

    def _banner(self, text: str) -> None:
        label = self.large.render(text, True, (28, 24, 16))
        rect = label.get_rect(center=((self.win_w - PANEL_W) // 2, 36))
        pad = rect.inflate(28, 16)
        self.screen.fill(SELECT, pad)
        self.screen.blit(label, rect)

    def _draw_panel(self) -> None:
        panel_x = self.win_w - PANEL_W
        self.screen.fill(PANEL, pygame.Rect(panel_x, 0, PANEL_W, self.win_h))
        self._text(self.large, "Island Factory", panel_x + 16, 14, INK)
        subtitle = "Test mode. Wood does not run out." if self.game.stock.unlimited_wood else "One island. No coins."
        self._text(self.small, subtitle, panel_x + 16, 46, DIM)
        self._draw_power(panel_x)
        self._draw_resources(panel_x)
        self._text(self.small, "Tool pile", panel_x + 16, 196, DIM)
        for index, rect in enumerate(self.slots):
            fill = SELECT if index == self.armed else PANEL_2
            pygame.draw.rect(self.screen, fill, rect)
            if index < len(self.game.tools):
                label = self.game.tool_label(self.game.tools[index])
                self._text(self.small, label, rect.x + 6, rect.y + 8, INK if index != self.armed else (28, 24, 16))
        kind = self._armed_kind()
        if kind is not None and self.armed is not None:
            self._text(self.font, self.game.tool_label(self.game.tools[self.armed]), panel_x + 16, 294, SELECT)
            blurb = wrap(self.game.blurb(kind), self.small, PANEL_W - 36)
            for index, line in enumerate(blurb[:2]):
                self._text(self.small, line, panel_x + 16, 316 + index * 16, DIM)
            pygame.draw.rect(self.screen, PANEL_2, self.rot_l)
            pygame.draw.rect(self.screen, PANEL_2, self.rot_r)
            self._text(self.font, "‹", self.rot_l.x + 14, self.rot_l.y + 2, INK)
            self._text(self.font, "›", self.rot_r.x + 14, self.rot_r.y + 2, INK)
            self._text(self.small, f"Facing {DIR_NAMES[self.facing]}", self.rot_r.right + 10, self.rot_r.y + 6, DIM)
        self._draw_jobs(panel_x)
        previous = self.screen.get_clip()
        self.screen.set_clip(self.recipe_clip)
        for rect, recipe_id in self.recipes:
            self._draw_recipe(rect, RECIPES[recipe_id])
        self.screen.set_clip(previous)
        hint_y = self.win_h - 162
        for index, line in enumerate(wrap(self.game.hint(), self.small, PANEL_W - 32)[:4]):
            self._text(self.small, line, panel_x + 16, hint_y + index * 16, INK)
        if self.toast_t > 0:
            self._text(self.small, self.toast, panel_x + 16, self.win_h - 78, BAD)
        elif self.hover:
            self._text(self.small, self.hover, panel_x + 16, self.win_h - 78, DIM)
        for rect, speed in self.speeds:
            fill = SELECT if speed == self.speed else PANEL_2
            pygame.draw.rect(self.screen, fill, rect)
            label = self.small.render(f"{speed}×", True, (28, 24, 16) if speed == self.speed else INK)
            self.screen.blit(label, (rect.centerx - label.get_width() / 2, rect.y + 5))

    def _draw_power(self, panel_x: int) -> None:
        game = self.game
        color = BAD if game.brownout else GOOD
        label = f"{game.supply:.0f} W in    {game.demand} W out"
        if game.brownout:
            label += "   frozen"
        self._text(self.small, label, panel_x + 16, 68, color)
        track = pygame.Rect(panel_x + 16, 86, PANEL_W - 32, 8)
        self.screen.fill(PANEL_2, track)
        self.screen.fill(color, pygame.Rect(track.x, track.y, int(track.width * min(1, game.supply / 40)), track.height))
        mark = track.x + int(track.width * min(1, game.demand / 40))
        pygame.draw.line(self.screen, INK, (mark, track.y - 2), (mark, track.bottom + 2), 1)
        if game.battery_cap:
            self._text(
                self.small,
                f"Battery {game.battery_ws:.0f} / {game.battery_cap}",
                panel_x + 16,
                98,
                DIM,
            )

    def _draw_resources(self, panel_x: int) -> None:
        for index, resource in enumerate(RESOURCES):
            y = 120 + index * 18
            if resource == WOOD and self.game.stock.unlimited_wood:
                shown = "unlimited"
                color = INK
            else:
                have = self.game.stock.get(resource)
                cap = self.game.stock.cap(resource)
                shown = f"{have} / {cap}" if cap else "—"
                color = INK if cap or resource == WOOD else DIM
            self._text(self.small, f"{NAMES[resource]}   {shown}", panel_x + 28, y, color)
            pygame.draw.rect(self.screen, ITEM_COLOR.get(resource, DIM), pygame.Rect(panel_x + 16, y + 3, 8, 8))

    def _draw_jobs(self, panel_x: int) -> None:
        y = self.job_y
        self._text(self.small, "Workshop", panel_x + 16, y, DIM)
        if not self.game.queue:
            self._text(self.small, "Idle", panel_x + 90, y, DIM)
            return
        recipe = RECIPES[self.game.queue[0]]
        frac = min(1.0, self.game.craft_t / recipe.seconds) if recipe.seconds else 1
        bar = pygame.Rect(panel_x + 16, y + 18, PANEL_W - 40, 8)
        self.screen.fill(PANEL_2, bar)
        self.screen.fill(SELECT, pygame.Rect(bar.x, bar.y, int(bar.width * frac), bar.height))
        waiting = len(self.game.queue) - 1
        extra = f"  +{waiting}" if waiting else ""
        self._text(self.small, recipe.name + extra, panel_x + 16, y + 30, INK)

    def _draw_recipe(self, rect: pygame.Rect, recipe) -> None:
        affordable = self.game.stock.can_pay(recipe.cost)
        self.screen.fill((44, 52, 58) if affordable else (32, 34, 36), rect)
        title_color = INK if affordable else DIM
        self._text(self.small, recipe.name, rect.x + 8, rect.y + 4, title_color)
        detail = f"{cost_text(recipe.cost)}   {recipe.seconds:.0f}s"
        self._text(self.small, detail, rect.x + 8, rect.y + 22, DIM)

    def _text(self, font: pygame.font.Font, text: str, x: float, y: float, color: tuple[int, int, int]) -> None:
        self.screen.blit(font.render(text, True, color), (x, y))


METAL_LETTER = {COPPER_EXT: "Cu", IRON_EXT: "Fe", GOLD_EXT: "Au"}


def load_env_file(path) -> None:
    """Fill in variables the shell did not already set. A real export wins."""
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def main() -> None:
    load_env_file(Path(__file__).resolve().parent.parent / ".env")
    App().run()
