import streamlit as st
import json
import pandas as pd
import numpy as np
import time
from streamlit_option_menu import option_menu
from scripts.fbref_club_data import fetch_fbref_stats
from scripts.fbref_players_data import update_fbref_players_data
from scripts.fbref_h2h_data import get_h2h_data
from scripts.print_h2h import head_to_head_section

# --- Page Configuration ---
st.set_page_config(page_title="Betylitics", layout="wide")

# --- Load JSON Data ---
with open("artifacts/fbref_data_clubs.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Extraire et trier les pays : ceux avec Featured=true en premier.
featured_countries = [country for country, details in data.items() if details.get("Featured", False)]
other_countries = sorted([country for country in data.keys() if country not in featured_countries])
sorted_countries = featured_countries + other_countries

display_to_country_key = {country.replace("Clubs de football de ", ""): country for country in sorted_countries}
displayed_countries = list(display_to_country_key.keys())


def get_clubs(country_key, league):
    # Récupère la liste des clubs pour un pays et une ligue donnée
    return data[country_key]["League"].get(league, [])

st.logo(image="assets/logo.png", size="large", icon_image="assets/logo.png")
# --- Sidebar: Sélection des équipes ---
with st.sidebar:
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
        start_full = st.button("🚀 Start Full analysis")
    with col_buttons[1]:
        start_fast = st.button("⚡ Start Fast analysis")

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

st.image(image="assets/logo.png", width=100)
# --- Menu principal via option_menu ---
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
    # Sous-menu horizontal (Home / Away)
    selected_sub = option_menu(
        menu_title=None,
        options=["Home", "Away"],
        icons=["house", "airplane"],
        orientation="horizontal",
        default_index=0,
        styles={
            "container": {"padding": "0px", "background-color": "rgba(0,0,0,0)"},
            "nav-link": {"background-color": "rgba(0,0,0,0)", "font-size": "14px", "text-align": "center", "margin": "0px", "--hover-color": "rgba(255,255,255,0.1)"},
            "nav-link-selected": {"background-color": "rgba(0,0,0,0)", "border-bottom": "3px solid green", "font-weight": "bold"},
        },
    )
    if selected_sub == "Home":
        selected_sub_sub = option_menu(
            menu_title=None,
            options=["Team Statistics", "Players Statistics"],
            icons=["bar-chart-line", "people"],
            orientation="horizontal",
            default_index=0,
            styles={
                "container": {"padding": "0px", "background-color": "rgba(0,0,0,0)"},
                "nav-link": {"background-color": "rgba(0,0,0,0)", "font-size": "14px", "text-align": "center", "margin": "0px", "--hover-color": "rgba(255,255,255,0.1)"},
                "nav-link-selected": {"background-color": "rgba(0,0,0,0)", "border-bottom": "3px solid green", "font-weight": "bold"},
            },
        )
        if selected_sub_sub == "Team Statistics":
            st.write("Contenu relatif aux équipes (Home).")
        else:
            st.write("Contenu relatif aux joueurs (Home).")
    elif selected_sub == "Away":
        selected_sub_sub = option_menu(
            menu_title=None,
            options=["Team Statistics", "Players Statistics"],
            icons=["bar-chart-line", "people"],
            orientation="horizontal",
            default_index=0,
            styles={
                "container": {"padding": "0px", "background-color": "rgba(0,0,0,0)"},
                "nav-link": {"background-color": "rgba(0,0,0,0)", "font-size": "14px", "text-align": "center", "margin": "0px", "--hover-color": "rgba(255,255,255,0.1)"},
                "nav-link-selected": {"background-color": "rgba(0,0,0,0)", "border-bottom": "3px solid green", "font-weight": "bold"},
            },
        )
        if selected_sub_sub == "Team Statistics":
            st.write("Contenu relatif aux équipes (Away).")
        else:
            st.write("Contenu relatif aux joueurs (Away).")
elif selected_main == "Facts":
    st.write("Autres faits et informations.")
