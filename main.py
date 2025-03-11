from helper import create_parser, log_info, log_success, log_error, log_warning
from fbref_countries import fetch_fbref_countries

def main():
    # Create the command-line parser using our helper module
    parser = create_parser()
    args = parser.parse_args()

    # Check which subcommand was invoked
    if args.command == 'get-countries':
        log_info("Executing 'get-countries' command...")
        fetch_fbref_countries(url=args.url, output_file=args.output)
    else:
        log_warning("No valid command provided.")
        parser.print_help()

if __name__ == '__main__':
    main()
