set -euo pipefail

export ROW=2
export SERVER_NAME="SERVER_NAME"
export SHEET_ID="your_sheet_id"
export GOOGLE_APPLICATION_CREDENTIALS="your_path.json"

watch -n 60 'python update_gsheet.py'
