import argparse
from colorama import Fore, Style, init

# Initialize colorama for colored terminal output
init(autoreset=True)

def log_info(message):
    """
    Prints an informational message in blue.
    """
    print(f"{Fore.BLUE}{message}{Style.RESET_ALL}")

def log_success(message):
    """
    Prints a success message in green.
    """
    print(f"{Fore.GREEN}{message}{Style.RESET_ALL}")

def log_error(message):
    """
    Prints an error message in red.
    """
    print(f"{Fore.RED}{message}{Style.RESET_ALL}")

def log_warning(message):
    """
    Prints a warning message in yellow.
    """
    print(f"{Fore.YELLOW}{message}{Style.RESET_ALL}")

def create_parser():
    parser = argparse.ArgumentParser(
        description="CLI Helper: A tool to fetch data from fbref and perform various tasks."
    )
    subparsers = parser.add_subparsers(dest='command', help="Available commands")

    # Subcommand: get-countries
    get_countries_parser = subparsers.add_parser(
        'get-countries',
        help="Fetch fbref countries data and save it as a JSON file."
    )
    get_countries_parser.add_argument(
        '--url', type=str, default='https://fbref.com/fr/equipes/',
        help="The URL to fetch data from. Default: https://fbref.com/fr/equipes/"
    )
    get_countries_parser.add_argument(
        '--output', type=str, default='fbref_data_countries.json',
        help="The JSON output file name. Default: fbref_data_countries.json"
    )
    
    # Additional subcommands can be added here in the future.
    
    return parser
