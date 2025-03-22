#!/bin/bash
# Revised script to update the st.caption element in app.py
# The new caption is built from:
#   - A fixed version string: v1.0.0
#   - Today's date in YYYYMMDD format
#   - A random 4-character UUID (lowercase)

# Fixed version string
version="v1.0.0"

# Today's date in the format YYYYMMDD
today=$(date +%Y%m%d)
hour=$(date "+%Y-%m-%d %H:%M")

# Generate a random 4-character string from uuidgen
uuid=$(uuidgen | tr '[:upper:]' '[:lower:]' | cut -c1-4)

# Build the new caption
new_caption="⚙️ ${version}-${today}.${uuid} - {update_message}"

# Use a simpler pattern to match any st.caption call
# This pattern matches: st.caption("anything")
sed -i.bak -E "s/(last_updated_str = \")[^\"]*(\")/\1${hour}\2/" app.py
sed -i.bak -E "s/st\.caption\(f?\"[^\"]*\"\)/st.caption\(f\"${new_caption}\"\)/" app.py

# Remove the backup file if it exists
rm -f app.py.bak

echo "Updated caption to: ${new_caption}"
