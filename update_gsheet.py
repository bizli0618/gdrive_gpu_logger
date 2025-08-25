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
import time

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

# Sampling configuration.  ``LOG_DURATION_SEC`` controls the total period
# over which GPU usage is aggregated.  When set to ``0`` a single snapshot is
# taken.  ``POLL_INTERVAL_SEC`` controls how often the GPUs are sampled during
# that period.
LOG_DURATION = int(os.environ.get("LOG_DURATION_SEC", "0"))
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SEC", "60"))

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


def _snapshot_internal() -> list[tuple[str, int, float, float, float]]:
    """Return a snapshot of GPU usage aggregated by user.

    Each tuple contains ``(user, gpu_id, mem_used_gb, total_gb, util)``.
    """

    rows: list[tuple[str, int, float, float, float]] = []
    for i in range(nv.nvmlDeviceGetCount()):
        handle = nv.nvmlDeviceGetHandleByIndex(i)
        util = nv.nvmlDeviceGetUtilizationRates(handle).gpu
        gpu_mem = nv.nvmlDeviceGetMemoryInfo(handle)
        total_gb = round(gpu_mem.total / (1024 ** 3), 3)
        try:
            proc_infos = nv.nvmlDeviceGetComputeRunningProcesses(handle)
        except nv.NVMLError_NotSupported:
            proc_infos = []

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
            rows.append((user, i, mem, total_gb, util))
    return rows


def _snapshot_external() -> list[tuple[int, str, str, int, float, float, float]]:
    """Return a snapshot of GPU usage for each process.

    Each tuple contains ``(pid, cmd, user, gpu_id, mem_used_gb, total_gb, util)``.
    """

    rows: list[tuple[int, str, str, int, float, float, float]] = []
    for i in range(nv.nvmlDeviceGetCount()):
        handle = nv.nvmlDeviceGetHandleByIndex(i)
        util = nv.nvmlDeviceGetUtilizationRates(handle).gpu
        gpu_mem = nv.nvmlDeviceGetMemoryInfo(handle)
        total_gb = round(gpu_mem.total / (1024 ** 3), 3)
        try:
            proc_infos = nv.nvmlDeviceGetComputeRunningProcesses(handle)
        except nv.NVMLError_NotSupported:
            proc_infos = []

        if not proc_infos:
            rows.append((0, "IDLE", "-", i, 0.0, total_gb, util))
        for p in proc_infos:
            mem_gb = round(p.usedGpuMemory / (1024 ** 3), 3)
            try:
                proc = psutil.Process(p.pid)
                user = proc.username()
                cmd = " ".join(proc.cmdline())[:40]
            except psutil.Error:
                user = "unknown"
                cmd = "unknown"
            rows.append((p.pid, cmd, user, i, mem_gb, total_gb, util))
    return rows


nv.nvmlInit()
host = os.environ.get("SERVER_NAME", os.uname().nodename)
start_ts = datetime.datetime.now(TZ)

# Aggregate samples over the desired period.
agg: dict[tuple[object, ...], list[float]] = {}
count: dict[tuple[object, ...], int] = {}

end_time = time.time() + max(LOG_DURATION, 0)
while True:
    if SERVER_TYPE == "internal":
        snap = _snapshot_internal()
        for user, gpu_id, mem, total, util in snap:
            key = (user, gpu_id)
            stats = agg.setdefault(key, [0.0, 0.0, total])  # mem, util, total
            stats[0] += mem
            stats[1] += util
            count[key] = count.get(key, 0) + 1
    else:
        snap = _snapshot_external()
        for pid, cmd, user, gpu_id, mem, total, util in snap:
            key = (pid, cmd, user, gpu_id)
            stats = agg.setdefault(key, [0.0, 0.0, total])
            stats[0] += mem
            stats[1] += util
            count[key] = count.get(key, 0) + 1

    if time.time() >= end_time or LOG_DURATION <= 0:
        break
    time.sleep(POLL_INTERVAL)

end_ts = datetime.datetime.now(TZ)
nv.nvmlShutdown()

ts_range = start_ts.strftime("%m-%d / %H:%M:%S")
if LOG_DURATION > 0:
    ts_range += "-" + end_ts.strftime("%H:%M:%S")

rows: list[list[object]] = []
if SERVER_TYPE == "internal":
    for (user, gpu_id), (mem_sum, util_sum, total_gb) in agg.items():
        c = count[(user, gpu_id)]
        rows.append(
            [
                ts_range,
                host,
                user,
                gpu_id,
                round(mem_sum / c, 3),
                total_gb,
                round(util_sum / c, 1),
            ]
        )
else:
    for (pid, cmd, user, gpu_id), (mem_sum, util_sum, total_gb) in agg.items():
        c = count[(pid, cmd, user, gpu_id)]
        rows.append(
            [
                ts_range,
                host,
                pid,
                cmd,
                user,
                gpu_id,
                round(mem_sum / c, 3),
                total_gb,
                round(util_sum / c, 1),
            ]
        )


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

