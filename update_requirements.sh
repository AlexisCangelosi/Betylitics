#!/bin/bash
rm requirements.txt
python3 -m  pipreqs.pipreqs . --force
