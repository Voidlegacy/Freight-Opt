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

    def calculate_fuel_cost(c):
        route = (c['start_location_name'], c['end_location_name'])
        if route == ("Jita IV - Moon 4 - Caldari Navy Assembly Plant", "UALX-3 - 1st Goonstantinople"):
            return round(52.276 * 2200 * isotope_cost)
        elif route == ("UALX-3 - 1st Goonstantinople", "Jita IV - Moon 4 - Caldari Navy Assembly Plant"):
            return round(35.357 * 2200 * isotope_cost)
        return round(c['lightyears'] * 2200 * isotope_cost)

    for _, row in contracts.iterrows():
        vol = row['volume']
        row_dict = row.to_dict()
        current.append(row_dict)
        current_volume += vol

        if current_volume > FREIGHTER_VOLUME_LIMIT:
            current.pop()
            current_volume -= vol

            for c in current:
                c['fuel_cost'] = calculate_fuel_cost(c)

            dest_systems = set(c['end_system_id'] for c in current)
            includes_amarr = AMARR_SYSTEM_ID in dest_systems
            fuel_cost = max(c['fuel_cost'] for c in current)
            if includes_amarr:
                fuel_cost += 20_000_000

            fuel_cost_total += fuel_cost
            freighters.append(current)
            freighters_used += 1
            if freighters_used == max_freighters:
                return freighters, fuel_cost_total

            current = [row_dict]
            current_volume = vol

    if current and freighters_used < max_freighters:
        for c in current:
            c['fuel_cost'] = calculate_fuel_cost(c)

        dest_systems = set(c['end_system_id'] for c in current)
        includes_amarr = AMARR_SYSTEM_ID in dest_systems
        fuel_cost = max(c['fuel_cost'] for c in current)
        if includes_amarr:
            fuel_cost += 20_000_000

        fuel_cost_total += fuel_cost * 1.1
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
        fuel_cost = max(c['fuel_cost'] for c in manifest)

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
    f.write(f"Total Cost of Fuel: {round(grand_total_fuel):,} ISK\n")
    f.write(f"Total Profit: {round(grand_total_profit):,} ISK\n")
    f.write(f"Isk per Isotope: {round(isotope_cost):,} ISK\n")
    f.write(f"Freighters Used: {len(out_freighters)} outbound, {len(in_freighters)} inbound\n")