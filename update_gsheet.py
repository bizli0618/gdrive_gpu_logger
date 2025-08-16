import os, time, datetime, pytz
import pynvml as nv
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIG ---
TZ = pytz.timezone("Asia/Seoul")
if True:
    SHEET_ID = os.environ.get("SHEET_ID")              # e.g., 1AbC...XYZ
    SHEET_TAB = os.environ.get("SHEET_TAB", "GPU")     # worksheet/tab name
    SA_JSON   = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")  # path to service account JSON
    # --- AUTH ---
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(SA_JSON, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    try:
        ws = sh.worksheet(SHEET_TAB)
    except gspread.exceptions.WorksheetNotFound:
        print('create a tab named GPU')
        assert False
        # ws = sh.add_worksheet(title=SHEET_TAB, rows=1, cols=12)
        # ws.append_row(["timestamp","host","gpu_index","name","util_percent","mem_used_GB","mem_total_GB","temp_C"])

# --- GPU METRICS ---
nv.nvmlInit()
host = os.environ.get("SERVER_NAME", os.uname().nodename)
# now = datetime.datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S%z")
now = datetime.datetime.now(TZ).strftime("%m-%d / %H:%M:%S")

rows = []
for i in range(nv.nvmlDeviceGetCount()):
    h = nv.nvmlDeviceGetHandleByIndex(i)
    name = nv.nvmlDeviceGetName(h)
    util = nv.nvmlDeviceGetUtilizationRates(h).gpu
    gpu_mem  = nv.nvmlDeviceGetMemoryInfo(h)
    temp = nv.nvmlDeviceGetTemperature(h, nv.NVML_TEMPERATURE_GPU)
    rows.append([
        now, host, i, util,
        round(gpu_mem.used/(1.0 * (1024 ** 3)),3), round(gpu_mem.total/(1.0 * (1024 ** 3)),3), temp, name
    ])

# Batch append (1 API call even for many GPUs)
start_row = int(os.environ.get("ROW"))
end_row = start_row + len(rows) - 1
range_str = f"A{start_row}:H{end_row}"  # adjust H to your last column


if rows:
    # ws.append_rows(rows, value_input_option="USER_ENTERED")
    ws.update(range_name=range_str, values=rows, value_input_option="USER_ENTERED")

nv.nvmlShutdown()

