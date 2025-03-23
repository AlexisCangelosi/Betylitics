#!/usr/bin/env python3
import json
import argparse

def print_structure(data, level=1, max_level=4):
    """
    Affiche récursivement l'arborescence d'un JSON sans afficher les données,
    en s'arrêtant au niveau max_level.
    
    - level: niveau courant (1 pour la racine)
    - max_level: niveau maximum à afficher
    """
    prefix = " " * ((level - 1) * 4)  # Chaque niveau est indenté de 4 espaces
    if isinstance(data, dict):
        for key, value in data.items():
            print(f"{prefix}{key}")
            if level < max_level:
                print_structure(value, level + 1, max_level)
    elif isinstance(data, list) and data:
        print(f"{prefix}[]")
        if level < max_level:
            print_structure(data[0], level + 1, max_level)

def main():
    parser = argparse.ArgumentParser(
        description="Affiche l'arborescence (hiérarchie) d'un fichier JSON jusqu'au 4ème niveau sans afficher les données."
    )
    parser.add_argument("json_file", help="Chemin vers le fichier JSON")
    args = parser.parse_args()

    try:
        with open(args.json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Erreur lors du chargement du JSON : {e}")
        return

    print_structure(data, level=1, max_level=4)

if __name__ == "__main__":
    main()
