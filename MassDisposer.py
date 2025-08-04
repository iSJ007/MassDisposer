import requests
import csv
import json
import time
import os
from pathlib import Path
from dotenv import load_dotenv
from copy import deepcopy

# Load environment variables from .env file
load_dotenv()

CSV_FILENAME = Path('test1.csv')  # CSV must have "ID", "Serial Number", and "Asset Tag" columns
DISPOSED_STATUS_JSON = Path('DisposedStatus.json')
COMMENT_JSON = Path('Comment.json')

# Environment variables
APP_ID = os.getenv('APP_ID')
AUTH_URL = os.getenv('AUTH_URL')
API_BASE_URL = os.getenv('API_BASE_URL')
USERNAME = os.getenv('ACCOUNT')
PASSWORD = os.getenv('PASSWORD')


def get_bearer_token(username, password):
    try:
        response = requests.post(AUTH_URL, json={
            "username": username,
            "password": password
        })
        response.raise_for_status()
        token = response.text.strip('"')
        print("[INFO] Authenticated successfully.")
        return token
    except requests.HTTPError as e:
        print(f"[ERROR] Authentication failed: {e}. Check credentials and API URLs.")
    return None


def read_ids_from_csv(file_path):
    
    asset_data = []
    try:
        with open(file_path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                asset_id = row.get('ID', '').strip()
                serial_number = row.get('Serial Number', '').strip()

                if (
                    asset_id
                    and serial_number
                    and asset_id.upper() != 'NOT FOUND IN ITSM'
                    and serial_number.upper() != 'NOT FOUND IN ITSM'
                ):
                    asset_data.append({
                        'ID': asset_id,
                        'SerialNumber': serial_number,
                    })
        return asset_data
    except FileNotFoundError:
        print(f"[ERROR] CSV file not found at: {file_path}")
    except Exception as e:
        print(f"[ERROR] An error occurred while reading the CSV file: {e}")
    return []


def read_json_data(file_path):
    try:
        with open(file_path, 'r') as json_file:
            data = json.load(json_file)
        return data
    except FileNotFoundError:
        print(f"[ERROR] JSON file not found at: {file_path}")
    except json.JSONDecodeError:
        print(f"[ERROR] Failed to parse JSON from file: {file_path}")
    except Exception as e:
        print(f"[ERROR] An error occurred while reading the JSON file: {e}")
    return None


def update_asset_status(app_id, asset_id, token, update_data):
    
    url = f"{API_BASE_URL}/{app_id}/assets/{asset_id}"
    
    
    patch_document = []
    for key, value in update_data.items():
        patch_document.append({
            "op": "replace",
            "path": f"/{key}",
            "value": value
        })

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'  
    }
    
    try:
        
        response = requests.patch(url, headers=headers, json=patch_document)
        response.raise_for_status()
        print(f"[INFO] Successfully updated status for asset {asset_id}.")
        return True
    except requests.HTTPError as e:
        print(f"[ERROR] Failed to update asset {asset_id}. HTTP error: {e}")
        try:
            # Print the response content to get more details on the error
            print(f"Response content: {response.json()}")
        except json.JSONDecodeError:
            print(f"Response content: {response.text}")
    except requests.RequestException as e:
        print(f"[ERROR] Network error when updating asset {asset_id}: {e}")
    return False


def post_asset_feed_entry(app_id, asset_id, token, comment_data):
    url = f"{API_BASE_URL}/{app_id}/assets/{asset_id}/feed"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }
    try:
        response = requests.post(url, headers=headers, json=comment_data)
        response.raise_for_status()
        print(f"[INFO] Feed entry posted for asset {asset_id}.")
        return True
    except requests.HTTPError as e:
        print(f"[ERROR] Failed to post feed entry for asset {asset_id}. HTTP error: {e}")
    except requests.RequestException as e:
        print(f"[ERROR] Network error when posting feed entry for {asset_id}: {e}")
    return False


def main():
    print("--- Starting Asset Disposer ---")

    if not all([APP_ID, AUTH_URL, API_BASE_URL, USERNAME, PASSWORD]):
        print("[FATAL] Required environment variables are not set. Please check your .env file.")
        return

    token = get_bearer_token(USERNAME, PASSWORD)
    if not token:
        print("[FATAL] Exiting due to authentication failure.")
        return

    assets_to_process = read_ids_from_csv(CSV_FILENAME)
    if not assets_to_process:
        print(f"[WARNING] No valid asset entries found in '{CSV_FILENAME}'. Exiting.")
        return

    print(f"[INFO] Found {len(assets_to_process)} valid asset entries to process.")

    status_update_payload = read_json_data(DISPOSED_STATUS_JSON)
    comment_payload = read_json_data(COMMENT_JSON)

    if not status_update_payload or not comment_payload:
        print("[FATAL] Exiting due to missing or invalid JSON data.")
        return

    print("\n[INFO] Starting Mass Disposing...")

    for i, asset in enumerate(assets_to_process, 1):
        asset_id = asset['ID']
        serial_number = asset['SerialNumber']
        print(f"\n[INFO] Processing asset ID {asset_id} ({i}/{len(assets_to_process)})...")

        # Create fresh payload copy and add dynamic fields
        current_payload = deepcopy(status_update_payload)
        current_payload['serialNumber'] = serial_number

        update_successful = update_asset_status(APP_ID, asset_id, token, current_payload)

        if update_successful:
            time.sleep(1)
            post_asset_feed_entry(APP_ID, asset_id, token, comment_payload)

        if i < len(assets_to_process):
            time.sleep(1)

    print("\n--- Processing Complete ---")


if __name__ == '__main__':
    main()
