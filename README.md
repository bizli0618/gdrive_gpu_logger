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

See `run.sh` for an example of the required environment variables.
