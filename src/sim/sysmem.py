"""Cross-platform pure-stdlib process RSS memory reader (Windows, Linux, macOS)."""

from __future__ import annotations

import os
import subprocess
import sys


def _get_rss_bytes_windows(pid: int) -> int | None:
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        PROCESS_VM_READ = 0x0010
        kernel32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi

        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, pid)
        if not handle:
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return None
        try:
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return int(counters.WorkingSetSize)
            return None
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return None


def _get_descendant_pids_windows(root_pid: int) -> list[int]:
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_void_p),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.WCHAR * 260),
            ]

        TH32CS_SNAPPROCESS = 0x00000002
        INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
        kernel32.Process32FirstW.restype = wintypes.BOOL
        kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
        kernel32.Process32NextW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snap == INVALID_HANDLE_VALUE or not snap:
            return [root_pid]

        children: dict[int, list[int]] = {}
        try:
            pe = PROCESSENTRY32W()
            pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            ok = kernel32.Process32FirstW(snap, ctypes.byref(pe))
            while ok:
                children.setdefault(int(pe.th32ParentProcessID), []).append(int(pe.th32ProcessID))
                ok = kernel32.Process32NextW(snap, ctypes.byref(pe))
        finally:
            kernel32.CloseHandle(snap)

        seen: set[int] = {root_pid}
        stack = [root_pid]
        while stack:
            cur = stack.pop()
            for child in children.get(cur, ()):
                if child not in seen:
                    seen.add(child)
                    stack.append(child)
        return sorted(seen)
    except Exception:
        return [root_pid]


def _get_rss_bytes_linux(pid: int) -> int | None:
    try:
        with open(f"/proc/{pid}/status", "r", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        return int(parts[1]) * 1024
        return None
    except Exception:
        return None


def _get_rss_bytes_ps(pid: int) -> int | None:
    try:
        proc = subprocess.run(
            ["ps", "-o", "rss=", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=False,
            timeout=1.5,
        )
        if proc.returncode != 0:
            return None
        val = proc.stdout.strip()
        if not val:
            return None
        return int(val.splitlines()[0].strip()) * 1024
    except Exception:
        return None


def get_rss_mb(pid: int | None = None) -> float | None:
    """Return Resident Set Size (WorkingSet on Windows) in MiB for pid (default: self)."""
    target_pid = os.getpid() if pid is None else int(pid)
    raw: int | None = None
    if sys.platform.startswith("win"):
        raw = _get_rss_bytes_windows(target_pid)
    elif sys.platform.startswith("linux"):
        raw = _get_rss_bytes_linux(target_pid)
        if raw is None:
            raw = _get_rss_bytes_ps(target_pid)
    else:
        raw = _get_rss_bytes_ps(target_pid)

    if raw is None or raw <= 0:
        return None
    return round(raw / (1024.0 * 1024.0), 1)


def get_process_tree_rss_mb(root_pids: list[int]) -> float | None:
    """Return total RSS in MiB across the given root PIDs and any child processes."""
    if sys.platform.startswith("win"):
        all_pids: set[int] = set()
        for rp in root_pids:
            all_pids.update(_get_descendant_pids_windows(int(rp)))
        total_bytes = 0
        for pid in all_pids:
            b = _get_rss_bytes_windows(pid)
            if b:
                total_bytes += b
        return round(total_bytes / (1024.0 * 1024.0), 1) if total_bytes > 0 else None

    if sys.platform.startswith(("linux", "darwin")):
        # Aggregate root_pids plus matching children via ps
        try:
            proc = subprocess.run(
                ["ps", "-eo", "pid=,ppid=,rss="],
                capture_output=True,
                text=True,
                check=False,
                timeout=1.5,
            )
            if proc.returncode == 0:
                children: dict[int, list[int]] = {}
                rss_map: dict[int, int] = {}
                for line in proc.stdout.splitlines():
                    parts = line.split()
                    if len(parts) == 3:
                        p, pp, r = int(parts[0]), int(parts[1]), int(parts[2])
                        children.setdefault(pp, []).append(p)
                        rss_map[p] = r
                seen: set[int] = set(int(p) for p in root_pids)
                stack = list(seen)
                while stack:
                    cur = stack.pop()
                    for ch in children.get(cur, ()):
                        if ch not in seen:
                            seen.add(ch)
                            stack.append(ch)
                kb = sum(rss_map.get(p, 0) for p in seen)
                return round(kb / 1024.0, 1) if kb > 0 else None
        except Exception:
            pass

    # Fallback sum over root PIDs
    total_mb = 0.0
    any_ok = False
    for rp in root_pids:
        val = get_rss_mb(rp)
        if val is not None:
            total_mb += val
            any_ok = True
    return round(total_mb, 1) if any_ok else None
