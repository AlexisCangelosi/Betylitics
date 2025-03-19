import argparse
import sys
import json
import requests
from bs4 import BeautifulSoup
import urllib.parse
import pandas as pd
import re
import time
from collections import OrderedDict  # Pour garantir l'ordre des clés

# Attempt to import Streamlit. If not available, use None.
try:
    import streamlit as st
except ImportError:
    st = None

def transform_url(url):
    """
    Transform the input URL from historical format to the new format.
    Example:
      Input:  https://fbref.com/fr/equipes/d01a653b/historique/Stats-et-historique-de-Argentinos-Juniors
      Output: https://fbref.com/fr/equipes/d01a653b/Statistiques-Argentinos-Juniors
    """
    return url.replace("/historique/Stats-et-historique-de-", "/Statistiques-")

def extract_team_name(url):
    """
    Extract the team name from the page's <h1> text by removing the prefix 
    "Stats et historique de " if present.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "lxml")
        h1 = soup.find("h1")
        if h1:
            h1_text = h1.get_text(strip=True)
            prefix = "Stats et historique de "
            if h1_text.startswith(prefix):
                return h1_text[len(prefix):].strip()
            else:
                return h1_text
        return "Unknown Team"
    except Exception as e:
        return "Unknown Team"

def parse_table(table):
    """
    Parse a table with a two-level header.
    Returns a dictionary with:
      - "header": {"data_tip": {subheader_text: list of formatted data-tip values, ...}}
      - "rows": list of OrderedDicts mapping subheader names to cell data.
    
    Pour la colonne "Joueur", l'URL associée est récupérée (si présente) et insérée en première position sous la clé "Joueur URL".
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
            # Retrieve the data-tip attribute if available
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
                # Pour la colonne "Joueur", récupérer aussi l'URL du lien s'il existe
                if header.lower() == "joueur":
                    a_tag = cell.find("a")
                    player_url = a_tag["href"] if a_tag and a_tag.has_attr("href") else ""
                    # Insérer l'URL en premier
                    row_dict["Joueur URL"] = player_url
                    row_dict[header] = cell.get_text(strip=True)
                else:
                    row_dict[header] = cell.get_text(strip=True)
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

def process_url(url, url_index, total, progress_bar=None):
    """
    Process a single FBref URL with detailed sub-steps updated via the progress bar.
    
    Sub-steps:
      1. Extract team name (transform URL and extract name)
      2. Fetch page (GET request)
      3. Parse standard tables (avec récupération de l'URL du joueur)
      4. Parse extra tables based on a list of id prefixes (e.g. keeper, advanced keeper, etc.)
      5. Merge extra stats into standard tables (only add new data)
      6. Retrieve calendar/results (match logs) and insert into 'venues'
      7. Finalize and return data
    """
    def update_local(fraction, step_text=""):
        if progress_bar:
            overall_progress = int(((url_index + fraction) / total) * 100)
            progress_bar.progress(overall_progress, text=f"URL {url_index+1}/{total}: {step_text}")
    
    # Step 1: Extract team name and transform URL
    update_local(0.1, "Extracting team name")
    team = extract_team_name(url)
    transformed = transform_url(url)
    
    # Step 2: Fetch the page
    update_local(0.2, "Fetching page")
    try:
        response = requests.get(transformed)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching URL: {e}", file=sys.stderr)
        return None
    
    # Step 3: Parse standard tables
    update_local(0.3, "Parsing standard tables")
    soup = BeautifulSoup(response.content, "lxml")
    standard_tables = soup.find_all("table", id=lambda x: x and x.startswith("stats_standard_"))
    standard_tables_data = []
    for table in standard_tables:
        table_data = parse_table(table)
        standard_tables_data.append(table_data)
    
    # Step 4: Parse extra tables based on a list of prefixes (e.g. keeper, advanced keeper, etc.)
    extra_prefixes = ["stats_keeper_", "stats_keeper_adv_", "stats_shooting_", "stats_passing_types_", "stats_gca_", "stats_defense_", "stats_possession_", "stats_playing_time_", "stats_misc_"]
    extra_tables_data = []
    base_progress = 0.4
    update_progress = ((0.7 - 0.4) / len(extra_prefixes))
    for prefix in extra_prefixes:
        update_local(base_progress, f"Parsing extra tables: {prefix}")
        extra_tables = soup.find_all("table", id=lambda x: x and x.startswith(prefix))
        for table in extra_tables:
            table_data = parse_table(table)
            extra_tables_data.append(table_data)
            base_progress = base_progress + update_progress
    
    # Step 5: Merge extra stats into standard tables
    update_local(0.7, "Merging extra stats")
    if extra_tables_data:
        merged_tables = merge_keeper_stats(standard_tables_data, extra_tables_data)
    else:
        merged_tables = standard_tables_data

    # Step 6: Retrieve calendar/results table (match logs) and insert into 'venues'
    update_local(0.8, "Retrieving match logs")
    matchlogs_table = soup.find("table", id=lambda x: x and x.startswith("matchlogs_for"))
    if matchlogs_table:
        matchlogs_data = parse_table(matchlogs_table)
        venues = {"header": matchlogs_data["header"], "venues": matchlogs_data["rows"]}
    else:
        venues = {}
    
    # Step 7: Finalize
    update_local(0.9, "Finalizing data")
    time.sleep(0.2)
    update_local(1.0, "URL processing complete")
    
    return {"team": team, "tables": merged_tables, "venues": venues}

def fetch_fbref_stats(urls, output_file="fbref_stats.json"):
    """
    Process a list of FBref URLs and output a JSON object with the results.
    The progress bar is updated in detail for each URL and its sub-steps if Streamlit is available.
    """
    datasets = []
    total = len(urls)
    
    progress_bar = st.progress(0, text="Starting FBref Stats Fetching...") if st else None

    for index, url in enumerate(urls):
        print(f"Processing URL: {url}")
        data = process_url(url, index, total, progress_bar)
        if data:
            datasets.append(data)
        time.sleep(0.5)
    
    if progress_bar:
        progress_bar.progress(100, text="Processing complete")
        progress_bar.empty()
    
    output = {"datasets": datasets}
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=4, ensure_ascii=False)
        print(f"JSON output saved to {output_file}")
    except Exception as e:
        print(f"Error writing JSON to {output_file}: {e}", file=sys.stderr)
    
    return output

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fetch FBref stats tables and output JSON with data-tip for sub-headers and team name. "
                    "Use --fetch for exactly 2 URLs or --unique for 1 URL."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--fetch", nargs=2, help="Provide exactly 2 FBref URLs to fetch data from")
    group.add_argument("--unique", nargs=1, help="Provide exactly 1 FBref URL to fetch data from")
    args = parser.parse_args()

    urls = []
    if args.fetch:
        urls = args.fetch
    elif args.unique:
        urls = args.unique
    else:
        url_input = input("Please enter a FBref URL: ").strip()
        if url_input:
            urls = [url_input]
        else:
            print("No URL provided. Exiting.", file=sys.stderr)
            sys.exit(1)

    fetch_fbref_stats(urls)
