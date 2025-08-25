### GPU Usage Logger (Google Sheet)

<img src="google_sheet.png" alt="Google Sheet Example" width="60%">

Simple GPU-usage logger based on Google Cloud API
* Google Cloud Service instructions from ChatGPT (written in 25.08, **DO NOT UPLOAD YOUR CREDIENTIAL FILES ONLINE!**)
  <img src="chatgpt_guide.png"  width="60%">
* Google Sheet example color & number formattings example [link](https://docs.google.com/spreadsheets/d/1CgUvc--pjhSz-DaDB7aL1pu_jVzZ7MLml-cEmmmwe8Q/edit?usp=sharing)
* Required python packages:
  ```pip install pynvml psutil gspread google-auth pytz```
* Without using python virtual enviornment we encountered an error related to external package restrictions. We used the following command to resolve the problem:  
  ```python3 -m pip config set global.break-system-packages true``` 
* We used a tmux session to run the script (run.sh) in the background.

#### Internal vs. External logging

Set `SERVER_TYPE` to `internal` to aggregate usage per user or to
`external` to log every GPU-bound process. The script writes to separate
worksheets:

| Variable | Description |
| --- | --- |
| `SHEET_TAB_USERS` | Worksheet for `internal` servers (default `GPU_USERS`) |
| `SHEET_TAB_PROCS` | Worksheet for `external` servers (default `GPU_PROCS`) |

These variables specify the names of the worksheet tabs (not user names).
If a tab does not exist, it will be created automatically with the
appropriate headers. See `run.sh` for an example of the required
environment variables.

#### Time-based aggregation

The logger can aggregate GPU usage over a fixed period instead of recording a
single snapshot. Configure the sampling with:

| Variable | Description |
| --- | --- |
| `LOG_DURATION_SEC` | Total seconds to sample before writing a row (0 for single snapshot) |
| `POLL_INTERVAL_SEC` | Seconds between samples during that period |

For example, to sample every minute for an hour:

```bash
export LOG_DURATION_SEC=3600
export POLL_INTERVAL_SEC=60
python update_gsheet.py
```
