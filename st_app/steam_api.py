
import requests
import re
from typing import List, Dict, Optional

def resolve_vanity_url(api_key: str, vanity_name: str) -> Optional[str]:
    """
    Converts a Steam vanity URL name to a 64-bit Steam ID.
    """
    url = "http://api.steampowered.com/ISteamUser/ResolveVanityURL/v0001/"
    params = {
        "key": api_key,
        "vanityurl": vanity_name
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json().get("response", {})
        if data.get("success") == 1:
            return data.get("steamid")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error resolving vanity URL: {e}")
        return None

def get_user_played_games(api_key: str, steam_id: str) -> List[Dict]:
    """
    Fetches a list of all games a Steam user owns, including playtime.
    """
    url = "http://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/"
    params = {
        "key": api_key,
        "steamid": steam_id,
        "format": "json",
        "include_appinfo": True,
        "include_played_free_games": True,
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json().get("response", {})
        return data.get("games", [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching user games: {e}")
        return []

def get_games_from_profile_url(api_key: str, profile_url: str) -> Optional[List[Dict]]:
    """
    Orchestrates fetching games from a full Steam profile URL.
    Handles both vanity URLs and direct 64-bit ID URLs.
    """
    # Regex to find vanity name or 64-bit ID
    vanity_match = re.search(r"steamcommunity.com/id/([^/]+)", profile_url)
    id_match = re.search(r"steamcommunity.com/profiles/(\d{17})", profile_url)

    steam_id = None
    if id_match:
        steam_id = id_match.group(1)
    elif vanity_match:
        vanity_name = vanity_match.group(1)
        steam_id = resolve_vanity_url(api_key, vanity_name)
        if not steam_id:
            print(f"Could not resolve vanity URL for: {vanity_name}")
            return None
    else:
        print("Invalid Steam profile URL format.")
        return None

    return get_user_played_games(api_key, steam_id)
