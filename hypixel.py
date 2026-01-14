import os
import requests
import time
import shutil
from collections import defaultdict
import threading

# Configuration
COOKIES_FOLDER = "cookies"
RESULTS_FOLDER = "results"
MOJANG_API = "https://api.mojang.com/users/profiles/minecraft/"
MOJANG_UUID_API = "https://api.mojang.com/user/profiles/"
MOJANG_HISTORY_API = "https://api.mojang.com/user/profiles/{uuid}/names"
HYPIXEL_API = "https://api.hypixel.net/"
HYPIXEL_API_KEY = "789891d7-6084-4d51-bae3-517afbe55ca9"

# Stats tracking
stats = defaultdict(int)
stats_lock = threading.Lock()
checked_count = 0
failed_usernames = []
username_changes = []
rate_limited_queue = []

def ensure_folder_exists(folder_name):
    """Ensure a specific folder exists, create only when needed"""
    folder_path = os.path.join(RESULTS_FOLDER, folder_name)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    return folder_path

def copy_file_to_category(filename, category):
    """Copy txt file to appropriate category folder"""
    try:
        source = os.path.join(COOKIES_FOLDER, filename)
        ensure_folder_exists(category)
        destination = os.path.join(RESULTS_FOLDER, category, filename)
        
        if os.path.exists(source):
            shutil.copy2(source, destination)
            return True
    except Exception as e:
        print(f"Error copying file {filename} to {category}: {e}")
    return False

def get_uuid_from_username(username):
    """Get UUID for username - returns (uuid, current_name, error, rate_limited)"""
    try:
        url = f"{MOJANG_API}{username}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data['id'], data['name'], None, False
        elif response.status_code == 204:
            return None, None, "Username doesn't exist", False
        elif response.status_code == 429:
            return None, None, "Rate limited by Mojang API", True
        else:
            return None, None, f"Mojang API error: {response.status_code}", False
    except requests.exceptions.Timeout:
        return None, None, "Mojang API timeout", False
    except requests.exceptions.ConnectionError:
        return None, None, "Connection error to Mojang API", False
    except Exception as e:
        return None, None, f"Unexpected error: {str(e)}", False

def get_name_history(uuid):
    """Get name change history for a UUID"""
    try:
        url = f"https://api.mojang.com/user/profiles/{uuid}/names"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            return response.json(), None, False
        elif response.status_code == 429:
            return None, "Rate limited by Mojang API", True
        else:
            return None, f"Error fetching name history: {response.status_code}", False
    except Exception as e:
        return None, f"Error: {str(e)}", False

def get_hypixel_data(uuid):
    """Fetch player data from Hypixel API with error handling"""
    try:
        response = requests.get(
            f"{HYPIXEL_API}player",
            params={"key": HYPIXEL_API_KEY, "uuid": uuid},
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json(), None, False
        elif response.status_code == 403:
            return None, "Invalid API key", False
        elif response.status_code == 429:
            return None, "Rate limited by Hypixel API", True
        else:
            return None, f"Hypixel API error: {response.status_code}", False
    except requests.exceptions.Timeout:
        return None, "Hypixel API timeout", False
    except requests.exceptions.ConnectionError:
        return None, "Connection error to Hypixel API", False
    except Exception as e:
        return None, f"Unexpected error: {str(e)}", False

def format_timestamp(timestamp):
    """Convert timestamp to readable format"""
    if not timestamp:
        return "Never"
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp / 1000))

def get_rank(player_data):
    """Extract rank from player data"""
    if not player_data or not player_data.get('success'):
        return "None"
    
    player = player_data.get('player', {})
    if not player:
        return "None"
    
    if player.get('rank'):
        return player['rank']
    if player.get('monthlyPackageRank'):
        rank = player['monthlyPackageRank']
        return rank.replace('SUPERSTAR', 'MVP_PLUS_PLUS')
    if player.get('newPackageRank'):
        return player['newPackageRank'].replace('VIP_PLUS', 'VIP_PLUS').replace('MVP_PLUS', 'MVP_PLUS')
    if player.get('packageRank'):
        return player['packageRank']
    
    return "None"

def display_stats():
    """Display live statistics"""
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=" * 70)
    print("HYPIXEL PROFILE CHECKER - LIVE STATS")
    print("=" * 70)
    print(f"\nTotal Checked: {checked_count}")
    print(f"Rate Limited (Queued for Recheck): {len(rate_limited_queue)}")
    print("\n--- RANK DISTRIBUTION ---")
    for rank, count in sorted(stats.items()):
        print(f"{rank}: {count}")
    
    if username_changes:
        print("\n--- USERNAME CHANGES DETECTED ---")
        for old, new in username_changes[-5:]:
            print(f"  {old} → {new}")
        if len(username_changes) > 5:
            print(f"  ... and {len(username_changes) - 5} more")
    
    if failed_usernames:
        print("\n--- FAILED LOOKUPS ---")
        for username, reason in failed_usernames[-5:]:
            print(f"  {username}: {reason}")
        if len(failed_usernames) > 5:
            print(f"  ... and {len(failed_usernames) - 5} more")
    
    print("=" * 70)

def extract_username_from_filename(filename):
    """Extract username from filename like [text1][text2][text3][username].txt"""
    name = filename.replace('.txt', '')
    parts = name.split('[')
    if len(parts) > 0:
        last_part = parts[-1].rstrip(']')
        return last_part
    return None

def check_player(username, filename, is_recheck=False):
    """Check a single player and update stats"""
    global checked_count
    
    # Validate username format
    if not username or len(username) < 3 or len(username) > 16:
        with stats_lock:
            stats['Invalid_Username'] += 1
            failed_usernames.append((username, "Invalid username format"))
            if not is_recheck:
                checked_count += 1
        print(f"\n[✗] {username}")
        print(f"    Error: Invalid username format - skipping")
        return
    
    # Get UUID and current username
    uuid, current_username, error, rate_limited = get_uuid_from_username(username)
    
    if rate_limited:
        with stats_lock:
            if (username, filename) not in rate_limited_queue:
                rate_limited_queue.append((username, filename))
        print(f"\n[⏸] {username}")
        print(f"    Rate limited - will recheck later")
        print(f"    Sleeping for 2 seconds...")
        time.sleep(2)
        return
    
    if not uuid:
        with stats_lock:
            stats['Failed_Lookup'] += 1
            failed_usernames.append((username, error))
            if not is_recheck:
                checked_count += 1
        copy_file_to_category(filename, "Failed_Lookup")
        print(f"\n[✗] {username}")
        print(f"    Error: {error}")
        print(f"    📁 Copied to: Failed_Lookup")
        return
    
    # Check if username changed
    name_changed = False
    history, hist_error, hist_rate_limited = get_name_history(uuid)
    
    if hist_rate_limited:
        with stats_lock:
            if (username, filename) not in rate_limited_queue:
                rate_limited_queue.append((username, filename))
        print(f"\n[⏸] {username}")
        print(f"    Rate limited on name history - will recheck later")
        print(f"    Sleeping for 2 seconds...")
        time.sleep(2)
        return
    
    if history and len(history) > 1:
        if current_username.lower() != username.lower():
            name_changed = True
            with stats_lock:
                username_changes.append((username, current_username))
            print(f"\n[⚠] Username changed: {username} → {current_username}")
    
    # Get Hypixel data
    player_data, error, hypixel_rate_limited = get_hypixel_data(uuid)
    
    if hypixel_rate_limited:
        with stats_lock:
            if (username, filename) not in rate_limited_queue:
                rate_limited_queue.append((username, filename))
        print(f"\n[⏸] {username}")
        print(f"    Hypixel rate limited - will recheck later")
        print(f"    Sleeping for 2 seconds...")
        time.sleep(2)
        return
    
    if not player_data or not player_data.get('success'):
        with stats_lock:
            stats['Failed_Lookup'] += 1
            failed_usernames.append((current_username, error or "API unsuccessful"))
            if not is_recheck:
                checked_count += 1
        copy_file_to_category(filename, "Failed_Lookup")
        print(f"\n[✗] {current_username}")
        print(f"    Error: {error or 'API unsuccessful'}")
        print(f"    📁 Copied to: Failed_Lookup")
        return
    
    player = player_data.get('player', {})
    if not player:
        with stats_lock:
            stats['No_Profile'] += 1
            if not is_recheck:
                checked_count += 1
        copy_file_to_category(filename, "No_Profile")
        print(f"\n[⚠] {current_username}")
        print(f"    Warning: Never played on Hypixel")
        print(f"    📁 Copied to: No_Profile")
        return
    
    # Extract information
    rank = get_rank(player_data)
    last_login = player.get('lastLogin', 0)
    last_logout = player.get('lastLogout', 0)
    
    # Determine online status
    is_online = last_login > last_logout if last_login and last_logout else False
    
    # Update stats
    with stats_lock:
        stats[rank] += 1
        if name_changed:
            stats['Username_Changed'] += 1
        if is_online:
            stats['Currently_Online'] += 1
        if not is_recheck:
            checked_count += 1
    
    # Copy file to categories
    categories_to_copy = []
    
    # Rank folder
    categories_to_copy.append(rank)
    copy_file_to_category(filename, rank)
    
    # Print individual result
    print(f"\n[✓] {current_username}")
    if name_changed:
        print(f"    Old Username: {username}")
    print(f"    Rank: {rank}")
    print(f"    Last Login: {format_timestamp(last_login)}")
    print(f"    Status: {'ONLINE' if is_online else 'OFFLINE'}")
    print(f"    📁 Copied to: {', '.join(categories_to_copy)}")

def main():
    """Main execution function"""
    global checked_count
    
    # Create base results folder
    if not os.path.exists(RESULTS_FOLDER):
        os.makedirs(RESULTS_FOLDER)
    
    # Check if folder exists
    if not os.path.exists(COOKIES_FOLDER):
        print(f"Error: Folder '{COOKIES_FOLDER}' not found!")
        return
    
    # Get all .txt files
    txt_files = [f for f in os.listdir(COOKIES_FOLDER) if f.endswith('.txt')]
    
    if not txt_files:
        print("No .txt files found in the cookies folder!")
        return
    
    # Extract usernames
    usernames_files = []
    for filename in txt_files:
        username = extract_username_from_filename(filename)
        if username:
            usernames_files.append((username, filename))
    
    print(f"Found {len(usernames_files)} accounts to check\n")
    print("Starting checks...\n")
    
    # Check each player
    for i, (username, filename) in enumerate(usernames_files, 1):
        print(f"\n[{i}/{len(usernames_files)}] Checking: {username}")
        check_player(username, filename)
        
        # Display updated stats every 5 checks
        if i % 5 == 0:
            display_stats()
        
        # Small delay between checks
        time.sleep(0.3)
    
    # Recheck rate limited accounts
    if rate_limited_queue:
        print("\n\n" + "=" * 70)
        print(f"RECHECKING {len(rate_limited_queue)} RATE LIMITED ACCOUNTS")
        print("=" * 70)
        
        retry_count = 0
        while rate_limited_queue and retry_count < 3:
            retry_count += 1
            print(f"\n--- RETRY ATTEMPT {retry_count} ---")
            
            # Create a copy of the queue
            current_queue = rate_limited_queue.copy()
            rate_limited_queue.clear()
            
            for i, (username, filename) in enumerate(current_queue, 1):
                print(f"\n[{i}/{len(current_queue)}] Rechecking: {username}")
                check_player(username, filename, is_recheck=True)
                time.sleep(0.5)
            
            if rate_limited_queue:
                print(f"\nStill {len(rate_limited_queue)} accounts rate limited. Waiting 5 seconds...")
                time.sleep(5)
        
        # If still rate limited after retries, treat as failed lookup
        if rate_limited_queue:
            print(f"\n{len(rate_limited_queue)} accounts still rate limited after retries - marking as failed")
            for username, filename in rate_limited_queue:
                copy_file_to_category(filename, "Failed_Lookup")
                with stats_lock:
                    stats['Failed_Lookup'] += 1
    
    # Final stats display
    print("\n\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)
    display_stats()
    print("\nFiles have been organized into the 'results' folder!")
    print("\nFolder structure:")
    print("  - Rank folders: VIP, VIP_PLUS, MVP, MVP_PLUS, MVP_PLUS_PLUS, None")
    print("  - Error folders: Failed_Lookup, No_Profile")
    print("\nEach account is copied to its rank folder for easy organization!")

if __name__ == "__main__":
    main()
