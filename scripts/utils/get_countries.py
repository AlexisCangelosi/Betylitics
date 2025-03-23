import requests
from bs4 import BeautifulSoup
import pandas as pd
from colorama import Fore, Style  # For colored terminal output
import pycountry

def clean_country_name(raw_country: str) -> str:
    """
    Removes the prefix "Clubs de football de " from the raw country name.
    For example, "Clubs de football de Albania" becomes "Albania".
    """
    prefix = "Clubs de football de "
    if raw_country.startswith(prefix):
        return raw_country[len(prefix):].strip()
    return raw_country.strip()

def code_to_flag(country_code: str) -> str:
    """
    Converts a two-letter country code into its corresponding flag emoji.
    This uses Unicode regional indicator symbols.
    For example, "FR" becomes 🇫🇷 and "AR" becomes 🇦🇷.
    """
    return ''.join(chr(ord(char) + 127397) for char in country_code.upper())

def get_country_info(country: str) -> (str, str):
    """
    Uses pycountry to retrieve the country's official two-letter code (alpha_2)
    and its corresponding flag emoji.
    
    If pycountry cannot find a match, it falls back to using the first two letters
    of the cleaned country name.
    """
    try:
        # search_fuzzy returns a list of possible matches
        result = pycountry.countries.search_fuzzy(country)
        if result:
            country_obj = result[0]
            abbrev = country_obj.alpha_2
            flag = code_to_flag(abbrev)
            return abbrev, flag
    except Exception as e:
        # Fallback if pycountry search fails
        abbrev = country[:2].upper()
        flag = code_to_flag(abbrev)
        return abbrev, flag

def fetch_fbref_countries(url='https://fbref.com/fr/equipes/', output_file='artifacts/fbref_data_countries.json'):
    """
    Fetches table data from the fbref website, extracts the first four columns and URLs,
    and uses pycountry to determine each country's two-letter abbreviation and flag emoji.
    The data is then saved as a JSON file.
    """
    # Fetch the page content
    response = requests.get(url)
    if response.status_code != 200:
        print(f"{Fore.RED}Error fetching the page: {response.status_code}{Style.RESET_ALL}")
        return
    else:
        print(f"{Fore.BLUE}Page fetched successfully. Processing HTML...{Style.RESET_ALL}")

    # Parse the HTML content with BeautifulSoup using the lxml parser
    soup = BeautifulSoup(response.content, 'lxml')

    # Locate the table with the id 'countries'
    table = soup.find("table", id="countries")
    if table is None:
        print(f"{Fore.RED}Error: Could not find the table with id 'countries'.{Style.RESET_ALL}")
        return

    # Extract header names from the table's header row (only the first four headers)
    headers = [th.get_text(strip=True) for th in table.find('thead').find_all('th')][:4]

    data = []         # List to store the table rows (first 4 columns)
    urls = []         # List to store the URL from the first column
    abbreviations = []  # List to store the computed country abbreviations
    flags = []        # List to store the computed flag emojis

    # Iterate over each row in the table body
    for row in table.find('tbody').find_all('tr'):
        cells = row.find_all(['th', 'td'])
        if len(cells) < 4:
            continue

        # Extract text content for the first 4 columns
        row_data = [cell.get_text(strip=True) for cell in cells[:4]]
        
        # Get and clean the country name from the first column
        raw_country = row_data[0]
        country = clean_country_name(raw_country)
        
        # Retrieve the official abbreviation and flag emoji using pycountry
        abbrev, flag = get_country_info(country)
        abbreviations.append(abbrev)
        flags.append(flag)
        
        # For the first column, extract the URL from the <a> tag (if available)
        first_cell = cells[0]
        a_tag = first_cell.find('a')
        if a_tag and a_tag.has_attr('href'):
            link = a_tag['href']
            if not link.startswith('http'):
                link = 'https://fbref.com' + link
        else:
            link = None
        urls.append(link)
        
        data.append(row_data)

    # Create a DataFrame with the first four columns using the extracted headers
    df = pd.DataFrame(data, columns=headers)
    # Add the URLs, abbreviations, and flag emojis as new columns
    df['Link'] = urls
    df['Abbreviation'] = abbreviations
    df['Flag'] = flags

    # Save the DataFrame to a JSON file (records orientation)
    try:
        df.to_json(output_file, orient='records', indent=4, force_ascii=False)
        print(f"{Fore.GREEN}Task completed successfully! Data saved to {output_file}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Error saving JSON file: {e}{Style.RESET_ALL}")

if __name__ == "__main__":
    fetch_fbref_countries()
