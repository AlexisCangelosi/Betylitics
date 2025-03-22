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
    red_metrics = {"Consecutive defeats", "No win", "1 goal conceded or more", "No goal scored"}
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

def display_team_summary(datasets: list):
    """
    Displays the "Summary" view for a team with dynamic filtering and calculations.
    
    The function:
      1. Sorts the venues data by date (descending) and filters out future/incomplete matches.
      2. Provides dynamic st.pills (on a single row) for:
         - Competition selection (with an "All" option),
         - Match type selection (Overall, Home, Away),
         - Table selection ("Form" or "Streak").
      3. Uses a select slider for match count selection (options: "3", "5", "6", "10", "15", "20").
      4. Calculates key "Form" statistics and displays them if "Form" is selected.
      5. Computes streak metrics and displays them if "Streak" is selected.
      6. Always displays the filtered match table (df_to_display) with conditional row coloring.
    """
    # Extract team names from datasets
    team_names = [extract_team_name(ds.get("team", "Unknown")) for ds in datasets]
    # Display team selection pills
    selected_team = st.pills(
        "Select Team",
        options=team_names,
        selection_mode="single",
        default=team_names[0],
        key="team_selection"
    )
    # Find the dataset corresponding to the selected team
    selected_index = team_names.index(selected_team)
    team_data = datasets[selected_index]

    # Retrieve 'venues' data from the team dataset
    venues_obj = team_data.get("venues", {})
    if not venues_obj:
        st.info("No 'venues' object found in this dataset.")
        return

    venues_list = venues_obj.get("venues", [])
    if not venues_list:
        st.info("No venues data found under 'venues' key.")
        return

    # Convert venues data to DataFrame
    df_summary = pd.DataFrame(venues_list)
    if "Date" not in df_summary.columns:
        st.info("No 'Date' column found in the venues data.")
        st.dataframe(df_summary)
        return

    # Convert 'Date' column to datetime and sort descending (most recent first)
    df_summary["Date_parsed"] = pd.to_datetime(df_summary["Date"], errors="coerce")
    df_summary = df_summary.sort_values("Date_parsed", ascending=False).reset_index(drop=True)

    # Filter out matches that have not been played (Résultat must be V, D, or N)
    if "Résultat" in df_summary.columns:
        df_summary = df_summary[df_summary["Résultat"].isin(["V", "D", "N"])]
    else:
        st.warning("No 'Résultat' column found. Unable to filter out future matches.")

    # Ensure numeric columns are parsed properly
    for col in ["BM", "BE"]:
        if col in df_summary.columns:
            df_summary[col] = df_summary[col].apply(extract_main_value)

    # --- Dynamic Pill Selections on a Single Row ---
    if "Comp" in df_summary.columns and not df_summary.empty:
        comp_values = df_summary["Comp"].dropna().unique().tolist()
        comp_values = sorted(comp_values)
        comp_options = ["All"] + comp_values
    else:
        comp_options = ["All"]

    match_type_options = ["Overall", "Home", "Away"]
    table_options = ["Form", "Streak"]

    col_comp, col_type, col_count, col_table = st.columns([4, 2.5, 4, 2.5])
    with col_comp:
        selected_comp = st.pills(
            "Select Competition",
            comp_options,
            selection_mode="single",
            default="All",
            key=f"comp_pills"
        )
    with col_type:
        selected_type = st.pills(
            "Select match type",
            match_type_options,
            selection_mode="single",
            default="Overall",
            key=f"match_type_pills"
        )
    with col_count:
        # Replace the pill with a select slider for match count
        matches_count = st.select_slider(
            "Select number of matches",
            options=["3", "5", "6", "10", "15", "20"],
            value="10",
            key=f"match_count_slider"
        )
    with col_table:
        selected_table = st.pills(
            "Select table",
            table_options,
            selection_mode="single",
            default="Form",
            key=f"table_pills"
        )

    if selected_comp != "All":
        df_summary = df_summary[df_summary["Comp"] == selected_comp]

    if selected_type != "Overall" and "Tribune" in df_summary.columns:
        if selected_type == "Home":
            df_summary = df_summary[df_summary["Tribune"] == "Domicile"]
        elif selected_type == "Away":
            df_summary = df_summary[df_summary["Tribune"] == "Extérieur"]

    # Convert the slider selection to integer
    count_to_take = int(matches_count)
    df_filtered = df_summary.head(count_to_take)

    # --- Calculations for Form View ---
    num_matches = len(df_filtered)
    wins = sum(df_filtered["Résultat"] == "V") if "Résultat" in df_filtered.columns else 0
    draws = sum(df_filtered["Résultat"] == "N") if "Résultat" in df_filtered.columns else 0
    losses = sum(df_filtered["Résultat"] == "D") if "Résultat" in df_filtered.columns else 0

    goals_scored = df_filtered["BM"].sum() if "BM" in df_filtered.columns else 0
    goals_conceded = df_filtered["BE"].sum() if "BE" in df_filtered.columns else 0
    goal_diff = goals_scored - goals_conceded
    points = wins * 3 + draws

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
    stats_data = {
        "Matches Played": [num_matches],
        "Wins": [wins],
        "Draws": [draws],
        "Losses": [losses],
        "Goals Scored": [goals_scored],
        "Goals Conceded": [goals_conceded],
        "Goal Diff": [goal_diff],
        "Points": [points],
        "Last 5": [emoji_str]
    }
    stats_df = pd.DataFrame(stats_data)

    # --- Display the Form/Stats Table Based on Selected Table Pill ---
    if selected_table == "Form":
        st.dataframe(stats_df, hide_index=True)
    elif selected_table == "Streak":
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

            streaks = {
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
            filtered_streaks = {k: v for k, v in streaks.items() if v != ""}
            if filtered_streaks:
                streaks_df = pd.DataFrame([filtered_streaks])
                st.subheader("Streak Metrics")
                st.dataframe(streaks_df.style.apply(style_streaks, axis=1), hide_index=True)
            else:
                st.info("No non-zero streaks to display.")
        else:
            st.info("No matches available for streak analysis.")

    # --- Always display the filtered match table ---
    display_mode = st.pills(
        "Display Mode",
        options=["Default", "Wide"],
        selection_mode="single",
        default="Default",
        key=f"display_mode"
    )
    if display_mode != "Wide":
        columns_to_show = ["Date", "Comp", "Tour", "Résultat", "BM", "BE", "Adversaire"]
        df_to_display = df_filtered[[col for col in columns_to_show if col in df_filtered.columns]]
    else:
        df_to_display = df_filtered.drop(columns=["Date_parsed"], errors="ignore")
    if not df_to_display.empty:
        st.dataframe(df_to_display.style.apply(highlight_result, axis=1), hide_index=True)
    else:
        st.info("No matches available after filtering.")

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

def display_statistics():
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
        key="subview_selection"
    )

    if selected_sub_view == "Form & Streak":
        display_team_summary(datasets)
    elif selected_sub_view == "Team Statistics":
        display_team_stats(datasets[0])  # You may modify this as needed
    elif selected_sub_view == "Player Statistics":
        display_player_stats(datasets[0])


# --- Main Execution ---

if __name__ == "__main__":
    st.title("Football Statistics")
    st.write("View team or player statistics based on the loaded dataset.")
    display_statistics()
