import requests
from bs4 import BeautifulSoup
import pandas as pd
from colorama import Fore, Style  # For colored terminal output

def fetch_fbref_countries(url='https://fbref.com/fr/equipes/', output_file='artifacts/fbref_data_countries.json'):
    """
    Fetches table data from the fbref website, processes it to extract the first 4 columns and URLs,
    then saves the data as a JSON file.

    Parameters:
        url (str): The URL to fetch data from.
        output_file (str): The JSON file name to save the data.

    Returns:
        None
    """
    # Fetch the page content
    response = requests.get(url)
    if response.status_code != 200:
        print(f"{Fore.RED}Error fetching the page: {response.status_code}{Style.RESET_ALL}")
        return
    else:
        print(f"{Fore.BLUE}Page fetched successfully. Processing HTML...{Style.RESET_ALL}")

    # Parse the HTML content using BeautifulSoup with the lxml parser
    soup = BeautifulSoup(response.content, 'lxml')

    # Locate the table with the id 'countries'
    table = soup.find("table", id="countries")
    if table is None:
        print(f"{Fore.RED}Error: Could not find the table with id 'countries'.{Style.RESET_ALL}")
        return

    # Extract header names from the table's header row and use only the first four headers
    headers = [th.get_text(strip=True) for th in table.find('thead').find_all('th')][:4]

    # Initialize lists to store the extracted data and URLs
    data = []
    urls = []  # to store the URL from the first column

    # Iterate over each row in the table body
    for row in table.find('tbody').find_all('tr'):
        # Extract all cells (both header and data cells)
        cells = row.find_all(['th', 'td'])
        # Ensure the row has at least 4 cells
        if len(cells) < 4:
            continue

        # Extract text content for the first 4 columns
        row_data = [cell.get_text(strip=True) for cell in cells[:4]]
        
        # For the first column, extract the URL from the <a> tag if available
        first_cell = cells[0]
        a_tag = first_cell.find('a')
        if a_tag and a_tag.has_attr('href'):
            link = a_tag['href']
            if not link.startswith('http'):
                link = 'https://fbref.com' + link
        else:
            link = None
        urls.append(link)
        
        # Append the row data to our data list
        data.append(row_data)

    # Create a DataFrame with the first four columns and assign the corresponding headers
    df = pd.DataFrame(data, columns=headers)
    # Add the URLs as a new column to the DataFrame
    df['Link'] = urls

    # Save the DataFrame to a JSON file using 'records' orientation
    try:
        df.to_json(output_file, orient='records', indent=4, force_ascii=False)
        print(f"{Fore.GREEN}Task completed successfully! Data saved to {output_file}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Error saving JSON file: {e}{Style.RESET_ALL}")
