# Island Factory

A top-down observer game. The Queen stays at sea until a gold castle can receive her. There is no shop and no coins. Wood, copper, and iron build the works. Gold builds the castle.

```bash
cd ~/Documents/island-factory
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

The checks under `tests/` do not open a window:

```bash
python -m unittest discover -s tests -v
```

## How you play

You are not on the island. The mouse is your hands.

- Click a tree and wait. Drag the log onto the stockpile, or onto the wood line in the panel.
- Order a job from the list. It lands on the tool pile. Click it, turn it with the arrows, then click the grass.
- Belts are drawn by dragging. They face the way you drag.
- Click a generator to light it. Click any other machine to pause it. Hold a dump to heave sand into the sea.
- Drag a machine onto the tool pile to pick it up.
- Right-drag pans. The wheel zooms. Escape puts down whatever you are holding. The 1× 2× 4× buttons speed the island up.

An arm has to face a sand tile. Sand comes out of its back. On an extractor, sand enters the back, leaves the front, and the metal leaves on the right-hand side. That metal has to reach the bright tile on the south edge of the stockpile.

One fire feeds the first machines. Two fires are the most the grove can keep feeding. A third fire eats the trees faster than they grow back.

## The v1 line

Grass under the east sand, arm facing up into it. Sand runs south through the copper extractor into a dump. Copper leaves to the west and rides the open grass above the pads, then down into the bright stockpile tile. Iron goes on that same sand belt, between copper and the dump. Gold goes between iron and the dump, and only the castle spends it.

The balance numbers live in `island_factory/constants.py`.
