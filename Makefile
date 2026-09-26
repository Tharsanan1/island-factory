.PHONY: run test

run:
	.venv/bin/python main.py

test:
	.venv/bin/python -m unittest discover -s tests -v
