import streamlit as st
import json
import pandas as pd
import numpy as np
import time
from fbref_club_data import fetch_fbref_stats
from fbref_players_data import update_fbref_players_data

# --- Page Configuration ---
st.set_page_config(page_title="Football Clubs Analysis - FBRef", layout="wide")

# --- Load JSON Data ---
with open("fbref_data_clubs.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# --- Create Country Mapping ---
# Build a mapping from original keys to display names (removing the prefix)
# Example: "Clubs de football de France" --> "France"
country_key_to_display = {key: key.replace("Clubs de football de ", "") for key in data.keys()}
# Invert the mapping to retrieve the original key from the displayed name
display_to_country_key = {display: key for key, display in country_key_to_display.items()}
# Create a list of displayed countries
displayed_countries = list(display_to_country_key.keys())

# --- Function to Retrieve Clubs ---
def get_clubs(country_key, league):
    # country_key is the original key from the JSON
    return data[country_key][league] if country_key and league in data[country_key] else []

# --- User Interface ---
st.title("⚽ Football Clubs Analysis with FBRef")

# Option to use the same country and league for both teams
same_settings = st.checkbox("Use same country and league for Club 2", value=False)

if same_settings:
    # Use displayed countries in the selectbox for common selection
    selected_country_display = st.selectbox("Country", displayed_countries, key="country")
    # Retrieve the actual key from the mapping
    actual_country_key = display_to_country_key[selected_country_display]
    league = st.selectbox("League", list(data[actual_country_key].keys()), key="league")
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
        league1 = st.selectbox("League", list(data[actual_country_key1].keys()), key="league1")
        clubs1 = get_clubs(actual_country_key1, league1)
        club1 = st.selectbox("🔵 Home Team", [club["Club Name"] for club in clubs1], key="club1")
    with col2:
        selected_country_display2 = st.selectbox("Country", displayed_countries, key="country2")
        actual_country_key2 = display_to_country_key[selected_country_display2]
        league2 = st.selectbox("League", list(data[actual_country_key2].keys()), key="league2")
        clubs2 = get_clubs(actual_country_key2, league2)
        club2 = st.selectbox("🔴 Away Team", [club["Club Name"] for club in clubs2], key="club2")

# --- Analyze Button and URL Retrieval ---
analyze = st.button("🚀 Start Analysis")

if same_settings:
    club1_url = next((club["Club URL"] for club in clubs if club["Club Name"] == club1), None)
    club2_url = next((club["Club URL"] for club in clubs if club["Club Name"] == club2), None)
else:
    club1_url = next((club["Club URL"] for club in clubs1 if club["Club Name"] == club1), None)
    club2_url = next((club["Club URL"] for club in clubs2 if club["Club Name"] == club2), None)

# --- Launch Analysis with Progress Animation ---
if analyze:
    if club1_url and club2_url:
        # Create a placeholder to display the progress animation and analysis feedback
        info_placeholder = st.empty()
        
        # After the progress animation, fetch the FBRef statistics
        fetch_fbref_stats([club1_url, club2_url])
        
        info_placeholder.info("✅ Récuperation des clubs datas terminée...")

        update_fbref_players_data()

        info_placeholder.info("✅ Récuperation des players datas terminée...")


    else:
        # Display an error message in red if the club URLs cannot be retrieved
        st.markdown('<p style="color:red;">⚠️ Unable to retrieve the URLs for the selected clubs.</p>', unsafe_allow_html=True)
