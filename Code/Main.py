

from ortools.sat.python import cp_model
import pandas as pd
import os, glob

# === Load latest CSV ===
list_of_files = glob.glob("*.csv")
latest_file = max(list_of_files, key=os.path.getmtime)
print(f"Using latest file: {latest_file}")
df = pd.read_csv(latest_file)

# === Add Direction and Volume Limit ===
def get_direction(row):
    if 'jita' in row['From'].lower():
        return 'Inbound'
    elif 'jita' in row['To'].lower():
        return 'Outbound'
    return 'Other'

df['Direction'] = df.apply(get_direction, axis=1)
df['Limit'] = df['Direction'].apply(lambda x: 350000 if x == 'Inbound' else 207147.5 if x == 'Outbound' else 0)
df = df[df['Direction'].isin(['Inbound', 'Outbound'])]

# === Optimize Bin Packing for a Given Direction ===
def optimize_direction(direction_label, volume_limit):
    df_dir = df[df['Direction'] == direction_label].reset_index(drop=True)
    volumes = df_dir['Volume'].tolist()
    n = len(volumes)
    if n == 0:
        return f"No {direction_label} contracts found."

    max_bins = n
    model = cp_model.CpModel()
    x = {}
    y = {}

    for i in range(n):
        for j in range(max_bins):
            x[(i, j)] = model.NewBoolVar(f"x_{i}_{j}")

    for j in range(max_bins):
        y[j] = model.NewBoolVar(f"y_{j}")

    for i in range(n):
        model.Add(sum(x[(i, j)] for j in range(max_bins)) == 1)

    for j in range(max_bins):
        model.Add(
            sum(x[(i, j)] * volumes[i] for i in range(n)) <= volume_limit
        ).OnlyEnforceIf(y[j])
        for i in range(n):
            model.Add(y[j] >= x[(i, j)])

    model.Minimize(sum(y[j] for j in range(max_bins)))
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    result = []
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        freighters = {}
        for j in range(max_bins):
            if solver.Value(y[j]):
                freighters[j] = []

        for i in range(n):
            for j in range(max_bins):
                if solver.Value(x[(i, j)]):
                    freighters[j].append(i)
                    break

        result.append(f"Minimum {direction_label} freighters needed: {len(freighters)}")
        for j, contract_ids in freighters.items():
            used = sum(volumes[i] for i in contract_ids)
            result.append(f"\nFreighter {j + 1} - Used: {used:.2f} m³")
            for i in contract_ids:
                row = df_dir.loc[i]
                result.append(f"  - {row['Issuer']} >> {row['To']} {row['Volume']} m³ | Rush: {row['Rush']}")
    else:
        result.append(f"No feasible solution for {direction_label} contracts.")

    return "\n".join(result)

# === Run Optimizer for Both Directions ===
print("\n=== INBOUND ===\n")
print(optimize_direction('Inbound', 350000))

print("\n=== OUTBOUND ===\n")
print(optimize_direction('Outbound', 207147.5))
