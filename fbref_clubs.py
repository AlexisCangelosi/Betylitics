import os
import sys
import json
import time
import random  # For random delay between requests
import requests
from bs4 import BeautifulSoup
from colorama import Fore, Style, init
from helper import create_parser, log_info, log_success, log_error, log_warning
from tqdm import tqdm

# Initialize colorama for colored terminal output
init(autoreset=True)

# Create a session with a custom User-Agent header
session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/90.0.4430.93 Safari/537.36"
    )
})

def fetch_clubs_from_url(country_name, url):
    """
    Fetches the clubs table from a given country's URL.
    
    Processes the table with id="clubs" by:
      - Dropping columns 4 to 7 (0-indexed: indices 3,4,5,6).
      - Extracting URLs from column 1 (cell index 0) and column 3 (cell index 2).
      - Skipping rows where the third column is empty.
    
    Implements an exponential backoff retry mechanism to handle HTTP 429 errors.
    If maximum retries are reached without success, the script aborts.
    
    At the end of fetching the clubs for a country, a random delay (with progress bar)
    is applied to simulate human-like pacing.
    
    Parameters:
        country_name (str): Name of the country (for logging purposes).
        url (str): The URL of the country's fbref page.
    
    Returns:
        list: A list of club dictionaries.
    """
    retries = 5
    initial_delay = 10  # Initial delay in seconds for backoff
    delay = initial_delay
    response = None

    for attempt in range(1, retries + 1):
        try:
            response = session.get(url)
            if response.status_code == 429:
                log_warning(
                    f"Received 429 Too Many Requests for {url}. "
                    f"Waiting {delay} seconds (attempt {attempt}/{retries})."
                )
                # Show progress bar for retry delay
                for _ in tqdm(range(int(delay * 10)), desc="Retry Delay", unit="0.1s", leave=False):
                    time.sleep(0.1)
                delay *= 2  # Exponential backoff: double the delay each time
            else:
                break  # Exit the loop if we don't get a 429
        except Exception as e:
            log_error(f"Exception fetching {url}: {e}")
            sys.exit(1)

    if response is None or response.status_code != 200:
        log_error(
            f"Error fetching {url}: {response.status_code if response else 'No Response'}. "
            "Maximum retries reached. Aborting script."
        )
        sys.exit(1)
    else:
        log_info(f"Fetched page for country '{country_name}': {url}")
    
    soup = BeautifulSoup(response.content, 'lxml')
    clubs_table = soup.find("table", id="clubs")
    if clubs_table is None:
        log_warning(f"No clubs table found for {country_name} at {url}")
        return []
    
    tbody = clubs_table.find('tbody')
    if not tbody:
        log_warning(f"No table body found in clubs table for {country_name} at {url}")
        return []
    
    clubs = []
    rows = tbody.find_all('tr')
    for row in rows:
        cells = row.find_all(['th', 'td'])
        if not cells:
            continue
        
        # Extract text for every cell
        row_texts = [cell.get_text(strip=True) for cell in cells]
        
        # Skip rows that don't have enough columns to drop the unwanted ones.
        # Expect at least 8 cells if we want to drop cells 3 to 6.
        if len(row_texts) < 8:
            continue
        
        # Drop columns 4 to 7 (0-indexed: indices 3,4,5,6)
        filtered_texts = row_texts[:3] + row_texts[7:]
        
        # Extract URL from the first cell (Club URL)
        club_url = None
        a_tag = cells[0].find('a')
        if a_tag and a_tag.has_attr('href'):
            club_url = a_tag['href']
            if not club_url.startswith("http"):
                club_url = 'https://fbref.com' + club_url

        # Extract URL from the third cell (League URL)
        league_url = None
        a_tag_league = cells[2].find('a')
        if a_tag_league and a_tag_league.has_attr('href'):
            league_url = a_tag_league['href']
            if not league_url.startswith("http"):
                league_url = 'https://fbref.com' + league_url
        
        # Only keep rows where the third column (after filtering) is not empty.
        if len(filtered_texts) < 3 or not filtered_texts[2]:
            continue
        
        # Construct a club dictionary.
        # Assume:
        #   - filtered_texts[0] is the Club Name.
        #   - filtered_texts[1] is the "Sexe" field.
        #   - filtered_texts[2] is the League name.
        #   - filtered_texts[3:] contains additional information.
        club_data = {
            "Club Name": filtered_texts[0],
            "Sexe": filtered_texts[1],
            "League": filtered_texts[2],
            "Additional": filtered_texts[3:] if len(filtered_texts) > 3 else [],
            "Club URL": club_url,
            "League URL": league_url
        }
        clubs.append(club_data)
    
    # Apply a random delay with progress bar at the end of the fetch for this country
    delay_after_fetch = random.uniform(2, 5)
    log_info(f"Waiting {delay_after_fetch:.1f} seconds before finishing fetch for {country_name}...")
    for _ in tqdm(range(int(delay_after_fetch * 10)), desc="Club Fetch Delay", unit="0.1s", leave=False):
        time.sleep(0.1)
    
    log_success(f"Found {len(clubs)} clubs for {country_name}")
    return clubs

def update_clubs_json(new_clubs, output_file="fbref_data_clubs.json"):
    """
    Updates (or creates) the JSON file grouping clubs by country and then by league.
    
    The JSON structure will be:
        {
            "Country1": {
                "League1": [ list of clubs ],
                "League2": [ list of clubs ]
            },
            "Country2": { ... }
        }
    
    If a club (identified by its 'Club Name') is already present in the specified country and league,
    it is not added again.
    
    Parameters:
        new_clubs (list): A list of tuples (country_name, club_data).
        output_file (str): The JSON file to update.
    """
    # Load existing data if file exists
    if os.path.exists(output_file):
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                clubs_data = json.load(f)
        except Exception as e:
            log_error(f"Error reading {output_file}: {e}")
            clubs_data = {}
    else:
        clubs_data = {}
    
    added_count = 0
    for country, club in new_clubs:
        country_entry = clubs_data.get(country, {})
        league = club.get("League", "Unknown League")
        league_clubs = country_entry.get(league, [])
        
        # Check if the club already exists in this league (by club name)
        exists = any(existing.get("Club Name") == club.get("Club Name") for existing in league_clubs)
        if not exists:
            league_clubs.append(club)
            country_entry[league] = league_clubs
            clubs_data[country] = country_entry
            added_count += 1
    
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(clubs_data, f, indent=4, ensure_ascii=False)
        log_success(f"Updated clubs JSON file '{output_file}'. {added_count} new clubs added.")
    except Exception as e:
        log_error(f"Error writing to {output_file}: {e}")

def fetch_fbref_clubs(countries_file="fbref_data_countries.json", output_file="fbref_data_clubs.json"):
    """
    Main function that:
      - Loads countries data from the specified JSON file.
      - For each country, fetches the clubs table from its URL.
      - Processes and filters the clubs data.
      - Updates the clubs JSON file grouping clubs by country then by league.
    
    Introduces a random delay between processing each country (with progress bar)
    to reduce the risk of 429 errors.
    
    Parameters:
        countries_file (str): The input JSON file with countries data.
        output_file (str): The JSON file to update with clubs data.
    """
    # Load countries data
    try:
        with open(countries_file, "r", encoding="utf-8") as f:
            countries_data = json.load(f)
        log_success(f"Loaded countries data from '{countries_file}'.")
    except Exception as e:
        log_error(f"Error loading countries file '{countries_file}': {e}")
        sys.exit(1)
    
    all_new_clubs = []
    for entry in countries_data:
        # Assume the country name is stored under key "Pays" (or "Country" if not)
        country_name = entry.get("Pays") or entry.get("Country") or "Unknown Country"
        country_url = entry.get("Link")
        if not country_url:
            log_warning(f"No URL found for country '{country_name}'. Skipping.")
            continue
        
        clubs = fetch_clubs_from_url(country_name, country_url)
        for club in clubs:
            all_new_clubs.append((country_name, club))
        
        # Add a random delay between 3 and 7 seconds with a progress bar
        delay_between = random.uniform(3, 7)
        log_info(f"Waiting {delay_between:.1f} seconds before processing next country...")
        for _ in tqdm(range(int(delay_between * 10)), desc="Global Delay", unit="0.1s", leave=False):
            time.sleep(0.1)
    
    if all_new_clubs:
        update_clubs_json(all_new_clubs, output_file)
    else:
        log_warning("No new clubs found to update.")

# If this script is run directly, call the main function with default file names.
if __name__ == '__main__':
    fetch_fbref_clubs()
