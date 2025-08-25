"""Log GPU usage to Google Sheets.

This script supports two modes depending on the ``SERVER_TYPE``
environment variable:

``internal``
    Aggregates GPU memory usage per user on each GPU.

``external``
    Records a row for every GPU-bound process including the command
    line, user name and PID.

Rows are written to separate Google Sheet tabs so that internal and
external servers can be managed independently.
"""

from __future__ import annotations

import datetime
import os
from collections import defaultdict

import gspread
import psutil
import pynvml as nv
import pytz
from google.oauth2.service_account import Credentials


# ---------------------------------------------------------------------------
# Configuration & Google Sheet access
# ---------------------------------------------------------------------------

TZ = pytz.timezone("Asia/Seoul")

SERVER_TYPE = os.environ.get("SERVER_TYPE", "internal").lower()
if SERVER_TYPE not in {"internal", "external"}:
    raise ValueError("SERVER_TYPE must be 'internal' or 'external'")

SHEET_ID = os.environ.get("SHEET_ID")
SA_JSON = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
TAB_USERS = os.environ.get("SHEET_TAB_USERS", "GPU_USERS")
TAB_PROCS = os.environ.get("SHEET_TAB_PROCS", "GPU_PROCS")

scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file(SA_JSON, scopes=scopes)
gc = gspread.authorize(creds)
sh = gc.open_by_key(SHEET_ID)
tab_name = TAB_USERS if SERVER_TYPE == "internal" else TAB_PROCS
try:
    ws = sh.worksheet(tab_name)
except gspread.exceptions.WorksheetNotFound:  # pragma: no cover - requires remote sheet
    # Create the worksheet with an appropriate header if it doesn't exist.
    if SERVER_TYPE == "internal":
        header = [
            "timestamp",
            "server",
            "user",
            "gpu_id",
            "mem_used_gb",
            "total_gb",
            "util%",
        ]
        ws = sh.add_worksheet(title=tab_name, rows=1000, cols=len(header))
    else:
        header = [
            "timestamp",
            "server",
            "pid",
            "cmd",
            "user",
            "gpu_id",
            "mem_used_gb",
            "total_gb",
            "util%",
        ]
        ws = sh.add_worksheet(title=tab_name, rows=1000, cols=len(header))
    ws.append_row(header)


# ---------------------------------------------------------------------------
# GPU information gathering
# ---------------------------------------------------------------------------


SERVER_TYPE = os.environ.get("SERVER_TYPE", "internal").lower()
if SERVER_TYPE not in {"internal", "external"}:
    raise ValueError("SERVER_TYPE must be 'internal' or 'external'")

SHEET_ID = os.environ.get("SHEET_ID")
SA_JSON = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
TAB_USERS = os.environ.get("SHEET_TAB_USERS", "GPU_USERS")
TAB_PROCS = os.environ.get("SHEET_TAB_PROCS", "GPU_PROCS")

scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file(SA_JSON, scopes=scopes)
gc = gspread.authorize(creds)
sh = gc.open_by_key(SHEET_ID)
tab_name = TAB_USERS if SERVER_TYPE == "internal" else TAB_PROCS
try:
    ws = sh.worksheet(tab_name)


# ---------------------------------------------------------------------------
# GPU information gathering
# ---------------------------------------------------------------------------

nv.nvmlInit()
host = os.environ.get("SERVER_NAME", os.uname().nodename)
now = datetime.datetime.now(TZ).strftime("%m-%d / %H:%M:%S")

rows: list[list[object]] = []

for i in range(nv.nvmlDeviceGetCount()):
    handle = nv.nvmlDeviceGetHandleByIndex(i)
    util = nv.nvmlDeviceGetUtilizationRates(handle).gpu
    gpu_mem = nv.nvmlDeviceGetMemoryInfo(handle)
    total_gb = round(gpu_mem.total / (1024 ** 3), 3)

    try:
        proc_infos = nv.nvmlDeviceGetComputeRunningProcesses(handle)
    except nv.NVMLError_NotSupported:
        proc_infos = []

    if SERVER_TYPE == "internal":
        usage_by_user: dict[str, float] = defaultdict(float)
        for p in proc_infos:
            mem_gb = round(p.usedGpuMemory / (1024 ** 3), 3)
            try:
                user = psutil.Process(p.pid).username()
            except psutil.Error:
                user = "unknown"
            usage_by_user[user] += mem_gb
        if not usage_by_user:
            usage_by_user["IDLE"] = 0.0
        for user, mem in usage_by_user.items():
            rows.append([now, host, user, i, mem, total_gb, util])
    else:  # external
        if not proc_infos:
            rows.append([now, host, 0, "IDLE", "-", i, 0.0, total_gb, util])
        for p in proc_infos:
            mem_gb = round(p.usedGpuMemory / (1024 ** 3), 3)
            try:
                proc = psutil.Process(p.pid)
                user = proc.username()
                cmd = " ".join(proc.cmdline())[:40]
            except psutil.Error:
                user = "unknown"
                cmd = "unknown"
            rows.append([now, host, p.pid, cmd, user, i, mem_gb, total_gb, util])

nv.nvmlShutdown()


# ---------------------------------------------------------------------------
# Sheet update
# ---------------------------------------------------------------------------

start_row = int(os.environ.get("ROW", "2"))
end_row = start_row + len(rows) - 1

if SERVER_TYPE == "internal":
    range_str = f"A{start_row}:G{end_row}"
else:
    range_str = f"A{start_row}:I{end_row}"

if rows:  # pragma: no branch - simple batch update
    ws.update(range_name=range_str, values=rows, value_input_option="USER_ENTERED")

