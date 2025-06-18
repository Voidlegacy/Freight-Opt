import pandas as pd
import os, glob
from datetime import datetime

# === Load latest CSV file ===
print("Looking for CSVs in:", os.getcwd())
csv_dir = "data"
list_of_files = glob.glob(os.path.join(csv_dir, "*.csv"))
if not list_of_files:
    raise FileNotFoundError("No CSV files found in the ./data folder.")
latest_file = max(list_of_files, key=os.path.getmtime)
print(f"Using latest file: {latest_file}")
df = pd.read_csv(latest_file)

# === Clean column headers ===
df.columns = [col.strip().lower() for col in df.columns]
print("CSV Columns Detected:", df.columns.tolist())

# === Convert volume to numeric ===
df['volume'] = pd.to_numeric(df['volume'].astype(str).str.replace(',', ''), errors='coerce').round().astype('Int64')
if df['volume'].isnull().any():
    raise ValueError("Some rows have invalid or missing volume values.")

# === Convert reward to numeric ===
df['reward'] = pd.to_numeric(df['reward'].astype(str).str.replace(',', ''), errors='coerce').round().astype('Int64')
if df['reward'].isnull().any():
    raise ValueError("Some rows have invalid or missing reward values.")

# === Determine direction ===
def get_direction(row):
    if 'jita' in row['from'].lower():
        return 'Inbound'
    elif 'jita' in row['to'].lower():
        return 'Outbound'
    elif 'amarr' in row['from'].lower():
        return 'Inbound' 
    elif 'amarr' in row['to'].lower():
        return 'Outbound'
    return 'Inbound'


df['direction'] = df.apply(get_direction, axis=1)
df = df[df['direction'].isin(['Inbound', 'Outbound'])]

# === Volume limits with margin ===
LIMITS = {
    'Inbound': 350000,
    'Outbound': 207125
}

# === FFD bin-packing algorithm ===
def pack_freighters(df_dir, direction):
    limit = LIMITS[direction]
    parcels = df_dir.sort_values(by='volume', ascending=False).to_dict('records')
    freighters = []

    for parcel in parcels:
        placed = False
        for freighter in freighters:
            if freighter['used'] + parcel['volume'] <= limit:
                freighter['parcels'].append(parcel)
                freighter['used'] += parcel['volume']
                freighter['reward'] += parcel['reward']
                placed = True
                break
        if not placed:
            freighters.append({
                'used': parcel['volume'],
                'reward': parcel['reward'],
                'parcels': [parcel]
            })

    return freighters

# === Format manifest output ===
def create_manifest_text(freighters, direction):
    lines = [f"Minimum {direction} freighters needed: {len(freighters)}"]
    for i, f in enumerate(freighters, 1):
        lines.append(f"\nFreighter {i} - Used: {f['used']} m³ | Reward: {f['reward']}isk")
        for p in f['parcels']:
            lines.append(f"  - {p['issuer']} >> {p['to']} {p['volume']} m³ | Rush: {p['rush']}")
    return '\n'.join(lines)

# === Run for each direction ===
output = {}
os.makedirs("outputs", exist_ok=True)
timestamp = datetime.now().strftime("%d_%H%M")

for direction in ['Inbound', 'Outbound']:
    df_dir = df[df['direction'] == direction]
    if df_dir.empty:
        print(f"No {direction} contracts — skipping.")
        continue

    freighters = pack_freighters(df_dir, direction)
    manifest = create_manifest_text(freighters, direction)
    output[direction] = manifest

    print(f"\n=== {direction.upper()} ===\n")
    print(manifest)

    filename = f"{direction.lower()}_manifest_{timestamp}.txt"
    with open(os.path.join("outputs", filename), "w", encoding="utf-8") as f:
        f.write(f"=== {direction.upper()} ===\n\n")
        f.write(manifest)

input("\nDone! Press Enter to close...")
