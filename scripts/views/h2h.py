import streamlit as st
import streamlit.components.v1 as components
import json
import difflib
import re
from datetime import datetime
import pandas as pd
import unicodedata
from streamlit_option_menu import option_menu


def normalize_team_name(name: str) -> str:
    """
    Normalize a team name by removing accents, spaces, and hyphens,
    and converting to lowercase.

    Parameters:
        name (str): The team name to normalize.

    Returns:
        str: Normalized team name.
    """
    # Remove accents (diacritics)
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    # Remove spaces and hyphens, and convert to lowercase
    return re.sub(r'[\s\-]', '', name.lower())

def get_closest_team_name(abbrev: str, team_names: list) -> str:
    """
    Retourne le nom d'équipe le plus proche dans team_names pour l'abréviation donnée.
    
    Parameters:
        abbrev (str): Le nom abrégé.
        team_names (list): Liste de noms complets à comparer.
    
    Returns:
        str: Le nom complet le plus proche ou l'abréviation si aucun match n'est trouvé.
    """
    # Normalisation pour faciliter la comparaison
    abbrev_norm = normalize_team_name(abbrev)
    normalized_names = {name: normalize_team_name(name) for name in team_names}
    
    # On utilise difflib pour obtenir le meilleur match
    best_match = difflib.get_close_matches(abbrev_norm, list(normalized_names.values()), n=1, cutoff=0.5)
    if best_match:
        # Récupérer le nom complet correspondant en inversant la normalisation
        for full_name, norm in normalized_names.items():
            if norm == best_match[0]:
                return full_name
    return abbrev

def parse_scorebox_list(team_list):
    """
    Transforms a list [TeamName, {stat1: val1}, {stat2: val2}, ...] into a dictionary.
    
    Example:
        Input: ["TeamA", {"wins": "3"}, {"goals": "5"}]
        Output: {"team_name": "TeamA", "wins": 3, "goals": "5"}
    
    Parameters:
        team_list (list): List containing the team name and subsequent stat dictionaries.
    
    Returns:
        dict: Dictionary with the team name and stats.
    """
    if not team_list:
        return {}
    team_name = team_list[0] if isinstance(team_list[0], str) else "Unknown"
    stats = {"team_name": team_name}
    for item in team_list[1:]:
        if isinstance(item, dict):
            for key, value in item.items():
                # Convert numeric values to integers if possible
                stats[key] = int(value) if isinstance(value, str) and value.isdigit() else value
    return stats

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

def extract_match_teams(report_url: str, scorebox_home: str, scorebox_away: str):
    """
    Extracts team names from the match report URL based on tokens before the date token.
    The function splits the URL's last part into tokens and tests all possible splits
    to match them against the home and away team names provided (after normalization).
    
    Parameters:
        report_url (str): The URL of the match report.
        scorebox_home (str): Home team name from the scorebox.
        scorebox_away (str): Away team name from the scorebox.
    
    Returns:
        tuple: (extracted_home, extracted_away) team names.
    """
    # Get the last part of the URL and split into tokens by hyphen
    last_part = report_url.rstrip("/").split("/")[-1]
    tokens = last_part.split("-")

    # Collect tokens until the first numeric token (assumed to be part of the date)
    candidate_tokens = []
    for token in tokens:
        if token.isdigit():
            break
        candidate_tokens.append(token)

    best_split = (None, None)
    best_score = -1

    # Try every possible split (ensuring at least one token for each team)
    for split_point in range(1, len(candidate_tokens)):
        candidate_home = "-".join(candidate_tokens[:split_point])
        candidate_away = "-".join(candidate_tokens[split_point:])

        # Normalize candidate names and scorebox team names
        cand_home_norm = normalize_team_name(candidate_home)
        cand_away_norm = normalize_team_name(candidate_away)
        score_home_norm = normalize_team_name(scorebox_home)
        score_away_norm = normalize_team_name(scorebox_away)

        score = 0
        if cand_home_norm == score_home_norm:
            score += 1
        if cand_away_norm == score_away_norm:
            score += 1

        if score > best_score:
            best_score = score
            best_split = (candidate_home, candidate_away)

    return best_split

def is_home_match(match: dict, scorebox_home: str, scorebox_away: str) -> bool:
    """
    Determines if the match is a home match for the team corresponding to scorebox_home.
    It uses the match report URL to extract team names and compares the home team name.
    
    Parameters:
        match (dict): The match data containing at least the key "Rapport de match".
        scorebox_home (str): Home team name from the scorebox.
        scorebox_away (str): Away team name from the scorebox.
    
    Returns:
        bool: True if it's a home match, False otherwise.
    """
    report_url = match.get("Rapport de match", "")
    if not report_url:
        return False
    extracted_home, _ = extract_match_teams(report_url, scorebox_home, scorebox_away)
    if extracted_home:
        return normalize_team_name(scorebox_home) in normalize_team_name(extracted_home)
    return False

def is_away_match(match: dict, scorebox_home: str, scorebox_away: str) -> bool:
    """
    Determines if the match is an away match for the team corresponding to scorebox_home.
    
    Parameters:
        match (dict): The match data containing at least the key "Rapport de match".
        scorebox_home (str): Home team name from the scorebox.
        scorebox_away (str): Away team name from the scorebox.
    
    Returns:
        bool: True if it's an away match, False otherwise.
    """
    report_url = match.get("Rapport de match", "")
    if not report_url:
        return False
    extracted_home, _ = extract_match_teams(report_url, scorebox_home, scorebox_away)
    if extracted_home:
        return normalize_team_name(scorebox_home) not in normalize_team_name(extracted_home)
    return False

def parse_score(score_str: str):
    """
    Parse a score string (e.g., "1–0" or "1-0") and return a tuple (home_score, away_score).
    
    Parameters:
        score_str (str): The score string.
    
    Returns:
        tuple: (home_score, away_score) as integers, or (None, None) if parsing fails.
    """
    try:
        score_clean = re.sub(r"\(.*?\)", "", score_str)
        # Split on hyphen or en-dash
        parts = re.split(r"[–-]", score_clean)
        return int(parts[0].strip()), int(parts[1].strip())
    except Exception:
        return None, None

def get_legend_html() -> str:
    """
    Returns the HTML string used as a legend for the match table.
    
    Returns:
        str: HTML content representing the legend.
    """
    return """
    <div style="margin-top: 2px; margin-bottom: 5px">
        <!-- Strong label for the legend -->
        <strong>Legend:</strong>
        <!-- Each item is wrapped in a span to ensure inline display -->
        <span style="margin-left: 10px;">
            <!-- Green square for Win -->
            <span style="display:inline-block; width:15px; height:15px; background-color:#33cc66; margin-right:5px;"></span>
            Win
        </span>
        <span style="margin-left: 10px;">
            <!-- Red square for Lose -->
            <span style="display:inline-block; width:15px; height:15px; background-color:#cc3333; margin-right:5px;"></span>
            Lose
        </span>
        <span style="margin-left: 10px;">
            <!-- Orange square for Draw -->
            <span style="display:inline-block; width:15px; height:15px; background-color:#ff9900; margin-right:5px;"></span>
            Draw
        </span>
        <span style="margin-left: 10px;">
            <!-- Blue square for Incoming -->
            <span style="display:inline-block; width:15px; height:15px; background-color:#75c3ff; margin-right:5px;"></span>
            Incoming
        </span>
    </div>

    """

def display_match_table(match_list: list):
    """
    Converts a list of match dictionaries into a pandas DataFrame and displays it as a table,
    showing only the columns "Comp", "Date", "Domicile", "Score", and "Extérieur". Rows with an empty
    score are highlighted in blue. Additional highlighting is applied to the "Domicile" and "Extérieur"
    columns based on match results.
    
    Parameters:
        match_list (list): List of match dictionaries.
    """
    if not match_list:
        st.write("No matches found.")
        return

    df = pd.DataFrame(match_list)
    # Only display selected columns if available
    columns_to_display = ["Comp", "Date", "Domicile", "Score", "Extérieur"]
    df = df[[col for col in columns_to_display if col in df.columns]]
    
    # Remove rows with header-like entries and reset index
    df = df[df["Score"].astype(str).str.lower() != "score"].reset_index(drop=True)

    # Convert "Date" column to datetime for filtering
    df["Date_parsed"] = pd.to_datetime(df["Date"], format="%Y-%m-%d", errors="coerce")
    today = pd.to_datetime(datetime.today().strftime("%Y-%m-%d"))
    mask = ~((df["Score"].isna() | (df["Score"].astype(str).str.strip() == "")) & (df["Date_parsed"] < today))
    df = df[mask].drop(columns=["Date_parsed"]).reset_index(drop=True)

    def highlight_empty(row):
        if pd.isna(row["Score"]) or row["Score"].strip() == "":
            return ['background-color: #75c3ff'] * len(row)
        return [''] * len(row)

    def highlight_teams(row):
        styles = [''] * len(row)
        score = row.get("Score", "")
        if pd.isna(score) or score.strip() == "":
            return styles  # Score is empty; styling handled in highlight_empty
        home_score, away_score = parse_score(score)
        if home_score is None or away_score is None:
            return styles
        try:
            domicile_idx = list(row.index).index("Domicile")
            exterieur_idx = list(row.index).index("Extérieur")
        except ValueError:
            return styles

        # Apply color based on match result
        if home_score > away_score:
            styles[domicile_idx] = 'background-color: #33cc66'  # Home win in light green
            styles[exterieur_idx] = 'background-color: #cc3333'  # Away loss in light red
        elif home_score < away_score:
            styles[domicile_idx] = 'background-color: #cc3333'
            styles[exterieur_idx] = 'background-color: #33cc66'
        else:
            styles[domicile_idx] = styles[exterieur_idx] = 'background-color: #ff9900'
        return styles

    styled_df = (df.reset_index(drop=True)
                   .style.apply(highlight_empty, axis=1)
                   .apply(highlight_teams, axis=1)
                   .set_properties(**{'text-align': 'center'})
                   .set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}])
                )
    # Note: st.dataframe may not render styles in all cases.
    st.dataframe(styled_df, hide_index=True)

def get_color_from_percentage(value):
    """
    Compute a HEX color based on a percentage value using multiple stops.
    
    Stops:
      0%   -> #993333 (rouge)
      25%  -> #CC6633 (orange)
      50%  -> #E69933 (ambre)
      75%  -> #669933 (lime)
      100% -> #336633 (vert)
    """
    value = max(0, min(100, value))
    stops = [
        (0, (153, 51, 51)),    # #993333
        (25, (204, 102, 51)),  # #CC6633
        (50, (230, 153, 51)),  # #E69933
        (75, (102, 153, 51)),  # #669933
        (100, (51, 102, 51))   # #336633
    ]
    for i in range(len(stops) - 1):
        lower_perc, lower_color = stops[i]
        upper_perc, upper_color = stops[i+1]
        if lower_perc <= value <= upper_perc:
            t = (value - lower_perc) / (upper_perc - lower_perc)
            r = lower_color[0] + t * (upper_color[0] - lower_color[0])
            g = lower_color[1] + t * (upper_color[1] - lower_color[1])
            b = lower_color[2] + t * (upper_color[2] - lower_color[2])
            return f"#{int(r):02X}{int(g):02X}{int(b):02X}"
    return f"#{stops[-1][1][0]:02X}{stops[-1][1][1]:02X}{stops[-1][1][2]:02X}"


def get_gradient_from_percentage(value):
    """
    Returns a CSS linear gradient string based on the given percentage.
    La première couleur correspond au pourcentage donné, la deuxième à (value+5), 
    ce qui crée un léger dégradé.
    """
    color1 = get_color_from_percentage(value)
    color2 = get_color_from_percentage(min(value + 25, 100))
    return f"linear-gradient(135deg, {color1} 0%, {color2} 100%)"

# -----------------------------------------------
# CSS personnalisé pour les cards et metrics
# -----------------------------------------------
def display_data(matches, home_team_name,away_team_name,logo):
    home_win = draw = away_win = 0
    home_goal = away_goal = 0
    btts = 0
    over15 = 0
    over25 = 0

    for m in matches:
        home_score, away_score = parse_score(m.get("Score", ""))
        if home_score is None or away_score is None:
            continue
        if home_score > away_score:
            home_win += 1
        elif home_score < away_score:
            away_win += 1
        else:
            draw += 1
        
        if home_score > 0 and away_score > 0:
            btts += 1
        if home_score + away_score >= 2:
            over15 += 1
        if home_score + away_score >= 3:
            over25 += 1

        home_goal += home_score
        away_goal += away_score
    
    total_games = len(matches)
    home_win_pct = home_win / total_games
    draw_pct = draw / total_games
    away_win_pct = away_win / total_games
    
    btts_pct = btts / len(matches)
    over15_pct = over15 / len(matches)
    over25_pct = over25 / len(matches)

    btts_pct = btts / len(matches)
    over15_pct = over15 / len(matches)
    over25_pct = over25 / len(matches)

    st.markdown(
        """
        <style>
        body {
        margin: 0;
        padding: 20px;
        background: #333; /* Couleur de fond sombre */
        }

        .stats-container {
        display: flex;
        width: 100%;             /* Occupe toute la largeur disponible */
        gap: 20px;
        justify-content: center;
        border-radius: 10px;
        margin-bottom: 10px;
        }

        /* Boîte principale avec layout horizontal */
        .stat-box {
        flex: 1;
        position: relative;
        min-height: 60px;
        border-radius: 8px;
        color: #fff;
        padding: 8px 10px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.2);
        overflow: hidden;
        display: flex;
        flex-direction: row;           /* Layout horizontal */
        justify-content: space-between; /* Espace entre la partie gauche et droite */
        align-items: center;            /* Alignement vertical centré */
        }

        /* Conteneur pour le label et la valeur à gauche */
        .stat-left {
        display: flex;
        flex-direction: column;
        justify-content: center;
        }

        /* Label du haut */
        .stat-label {
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 2px;
        font-weight: bold;
        }

        /* Valeur principale */
        .stat-value {
        font-size: 17px;
        font-weight: bold;
        padding-left: 2px;
        }

        /* Bloc pour la sous-métrique affiché à droite */
        .stat-sub {
        font-size: 16px;
        line-height: 1.2;
        color: #fff;
        font-weight: bold;
        background: rgba(255, 255, 255, 0.3);
        padding: 5px 5px;
        border-radius: 5px;
        /* Pour s'assurer que le bloc occupe un minimum d'espace */
        min-width: 40px;
        text-align: center;
        }

        /* Couleurs fixes pour certaines boxes */
        .box1 { 
        background: linear-gradient(135deg, #24C6DC 0%, #514A9D 100%);
        }
        .box_win { 
        background: linear-gradient(135deg, #a8e063 0%, #56ab2f 100%);
        }
        .box_draw { 
        background: linear-gradient(135deg, #f09819 0%, #ff512f 100%);
        }
        .box_lose { 
        background: linear-gradient(135deg, #ff512f 0%, #cc0000 100%);
        }

        </style>
        """,
        unsafe_allow_html=True
    )
    
    if home_win_pct > away_win_pct:
        col1_bg_color = "box_win"
        col2_bg_color = "box_lose"
    elif home_win_pct < away_win_pct:
        col2_bg_color = "box_win"
        col1_bg_color = "box_lose"
    else:
        col2_bg_color = "box1"
        col1_bg_color = "box1"


    # Example metric display with a centered title above the metric value.
    # Example metric display with a centered title above the metric value.
    col1, col2, col3 = st.columns([5,2,5])
    col2.markdown(
        f"""
        <div class="stats-container box1">
            <div class="stat-box">
                <div class="stat-left">
                <div class="stat-label">
                    Matches played
                </div>
                </div>
                <div class="stat-sub">
                {len(matches)}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    col1, col2,col3,col4,col5 = st.columns([2,3,1,3,2])
    col2.markdown(
        f"""
        <div class="stats-container {col1_bg_color}">
            <div class="stat-box">
                <div class="stat-left">
                <div class="stat-label">
                    <img src="{logo[0]}" alt="Team Logo" style="width:20px; height:20px; border-radius:50%;"> {home_team_name} won
                </div>
                <div class="stat-value">
                    {home_win_pct * 100:.0f}%
                </div>
                </div>
                <div class="stat-sub">
                ⚽ Scored → {home_goal}<br>
                📈 Avg → {(home_goal / len(matches)):.2f}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    col3.markdown(
        f"""
        <div class="stats-container box_draw">
            <div class="stat-box">
                <div class="stat-label">
                    <div class="stat-label">Draw</div>
                <div class="stat-value-container">
                    <div class="stat-value">{draw_pct * 100:.0f}%</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    col4.markdown(
        f"""
        <div class="stats-container {col2_bg_color}">
            <div class="stat-box">
                <div class="stat-left">
                <div class="stat-label">
                    <img src="{logo[1]}" alt="Team Logo" style="width:20px; height:20px; border-radius:50%;"> {away_team_name} won
                </div>
                <div class="stat-value">
                    {away_win_pct * 100:.0f}%
                </div>
                </div>
                <div class="stat-sub">
                ⚽ Scored → {away_goal}<br>
                📈 Avg → {(away_goal / len(matches)):.2f}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    col1, col2,col3,col4,col5,col6= st.columns([2,1,1,1,1,2])
    col2.markdown(
        f"""
        <div class="stats-container" style="background: {get_gradient_from_percentage(btts_pct * 100)}">
            <div class="stat-box">
                <div class="stat-left">
                <div class="stat-label">
                    BTTS
                </div>
                </div>
                <div class="stat-sub">
                {btts_pct* 100:.0f}%
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    col3.markdown(
        f"""
        <div class="stats-container" style="background: {get_gradient_from_percentage((1 - btts_pct) * 100)}">
            <div class="stat-box">
                <div class="stat-left">
                <div class="stat-label">
                    OTS
                </div>
                </div>
                <div class="stat-sub">
                    {(1-btts_pct)* 100:.0f}%
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    col4.markdown(
        f"""
        <div class="stats-container" style="background: {get_gradient_from_percentage(over15_pct * 100)}">
            <div class="stat-box">
                <div class="stat-left">
                <div class="stat-label">
                    Over 1,5
                </div>
                </div>
                <div class="stat-sub">
                    {over15_pct * 100:.0f}%
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    col5.markdown(
        f"""
        <div class="stats-container" style="background: {get_gradient_from_percentage(over25_pct * 100)}">
            <div class="stat-box">
                <div class="stat-left">
                <div class="stat-label">
                    Over 2,5
                </div>
                </div>
                <div class="stat-sub">
                    {over25_pct * 100:.0f}%
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    st.caption(get_legend_html(), unsafe_allow_html=True)
    display_match_table(matches)

def head_to_head_section():
    """
    Loads the JSON file with head-to-head data, extracts team statistics and match history,
    computes metrics, and displays the information across three tabs: All Matches, Home Matches, and Away Matches.
    """
    # Load JSON file
    with open("artifacts/fbref_stats.json", "r", encoding="utf-8") as f3:
        infos = json.load(f3)
        
    datasets = infos.get("datasets", [])
    logo = [extract_team_name(ds.get("team_logo_url", "Unknown")) for ds in datasets]

    try:
        with open("artifacts/fbref_h2h.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        st.error(f"Unable to load fbref_h2h.json: {e}")
        st.stop()
    
    if not data:
        st.info('No analyse done..', icon="ℹ️")
        st.stop()

    # Extract team stats from the scorebox
    scorebox = data.get("scorebox", {})
    home_team_list = scorebox.get("home_team", [])
    away_team_list = scorebox.get("away_team", [])
    home_stats = parse_scorebox_list(home_team_list)
    away_stats = parse_scorebox_list(away_team_list)

    home_team_name = home_stats.get("team_name", "Team A")
    away_team_name = away_stats.get("team_name", "Team B")
    teams_name = [home_team_name, away_team_name]

    # Retrieve match history
    games_info = data.get("games_history_all", {})
    matches = games_info.get("rows", [])
    filtered_matches = [m for m in matches if m.get("Score", "").strip() != ""]

    # Création de deux colonnes
    col1, col2,col3 = st.columns([3,6,3])
    # Dans la première colonne, on place les pills pour la sélection "All", "Home", "Away"
    with col1:
        option_map = {
            "All": "💯",
            "Home": "🏠",
            "Away": "✈️"
        }
        selection2 = st.pills(
            label="View",
            options=list(option_map.keys()),
            format_func=lambda option: option_map[option],
            selection_mode="single",
            default="All",  # Option par défaut
            label_visibility="collapsed"
        )
    
    # Dans la deuxième colonne, on place les pills pour la sélection du nombre de matches
    with col3:
        options_count = ["All", "Last 6", "Last 10"]
        selection = st.pills("Match count", options_count, selection_mode="single", default="All", label_visibility="collapsed")

    # Filtrage de la liste des matches en fonction de la sélection
    if selection == "Last 6":
        filtered_matches = [m for m in matches if m.get("Score", "").strip() != ""]
        matches = filtered_matches[:6]
    elif selection == "Last 10":
        filtered_matches = [m for m in matches if m.get("Score", "").strip() != ""]
        matches = filtered_matches[:10]

    if selection2 == "All":
        display_data(matches,home_team_name,away_team_name,logo)
    elif selection2 == "Home":
        matches = [m for m in matches if is_home_match(m, home_team_name, away_team_name)]
        display_data(matches,home_team_name,away_team_name,logo)

    elif selection2 == "Away":
        matches = [m for m in matches if is_away_match(m, home_team_name, away_team_name)]
        display_data(matches,home_team_name,away_team_name,logo)

def main():
    st.title("Head to Head Analysis")
    head_to_head_section()
    

if __name__ == "__main__":
    main()
