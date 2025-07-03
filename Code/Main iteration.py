import pandas as pd
from ortools.sat.python import cp_model

# === User Inputs ===
while True:
    try:
        isotope_cost = float(input("Enter cost per isotope (ISK): "))
        break  # Exit loop if input is valid
    except ValueError:
        print("Invalid input. Please enter a numeric value.")

# === Configuration ===
FREIGHTER_VOLUME_LIMIT = 350_000  # m3
JITA_SYSTEM_ID = 30000142
UALX_SYSTEM_ID = 30004807
AMARR_SYSTEM_ID = 30002187

# === Empty-leg jump costs ===
jita_to_ualx_ly = 52.276
ualx_to_jita_ly = 35.357
isotopes_per_ly = 2200

# === Read CSV ===
df = pd.read_csv("corporate_contracts_filtered.csv")

# === Tag Inbound/Outbound ===
df['direction'] = df['end_system_id'].apply(lambda x: 'outbound' if x == JITA_SYSTEM_ID else ('inbound' if x == UALX_SYSTEM_ID else 'unknown'))

# === Filter out unknown directions ===
df = df[df['direction'] != 'unknown']

# === Sort contracts by volume descending ===
df = df.sort_values(by="volume", ascending=False).reset_index(drop=True)

# === Split contracts by direction ===
outbound_contracts = df[df['direction'] == 'outbound']
inbound_contracts = df[df['direction'] == 'inbound']
out_contracts_list = outbound_contracts.to_dict('records')
in_contracts_list = inbound_contracts.to_dict('records')



def minimize_freighters (contracts, FREIGHTER_VOLUME_LIMIT):
        for c in contracts:
            c['volume'] = int(-(-c['volume'] // 1))  # Round up to nearest integer for volume
        model = cp_model.CpModel()
        num_contracts = len(contracts)
        max_bins = num_contracts # Worst case; 1 contract per freighter

        x = {}
        for c in range(num_contracts):
            for b in range(max_bins):
                x[(c,b)] = model.NewBoolVar(f'contract_{c}_in_bin_{b}')
        used = [model.NewBoolVar(f'used_bin_{b}') for b in range(max_bins)]

        for c in range(num_contracts):
            model.add(sum(x[(c,b)] for b in range(max_bins)) == 1)  # Each contract must be assigned to exactly one bin

        for b in range(max_bins):
            model.add(
                sum(x[(c, b)] * contracts[c]['volume'] for c in range(num_contracts)) <= FREIGHTER_VOLUME_LIMIT
            )
            for c in range(num_contracts):
                model.add(x[(c,b)] <= used[b]) # If a contract is in a bin, it is used.
        
        # Minimize the number of Freighters used
        model.minimize(sum(used))

        # Solve
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            freighter_allocations = []
            for b in range(max_bins):
                if solver.Value(used[b]):
                    manifest = []
                    for c in range(num_contracts):
                        if solver.Value(x[(c,b)]):
                            manifest.append(contracts[c])
                    freighter_allocations.append(manifest)
            return freighter_allocations, 0
        else:
            print("No feasible solution found.")
            return [], 0
        
        # === Allocate Freighters for Each Direction ===
out_freighters, out_fuel = minimize_freighters(out_contracts_list, FREIGHTER_VOLUME_LIMIT)
in_freighters, in_fuel = minimize_freighters(in_contracts_list, FREIGHTER_VOLUME_LIMIT)

def calculate_fuel_cost(c):
    route = (c['start_location_name'], c['end_location_name'])
    if route == ("Jita IV - Moon 4 - Caldari Navy Assembly Plant", "UALX-3 - 1st Goonstantinople"):
        return round(52.276 * 2200 * isotope_cost)
    elif route == ("UALX-3 - 1st Goonstantinople", "Jita IV - Moon 4 - Caldari Navy Assembly Plant"):
        return round(35.357 * 2200 * isotope_cost)
    return round(c['lightyears'] * 2200 * isotope_cost)

for manifest in out_freighters + in_freighters:
        for c in manifest:
            c['fuel_cost'] = calculate_fuel_cost(c)

# === Calculate Empty Leg Fuel Costs ===
unused_out = max(0, len(in_freighters) - len(out_freighters))
unused_in = max(0, len(out_freighters) - len(in_freighters))
full_econs = (1 - 0.244)
empty_leg_fuel = (
    unused_out * round((ualx_to_jita_ly * isotopes_per_ly * isotope_cost) * full_econs) +
    unused_in * round((jita_to_ualx_ly * isotopes_per_ly * isotope_cost) * full_econs)
)



# === Write Manifest ===
grand_total_fuel = empty_leg_fuel
grand_total_profit = 0
with open("freight_manifest.txt", "w") as f:
    f.write("=== OUTBOUND ===\n")
    for i, manifest in enumerate(out_freighters, 1):
        total_vol = sum(c['volume'] for c in manifest)
        total_reward = sum(c['reward'] for c in manifest)
        fuel_cost = max(c['fuel_cost'] for c in manifest)

        # Applies reductions in fuel use because of econs
        if total_vol > 270_000:
            discounted_fuel = fuel_cost
        elif total_vol > 200_000:
            discounted_fuel = fuel_cost * (1 - 0.10)
        elif total_vol > 150_000:
            discounted_fuel = fuel_cost * (1 - 0.1869)
        else:
            discounted_fuel = fuel_cost * (1 - 0.244)

        profit = total_reward - discounted_fuel
        grand_total_fuel += discounted_fuel
        grand_total_profit += profit

        f.write(f"Freighter {i} | Total Volume: {round(total_vol)} m3 | Total Reward: {round(total_reward):,} ISK | Fuel Cost: {round(discounted_fuel):,} ISK | Base fuel: {round(fuel_cost)} | Profit: {round(profit):,} ISK\n")
        for c in manifest:
            f.write(f"Issuer {c['issuer_name']} | Volume: {round(c['volume'])} m3 |     Outbound    |      Origin: {c['start_location_name']} |        Destination: {c['end_location_name']}\n")
        f.write("\n")

    f.write("=== INBOUND ===\n")
    for i, manifest in enumerate(in_freighters, 1):
        total_vol = sum(c['volume'] for c in manifest)
        total_reward = sum(c['reward'] for c in manifest)
        fuel_cost = max(c['fuel_cost'] for c in manifest)

        # Applies reductions in fuel use because of econs
        if total_vol > 270_000:
            discounted_fuel = fuel_cost
        elif total_vol > 200_000:
            discounted_fuel = fuel_cost * (1 - 0.10)
        elif total_vol > 150_000:
            discounted_fuel = fuel_cost * (1 - 0.1869)
        else:
            discounted_fuel = fuel_cost * (1 - 0.244)

        profit = total_reward - discounted_fuel
        grand_total_fuel += discounted_fuel
        grand_total_profit += profit

        f.write(f"Freighter {i} | Total Volume: {round(total_vol)} m3 | Total Reward: {round(total_reward):,} ISK | Fuel Cost: {round(discounted_fuel):,} ISK |Base fuel: {round(fuel_cost)} | Profit: {round(profit):,} ISK\n")
        for c in manifest:
            f.write(f"Issuer {c['issuer_name']} | Volume: {round(c['volume'])} m3 |     Inbound     | Origin:  {c['start_location_name']} | Destination:    {c['end_location_name']}\n")
        f.write("\n")

    f.write("=== Summary ===\n")
    f.write(f"Total Cost of Fuel: {round(grand_total_fuel + empty_leg_fuel):,} ISK\n")
    f.write(f"Total Profit: {round(grand_total_profit - empty_leg_fuel):,} ISK\n")
    f.write(f"Isk per Isotope: {round(isotope_cost):,} ISK\n")
    f.write(f"Freighters Used: {len(out_freighters)} outbound, {len(in_freighters)} inbound\n")
    if unused_out > 0 or unused_in > 0:
        f.write(f"Empty Freighters out: {round(unused_out)} | Empty Freighters in: {round(unused_in)}\n")
