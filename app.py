import streamlit as st
import json
import pandas as pd
import numpy as np
import time
import re
from datetime import datetime
from streamlit_option_menu import option_menu
from scripts.controler.get_team_data import fetch_fbref_stats
from scripts.controler.get_players_data import update_fbref_players_data
from scripts.controler.get_h2h_data import get_h2h_data
from scripts.controler.get_matches import get_matches
from scripts.views.h2h import head_to_head_section
from scripts.views.statistics import display_statistics

# --- Page Configuration ---
st.set_page_config(page_title="Betylitics", layout="wide")

# --- Load JSON Data ---
with open("artifacts/fbref_data_clubs.json", "r", encoding="utf-8") as f:
    data = json.load(f)

with open("artifacts/fbref_matches.json", "r", encoding="utf-8") as f2:
    venues = json.load(f2)

with open("artifacts/fbref_stats.json", "r", encoding="utf-8") as f3:
    infos = json.load(f3)

# Extraire et trier les pays : ceux avec Featured=true en premier.
featured_countries = [country for country, details in data.items() if details.get("Featured", False)]
other_countries = sorted([country for country in data.keys() if country not in featured_countries])
sorted_countries = featured_countries + other_countries

display_to_country_key = {country.replace("Clubs de football de ", ""): country for country in sorted_countries}
displayed_countries = list(display_to_country_key.keys())


def get_clubs(country_key, league):
    # Récupère la liste des clubs pour un pays et une ligue donnée
    return data[country_key]["League"].get(league, [])

def reset_json_files():
    """
    Supprime le contenu des fichiers JSON en les écrasant avec un objet JSON vide.
    """
    files = ["artifacts/fbref_h2h.json", "artifacts/fbref_stats.json"]
    for file in files:
        try:
            # Ouvre le fichier en écriture et écrase son contenu avec un objet JSON vide.
            with open(file, "w", encoding="utf-8") as f:
                f.write("{}")
        except Exception as e:
            st.toast(f"Erreur lors de la réinitialisation",icon="🚨")
    st.toast(f"Analyse réinitialisé.",icon='🔄')

def extract_team_name(team_str: str) -> str:
    """
    Extracts the team name from a full string.
    Expected format:
      "Statistiques YYYY-YYYY TEAM_NAME(Ligue ...)"
    Returns the TEAM_NAME part, e.g., "Strasbourg" or "Lyon".
    """
    match = re.search(r"Statistiques\s+\d{4}-\d{4}\s+([^(]+)", team_str)
    if match:
        return match.group(1).strip()
    # Fallback: remove the "Statistiques" prefix and anything in parentheses.
    team_str = team_str.replace("Statistiques", "").strip()
    if "(" in team_str:
        team_str = team_str.split("(")[0].strip()
    return team_str


st.logo(image="assets/logo.png", size="large", icon_image="assets/logo.png")
# --- Sidebar: Sélection des équipes ---
with st.sidebar:
    # Create three columns with adjustable width proportions
    col1, col2, col3 = st.columns([3, 2, 1])  # Adjust these numbers as needed for layout proportions

    with col1:
        # Options for the pills component
        options = ["Events", "Manual"]
        # Display the pills component (assuming st.pills is available in your version)
        selection = st.pills("Search", options, selection_mode="multi", default="Events")

    with col3:
        # Display the image (logo) with a fixed width
        st.image("assets/logo.png", width=100)

    if "Manual" in selection:
        same_settings = st.toggle("Use same league for away", value=True)
        if same_settings:
            selected_country_display = st.selectbox("Country", displayed_countries, key="country")
            # Dans la nouvelle structure, la clé du pays est le nom lui-même.
            actual_country_key = display_to_country_key[selected_country_display]
            country_data = data[actual_country_key]
            # Récupérer la liste des ligues pour ce pays
            leagues = list(country_data.get("League", {}).keys())
            # Trier les ligues : celles figurant dans "Featured_league" en premier
            featured_leagues = country_data.get("Featured_league", [])
            other_leagues = sorted([league for league in leagues if league not in featured_leagues])
            sorted_leagues = featured_leagues + other_leagues
            league = st.selectbox("League", sorted_leagues, key="league")
            clubs = get_clubs(actual_country_key, league)
            col1, col2 = st.columns(2)
            with col1:
                club1 = st.selectbox("🔵 Home Team", [club["Club Name"] for club in clubs], key="club1")
            with col2:
                club2 = st.selectbox("🔴 Away Team", [club["Club Name"] for club in clubs if club["Club Name"] != club1], key="club2")
        else:
            col1, col2 = st.columns(2)
            with col1:
                selected_country_display1 = st.selectbox("Country", displayed_countries, key="country1")
                actual_country_key1 = display_to_country_key[selected_country_display1]
                country_data1 = data[actual_country_key1]
                leagues1 = list(country_data1.get("League", {}).keys())
                featured_leagues1 = country_data1.get("Featured_league", [])
                other_leagues1 = sorted([league for league in leagues1 if league not in featured_leagues1])
                sorted_leagues1 = featured_leagues1 + other_leagues1
                league1 = st.selectbox("League", sorted_leagues1, key="league1")
                clubs1 = get_clubs(actual_country_key1, league1)
                club1 = st.selectbox("🔵 Home Team", [club["Club Name"] for club in clubs1], key="club1")
            with col2:
                selected_country_display2 = st.selectbox("Country", displayed_countries, key="country2")
                actual_country_key2 = display_to_country_key[selected_country_display2]
                country_data2 = data[actual_country_key2]
                leagues2 = list(country_data2.get("League", {}).keys())
                featured_leagues2 = country_data2.get("Featured_league", [])
                other_leagues2 = sorted([league for league in leagues2 if league not in featured_leagues2])
                sorted_leagues2 = featured_leagues2 + other_leagues2
                league2 = st.selectbox("League", sorted_leagues2, key="league2")
                clubs2 = get_clubs(actual_country_key2, league2)
                club2 = st.selectbox("🔴 Away Team", [club["Club Name"] for club in clubs2], key="club2")

        if same_settings:
            club1_url = next((club["Club URL"] for club in clubs if club["Club Name"] == club1), None)
            club2_url = next((club["Club URL"] for club in clubs if club["Club Name"] == club2), None)
        else:
            club1_url = next((club["Club URL"] for club in clubs1 if club["Club Name"] == club1), None)
            club2_url = next((club["Club URL"] for club in clubs2 if club["Club Name"] == club2), None)

        col_buttons = st.columns(2, gap="small")
        with col_buttons[0]:
            start_full = st.button("🚀 Full analysis")
        with col_buttons[1]:
            start_fast = st.button("⚡ Fast analysis")

        analysis_completed = False

        if start_full:
            if club1_url and club2_url:
                info_placeholder = st.empty()
                start_time = time.time()
                
                info_placeholder.info("🚀 Analyse des teams...")
                fetch_fbref_stats([club1_url, club2_url])
                info_placeholder.info("✅ Récupération des clubs terminée...")
                
                info_placeholder.info("🚀 Analyse des joueurs...")
                update_fbref_players_data()
                info_placeholder.info("✅ Récupération des joueurs terminée...")
                
                info_placeholder.info("🚀 Analyse des confrontations...")
                get_h2h_data(club1_url, club2_url)
                info_placeholder.info("✅ Récupération des confrontations terminée...")
                
                end_time = time.time()
                elapsed_time = end_time - start_time
                minutes = int(elapsed_time // 60)
                seconds = int(elapsed_time % 60)
                info_placeholder.success(f"Analyse full terminée en {minutes}:{seconds} min.")
                analysis_completed = True
            else:
                st.markdown('<p style="color:red;">⚠️ Unable to retrieve the URLs for the selected clubs.</p>', unsafe_allow_html=True)
        elif start_fast:
            if club1_url and club2_url:
                info_placeholder = st.empty()
                start_time = time.time()
                info_placeholder.info("⚡ Analyse des teams...")
                
                fetch_fbref_stats([club1_url, club2_url])
                info_placeholder.success("✅ Récupération des clubs terminée.")
                
                info_placeholder.info("⚡ Analyse des confrontations...")
                get_h2h_data(club1_url, club2_url)
                info_placeholder.info("✅ Récupération des confrontations terminée...")
                
                end_time = time.time()
                elapsed_time = end_time - start_time
                elapsed_seconds = int(elapsed_time)
                info_placeholder.success(f"Analyse rapide terminée en {elapsed_seconds} sec.")
                analysis_completed = True
            else:
                st.markdown('<p style="color:red;">⚠️ Unable to retrieve the URLs for the selected clubs.</p>', unsafe_allow_html=True)

        st.divider()

    if "Events" in selection:
        # --- Initialisation de la session ---
        if "matches" not in st.session_state:
            st.session_state.matches = []
        if "selected_match" not in st.session_state:
            st.session_state.selected_match = None
        if "analysis_started" not in st.session_state:
            st.session_state.analysis_started = False

        # 1. Sélection de la date et bouton de recherche
        selected_date = st.date_input("Select date", datetime.now())
        search = st.button("🔍 Search")

        if search:
            # Convertir la date en format "YYYY-MM-DD" pour get_matches()
            date_str = selected_date.strftime("%Y-%m-%d")
            # get_matches() doit retourner une liste de dictionnaires représentant les matches
            st.session_state.matches = get_matches(date_str)
            st.session_state.analysis_started = False  # Réinitialiser l'analyse

        # 2. Si des matches sont disponibles, afficher la selectbox pour le choix du match
        if st.session_state.matches and isinstance(st.session_state.matches, list) and len(st.session_state.matches) > 0:
            # Trier les matches par heure croissante
            sorted_matches = sorted(st.session_state.matches, key=lambda m: m.get("Heure", "00:00"))
            match_options = []
            match_mapping = {}
            for m in sorted_matches:
                display_str = (
                    f"{m.get('Country', 'Unknown')}/{m.get('Tour', 'Unknown')} - "
                    f"{m.get('Domicile', 'N/A')} vs {m.get('Extérieur', 'N/A')} ({m.get('Heure', 'N/A')})"
                )
                match_options.append(display_str)
                match_mapping[display_str] = m
            # Afficher la selectbox; l'option sélectionnée est stockée dans st.session_state.selected_match
            selected_match_display = st.selectbox("Matches", match_options, index=0)
            st.session_state.selected_match = match_mapping[selected_match_display]

            # 3. Boutons pour lancer l'analyse
            col_buttons = st.columns(2, gap="small")
            with col_buttons[0]:
                start_event_full = st.button("🚀 Event Full analysis")
            with col_buttons[1]:
                start_event_fast = st.button("⚡ Event Fast analysis")

            # Si l'un des boutons est pressé, on passe en mode analyse sans réinitialiser l'interface
            if start_event_full or start_event_fast:
                st.session_state.analysis_started = True

            # 4. Si l'analyse a été lancée, afficher les informations et exécuter l'analyse
            if st.session_state.analysis_started and st.session_state.selected_match:
                selected_match = st.session_state.selected_match
                match_id = selected_match.get("ID", "Unknown")
                home_url = selected_match.get("Domicile URL", "N/A")
                away_url = selected_match.get("Extérieur URL", "N/A")

                if start_event_full:
                    if home_url != "N/A" and away_url != "N/A":
                        info_placeholder = st.empty()
                        start_time = time.time()
                        info_placeholder.info("🚀 Analyse des teams...")
                        fetch_fbref_stats([home_url, away_url])
                        info_placeholder.info("✅ Récupération des clubs terminée...")
                        info_placeholder.info("🚀 Analyse des joueurs...")
                        update_fbref_players_data()
                        info_placeholder.info("✅ Récupération des joueurs terminée...")
                        info_placeholder.info("🚀 Analyse des confrontations...")
                        get_h2h_data(home_url, away_url)
                        info_placeholder.info("✅ Récupération des confrontations terminée...")
                        elapsed = time.time() - start_time
                        minutes = int(elapsed // 60)
                        seconds = int(elapsed % 60)
                        info_placeholder.success(f"Analyse full terminée en {minutes}:{seconds} min.")
                    else:
                        st.error("⚠️ Unable to retrieve the URLs for the selected clubs.")
                elif start_event_fast:
                    if home_url != "N/A" and away_url != "N/A":
                        info_placeholder = st.empty()
                        start_time = time.time()
                        info_placeholder.info("⚡ Analyse des teams...")
                        fetch_fbref_stats([home_url, away_url])
                        info_placeholder.success("✅ Récupération des clubs terminée.")
                        info_placeholder.info("⚡ Analyse des confrontations...")
                        get_h2h_data(home_url, away_url)
                        info_placeholder.info("✅ Récupération des confrontations terminée.")
                        elapsed = time.time() - start_time
                        info_placeholder.success(f"Analyse rapide terminée en {int(elapsed)} sec.")
                    else:
                        st.error("⚠️ Unable to retrieve the URLs for the selected clubs.")
        else:
            st.info("Aucun match n'a été trouvé pour cette date.")
    
    if st.button("🗑️ Reset"):
        reset_json_files()
    # Assume this timestamp is when your data was last updated.
    # For example, here we simulate it with a timestamp from one hour ago.
    last_updated_str = "2025-03-22 02:32"  # Replace this with your actual update time
    # For demonstration, we subtract 1 hour:
    last_updated = datetime.strptime(last_updated_str, "%Y-%m-%d %H:%M")

    # Compute the time difference
    now = datetime.now()
    time_diff = now - last_updated
    hours_ago = int(time_diff.total_seconds() // 3600)
    minutes_ago = int((time_diff.total_seconds() % 3600) // 60)

    # Create a dynamic update message
    if hours_ago > 0:
        update_message = f"🗘 {hours_ago} hour{'s' if hours_ago > 1 else ''} ago"
    else:
        update_message = f"🗘 {minutes_ago} minute{'s' if minutes_ago > 1 else ''} ago"

    st.caption(f"⚙️ v1.0.0-20250322.9914 - {update_message}")

# --- Menu principal via option_menu ---
datasets = infos.get("datasets", [])
team_names = [extract_team_name(ds.get("team", "Unknown")) for ds in datasets]
if len(team_names) >= 2:
        st.subheader(f"{team_names[0]} vs {team_names[1]}")

selected_main = option_menu(
    menu_title=None,
    options=["H2H", "Statistics", "Facts"],
    icons=["diagram-2", "bar-chart-line", "info-circle"],
    orientation="horizontal",
    default_index=0,
    styles={
        "container": {"padding": "0px", "background-color": "rgba(0,0,0,0)"},
        "nav-link": {"background-color": "rgba(0,0,0,0)", "font-size": "14px", "text-align": "center", "margin": "0px", "--hover-color": "rgba(255,255,255,0.1)"},
        "nav-link-selected": {"background-color": "rgba(0,0,0,0)", "border-bottom": "3px solid green", "font-weight": "bold"},
    },
)

if selected_main == "H2H":
    head_to_head_section()
elif selected_main == "Statistics":
    display_statistics()
elif selected_main == "Facts":
    st.write("Autres faits et informations.")
