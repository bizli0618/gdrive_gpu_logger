set -euo pipefail

export ROW=2
export SERVER_NAME="SERVER_NAME"
export SHEET_ID="<sheet_id>"                                 # https://docs.google.com/spreadsheets/d/<sheet_id>/edit ...
export GOOGLE_APPLICATION_CREDENTIALS="your_key_path.json"

# update sheet every 60 seconds
watch -n 60 'python update_gsheet.py'
