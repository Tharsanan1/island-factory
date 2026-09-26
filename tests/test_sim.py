"""Headless checks for the island rules. No window required."""

from __future__ import annotations

import os
import unittest

from island_factory.constants import (
    ARM,
    BELT,
    COPPER_EXT,
    DUMP,
    GENERATOR,
    LOG,
    SAND,
    SOCKETS,
    STUMP,
    THRONE,
    GROWN,
)
from island_factory.game import Game, Tool
from island_factory.recipes import RECIPES


def craft(game: Game, recipe_id: str) -> None:
    error = game.enqueue(recipe_id)
    assert error is None, error
    game.tick(RECIPES[recipe_id].seconds + 0.01)


def place_belt_path(game: Game, steps: list[tuple[int, int, int]]) -> None:
    """steps are (x, y, facing). The tool pile's first item must be a belt spool."""
    for x, y, facing in steps:
        error = game.place(0, x, y, facing)
        assert error is None, (x, y, facing, error)
        if not game.tools or game.tools[0].kind != BELT:
            if any(tool.kind == BELT for tool in game.tools):
                index = next(i for i, tool in enumerate(game.tools) if tool.kind == BELT)
                game.tools.insert(0, game.tools.pop(index))
            else:
                game.stock.wood += 2
                craft(game, "belt")
                belt = game.tools.pop()
                game.tools.insert(0, belt)


class IslandTest(unittest.TestCase):
    def test_chop_regrow_and_wood_cap(self) -> None:
        game = Game()
        tree = next(iter(game.trees.values()))
        self.assertIsNone(game.start_chop(tree.x, tree.y))
        game.tick(1.5)
        self.assertEqual(game.trees[(tree.x, tree.y)].state, LOG)
        self.assertIsNone(game.give_log(tree.x, tree.y))
        self.assertEqual(game.stock.wood, 1)
        self.assertEqual(game.trees[(tree.x, tree.y)].state, STUMP)
        game.tick(100)
        self.assertEqual(game.trees[(tree.x, tree.y)].state, GROWN)

        game.stock.wood = 20
        other = list(game.trees.values())[1]
        other.state = LOG
        self.assertEqual(game.give_log(other.x, other.y), "The stockpile cannot hold more wood.")
        self.assertEqual(other.state, LOG)

    def test_generator_burns_and_two_fires_cost_two_logs(self) -> None:
        game = Game()
        game.stock.wood = 20
        craft(game, "generator")
        craft(game, "generator")
        self.assertIsNone(game.place(0, 20, 20, 1))
        self.assertIsNone(game.place(0, 22, 20, 1))
        for machine in game.machines.values():
            machine.lit = True
        stocked = game.stock.wood
        for _ in range(100):
            game.tick(0.1)
        self.assertEqual(game.stock.wood, stocked - 2)
        self.assertAlmostEqual(game.supply, 20, places=5)

    def test_battery_covers_a_short_gap_then_browns_out(self) -> None:
        game = Game()
        game.stock.wood = 20
        craft(game, "battery")
        craft(game, "arm")
        self.assertIsNone(game.place(0, 21, 20, 1))  # battery, no watts
        # The arm is still in the pile. Face it north into sand at (35, 19).
        self.assertIsNone(game.place(0, 35, 20, 0))
        game.tick(0.1)
        self.assertTrue(game.brownout)
        self.assertEqual(game.demand, 2)

        game.battery_ws = 200
        game.tick(0.1)
        self.assertFalse(game.brownout)
        self.assertLess(game.battery_ws, 200)

    def test_arm_must_face_sand_and_copper_line_delivers(self) -> None:
        game = Game()
        game.stock.tier = 3
        game.stock.wood = 80
        craft(game, "generator")
        craft(game, "arm")
        self.assertEqual(game.place(1, 20, 20, 1), "The arm has to face a sand tile.")
        self.assertIsNone(game.place(0, 20, 20, 1))  # generator
        self.assertIsNone(game.place(0, 35, 20, 0))  # arm facing north into sand
        craft(game, "copper_ext")
        craft(game, "dump")
        self.assertIsNone(game.place(0, 35, 23, 2))  # extractor facing south
        self.assertIsNone(game.place(0, 35, 26, 2))  # dump
        craft(game, "belt")
        sand_belts = [(35, 21, 2), (35, 22, 2), (35, 24, 2), (35, 25, 2)]
        metal = [(x, 23, 3) for x in range(34, 9, -1)]
        metal += [(9, 23, 2), (9, 24, 2), (9, 25, 2), (9, 26, 3), (8, 26, 3)]
        metal[0] = (34, 23, 3)
        place_belt_path(game, sand_belts + metal)
        for machine in game.machines.values():
            if machine.kind == GENERATOR:
                machine.lit = True
        for _ in range(400):
            game.tick(0.1)
        self.assertGreater(game.lifetime_copper, 0)
        self.assertGreater(game.stock.copper, 0)
        dump = game.machines[(35, 26)]
        self.assertGreater(dump.waste, 0)
        self.assertFalse(game.brownout)

    def test_dump_back_pressure_stops_the_arm(self) -> None:
        game = Game()
        game.stock.tier = 1
        game.stock.wood = 40
        craft(game, "generator")
        craft(game, "arm")
        craft(game, "dump")
        craft(game, "belt")
        self.assertIsNone(game.place(0, 20, 20, 1))
        self.assertIsNone(game.place(0, 35, 20, 0))
        self.assertIsNone(game.place(0, 35, 22, 2))
        self.assertIsNone(game.place(0, 35, 21, 2))
        game.machines[(20, 20)].lit = True
        game.machines[(35, 22)].waste = 20
        for _ in range(50):
            game.tick(0.1)
        # One lump lands on the belt. The full dump refuses it, so the arm waits.
        self.assertEqual(game.scar.get((35, 19), 0), 1)

    def test_dump_can_be_moved_while_it_holds_sand(self) -> None:
        game = Game()
        game.stock.wood = 20
        craft(game, "dump")
        self.assertIsNone(game.place(0, 20, 20, 2))
        game.machines[(20, 20)].waste = 7
        self.assertIsNone(game.move_machine(20, 20, 21, 20, 2))
        self.assertEqual(game.machines[(21, 20)].waste, 7)
        self.assertIsNone(game.pickup(21, 20))
        self.assertEqual(game.tools[0].waste, 7)
        self.assertIsNone(game.place(0, 22, 20, 2))
        self.assertEqual(game.machines[(22, 20)].waste, 7)

    def test_unlimited_wood_powers_a_fire_with_an_empty_pile(self) -> None:
        os.environ["ISLAND_UNLIMITED_WOOD"] = "1"
        try:
            game = Game()
            self.assertTrue(game.stock.unlimited_wood)
            self.assertIsNone(game.enqueue("generator"))
            self.assertEqual(game.stock.wood, 0)
            game.tick(RECIPES["generator"].seconds + 0.01)
            self.assertIsNone(game.place(0, 20, 20, 1))
            game.machines[(20, 20)].lit = True
            game.tick(5)
            self.assertEqual(game.stock.wood, 0)
            self.assertAlmostEqual(game.supply, 10, places=5)
            self.assertFalse(game.brownout)
        finally:
            os.environ.pop("ISLAND_UNLIMITED_WOOD", None)

    def test_iron_every_second_sand_and_gold_every_fourth(self) -> None:
        self._assert_metals("iron_ext", [None, "iron"] * 3)
        self._assert_metals("gold_ext", [None, None, None, "gold", None, None, None, "gold"])

    def _assert_metals(self, kind: str, expected: list[str | None]) -> None:
        game = Game()
        game.stock.wood = 40
        craft(game, "generator")
        self.assertIsNone(game.place(0, 3, 5, 1))
        game.machines[(3, 5)].lit = True
        machine = game._add_machine(kind, 6, 5, 1, 1)
        seen: list[str | None] = []
        for _ in expected:
            machine.sand_in = SAND
            machine.sand_out = None
            machine.metal_out = None
            game.tick(1)
            seen.append(machine.metal_out)
        self.assertEqual(seen, expected)

    def test_paused_extractor_passes_sand_and_makes_no_metal(self) -> None:
        game = Game()
        game.stock.wood = 40
        craft(game, "generator")
        craft(game, "copper_ext")
        craft(game, "belt")
        self.assertIsNone(game.place(0, 4, 20, 1))
        self.assertIsNone(game.place(0, 6, 20, 1))  # faces east, input from the west
        self.assertIsNone(game.place(0, 5, 20, 1))
        self.assertIsNone(game.place(0, 7, 20, 1))
        game.machines[(6, 20)].paused = True
        game.machines[(5, 20)].belt_item = SAND
        game.machines[(5, 20)].belt_progress = 1
        game.machines[(4, 20)].lit = True
        game.tick(0.1)
        self.assertIsNone(game.machines[(6, 20)].metal_out)
        self.assertEqual(game.lifetime_copper, 0)
        game.tick(0.6)
        self.assertEqual(game.machines[(7, 20)].belt_item, SAND)

    def test_recipe_gates_and_castle_order(self) -> None:
        game = Game()
        self.assertNotIn("iron_ext", [recipe.id for recipe in game.visible_recipes()])
        game.lifetime_copper = 10
        self.assertIn("iron_ext", [recipe.id for recipe in game.visible_recipes()])
        game.lifetime_iron = 10
        game.stock.tier = 3
        game.stock.gold = 80
        self.assertEqual(game.visible_recipes()[-1].id, "foundation")
        craft(game, "foundation")
        self.assertIsNone(game.place(0, *SOCKETS["foundation"], 0))
        game.tools.append(Tool(kind=THRONE))
        self.assertEqual(
            game.place(0, *SOCKETS[THRONE], 0),
            "The castle is built in order.",
        )
        game.tools.clear()
        for piece in ("walls", "stairs", "dome", "throne"):
            game.stock.gold = 80
            craft(game, piece)
            self.assertIsNone(game.place(0, *SOCKETS[piece], 0))
        self.assertGreater(game.queen_t, 0)
        game.tick(8)
        self.assertTrue(game.won)

    def test_brownout_freezes_belts(self) -> None:
        game = Game()
        game.stock.wood = 20
        craft(game, "arm")
        self.assertIsNone(game.place(0, 35, 20, 0))
        belt = game._add_machine(BELT, 10, 10, 1, 1)
        belt.belt_item = SAND
        game.tick(1)
        self.assertTrue(game.brownout)
        self.assertEqual(belt.belt_progress, 0)


if __name__ == "__main__":
    unittest.main()
