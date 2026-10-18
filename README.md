# Car cost comparison

Compare the monthly cost of different cars (owned, leased, bought): fuel or electricity at today's prices, insurance, tax,
repairs, depreciation, tyres and more. Every cost can be ticked on or off, edited, hidden, or added as a custom cost.
The page also compares size, luggage and equipment (rear camera, parking sensors, adaptive cruise).

## Use it online (read-only)

The published version shows the data in `data/cars.json`. You can change anything you like, but your changes only live in
your own browser tab: they never change the published data. Use "Reset to published data" to start over.

## Run it on your own computer

Needs Python 3 (nothing to install). Double-click `start.bat`, or run `python app.py`, and open http://localhost:8765.
Locally every change is saved to `data/cars.json`.

## The data

All cars and costs are in `data/cars.json`. The format is described in `CLAUDE.md`.
