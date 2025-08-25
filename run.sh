set -euo pipefail

export ROW=2
export SERVER_NAME="SERVER_NAME"
export SERVER_TYPE="internal"              # or "external"
export SHEET_ID="<sheet_id>"                # https://docs.google.com/spreadsheets/d/<sheet_id>/edit ...
export SHEET_TAB_USERS="GPU_USERS"          # worksheet for internal servers
export SHEET_TAB_PROCS="GPU_PROCS"          # worksheet for external servers
export GOOGLE_APPLICATION_CREDENTIALS="your_key_path.json"

# update sheet every 60 seconds
watch -n 60 'python update_gsheet.py'
