"""
FBref Stats Fetcher with Optimized Request Delays

This script fetches FBref statistics using a delay (random between 3 and 5 seconds)
between each HTTP request to avoid receiving 429 responses.
It enriches each player's data and displays a progress bar in Streamlit.
"""

import argparse
import sys
import json
import requests
from bs4 import BeautifulSoup
import urllib.parse
import pandas as pd
import re
import time
import certifi
from collections import OrderedDict  # To maintain key order
import random
import string

# Base URL for completing relative URLs if needed.
BASE_URL = "https://fbref.com"

# Generate a unique 6-character ID for this script execution
SCRIPT_ID = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# Attempt to import Streamlit. If not available, use None.
try:
    import streamlit as st
except ImportError:
    st = None

# ANSI color codes
GREEN = "\033[92m"    # green: task executed successfully
ORANGE = "\033[93m"   # orange: task in progress
RED = "\033[91m"      # red: error in task
BLUE = "\033[94m"     # blue: transitional task
RESET = "\033[0m"

# Logging functions including the unique script ID
def print_success(message):
    print(f"{GREEN}[{SCRIPT_ID}][SUCCESS] {message}{RESET}")

def print_warning(message):
    print(f"{ORANGE}[{SCRIPT_ID}][WARNING] {message}{RESET}")

def print_error(message):
    print(f"{RED}[{SCRIPT_ID}][ERROR] {message}{RESET}")

def print_info(message):
    print(f"{BLUE}[{SCRIPT_ID}][INFO] {message}{RESET}")

# Create a global session with a custom User-Agent and common headers.
session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/90.0.4430.93 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5"
})

def safe_get(url, retries=3, initial_delay=5):
    """
    Performs a GET request directly (without proxy) with a delay between each request.
    If a 429 status is received, the request is retried with exponential backoff.
    """
    delay = initial_delay
    for attempt in range(1, retries + 1):
        try:
            print_info(f"Requesting {url} (Attempt {attempt}/{retries})")
            response = session.get(url, timeout=10, verify=certifi.where())
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 5))
                print_warning(f"Received 429 for {url}. Waiting {retry_after} seconds before retrying.")
                time.sleep(retry_after)
                continue
            response.raise_for_status()
            print_success(f"Successfully fetched {url}")

            # Affichage du spinner avec la durée du sleep
            sleep_time = random.uniform(2, 5)
            if st:
                with st.spinner(f"Update ...", show_time=True):
                    time.sleep(sleep_time)
            else:
                time.sleep(sleep_time)

            return response
        except Exception as e:
            if attempt == retries:
                print_error(f"Failed after {retries} attempts for {url}: {e}")
                raise e
            else:
                print_warning(f"Error accessing {url}: {e}. Retrying in {delay} seconds (Attempt {attempt}/{retries}).")
                time.sleep(delay)
                delay *= 2
    return None

def read_json(filename):
    """Reads a JSON file and returns the data."""
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(data, filename):
    """Writes data to a JSON file."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print_success(f"JSON file '{filename}' updated.")

def parse_table(table):
    """
    Parses a table with a two-level header.
    Returns a dictionary with:
      - "header": {"data_tip": {subheader_name: list of formatted values, ...}}
      - "rows": a list of OrderedDict preserving the column order.
    
    For the "Joueur" column, if a link is present, the player's URL is extracted
    (completed with BASE_URL if necessary) and inserted as "Joueur URL".
    """
    thead = table.find("thead")
    sub_tip = {}
    header_sub = []
    indices_to_keep = []
    if thead:
        header_rows = thead.find_all("tr")
        if len(header_rows) >= 2:
            sub_cells = header_rows[1].find_all(["th", "td"])
        elif len(header_rows) == 1:
            sub_cells = header_rows[0].find_all(["th", "td"])
        else:
            sub_cells = []
        for i, th in enumerate(sub_cells):
            text = th.get_text(strip=True)
            if text.lower() == "matchs":
                continue
            header_sub.append(text)
            indices_to_keep.append(i)
            tip = th.get("data-tip", None)
            if tip is not None:
                tip = tip.replace("<br>", "\n").replace("<strong>", "**").replace("</strong>", "**")
                tip = re.sub(r"<[^>]+>", "", tip)
                tip_values = [line.strip() for line in tip.split("\n") if line.strip()]
                sub_tip[text] = tip_values
    tbody = table.find("tbody")
    rows_data = []
    if tbody:
        for row in tbody.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if not cells:
                continue
            filtered_cells = [cells[i] for i in indices_to_keep if i < len(cells)]
            if len(filtered_cells) != len(header_sub):
                continue
            row_dict = OrderedDict()
            for header, cell in zip(header_sub, filtered_cells):
                if header.lower() == "joueur":
                    a_tag = cell.find("a")
                    if a_tag and a_tag.has_attr("href"):
                        player_url = a_tag["href"]
                        if not player_url.startswith("http"):
                            player_url = urllib.parse.urljoin(BASE_URL, player_url)
                    else:
                        player_url = ""
                    row_dict["Joueur URL"] = player_url
                    row_dict[header] = cell.get_text(strip=True)
                else:
                    row_dict[header] = cell.get_text(strip=True)
            rows_data.append(row_dict)
    return {"header": {"data_tip": sub_tip}, "rows": rows_data}

def get_player_additional_info(player_url):
    """
    For a player's URL, retrieves the page and extracts:
      - The player's photo URL
      - Additional text from <p> tags
      - Honors list
      - Scout summary table
      - Last 5 match logs table
    """
    if not player_url.startswith("http"):
        player_url = urllib.parse.urljoin(BASE_URL, player_url)
    try:
        response = safe_get(player_url)
    except Exception as e:
        print_error(f"Error fetching {player_url}: {e}")
        return {}
    
    soup = BeautifulSoup(response.content, "lxml")
    
    info_div = soup.find("div", id="info")
    if not info_div:
        return {}
    
    additional_info = {}
    
    # 1. Photo URL extraction
    meta_div = info_div.find("div", id="meta")
    photo_url = ""
    if meta_div:
        media_item = meta_div.find("div", class_="media-item")
        if media_item:
            img = media_item.find("img")
            if img and img.has_attr("src"):
                photo_url = img["src"]
    additional_info["photo_url"] = photo_url
    
    # 2. Additional text (all <p> tags within div#info)
    p_tags = info_div.find_all("p")
    additional_info["info"] = [p.get_text(strip=True) for p in p_tags if p.get_text(strip=True)]
    
    # 3. Honors list from <ul id="bling">
    palmares = []
    bling_ul = info_div.find("ul", id="bling")
    if bling_ul:
        for li in bling_ul.find_all("li"):
            item = {"text": li.get_text(strip=True)}
            if li.has_attr("data-tip"):
                item["data_tip"] = li["data-tip"].strip()
            palmares.append(item)
    additional_info["palmares"] = palmares
    
    # 4. Scout summary table
    scout_summary_table = soup.find("table", id=lambda x: x and x.startswith("scout_summary_"))
    if scout_summary_table:
        additional_info["scout_summary"] = parse_table(scout_summary_table)
    else:
        additional_info["scout_summary"] = {}
    
    # 5. Last 5 match logs table
    last_5_table = soup.find("table", id="last_5_matchlogs")
    if last_5_table:
        additional_info["last_5_matchlogs"] = parse_table(last_5_table)
    else:
        additional_info["last_5_matchlogs"] = {}
    
    return additional_info

def process_players_data(data):
    """
    Iterates through each dataset, table, and player in the JSON.
    For each player, retrieves additional info from their URL and stores it under "additional_info".
    The progress bar is updated in Streamlit if available.
    """
    total_players = 0
    for dataset in data.get("datasets", []):
        for table in dataset.get("tables", []):
            total_players += len(table.get("rows", []))
    
    # Création de la progress bar Streamlit si disponible
    progress_bar = st.progress(0, text="Updating players...") if st else None
    current_count = 0
    
    for dataset in data.get("datasets", []):
        for table in dataset.get("tables", []):
            for row in table.get("rows", []):
                player_url = row.get("Joueur URL", "").strip()
                player_name = row.get("Joueur")
                # Petit délai supplémentaire aléatoire (0 à 2s) entre chaque joueur
                wait = random.uniform(0, 2)

                if player_url:
                    additional_info = get_player_additional_info(player_url)
                    row["additional_info"] = additional_info

                    # Spinner qui affiche la durée de ce petit délai
                    if st:
                        with st.spinner(f"Wait for next player...", show_time=True):
                            time.sleep(wait)
                    else:
                        time.sleep(wait)

                current_count += 1
                if progress_bar:
                    progress = int((current_count / total_players) * 100)
                    progress_bar.progress(
                        progress, 
                        text=f"Updating: {player_name} ... ({progress}% - {current_count}/{total_players})"
                    )
                    
    if progress_bar:
        progress_bar.empty()
    return data

def update_fbref_players_data(json_file="artifacts/fbref_stats.json"):
    """
    Reads the JSON file, enriches each player's data by scraping their FBref page for additional info,
    and then updates the same file.
    Returns the updated data.
    """
    data = read_json(json_file)
    data = process_players_data(data)
    write_json(data, json_file)
    return data

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Enrich the fbref_stats JSON with additional information for each player."
    )
    parser.add_argument("--file", default="artifacts/bref_stats.json", help="Path to the JSON file to update")
    args = parser.parse_args()
    update_fbref_players_data(args.file)
