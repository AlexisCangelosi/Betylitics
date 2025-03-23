import streamlit as st
import pandas as pd
import json
import re

# --- Helper Functions ---

def normalize_team_name(name: str) -> str:
    """
    Normalize a team name by removing spaces and hyphens and converting to lowercase.
    """
    return re.sub(r'[\s\-]', '', name.lower())

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

def extract_main_value(value):
    """
    Extracts the main numeric value from a string.
    For example, "0(4)" will return 0 and "1(2)" will return 1.
    """
    if isinstance(value, str):
        m = re.match(r"^\s*(-?\d+)", value)
        if m:
            return int(m.group(1))
    try:
        return int(value)
    except:
        return 0

def highlight_result(row):
    """
    Returns a list of CSS styles to apply to each row based on the 'Résultat' value.
    V -> green, D -> red, N -> orange.
    """
    result = row.get("Résultat", "")
    if result == "V":
        return ["background-color: #2a623d"] * len(row)
    elif result == "D":
        return ["background-color: #740001"] * len(row)
    elif result == "N":
        return ["background-color: #d3a625"] * len(row)
    else:
        return [""] * len(row)

def current_streak(values, condition):
    """
    Returns the number of consecutive elements (starting from the first) in 'values'
    that satisfy the condition.
    """
    streak = 0
    for v in values:
        if condition(v):
            streak += 1
        else:
            break
    return streak

def style_streaks(row):
    """
    Returns a Series of CSS styles for each column in the streak row.
    For metrics in red_metrics ("Consecutive defeats", "No win", "1 goal conceded or more", "No goal scored"),
    if the value is nonzero, the cell is styled in red.
    For all other metrics, if the numeric value is greater than 1, the cell is styled in green.
    """
    red_metrics = {"Consecutive defeats", "No win", "1 goal conceded or more", "No goal scored","Consecutive defeats or draw"}
    styles = {}
    for col, val in row.items():
        try:
            numeric_val = float(val)
        except (ValueError, TypeError):
            numeric_val = 0
        
        if numeric_val > 0:
            if col in red_metrics:
                styles[col] = "background-color: #740001; color: white;"
            else:
                if numeric_val > 1:
                    styles[col] = "background-color: #2a623d; color: white;"
                else:
                    styles[col] = ""
        else:
            styles[col] = ""
    return pd.Series(styles)

# --- Modified display_team_summary Function ---
def display_team_summary(datasets: list, logo):
    """
    Displays the "Form" or "Streak" view for all teams.
    Instead of a team selection pill, the function iterates through every team in the datasets,
    computes their statistics, and displays a combined table with the team name as the first column.

    The "Combined Match Table" is now shown in 2 columns (one per team) with un filtre Home vs Away.
    Si l'utilisateur sélectionne "Home vs Away" :
      - La team 1 affiche ses matchs à domicile ("Domicile")
      - La team 2 affiche ses matchs à l'extérieur ("Extérieur")
    Inversement pour "Away vs Home".
    """
    # --- Global Dynamic Filter Selections (applied to all teams) ---
    # Build competition options by merging competitions from all datasets
    all_comp_options = set()
    for ds in datasets:
        venues = ds.get("venues", {}).get("venues", [])
        if venues:
            df_temp = pd.DataFrame(venues)
            if "Comp" in df_temp.columns:
                all_comp_options.update(df_temp["Comp"].dropna().unique().tolist())
    comp_options = ["All"] + sorted(list(all_comp_options))
    
    # Mise à jour des options de match_type
    match_type_options = ["Overall", "Home vs Away", "Away vs Home"]
    table_options = ["Form", "Streak"]

    col_comp, col_type, col_count, col_table = st.columns([4, 2.5, 4, 2.5])
    with col_comp:
        selected_comp = st.pills(
            "Select Competition",
            comp_options,
            selection_mode="single",
            default="All",
            key="comp_pills"
        )
    with col_type:
        selected_type = st.pills(
            "Select match type",
            match_type_options,
            selection_mode="single",
            default="Overall",
            key="match_type_pills"
        )
    with col_count:
        matches_count = st.select_slider(
            "Select number of matches",
            options=["3", "5", "6", "10", "15", "20"],
            value="10",
            key="match_count_slider"
        )
    with col_table:
        selected_table = st.pills(
            "Select table",
            table_options,
            selection_mode="single",
            default="Form",
            key="table_pills"
        )
    count_to_take = int(matches_count)
    
    # --- Prepare Data for Combined Tables ---
    form_rows = []   # List to hold form statistics rows for each team
    streak_rows = [] # List to hold streak statistics rows for each team
    
    # We will also keep track of each team's filtered match data
    results_by_team = {}

    # Process each team dataset with index (to appliquer le filtre home vs away)
    for idx, ds in enumerate(datasets):
        team_name = extract_team_name(ds.get("team", "Unknown"))
        venues_obj = ds.get("venues", {})
        venues_list = venues_obj.get("venues", [])
        if not venues_list:
            continue
        df_summary = pd.DataFrame(venues_list)
        
        # Sort & filter out unplayed matches
        if "Date" in df_summary.columns:
            df_summary["Date_parsed"] = pd.to_datetime(df_summary["Date"], errors="coerce")
            df_summary = df_summary.sort_values("Date_parsed", ascending=False).reset_index(drop=True)
        if "Résultat" in df_summary.columns:
            df_summary = df_summary[df_summary["Résultat"].isin(["V", "D", "N"])]
        
        # Ensure numeric columns are parsed properly
        for col in ["BM", "BE"]:
            if col in df_summary.columns:
                df_summary[col] = df_summary[col].apply(extract_main_value)
        
        # --- Apply Global Filters ---
        if selected_comp != "All" and "Comp" in df_summary.columns:
            df_summary = df_summary[df_summary["Comp"] == selected_comp]
        if selected_type != "Overall" and "Tribune" in df_summary.columns:
            if selected_type == "Home vs Away":
                # Pour Home vs Away: team 1 affiche "Domicile", team 2 affiche "Extérieur"
                if idx == 0:
                    df_summary = df_summary[df_summary["Tribune"] == "Domicile"]
                elif idx == 1:
                    df_summary = df_summary[df_summary["Tribune"] == "Extérieur"]
            elif selected_type == "Away vs Home":
                # Pour Away vs Home: team 1 affiche "Extérieur", team 2 affiche "Domicile"
                if idx == 0:
                    df_summary = df_summary[df_summary["Tribune"] == "Extérieur"]
                elif idx == 1:
                    df_summary = df_summary[df_summary["Tribune"] == "Domicile"]
        # Keep only the latest N matches
        df_filtered = df_summary.head(count_to_take)
        
        # Save the filtered DataFrame for the results table
        results_by_team[team_name] = df_filtered

        # --- Calculate Form Statistics for the Team ---
        num_matches = len(df_filtered)
        wins = sum(df_filtered["Résultat"] == "V") if "Résultat" in df_filtered.columns else 0
        draws = sum(df_filtered["Résultat"] == "N") if "Résultat" in df_filtered.columns else 0
        losses = sum(df_filtered["Résultat"] == "D") if "Résultat" in df_filtered.columns else 0

        goals_scored = df_filtered["BM"].sum() if "BM" in df_filtered.columns else 0
        goals_conceded = df_filtered["BE"].sum() if "BE" in df_filtered.columns else 0
        goal_diff = goals_scored - goals_conceded
        points = (wins * 3 + draws) / num_matches

        # Get last 5 match results as emoji
        df_for_chart = df_filtered.head(5)
        results_emoji = []
        if "Résultat" in df_for_chart.columns:
            for res in df_for_chart["Résultat"]:
                if res == "V":
                    results_emoji.append("🟢")
                elif res == "D":
                    results_emoji.append("🔴")
                elif res == "N":
                    results_emoji.append("🟡")
                else:
                    results_emoji.append("⚪")
        else:
            results_emoji = ["⚪"] * len(df_for_chart)
        emoji_str = " ".join(results_emoji)
        
        form_row = {
            "Team": team_name,
            "Matches Played": num_matches,
            "Wins": wins,
            "Draws": draws,
            "Losses": losses,
            "Goals Scored": goals_scored,
            "Goals Conceded": goals_conceded,
            "Goal Diff": goal_diff,
            "PPG": points,
            "Last 5": emoji_str
        }
        form_rows.append(form_row)
        
        # --- Calculate Streak Metrics for the Team ---
        if not df_filtered.empty:
            results = df_filtered["Résultat"].tolist() if "Résultat" in df_filtered.columns else []
            streak_consecutive_wins = current_streak(results, lambda x: x == "V")
            streak_consecutive_win_or_draw = current_streak(results, lambda x: x in ["V", "N"])
            streak_consecutive_draws = current_streak(results, lambda x: x == "N")
            streak_consecutive_defeats_or_draw = current_streak(results, lambda x: x in ["D", "N"])
            streak_consecutive_defeats = current_streak(results, lambda x: x == "D")
            streak_no_win = current_streak(results, lambda x: x != "V")
            streak_no_draw = current_streak(results, lambda x: x != "N")
            streak_no_defeat = current_streak(results, lambda x: x != "D")
            
            if "BM" in df_filtered.columns:
                bm_series = df_filtered["BM"].tolist()
                streak_1_goal_scored_or_more = current_streak(bm_series, lambda x: x >= 1)
                streak_no_goal_scored = current_streak(bm_series, lambda x: x == 0)
            else:
                streak_1_goal_scored_or_more = streak_no_goal_scored = 0

            if "BE" in df_filtered.columns:
                be_series = df_filtered["BE"].tolist()
                streak_1_goal_conceded_or_more = current_streak(be_series, lambda x: x >= 1)
                streak_no_goal_conceded = current_streak(be_series, lambda x: x == 0)
            else:
                streak_1_goal_conceded_or_more = streak_no_goal_conceded = 0

            if "BM" in df_filtered.columns and "BE" in df_filtered.columns:
                total_series = df_filtered.apply(lambda row: row["BM"] + row["BE"], axis=1).tolist()
                streak_GF_GA_over_2_5 = current_streak(total_series, lambda x: x >= 3)
                streak_GF_GA_under_2_5 = current_streak(total_series, lambda x: x <= 2)
            else:
                streak_GF_GA_over_2_5 = streak_GF_GA_under_2_5 = 0

            streaks_dict = {
                "Team": team_name,
                "Consecutive wins": streak_consecutive_wins if streak_consecutive_wins > 0 else "",
                "Consecutive wins or draw": streak_consecutive_win_or_draw if streak_consecutive_win_or_draw > 0 else "",
                "Consecutive draws": streak_consecutive_draws if streak_consecutive_draws > 0 else "",
                "Consecutive defeats or draw": streak_consecutive_defeats_or_draw if streak_consecutive_defeats_or_draw > 0 else "",
                "Consecutive defeats": streak_consecutive_defeats if streak_consecutive_defeats > 0 else "",
                "No win": streak_no_win if streak_no_win > 0 else "",
                "No draw": streak_no_draw if streak_no_draw > 0 else "",
                "No defeat": streak_no_defeat if streak_no_defeat > 0 else "",
                "1 goal scored or more": streak_1_goal_scored_or_more if streak_1_goal_scored_or_more > 0 else "",
                "1 goal conceded or more": streak_1_goal_conceded_or_more if streak_1_goal_conceded_or_more > 0 else "",
                "No goal scored": streak_no_goal_scored if streak_no_goal_scored > 0 else "",
                "No goal conceded": streak_no_goal_conceded if streak_no_goal_conceded > 0 else "",
                "GF+GA over 2.5": streak_GF_GA_over_2_5 if streak_GF_GA_over_2_5 > 0 else "",
                "GF+GA under 2.5": streak_GF_GA_under_2_5 if streak_GF_GA_under_2_5 > 0 else ""
            }
            # Only keep non-zero streaks (with value > 1) besides the team name
            streaks_data = {k: v for k, v in streaks_dict.items() if k == "Team" or (v != "" and int(v) > 1)}
            streak_rows.append(streaks_data)
        else:
            streak_rows.append({"Team": team_name})
    
    # --- Display the Combined Tables (Form / Streak) ---
    if selected_table == "Form":
        stats_df = pd.DataFrame(form_rows)
        st.dataframe(stats_df, hide_index=True)

    elif selected_table == "Streak":
        if streak_rows:
            streaks_df = pd.DataFrame(streak_rows)

            # Convert numeric streak columns to integer strings (no decimals)
            def format_streak_values(val):
                try:
                    return str(int(float(val)))
                except (ValueError, TypeError):
                    return val

            streaks_df = streaks_df.apply(lambda col: col.map(format_streak_values))
            st.dataframe(streaks_df.style.apply(style_streaks, axis=1), hide_index=True)
        else:
            st.info("No non-zero streaks to display.")
    
    # --- Display Combined Match Table in Two Columns (one for each team) ---
    # Filters are already applied; we just display the results side by side.
    display_mode = st.pills(
        "Display Mode",
        options=["Default", "Wide"],
        selection_mode="single",
        default="Default",
        key="display_mode"
    )

    teams_sorted = list(results_by_team.keys())
    if len(teams_sorted) == 2:
        col1, col2 = st.columns(2)

        # Left column: first team
        with col1:
            team_1 = teams_sorted[0]
            st.markdown(rf"""
<div style="font-size: 20px;">
    <img src="{logo[0]}" alt="Team Logo" style="width:40px; height:40px; border-radius:10%;padding-bottom: 2px">
    {team_1}
</div>
""", unsafe_allow_html=True)
            df_team_1 = results_by_team[team_1].copy()
            if not df_team_1.empty:
                if display_mode != "Wide":
                    columns_to_show = ["Date", "Comp", "Tour", "Résultat", "BM", "BE", "Adversaire"]
                    columns_to_show = [c for c in columns_to_show if c in df_team_1.columns]
                    df_team_1 = df_team_1[columns_to_show]
                else:
                    df_team_1 = df_team_1.drop(columns=["Date_parsed"], errors="ignore")
                st.dataframe(df_team_1.style.apply(highlight_result, axis=1), hide_index=True)
            else:
                st.info(f"No matches available for {team_1} after filtering.")

        # Right column: second team
        with col2:
            team_2 = teams_sorted[1]
            st.markdown(rf"""
<div style="font-size: 20px;">
    <img src="{logo[1]}" alt="Team Logo" style="width:40px; height:40px; border-radius:10px;padding-bottom: 2px">
    {team_2}
</div>
""", unsafe_allow_html=True)
            df_team_2 = results_by_team[team_2].copy()
            if not df_team_2.empty:
                if display_mode != "Wide":
                    columns_to_show = ["Date", "Comp", "Tour", "Résultat", "BM", "BE", "Adversaire"]
                    columns_to_show = [c for c in columns_to_show if c in df_team_2.columns]
                    df_team_2 = df_team_2[columns_to_show]
                else:
                    df_team_2 = df_team_2.drop(columns=["Date_parsed"], errors="ignore")
                st.dataframe(df_team_2.style.apply(highlight_result, axis=1), hide_index=True)
            else:
                st.info(f"No matches available for {team_2} after filtering.")

    else:
        for team_name in teams_sorted:
            st.subheader(team_name)
            df_team = results_by_team[team_name].copy()
            if not df_team.empty:
                if display_mode != "Wide":
                    columns_to_show = ["Date", "Comp", "Tour", "Résultat", "BM", "BE", "Adversaire"]
                    columns_to_show = [c for c in columns_to_show if c in df_team.columns]
                    df_team = df_team[columns_to_show]
                else:
                    df_team = df_team.drop(columns=["Date_parsed"], errors="ignore")
                st.dataframe(df_team.style.apply(highlight_result, axis=1), hide_index=True)
            else:
                st.info(f"No matches available for {team_name} after filtering.")

def display_team_stats(team_data: dict):
    """
    Placeholder for the "Team Statistics" view.
    """
    st.subheader("Team Statistics In progress...")

def display_player_stats(team_data: dict):
    """
    Placeholder for the "Player Statistics" view.
    """
    st.subheader("Player Statistics In progress...")

# --- Main Function to Render Statistics ---
def display_statistics(logo):
    """
    Loads JSON data from fbref_stats.json, extracts team information,
    and renders an interactive UI with sub-view pills for "Form & Streak",
    "Team Statistics", and "Player Statistics".
    """
    try:
        with open("artifacts/fbref_stats.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        st.error(f"Error loading JSON data: {e}")
        return

    datasets = data.get("datasets", [])
    if not datasets:
        st.info("No datasets found in the JSON data.")
        return

    sub_views = ["Form & Streak", "Team Statistics", "Player Statistics"]
    selected_sub_view = st.pills(
        "Select View",
        options=sub_views,
        selection_mode="single",
        default=sub_views[0],
        key="subview_selection",
        label_visibility="collapsed"
    )

    if selected_sub_view == "Form & Streak":
        display_team_summary(datasets, logo)
    elif selected_sub_view == "Team Statistics":
        display_team_stats(datasets[0])
    elif selected_sub_view == "Player Statistics":
        display_player_stats(datasets[0])

# --- Main Execution ---
if __name__ == "__main__":
    st.title("Football Statistics")
    st.write("View team or player statistics based on the loaded dataset.")
    # Par exemple, on suppose que logo est une liste contenant les URLs des logos pour chaque équipe
    logo = ["https://example.com/logo1.png", "https://example.com/logo2.png"]
    display_statistics(logo)
