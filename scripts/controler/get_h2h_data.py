"""
fbref_h2h_data.py

Module for fetching head-to-head (H2H) data from FBref.
Given two FBref team URLs (home and away), the module:
  - Builds the H2H URL.
  - Fetches the page using safe_get with delay to avoid 429 errors.
  - Retrieves and formats information from the scorebox div.
      The scorebox is split into two lists (home_team and away_team) where:
        • The first element is the team name.
        • Each subsequent stat (e.g. "11 victoires") is transformed into a dict like {"victoires": "11"}.
      The note (after "vs.") is removed.
  - Parses the table with id "games_history_all", omitting empty fields and only including matches from the last 10 years.
      For the column "Rapport de match", the cell content is replaced by the match report URL.
  - For each match with a report URL, fetches additional match stats from the report page:
        • From the div with id "team_stats": retrieves only percentage values.
  - Provides functions to return the data as a dict and to write it in a JSON file.
"""

import re
import time
import json
import random
import string
import certifi
import argparse
import requests
from bs4 import BeautifulSoup
import urllib.parse
from collections import OrderedDict
from datetime import datetime, timedelta

# Optionally import streamlit if available (for spinners and progress bar)
try:
    import streamlit as st
except ImportError:
    st = None

# ANSI color codes for logs
GREEN = "\033[92m"    # Success
ORANGE = "\033[93m"   # Warning
RED = "\033[91m"      # Error
BLUE = "\033[94m"     # Info
RESET = "\033[0m"

# Generate a unique 6-character script ID
SCRIPT_ID = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# Logging functions
def print_success(message):
    print(f"{GREEN}[{SCRIPT_ID}][SUCCESS] {message}{RESET}")

def print_warning(message):
    print(f"{ORANGE}[{SCRIPT_ID}][WARNING] {message}{RESET}")

def print_error(message):
    print(f"{RED}[{SCRIPT_ID}][ERROR] {message}{RESET}")

def print_info(message):
    print(f"{BLUE}[{SCRIPT_ID}][INFO] {message}{RESET}")

# Global session with custom headers
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
    Performs a GET request with a random delay (between 2 and 5 seconds) after a successful request,
    to avoid rate limits. Retries on 429 responses.
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
            
            sleep_time = random.uniform(0, 2)
            if st:
                with st.spinner(f"Waiting for {sleep_time:.1f} seconds to avoid rate limits...", show_time=True):
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

def extract_team_id_and_name(url):
    """
    Extracts the team ID and team name from a team URL.
    Supports both URL formats:
      1. https://fbref.com/fr/equipes/<TEAM_ID>/Statistiques-<TEAM_NAME>
      2. https://fbref.com/fr/equipes/<TEAM_ID>/historique/Stats-et-historique-de-<TEAM_NAME>
    Returns (team_id, team_name) or (None, None) if not found.
    """
    patterns = [
        r"/fr/equipes/([^/]+)/Statistiques-(.+)$",
        r"/fr/equipes/([^/]+)/historique/Stats-et-historique-de-(.+)$"
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1), match.group(2)
    return None, None

def build_h2h_url(home_url, away_url):
    """
    Builds the final head-to-head (H2H) URL from two team URLs.
    Example:
      home_url = "https://fbref.com/fr/equipes/e2d8892c/Statistiques-Paris-Saint-Germain"
                or "https://fbref.com/fr/equipes/d01a653b/historique/Stats-et-historique-de-Argentinos-Juniors"
      away_url = "https://fbref.com/fr/equipes/5c2737db/Statistiques-Le-Havre"
      => "https://fbref.com/fr/stathead/matchup/teams/e2d8892c/5c2737db/Historique-Paris-Saint-Germain-contre-Le-Havre"
    """
    home_id, home_name = extract_team_id_and_name(home_url)
    away_id, away_name = extract_team_id_and_name(away_url)
    if not home_id or not away_id or not home_name or not away_name:
        print_error("Unable to build H2H URL. Check the input team URLs.")
        return None
    base = "https://fbref.com/fr/stathead/matchup/teams"
    final_url = f"{base}/{home_id}/{away_id}/Historique-{home_name}-contre-{away_name}"
    return final_url

def parse_scorebox(soup):
    """
    Retrieves and formats information from the div with class "scorebox".
    Splits the text based on "vs.".
    
    Expected format in the first part (before "vs."):
      - The first line is the team name.
      - The following lines are statistics (e.g. "11 victoires", "3 matchs nuls", etc.)
    Each stat line is transformed into a dict, for example:
         "11 victoires" -> {"victoires": "11"}
    The note (after "vs.") is removed.
    
    Returns a dict with keys "home_team" and "away_team".
    """
    scorebox_div = soup.find("div", class_="scorebox")
    if not scorebox_div:
        return {}
    text_content = scorebox_div.get_text(separator="\n", strip=True)
    if "vs." in text_content:
        parts = text_content.split("vs.")
        part1 = parts[0].strip()
        lines = [line.strip() for line in part1.split("\n") if line.strip()]
        if len(lines) % 2 == 0:
            mid = len(lines) // 2
            home_lines = lines[:mid]
            away_lines = lines[mid:]
        else:
            mid = len(lines) // 2
            home_lines = lines[:mid]
            away_lines = lines[mid:]
        
        def transform_team_lines(lines):
            if not lines:
                return []
            team_name = lines[0]
            stats = []
            for line in lines[1:]:
                m = re.match(r"(\d+)\s+(.*)", line)
                if m:
                    stats.append({ m.group(2).lower(): m.group(1) })
                else:
                    stats.append(line)
            return [team_name] + stats
        
        return {
            "home_team": transform_team_lines(home_lines),
            "away_team": transform_team_lines(away_lines)
        }
    else:
        return {"raw_scorebox": text_content}

def parse_games_history_all(soup):
    """
    Retrieves the table with id "games_history_all" and extracts:
      - The header columns.
      - The rows data, omitting empty fields and only including matches from the last 10 years.
      - For the column "Rapport de match", replaces its cell content with the match report URL.
    Returns a dict with keys "header" and "rows".
    """
    table = soup.find("table", id="games_history_all")
    if not table:
        return {"header": [], "rows": []}
    
    header_cols = []
    thead = table.find("thead")
    if thead:
        header_row = thead.find("tr")
        if header_row:
            header_cols = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]
    
    rows_data = []
    tbody = table.find("tbody")
    ten_years_ago = datetime.now() - timedelta(days=10*365)
    if tbody:
        for tr in tbody.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            row_dict = OrderedDict()
            for i, col_name in enumerate(header_cols):
                if i < len(cells):
                    cell = cells[i]
                    cell_text = cell.get_text(strip=True)
                    if cell_text:
                        if col_name.strip().lower() == "rapport de match":
                            a_tag = cell.find("a")
                            if a_tag:
                                link = a_tag.get("href")
                                if link:
                                    row_dict[col_name] = urllib.parse.urljoin("https://fbref.com", link)
                                else:
                                    row_dict[col_name] = cell_text
                            else:
                                row_dict[col_name] = cell_text
                        else:
                            row_dict[col_name] = cell_text
            if row_dict:
                rows_data.append(row_dict)
    
    return {"header": header_cols, "rows": rows_data}

def fetch_h2h_data(home_url, away_url):
    """
    Builds the H2H URL, fetches the page, and parses the scorebox and games_history_all table.
    Then, for each match in the games history (from the last 10 years) that has a match report URL,
    fetches the report page and adds the match stats.
    Returns a dict containing:
      - "h2h_url": the constructed URL.
      - "scorebox": the formatted scorebox data.
      - "games_history_all": the parsed table data, with additional key "match_stats"
        for each match where a report URL is available.
    """
    h2h_url = build_h2h_url(home_url, away_url)
    if not h2h_url:
        return {}
    response = safe_get(h2h_url)
    if not response:
        return {}
    soup = BeautifulSoup(response.content, "lxml")
    scorebox_data = parse_scorebox(soup)
    games_history_data = parse_games_history_all(soup)
    
    return {
        "h2h_url": h2h_url,
        "scorebox": scorebox_data,
        "games_history_all": games_history_data
    }

def write_h2h_json(data, output_file="artifacts/fbref_h2h.json"):
    """
    Writes the H2H data to a JSON file.
    """
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print_success(f"H2H data saved to {output_file}")
    except Exception as e:
        print_error(f"Error writing H2H data to {output_file}: {e}")


# Standalone execution for testing
def get_h2h_data(home_url, away_url):
    data = fetch_h2h_data(home_url, away_url)
    if not data:
        print_error("No H2H data retrieved.")
        return
    write_h2h_json(data, "artifacts/fbref_h2h.json")

if __name__ == "__main__":
    # Example standalone execution
    home = "https://fbref.com/fr/equipes/e2d8892c/Statistiques-Paris-Saint-Germain" 
    away = "https://fbref.com/fr/equipes/5c2737db/Statistiques-Le-Havre"
    get_h2h_data(home, away)
