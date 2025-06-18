# Parcel Optimizer (EVE Jump Freighter Planner)

This script reads a CSV file of contracts and groups them into jump freighter trips using a First-Fit Decreasing bin-packing strategy.

## Features

- Handles both Inbound and Outbound contracts
- Volume limits:
  - Inbound: 350,000 m³
  - Outbound: 207,125 m³
- Generates manifest `.txt` files per direction
- Cleans column names and handles CSV volume formatting issues

## How to Use

1. Place your contract CSV inside the `data/` folder
2. Open a terminal in this folder
3. Run:

```bash
pip install -r requirements.txt
python optimize_freighters.py
