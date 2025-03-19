import argparse
import sys
import json
import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
import time
from collections import OrderedDict
from tqdm import tqdm  # Progress bar en console

# Base URL pour compléter les URLs relatives, si nécessaire.
BASE_URL = "https://fbref.com"

# Création d'une session globale avec un User-Agent personnalisé
session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/90.0.4430.93 Safari/537.36"
    )
})

def safe_get(url, retries=5, initial_delay=5):
    """
    Effectue un GET en appliquant un backoff exponentiel en cas de code 429.
    Retourne le response si le code HTTP est 200, sinon lève une exception.
    """
    delay = initial_delay
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url)
            if response.status_code == 429:
                print(f"[WARNING] 429 pour {url}. Attente de {delay} s (tentative {attempt}/{retries}).")
                time.sleep(delay)
                delay *= 2
                continue
            response.raise_for_status()
            return response
        except Exception as e:
            if attempt == retries:
                print(f"[ERROR] Echec après {retries} tentatives pour {url}: {e}")
                raise e
            else:
                print(f"[WARNING] Erreur lors de l'accès à {url}: {e}. Nouvelle tentative dans {delay} s (tentative {attempt}/{retries}).")
                time.sleep(delay)
                delay *= 2
    return None

def read_json(filename):
    """Lit un fichier JSON et retourne les données."""
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(data, filename):
    """Écrit les données dans un fichier JSON."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"JSON file '{filename}' updated.")

def parse_table(table):
    """
    Analyse une table avec un header à deux niveaux.
    Retourne un dictionnaire contenant :
      - "header": {"data_tip": {nom_du_subheader: liste de valeurs formatées, ...}}
      - "rows": une liste d'OrderedDict respectant l'ordre des colonnes.
    
    Pour la colonne "Joueur", si un lien est présent, l'URL du joueur est extraite
    (complétée avec BASE_URL si nécessaire) et insérée en première position sous la clé "Joueur URL".
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
    Pour une URL de joueur, récupère la page du joueur et extrait :
      - L'URL de la photo (dans div#info > div.media-item img)
      - Tout le texte des balises <p> dans div#info
      - Le palmarès (contenu dans <ul id="bling">)
      - La table scout_summary_* (si présente)
      - La table last_5_matchlogs (si présente)
    
    Retourne un dictionnaire avec ces informations.
    """
    # Vérifier si l'URL est complète
    if not player_url.startswith("http"):
        player_url = urllib.parse.urljoin(BASE_URL, player_url)
    try:
        response = safe_get(player_url)
    except Exception as e:
        print(f"[ERROR] Impossible de récupérer {player_url}: {e}", file=sys.stderr)
        return {}
    
    soup = BeautifulSoup(response.content, "lxml")
    
    info_div = soup.find("div", id="info")
    if not info_div:
        return {}
    
    additional_info = {}
    
    # 1. Photo URL
    meta_div = info_div.find("div", id="meta")
    photo_url = ""
    if meta_div:
        media_item = meta_div.find("div", class_="media-item")
        if media_item:
            img = media_item.find("img")
            if img and img.has_attr("src"):
                photo_url = img["src"]
    additional_info["photo_url"] = photo_url
    
    # 2. Texte complémentaire (tous les <p> de div#info)
    p_tags = info_div.find_all("p")
    additional_info["info"] = [p.get_text(strip=True) for p in p_tags if p.get_text(strip=True)]
    
    # 3. Palmares depuis <ul id="bling">
    palmares = []
    bling_ul = info_div.find("ul", id="bling")
    if bling_ul:
        for li in bling_ul.find_all("li"):
            item = {"text": li.get_text(strip=True)}
            if li.has_attr("data-tip"):
                item["data_tip"] = li["data-tip"].strip()
            palmares.append(item)
    additional_info["palmares"] = palmares
    
    # 4. Table scout_summary_*
    scout_summary_table = soup.find("table", id=lambda x: x and x.startswith("scout_summary_"))
    if scout_summary_table:
        additional_info["scout_summary"] = parse_table(scout_summary_table)
    else:
        additional_info["scout_summary"] = {}
    
    # 5. Table last_5_matchlogs
    last_5_table = soup.find("table", id="last_5_matchlogs")
    if last_5_table:
        additional_info["last_5_matchlogs"] = parse_table(last_5_table)
    else:
        additional_info["last_5_matchlogs"] = {}
    
    return additional_info

def process_players_data(data):
    """
    Parcourt chaque dataset, chaque table et chaque joueur dans le JSON.
    Pour chaque joueur, récupère l'URL (clé "Joueur URL") et scrappe les informations complémentaires.
    Les données récupérées sont ajoutées dans le sous-élément "additional_info" du joueur.
    Une barre de progression (tqdm) suit le traitement des joueurs.
    """
    total_players = 0
    # Comptabilisation du nombre total de joueurs à traiter
    for dataset in data.get("datasets", []):
        for table in dataset.get("tables", []):
            total_players += len(table.get("rows", []))
    
    pbar = tqdm(total=total_players, desc="Mise à jour des joueurs", unit="joueur")
    
    for dataset in data.get("datasets", []):
        for table in dataset.get("tables", []):
            for row in table.get("rows", []):
                player_url = row.get("Joueur URL", "").strip()
                if player_url:
                    # Récupère les infos complémentaires avec safe_get et update progressif
                    additional_info = get_player_additional_info(player_url)
                    row["additional_info"] = additional_info
                    time.sleep(0.3)  # Pause courte pour limiter les requêtes
                pbar.update(1)
    pbar.close()
    return data

def update_fbref_players_data(json_file="fbref_stats.json"):
    """
    Lit le fichier JSON (json_file), enrichit les données de chaque joueur en récupérant
    les informations complémentaires depuis sa page FBref et met à jour le même fichier.
    
    Retourne les données mises à jour.
    """
    data = read_json(json_file)
    data = process_players_data(data)
    write_json(data, json_file)
    return data

# Permet d'appeler la fonction depuis la ligne de commande ou de l'importer dans un autre script
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Enrichit le JSON fbref_stats avec des informations supplémentaires pour chaque joueur."
    )
    parser.add_argument("--file", default="fbref_stats.json", help="Chemin vers le fichier JSON à mettre à jour")
    args = parser.parse_args()
    update_fbref_players_data(args.file)
