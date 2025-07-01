import pandas as pd

# === User Inputs ===
freighter_count = int(input("How many freighters are you using (per direction)? "))
isotope_cost = float(input("Enter cost per isotope (ISK): "))

# === Configuration ===
FREIGHTER_VOLUME_LIMIT = 350_000  # m3
JITA_SYSTEM_ID = 30000142
UALX_SYSTEM_ID = 30004807
AMARR_SYSTEM_ID = 30002187

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

def allocate_freighters(contracts, max_freighters):
    freighters = []
    current = []
    current_volume = 0
    freighters_used = 0
    fuel_cost_total = 0

    for _, row in contracts.iterrows():
        vol = row['volume']

        row_dict = row.to_dict()
        current.append(row_dict)
        current_volume += vol

        if current_volume > FREIGHTER_VOLUME_LIMIT:
            current.pop()
            current_volume -= vol

            # Calculate unified fuel cost
            dest_systems = set(c['end_system_id'] for c in current)
            max_ly = max(c['lightyears'] for c in current)
            includes_amarr = AMARR_SYSTEM_ID in dest_systems
            includes_jita = JITA_SYSTEM_ID in dest_systems

            fuel_cost = round(max_ly * 2200 * isotope_cost)
            if includes_amarr:
                fuel_cost += 20_000_000

            for c in current:
                c['fuel_cost'] = fuel_cost

            fuel_cost_total += fuel_cost
            freighters.append(current)
            freighters_used += 1
            if freighters_used == max_freighters:
                return freighters, fuel_cost_total

            current = [row_dict]
            current_volume = vol

    if current and freighters_used < max_freighters:
        dest_systems = set(c['end_system_id'] for c in current)
        max_ly = max(c['lightyears'] for c in current)
        includes_amarr = AMARR_SYSTEM_ID in dest_systems
        includes_jita = JITA_SYSTEM_ID in dest_systems

        fuel_cost = round(max_ly * 2200 * isotope_cost)
        if includes_amarr:
            fuel_cost += 20_000_000

        for c in current:
            c['fuel_cost'] = fuel_cost

        fuel_cost_total += fuel_cost * 1.1  # Add 10% buffer for fuel cost
        freighters.append(current)

    return freighters, fuel_cost_total

# === Allocate Freighters for Each Direction ===
out_freighters, out_fuel = allocate_freighters(outbound_contracts, freighter_count)
in_freighters, in_fuel = allocate_freighters(inbound_contracts, freighter_count)

# === Write Manifest ===
grand_total_fuel = 0
grand_total_profit = 0
with open("freight_manifest.txt", "w") as f:
    f.write("=== OUTBOUND ===\n")
    for i, manifest in enumerate(out_freighters, 1):
        total_vol = sum(c['volume'] for c in manifest)
        total_reward = sum(c['reward'] for c in manifest)
        base_fuel = manifest[0]['fuel_cost'] if manifest else 0

        # Apply volume-based discount
        if total_vol > 270_000:
            discounted_fuel = base_fuel
        elif total_vol > 200_000:
            discounted_fuel = base_fuel * (1 - 0.10)
        elif total_vol > 150_000:
            discounted_fuel = base_fuel * (1 - 0.1869)
        else:
            discounted_fuel = base_fuel * (1 - 0.244)

        profit = total_reward - discounted_fuel
        grand_total_fuel += discounted_fuel
        grand_total_profit += profit

        f.write(f"Freighter {i} | Total Volume: {round(total_vol)} m3 | Total Reward: {round(total_reward):,} ISK | Fuel Cost: {round(discounted_fuel):,} ISK | Profit: {round(profit):,} ISK\n")
        for c in manifest:
            f.write(f"Issuer {c['issuer_name']} | Volume: {c['volume']} m3 |     Outbound    |      Origin: {c['start_location_name']} |        Destination: {c['end_location_name']}\n")
        f.write("\n")


    f.write("=== INBOUND ===\n")
    for i, manifest in enumerate(in_freighters, 1):
        total_vol = sum(c['volume'] for c in manifest)
        total_reward = sum(c['reward'] for c in manifest)
        base_fuel = manifest[0]['fuel_cost'] if manifest else 0

        # Apply volume-based discount
        if total_vol > 270_000:
            discounted_fuel = base_fuel
        elif total_vol > 200_000:
            discounted_fuel = base_fuel * (1 - 0.10)
        elif total_vol > 150_000:
            discounted_fuel = base_fuel * (1 - 0.1869)
        else:
            discounted_fuel = base_fuel * (1 - 0.244)

        profit = total_reward - discounted_fuel
        grand_total_fuel += discounted_fuel
        grand_total_profit += profit

        f.write(f"Freighter {i} | Total Volume: {round(total_vol)} m3 | Total Reward: {round(total_reward):,} ISK | Fuel Cost: {round(discounted_fuel):,} ISK | Profit: {round(profit):,} ISK\n")
        for c in manifest:
            f.write(f"Issuer {c['issuer_name']} | Volume: {c['volume']} m3 |     Inbound     | Origin:  {c['start_location_name']} | Destination:    {c['end_location_name']}\n")
        f.write("\n")

    
    f.write("=== Summary ===\n")
    f.write(f"Total Cost of Fuel: {round(grand_total_fuel):,} ISK\n")
    f.write(f"Total Profit: {round(grand_total_profit):,} ISK\n")
    f.write(f"Isk per Isotope: {round(isotope_cost):,} ISK\n")
    f.write(f"Freighters Used: {len(out_freighters)} outbound, {len(in_freighters)} inbound\n")

print(f"Freighters used: {len(out_freighters)} outbound, {len(in_freighters)} inbound")
print(f"Estimated total fuel cost: {round((out_fuel + in_fuel) * 2):,} ISK")