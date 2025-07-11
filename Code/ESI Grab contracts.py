import os
import requests
import pandas as pd
from urllib.parse import urlencode
from flask import Flask, request, redirect, session
from dotenv import load_dotenv
from math import sqrt
import subprocess
import webbrowser 
import threading
import time

load_dotenv("/workspaces/Freight-Opt/keys.env")

print("CLIENT_ID:", os.environ.get("ESI_CLIENT_ID"))

for file in ["corporate_contracts_filtered.csv", "freight_manifest.txt"]:
    if os.path.exists(file):
        os.remove(file)
        print(f"Removed existing file: {file}")
    else:
        print(f"File not found, skipping removal: {file}")

# === Nothing so permanent like a temporary solution ===
# This is a temporary mapping for known structures to their system IDs.
# Ideally this should be replaced with a more dynamic solution.
# This is just to avoid hitting the ESI too many times for known structures.
structure_system_map = {
    1046664001931: 30004807, # UALX-3
    60008494: 30002187, # Amarr
}
from werkzeug.middleware.proxy_fix import ProxyFix
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.secret_key = "G29F9hhdkOIJ3z4jg834jdkfjlj32KD=="
app.config.update(
    SESSION_COOKIE_NAME="esi_session",
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=True
)

# === Configuration ===
CLIENT_ID = os.environ.get("ESI_CLIENT_ID")
SECRET_KEY = os.environ.get("ESI_SECRET_KEY")
REDIRECT_URI = 'https://organic-carnival-7v9jw4vq4rx7crwrr-5000.app.github.dev/callback'
SCOPES = 'esi-contracts.read_corporation_contracts.v1 esi-universe.read_structures.v1'
AUTH_URL = 'https://login.eveonline.com/v2/oauth/authorize'
TOKEN_URL = 'https://login.eveonline.com/v2/oauth/token'
VERIFY_URL = 'https://esi.evetech.net/verify/'
ESI_BASE = 'https://esi.evetech.net/latest'

# === Helper Functions ===
def resolve_system_id(location_id, headers):
    if location_id in structure_system_map:
        return structure_system_map[location_id]

    loc_str = str(location_id)

    if loc_str.startswith(('102', '103', '104', '105', '106', '107', '108', '109')):
        r = requests.get(f"{ESI_BASE}/universe/structures/{location_id}/", headers=headers)
        print(f"Structure lookup {location_id} status: {r.status_code}")
        if r.status_code == 200:
            sys_id = r.json().get('system_id')
            if sys_id:
                return sys_id
            print("No system_id in structure response. Trying /universe/ids fallback...")
            fallback = requests.post(f"{ESI_BASE}/universe/ids/", headers=headers, json=[int(location_id)])
            if fallback.status_code == 200:
                structures = fallback.json().get("structures", [])
                if structures:
                    return structures[0].get("system_id")
    elif loc_str.startswith('600'):
        r = requests.get(f"{ESI_BASE}/universe/stations/{location_id}/", headers=headers)
        if r.status_code == 200:
            return r.json().get('system_id')
    elif loc_str.startswith('300'):
        return location_id
    return None

def resolve_location_name(location_id, headers):
    loc_str = str(location_id)
    if loc_str.startswith(('102', '103', '104', '105', '106', '107', '108', '109')):
        r = requests.get(f"{ESI_BASE}/universe/structures/{location_id}/", headers=headers)
        if r.status_code == 200:
            return r.json().get('name')
    elif loc_str.startswith('600'):
        r = requests.get(f"{ESI_BASE}/universe/stations/{location_id}/", headers=headers)
        if r.status_code == 200:
            return r.json().get('name')
    return "Unknown"

def get_system_position(system_id):
    r = requests.get(f"{ESI_BASE}/universe/systems/{system_id}/").json()
    return r.get('position')

def ly_distance(pos1, pos2):
    dx = pos1['x'] - pos2['x']
    dy = pos1['y'] - pos2['y']
    dz = pos1['z'] - pos2['z']
    meters = sqrt(dx**2 + dy**2 + dz**2)
    return meters / 9.4607e15

def resolve_id_to_name(id_list, headers):
    url = f"{ESI_BASE}/universe/names/"
    res = requests.post(url, headers=headers, json=id_list)
    if res.status_code == 200:
        return {entry['id']: entry['name'] for entry in res.json()}
    return {}


# === OAuth Callback ===
@app.route('/')
def login():
    state = os.urandom(8).hex()
    session['state'] = state
    print(f"Generated and stored state: {state}")
    params = {
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'client_id': CLIENT_ID,
        'scope': SCOPES,
        'state': state,
    }
    return redirect(f"{AUTH_URL}?{urlencode(params)}")

@app.route('/callback')
def callback():
    received_state = request.args.get('state')
    expected_state = session.get('state')
    if received_state != expected_state:
        return f"State mismatch. Expected: {expected_state}, Received: {received_state}", 400

    code = request.args.get('code')
    auth = (CLIENT_ID, SECRET_KEY)
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI
    }
    token_resp = requests.post(TOKEN_URL, auth=auth, data=data)
    token_resp.raise_for_status()
    tokens = token_resp.json()
    access_token = tokens['access_token']

    headers = {'Authorization': f'Bearer {access_token}'}
    verify = requests.get(VERIFY_URL, headers=headers).json()
    char_id = verify['CharacterID']

    char_info = requests.get(f"{ESI_BASE}/characters/{char_id}/", headers=headers).json()
    corp_id = char_info['corporation_id']

    contracts = []
    page = 1
    while True:
        contracts_url = f"{ESI_BASE}/corporations/{corp_id}/contracts/?datasource=tranquility&page={page}"
        resp = requests.get(contracts_url, headers=headers)
        if resp.status_code != 200:
            break
        page_data = resp.json()
        if not page_data:
            break
        contracts.extend(page_data)
        page += 1

    print(f"Retrieved {len(contracts)} total contracts.")

    filtered = []
    for c in contracts:
        if c.get('status') == 'outstanding':
            start_id = c.get('start_location_id')
            end_id = c.get('end_location_id')
            print(f"Contract {c.get('contract_id')} | start: {start_id}, end: {end_id}")
            if not (start_id and end_id):
                print("Missing location info. Skipping.")
                continue
            start_sys = resolve_system_id(start_id, headers)
            end_sys = resolve_system_id(end_id, headers)
            print(f"Resolved systems: {start_sys} → {end_sys}")
            if not (start_sys and end_sys):
                print("Failed to resolve systems. Skipping.")
                continue
            pos1 = get_system_position(start_sys)
            pos2 = get_system_position(end_sys)
            if not (pos1 and pos2):
                print("Missing system position. Skipping.")
                continue
            ly = ly_distance(pos1, pos2)

            start_name = resolve_location_name(start_id, headers)
            end_name = resolve_location_name(end_id, headers)

            filtered.append({
                'contract_id': c.get('contract_id'),
                'issuer_id': c.get('issuer_id'),
                'start_location_id': start_id,
                'start_location_name': start_name,
                'end_location_id': end_id,
                'end_location_name': end_name,
                'start_system_id': start_sys,
                'end_system_id': end_sys,
                'volume': c.get('volume'),
                'collateral': c.get('collateral'),
                'lightyears': round(ly, 2),
                'reward': c.get('reward'),
            })

    issuer_ids = list(set(c['issuer_id'] for c in filtered if c.get('issuer_id')))
    id_to_name = resolve_id_to_name(issuer_ids, headers)
    for c in filtered:
        c['issuer_name'] = id_to_name.get(c['issuer_id'], 'Unknown')

    print(f"Filtered down to {len(filtered)} outstanding contracts with distance.")

    df = pd.DataFrame(filtered)
    df.to_csv("corporate_contracts_filtered.csv", index=False)
    subprocess.run(["python3", "Code/Main iteration.py"])
    return "Corporate contracts exported to corporate_contracts_filtered.csv"



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)