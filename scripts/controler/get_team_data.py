"""
FBref Stats Fetcher with Additional Match Data Extraction

This script fetches FBref statistics for provided URLs and then extracts additional 
match information (events and team stats) from each match page found in the venues.
It performs HTTP GET requests directly and is compatible with Streamlit for progress display.
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
    # Logs a success message in green with the script ID
    print(f"{GREEN}[{SCRIPT_ID}][SUCCESS] {message}{RESET}")

def print_warning(message):
    # Logs a warning message in orange with the script ID
    print(f"{ORANGE}[{SCRIPT_ID}][WARNING] {message}{RESET}")

def print_error(message):
    # Logs an error message in red with the script ID
    print(f"{RED}[{SCRIPT_ID}][ERROR] {message}{RESET}")

def print_info(message):
    # Logs an informational message in blue with the script ID
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
    Performs a GET request directly (without proxy).
    If a 429 status is received, the request is retried with exponential backoff.
    
    Args:
        url (str): The URL to request.
        retries (int): The maximum number of retries before failing.
        initial_delay (int): The initial delay in seconds for the backoff.
    
    Returns:
        Response: The HTTP response if successful.
    
    Raises:
        Exception: If unable to fetch the URL after the given number of retries.
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

def transform_url(url):
    """
    Transform the input URL from historical format to the new format.
    
    Example:
      Input:  https://fbref.com/fr/equipes/d01a653b/historique/Stats-et-historique-de-Argentinos-Juniors
      Output: https://fbref.com/fr/equipes/d01a653b/Statistiques-Argentinos-Juniors
    """
    return url.replace("/historique/Stats-et-historique-de-", "/Statistiques-")

def extract_team_name_from_soup(soup):
    """
    Extract the team name from the provided BeautifulSoup object.
    It removes the prefix "Stats et historique de " if present.
    
    Args:
        soup (BeautifulSoup): Parsed HTML content.
    
    Returns:
        str: The extracted team name or "Unknown Team" if extraction fails.
    """
    h1 = soup.find("h1")
    if h1:
        h1_text = h1.get_text(strip=True)
        prefix = "Stats et historique de "
        if h1_text.startswith(prefix):
            return h1_text[len(prefix):].strip()
        else:
            return h1_text
    return "Unknown Team"

def parse_table(table):
    """
    Parse a table with a two-level header.
    Returns a dictionary with:
      - "header": {"data_tip": {subheader_text: list of formatted data-tip values, ...}}
      - "rows": list of OrderedDicts mapping subheader names to cell data.
    
    For the "Joueur" column, the associated URL is also extracted (if present)
    and inserted as the first key under "Joueur URL".
    
    Additionally, skip any row where the "MJ" (matches played) column equals 0.
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
            # Skip column if header equals "Matchs"
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
                    player_url = a_tag["href"] if a_tag and a_tag.has_attr("href") else ""
                    row_dict["Joueur URL"] = player_url
                    row_dict[header] = cell.get_text(strip=True)
                if header.lower() == "rapport de match":
                    a_tag = cell.find("a")
                    match_url = a_tag["href"] if a_tag and a_tag.has_attr("href") else ""
                    row_dict["Match URL"] = match_url
                    row_dict[header] = cell.get_text(strip=True)
                else:
                    row_dict[header] = cell.get_text(strip=True)
            # If the row has a "MJ" column and its value is 0, skip this row
            if "MJ" in row_dict:
                try:
                    if int(row_dict["MJ"]) == 0:
                        continue
                except Exception:
                    pass
            rows_data.append(row_dict)
    return {"header": {"data_tip": sub_tip}, "rows": rows_data}

def merge_keeper_stats(standard_tables, extra_tables):
    """
    Merge extra table data (e.g. keeper, advanced keeper stats, etc.) into standard table data for matching players.
    For each row in an extra table, if a row with the same "Joueur" exists in the standard table,
    add only the new keys (columns) that are not already present.
    Also, update the header with the new data-tip entries.
    """
    for extra_data in extra_tables:
        extra_header = extra_data["header"]["data_tip"]
        extra_rows = extra_data["rows"]
        for std_table in standard_tables:
            std_header = std_table["header"]["data_tip"]
            for extra_row in extra_rows:
                extra_player = extra_row.get("Joueur")
                for std_row in std_table["rows"]:
                    if std_row.get("Joueur") == extra_player:
                        for key, value in extra_row.items():
                            if key not in std_row:
                                std_row[key] = value
                        for key, tip in extra_header.items():
                            if key not in std_header:
                                std_header[key] = tip
    return standard_tables

def extract_match_events(soup):
    """
    Extract match events from the match page.
    Events are extracted from divs with id "a" and "b".
    For each event, extract the minute (using regex to find numeric values).
    Returns:
        dict: Mapping of team names to a list of event minutes.
    """
    events = {}
    # Attempt to get team names from team_stats header; if not available, default to "Team A" and "Team B"
    team_names = {"a": "Team A", "b": "Team B"}
    team_stats_div = soup.find(id="team_stats")
    if team_stats_div:
        headers = team_stats_div.find_all(["h1", "h2", "h3"])
        if len(headers) >= 2:
            team_names["a"] = headers[0].get_text(strip=True)
            team_names["b"] = headers[1].get_text(strip=True)
    
    # Process both events divs: "a" and "b"
    for div_id in ["a", "b"]:
        div = soup.find(id=div_id)
        team_key = team_names.get(div_id, f"Team {div_id.upper()}")
        events[team_key] = []
        if div:
            # Look for event elements inside the div (either <div class="event"> or <li> items)
            event_elements = div.find_all(["div", "li"], class_="event")
            if not event_elements:
                event_elements = div.find_all(["div", "li"])
            for event in event_elements:
                text = event.get_text(strip=True)
                # Extract the first number encountered (representing the minute)
                match = re.search(r"(\d+)", text)
                if match:
                    minute = int(match.group(1))
                    events[team_key].append(minute)
        else:
            print_warning(f"Events div with id '{div_id}' not found in match page.")
    return events

def extract_team_stats(soup):
    """
    Extract team statistics from the match page.
    Looks for a div with id "team_stats" and extracts stats such as possession,
    pass success rate, shots on target, yellow cards, and red cards.
    Assumes that the div contains a table where:
        - The first row has headers with team names.
        - Each subsequent row contains: stat name, value for team A, value for team B.
    Returns:
        dict: Dictionary with keys for each stat, mapping to a dict of team values.
    """
    stats = {
        "possession": {},
        "Pourcentage de passes réussies": {},
        "Tirs cadrés": {},
        "Carton jaune": {},
        "Carton rouge": {}
    }
    team_stats_div = soup.find(id="team_stats")
    if team_stats_div:
        table = team_stats_div.find("table")
        if table:
            rows = table.find_all("tr")
            if len(rows) >= 2:
                headers = rows[0].find_all(["th", "td"])
                if len(headers) >= 3:
                    team_a = headers[1].get_text(strip=True)
                    team_b = headers[2].get_text(strip=True)
                else:
                    team_a = "Team A"
                    team_b = "Team B"
                # Process each stat row
                for row in rows[1:]:
                    cells = row.find_all(["th", "td"])
                    if len(cells) >= 3:
                        stat_name = cells[0].get_text(strip=True)
                        value_a = cells[1].get_text(strip=True)
                        value_b = cells[2].get_text(strip=True)
                        # Map the stat name to our desired keys (case-insensitive matching)
                        lower_stat = stat_name.lower()
                        if lower_stat in ["possession"]:
                            stats["possession"][team_a] = value_a
                            stats["possession"][team_b] = value_b
                        elif lower_stat in ["pourcentage de passes réussies", "passes", "pass success", "pass success rate"]:
                            stats["Pourcentage de passes réussies"][team_a] = value_a
                            stats["Pourcentage de passes réussies"][team_b] = value_b
                        elif lower_stat in ["tirs cadrés", "shots on target"]:
                            stats["Tirs cadrés"][team_a] = value_a
                            stats["Tirs cadrés"][team_b] = value_b
                        elif lower_stat in ["carton jaune", "yellow cards"]:
                            stats["Carton jaune"][team_a] = value_a
                            stats["Carton jaune"][team_b] = value_b
                        elif lower_stat in ["carton rouge", "red cards"]:
                            stats["Carton rouge"][team_a] = value_a
                            stats["Carton rouge"][team_b] = value_b
        else:
            print_warning("No table found in team_stats div.")
    else:
        print_warning("team_stats div not found in match page.")
    return stats

def process_match(match_url):
    """
    Process a single match URL to extract event data and team statistics.
    A random delay between 1 and 3 seconds is applied before each request to avoid HTTP 429 errors.
    
    Args:
        match_url (str): The URL of the match page.
    
    Returns:
        dict: A dictionary containing 'events' and 'team_stats' keys.
    """
    # Introduce a random delay between 1 and 3 seconds
    time.sleep(random.uniform(2, 3))
    print_info(f"Fetching match page: https://fbref.com{match_url}")
    try:
        response = safe_get("https://fbref.com{match_url}")
        response.raise_for_status()
    except Exception as e:
        print_error(f"Failed to fetch match page {"https://fbref.com{match_url}"}: {e}")
        return {"events": {}, "team_stats": {}}
    soup = BeautifulSoup(response.content, "lxml")
    # Extract events and team statistics from the match page
    events = extract_match_events(soup)
    team_stats = extract_team_stats(soup)
    print_success(f"Successfully processed match page: {"https://fbref.com{match_url}"}")
    return {"events": events, "team_stats": team_stats}

def process_url(url, url_index, total, progress_bar=None):
    """
    Process a single FBref URL with detailed sub-steps updated via the progress bar.
    This function performs a single HTTP request, then reuses the page content for:
      1. Transforming the URL (if needed)
      2. Fetching the page (GET request using safe_get)
      3. Parsing the page (using BeautifulSoup)
      4. Extracting the team name and logo
      5. Parsing standard and extra tables
      6. Merging extra stats into standard tables
      7. Retrieving match logs (venues)
      8. Finalizing and returning data
    
    Additionally, match logs (venues) will later be used to extract match events and team statistics.
    """
    def update_local(fraction, step_text=""):
        if progress_bar:
            overall_progress = int(((url_index + fraction) / total) * 100)
            progress_bar.progress(overall_progress, text=f"URL {url_index+1}/{total}: {step_text}")

    # Transform the URL to the new format
    transformed = transform_url(url)
    
    update_local(0.1, "Fetching page once for all tasks")
    try:
        response = safe_get(transformed)
        response.raise_for_status()
    except Exception as e:
        print_error(f"Error fetching URL: {e}")
        return None

    # Parse the page content once using BeautifulSoup
    soup = BeautifulSoup(response.content, "lxml")
    
    update_local(0.2, "Extracting team name from page")
    team = extract_team_name_from_soup(soup)

    update_local(0.25, "Extracting team logo")
    # NEW: Extract team logo URL from the meta section.
    team_logo_url = None
    meta_div = soup.find(id="meta")
    if meta_div:
        first_div = meta_div.find("div")
        if first_div:
            img_tag = first_div.find("img")
            if img_tag and img_tag.get("src"):
                team_logo_url = urllib.parse.urljoin(url, img_tag["src"])
    
    update_local(1.3, "Parsing standard tables")
    standard_tables = soup.find_all("table", id=lambda x: x and x.startswith("stats_standard_"))
    standard_tables_data = [parse_table(table) for table in standard_tables]

    extra_prefixes = [
        "stats_keeper_", "stats_keeper_adv_", "stats_shooting_",
        "stats_passing_types_", "stats_gca_", "stats_defense_",
        "stats_possession_", "stats_playing_time_", "stats_misc_"
    ]
    extra_tables_data = []
    base_progress = 0.4
    update_progress = ((0.7 - 0.4) / len(extra_prefixes))
    for prefix in extra_prefixes:
        update_local(base_progress, f"Parsing extra tables: {prefix}")
        extra_tables = soup.find_all("table", id=lambda x: x and x.startswith(prefix))
        for table in extra_tables:
            extra_tables_data.append(parse_table(table))
        base_progress += update_progress

    update_local(0.7, "Merging extra stats")
    merged_tables = merge_keeper_stats(standard_tables_data, extra_tables_data) if extra_tables_data else standard_tables_data

    update_local(0.8, "Retrieving match logs")
    matchlogs_table = soup.find("table", id=lambda x: x and x.startswith("matchlogs_for"))
    venues = {"header": parse_table(matchlogs_table)["header"], "venues": parse_table(matchlogs_table)["rows"]} if matchlogs_table else {}

    update_local(0.9, "Finalizing data")
    time.sleep(random.uniform(0, 2))
    update_local(1.0, "URL processing complete")
    
    return {"team": team, "team_logo_url": team_logo_url, "tables": merged_tables, "venues": venues}

def fetch_fbref_stats(urls, output_file="artifacts/fbref_stats.json"):
    """
    Process a list of FBref URLs and output a JSON object with the results.
    For each URL, the script fetches standard data and match logs.
    Then, for each match log (venue) that contains a Match URL, it fetches additional 
    match events and team statistics.
    
    Example usage:
        test_urls = [
            "https://fbref.com/fr/equipes/d01a653b/historique/Stats-et-historique-de-Argentinos-Juniors",
            "https://fbref.com/fr/equipes/e2d8892c/Statistiques-Paris-Saint-Germain"
        ]
        fetch_fbref_stats(test_urls)
    """
    datasets = []
    total = len(urls)
    
    progress_bar = st.progress(0, text="Starting FBref Stats Fetching...") if st else None

    for index, url in enumerate(urls):
        print_info(f"Processing URL: {url}")
        data = process_url(url, index, total, progress_bar)
        if data:
            # Process match logs for additional match data
            venues = data.get("venues", {})
            match_rows = venues.get("venues", [])
            aggregated_events = {}
            aggregated_team_stats = {
                "possession": {},
                "Pourcentage de passes réussies": {},
                "Tirs cadrés": {},
                "Carton jaune": {},
                "Carton rouge": {}
            }
            for row in match_rows:
                match_url = row.get("Match URL", "")
                if match_url:
                    print_info(f"Processing match URL: {match_url}")
                    match_data = process_match(match_url)
                    # Aggregate event data
                    for team, minutes in match_data["events"].items():
                        if team not in aggregated_events:
                            aggregated_events[team] = []
                        aggregated_events[team].extend(minutes)
                    # Aggregate team stats (overwrite if multiple matches exist)
                    for stat, teams in match_data["team_stats"].items():
                        for team, value in teams.items():
                            aggregated_team_stats[stat][team] = value
            # Integrate aggregated match data into venues
            if venues:
                venues["events"] = aggregated_events
                venues["team_stats"] = aggregated_team_stats
                data["venues"] = venues
            datasets.append(data)
        time.sleep(random.uniform(1, 3))
    
    if progress_bar:
        progress_bar.progress(100, text="Processing complete")
        progress_bar.empty()
    
    output = {"datasets": datasets}
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=4, ensure_ascii=False)
        print_success(f"JSON output saved to {output_file}")
    except Exception as e:
        print_error(f"Error writing JSON to {output_file}: {e}")
    
    return output

if __name__ == "__main__":
    test_urls = [
        "https://fbref.com/fr/equipes/d01a653b/historique/Stats-et-historique-de-Argentinos-Juniors",
        "https://fbref.com/fr/equipes/e2d8892c/Statistiques-Paris-Saint-Germain"
    ]
    try:
        fetch_fbref_stats(test_urls)
    except Exception as ex:
        print_error(f"Error during request: {ex}")
        sys.exit(1)
