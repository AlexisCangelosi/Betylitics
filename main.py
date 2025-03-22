from scripts.utils.helper import create_parser, log_info, log_success, log_error, log_warning
from scripts.utils.get_countries import fetch_fbref_countries
from scripts.utils.get_clubs import fetch_fbref_clubs

def main():
    # Create the command-line parser using our helper module
    parser = create_parser()
    args = parser.parse_args()

    # Check which subcommand was invoked
    if args.command == 'get-countries':
        log_info("Executing 'get-countries' command...")
        fetch_fbref_countries(url=args.url, output_file=args.output)
    elif args.command == 'get-leagues':
        log_info("Executing 'get-leagues' command...")
        fetch_fbref_clubs(countries_file=args.url, output_file=args.output)
    else:
        log_warning("No valid command provided.")
        parser.print_help()

if __name__ == '__main__':
    main()
