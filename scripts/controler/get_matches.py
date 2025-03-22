#!/usr/bin/env python
"""
Script: get_matches.py
Description:
    Ce script prend en argument une date (ex: 2025-03-22) et forme une URL de la forme:
        https://fbref.com/fr/matchs/2025-03-22
    Il ouvre ensuite le fichier JSON "artefacts/fbref_data_clubs.json" et, pour chaque div
    dont l'id commence par "all_sched_", il récupère les href contenus dans les balises h2.
    Pour chaque href, il vérifie si l'URL de match est présente dans le fichier JSON (dans la partie "League URL").
    Si c'est le cas, il extrait la table présente dans la div (dont l'id commence par "sched_"),
    transforme son contenu en données structurées et ajoute :
      - "Domicile URL" et "Extérieur URL" extraites des cellules correspondantes,
      - "h2h_url" construite à partir de ces deux URLs.
    Le résultat final est enregistré dans le fichier "fbref_matches.json" sous forme d'une liste plate de dictionnaires.
    
Usage:
    python get_matches.py 2025-03-22
"""

import argparse
import json
import os
import re
import sys
import uuid

import requests
from bs4 import BeautifulSoup

# --- Fonctions pour extraire et construire l'URL H2H ---

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
      away_url = "https://fbref.com/fr/equipes/5c2737db/Statistiques-Le-Havre"
      => "https://fbref.com/fr/stathead/matchup/teams/e2d8892c/5c2737db/Historique-Paris-Saint-Germain-contre-Le-Havre"
    """
    home_id, home_name = extract_team_id_and_name(home_url)
    away_id, away_name = extract_team_id_and_name(away_url)
    if not home_id or not away_id or not home_name or not away_name:
        print("[ERROR] Unable to build H2H URL. Check the input team URLs.")
        return None
    base = "https://fbref.com/fr/stathead/matchup/teams"
    final_url = f"{base}/{home_id}/{away_id}/Historique-{home_name}-contre-{away_name}"
    return final_url

# --- Fonctions utilitaires ---

def url_in_json(url, data):
    """
    Recherche récursive de l'URL dans une structure JSON.
    Retourne True si la chaîne url est trouvée dans n'importe quelle valeur de type str.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if url_in_json(url, value):
                return True
    elif isinstance(data, list):
        for item in data:
            if url_in_json(url, item):
                return True
    elif isinstance(data, str):
        if data.strip() == url.strip():
            return True
    return False

def extract_table_from_div(div):
    """
    Recherche dans la div un enfant dont l'id commence par "div_sched_" 
    (ou "sched_") et retourne le HTML de la première table trouvée.
    Retourne None s'il n'y a pas de table.
    """
    sched_div = div.find(lambda tag: tag.has_attr('id') and (tag['id'].startswith("div_sched_") or tag['id'].startswith("sched_")))
    if sched_div:
        table = sched_div.find("table")
        if table:
            return str(table)
    table = div.find("table")
    if table:
        return str(table)
    return None

def parse_table_html(table_html):
    """
    Parse the HTML content of a table and return its data as a list of dictionaries.
    Each dictionary represents a row in the table, with keys derived from the table headers.
    Pour les colonnes "Domicile" et "Extérieur", si une balise <a> est présente, on ajoute
    également les clés "Domicile URL" et "Extérieur URL".
    
    Parameters:
        table_html (str): The HTML content of the table.
    
    Returns:
        list: A list of dictionaries with the table data.
    """
    soup = BeautifulSoup(table_html, "html.parser")
    
    # Extraction des en-têtes
    headers = []
    thead = soup.find("thead")
    if thead:
        header_row = thead.find("tr")
        if header_row:
            headers = [th.get_text(strip=True) for th in header_row.find_all("th")]
    
    data = []
    tbody = soup.find("tbody")
    if tbody:
        for row in tbody.find_all("tr"):
            cells = row.find_all(["td", "th"])
            row_data = {}
            for i, cell in enumerate(cells):
                key = headers[i] if i < len(headers) else f"col_{i+1}"
                cell_text = cell.get_text(strip=True)
                row_data[key] = cell_text
                # Pour "Domicile"
                if key.lower() == "domicile":
                    a_tag = cell.find("a")
                    if a_tag and a_tag.has_attr("href"):
                        row_data["Domicile URL"] = f"https://fbref.com{a_tag['href']}"
                # Pour "Extérieur" (prendre en compte "Exterieur" sans accent aussi)
                if key.lower() in ["extérieur", "exterieur"]:
                    a_tag = cell.find("a")
                    if a_tag and a_tag.has_attr("href"):
                        row_data["Extérieur URL"] = f"https://fbref.com{a_tag['href']}"
            # Si les deux URLs sont présentes, construire le h2h_url
            home_url = row_data.get("Domicile URL")
            away_url = row_data.get("Extérieur URL")
            if home_url and away_url:
                h2h = build_h2h_url(home_url, away_url)
                if h2h:
                    row_data["h2h_url"] = h2h
            row_data["ID"] = uuid.uuid4().hex[:6]
            data.append(row_data)
    return data

# --- Fonction principale get_matches ---

def get_matches(date_str):
    # 1. Former l'URL à partir de la date
    url = f"https://fbref.com/fr/matchs/{date_str}"
    print(f"[INFO] Formation de l'URL : {url}")
    
    # 2. Charger le fichier JSON des clubs
    clubs_json_path = os.path.join("artifacts", "fbref_data_clubs.json")
    try:
        with open(clubs_json_path, "r", encoding="utf-8") as f:
            clubs_data = json.load(f)
    except Exception as e:
        print(f"[ERROR] Impossible d'ouvrir {clubs_json_path}: {e}")
        sys.exit(1)
    
    # 3. Requête HTTP et parsing de l'HTML
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] La requête HTTP a échoué: {e}")
        sys.exit(1)
    
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Liste pour stocker les lignes extraites de toutes les tables
    all_rows = []
    
    # 4. Parcourir chaque div dont l'id commence par "all_sched_"
    all_sched_divs = soup.find_all("div", id=lambda x: x and x.startswith("all_sched_"))
    for div in all_sched_divs:
        h2_tags = div.find_all("h2")
        for h2 in h2_tags:
            # Récupérer le texte du span dans le h2 et le convertir en majuscules
            span_tag = h2.find("span")
            country_code = span_tag.get_text(strip=True).upper() if span_tag else ""
            
            a_tag = h2.find("a")
            if a_tag and a_tag.has_attr("href"):
                match_href = f"https://fbref.com{a_tag['href']}"
                if url_in_json(match_href, clubs_data):
                    table_html = extract_table_from_div(div)
                    if table_html:
                        table_data = parse_table_html(table_html)
                        # Ajouter la valeur du pays dans chaque ligne
                        for row in table_data:
                            row["Country"] = country_code
                        all_rows.extend(table_data)

    
    # 5. Enregistrer le résultat dans fbref_matches.json (liste plate de dictionnaires)
    output_path = "artifacts/fbref_matches.json"
    try:
        with open(output_path, "w", encoding="utf-8") as f_out:
            json.dump(all_rows, f_out, indent=4, ensure_ascii=False)
        print(f"[INFO] Résultat écrit dans {output_path}")
    except Exception as e:
        print(f"[ERROR] Impossible d'écrire dans {output_path}: {e}")
        sys.exit(1)
    
    return all_rows

# --- Exécution principale ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extraire les table_data des matches à partir d'une date donnée")
    parser.add_argument("date", type=str, help="Date au format YYYY-MM-DD (ex: 2025-03-22)")
    args = parser.parse_args()
    
    get_matches(args.date)
