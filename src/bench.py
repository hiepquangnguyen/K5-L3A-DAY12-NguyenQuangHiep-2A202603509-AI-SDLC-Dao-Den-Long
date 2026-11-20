"""Automated 3D benchmark runner for Đảo Đèn Lồng (Test Contract v1.3)."""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import math
import os
import platform
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from src.sim.config import ROOT_DIR, TICK_RATE, load_contract
from src.sim.engine import GameSim
from src.sim.sysmem import get_process_tree_rss_mb

WEB_DIR = ROOT_DIR / "web"
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}


def compute_bench_metrics(dt_ms_list: list[float]) -> dict:
    """Compute Contract v1.3 benchmark statistics from frame delta times (ms)."""
    clean = [float(x) for x in dt_ms_list if float(x) > 0.0]
    if not clean:
        raise ValueError("Benchmark recorded zero positive frame deltas")
    n = len(clean)
    total_ms = sum(clean)
    avg_fps = (1000.0 * n) / total_ms
    k = max(1, math.ceil(0.01 * n))
    slowest_k = sorted(clean, reverse=True)[:k]
    mean_slowest = sum(slowest_k) / len(slowest_k)
    p1_low_fps = 1000.0 / mean_slowest

    sorted_dt = sorted(clean)
    p95_idx = min(n - 1, max(0, math.ceil(0.95 * n) - 1))
    frame_ms_p95 = sorted_dt[p95_idx]

    return {
        "frames": int(n),
        "avg_fps": round(avg_fps, 1),
        "p1_low_fps": round(p1_low_fps, 1),
        "frame_ms_p95": round(frame_ms_p95, 1),
    }


def discover_browser() -> tuple[str, bool]:
    """Find Chromium/Edge binary across Windows, macOS, and Linux."""
    env_bin = os.environ.get("BENCH_BROWSER")
    if env_bin and Path(env_bin).is_file():
        return env_bin, True

    candidates: list[str] = []
    if sys.platform.startswith("win"):
        for base in (
            os.environ.get("PROGRAMFILES", r"C:\Program Files"),
            os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
            os.environ.get("LOCALAPPDATA", ""),
        ):
            if not base:
                continue
            candidates.extend(
                [
                    os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"),
                    os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe"),
                    os.path.join(base, "Chromium", "Application", "chrome.exe"),
                ]
            )
    elif sys.platform == "darwin":
        candidates.extend(
            [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                "/Applications/Chromium.app/Contents/MacOS/Chromium",
            ]
        )

    for exe in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge", "msedge", "chrome"):
        found = shutil.which(exe)
        if found:
            candidates.append(found)

    for cand in candidates:
        if cand and os.path.isfile(cand):
            return cand, True

    raise RuntimeError(
        "No Chromium/Chrome/Edge browser found for benchmark. Set BENCH_BROWSER env var to browser executable."
    )


def _ws_build_frame(opcode: int, payload: bytes) -> bytes:
    header = bytearray([0x80 | (opcode & 0x0F)])
    length = len(payload)
    if length < 126:
        header.append(length)
    elif length < 65536:
        header.append(126)
        header.extend(struct.pack("!H", length))
    else:
        header.append(127)
        header.extend(struct.pack("!Q", length))
    return bytes(header) + payload


def _find_free_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


class _BenchCoordinator:
    def __init__(self, seed: int, duration: float, t_proc_start: float) -> None:
        self.sim = GameSim.create_benchmark(seed=seed, contract=load_contract())
        self.duration = float(duration)
        self.t_proc_start = t_proc_start
        self.load_ms: int | None = None
        self.dt_ms: list[float] = []
        self.renderer: str = "Three.js r170"
        self.done_event = asyncio.Event()
        self.browser_pid: int | None = None
        self.peak_mem_mb: float | None = None


async def _send_http(
    writer: asyncio.StreamWriter, status: int, reason: str, ctype: str, body: bytes
) -> None:
    head = (
        f"HTTP/1.1 {status} {reason}\r\n"
        f"Content-Type: {ctype}\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Cache-Control: no-store\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii")
    writer.write(head + body)
    await writer.drain()


async def _handle_bench_ws(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    headers: dict[str, str],
    coord: _BenchCoordinator,
) -> None:
    ws_key = headers.get("sec-websocket-key")
    if not ws_key:
        writer.close()
        return

    accept = base64.b64encode(hashlib.sha1((ws_key.strip() + WS_GUID).encode("ascii")).digest()).decode("ascii")
    writer.write(
        (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
        ).encode("ascii")
    )
    await writer.drain()

    init_msg = {
        "type": "bench_init",
        "lanterns": [
            {"id": l.id, "pos": [round(l.x, 3), round(l.y, 3), round(l.z, 3)], "lit": l.lit}
            for l in coord.sim.lanterns
        ],
        "motes": [[round(m.x, 3), round(m.y, 3), round(m.z, 3)] for m in coord.sim.motes],
        "shades": [[round(s.x, 3), round(s.y, 3), round(s.z, 3)] for s in coord.sim.shades],
    }
    writer.write(_ws_build_frame(0x1, json.dumps(init_msg, separators=(",", ":")).encode("utf-8")))
    await writer.drain()

    dt = 1.0 / TICK_RATE
    loop = asyncio.get_running_loop()
    next_tick = loop.time()

    try:
        while not coord.done_event.is_set():
            now = loop.time()
            if now < next_tick:
                await asyncio.sleep(next_tick - now)
            next_tick += dt
            if loop.time() - next_tick > 0.25:
                next_tick = loop.time() + dt

            coord.sim.step(None)  # type: ignore[arg-type]
            # Send zero-allocation binary Float32Array frame [x0,y0,z0, ...] over WS (opcode 0x2)
            floats: list[float] = []
            for s in coord.sim.shades:
                floats.extend((s.x, s.y, s.z))
            bin_payload = struct.pack(f"<{len(floats)}f", *floats)
            writer.write(_ws_build_frame(0x2, bin_payload))
            await writer.drain()
    except ConnectionError:
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def _handle_bench_conn(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    coord: _BenchCoordinator,
) -> None:
    try:
        raw_head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5.0)
    except Exception:
        writer.close()
        return

    lines = raw_head.decode("latin-1").split("\r\n")
    req = lines[0].split(" ")
    if len(req) < 2:
        writer.close()
        return
    method = req[0].upper()
    path = req[1].split("?", 1)[0]
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()

    try:
        if path == "/ws" and headers.get("upgrade", "").lower() == "websocket":
            await _handle_bench_ws(reader, writer, headers, coord)
            return

        if method == "POST" and path in ("/api/bench/first_frame", "/api/bench/done"):
            clen = int(headers.get("content-length", "0"))
            body = await asyncio.wait_for(reader.readexactly(clen), timeout=10.0) if clen > 0 else b"{}"
            if path == "/api/bench/first_frame":
                if coord.load_ms is None:
                    coord.load_ms = max(1, round((time.perf_counter() - coord.t_proc_start) * 1000.0))
                await _send_http(writer, 200, "OK", "application/json", b'{"ok":true}')
            else:
                data = json.loads(body.decode("utf-8"))
                coord.dt_ms = [float(x) for x in data.get("dt_ms", [])]
                coord.renderer = str(data.get("renderer") or coord.renderer)
                await _send_http(writer, 200, "OK", "application/json", b'{"ok":true}')
                coord.done_event.set()
            return

        if method == "GET":
            rel = "bench.html" if path in ("/", "/bench", "/bench.html") else path.lstrip("/")
            cand = (WEB_DIR / rel).resolve()
            if cand.is_relative_to(WEB_DIR.resolve()) and cand.is_file():
                mime = MIME_TYPES.get(cand.suffix.lower(), "application/octet-stream")
                await _send_http(writer, 200, "OK", mime, cand.read_bytes())
                return

        await _send_http(writer, 404, "Not Found", "text/plain", b"Not Found")
    except Exception:
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def _sample_memory_loop(coord: _BenchCoordinator) -> None:
    while not coord.done_event.is_set():
        pids = [os.getpid()]
        if coord.browser_pid is not None:
            pids.append(coord.browser_pid)
        val = await asyncio.to_thread(get_process_tree_rss_mb, pids)
        if val is not None:
            coord.peak_mem_mb = val if coord.peak_mem_mb is None else max(coord.peak_mem_mb, val)
        await asyncio.sleep(1.0)


async def _run_bench_async(seed: int, duration: float, warmup: float, t_proc_start: float) -> dict:
    browser_exe, vsync_off = discover_browser()
    port = _find_free_port()
    coord = _BenchCoordinator(seed=seed, duration=duration, t_proc_start=t_proc_start)

    server = await asyncio.start_server(
        lambda r, w: _handle_bench_conn(r, w, coord),
        host="127.0.0.1",
        port=port,
    )

    url = f"http://127.0.0.1:{port}/bench?duration={duration}&warmup={warmup}"
    profile_dir = tempfile.mkdtemp(prefix="ddl_bench_")
    browser_cmd = [
        browser_exe,
        f"--app={url}",
        "--window-size=1280,720",
        "--disable-frame-rate-limit",
        "--disable-gpu-vsync",
        "--disable-background-timer-throttling",
        "--no-first-run",
        "--no-default-browser-check",
        f"--user-data-dir={profile_dir}",
    ]

    proc = subprocess.Popen(browser_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    coord.browser_pid = proc.pid
    mem_task = asyncio.create_task(_sample_memory_loop(coord))

    try:
        timeout_s = max(30.0, duration + warmup + 35.0)
        await asyncio.wait_for(coord.done_event.wait(), timeout=timeout_s)
    finally:
        coord.done_event.set()
        mem_task.cancel()
        try:
            await mem_task
        except asyncio.CancelledError:
            pass
        server.close()
        try:
            await server.wait_closed()
        except Exception:
            pass
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                proc.kill()
        shutil.rmtree(profile_dir, ignore_errors=True)

    metrics = compute_bench_metrics(coord.dt_ms)
    return {
        "contract_version": "1.3",
        "avg_fps": metrics["avg_fps"],
        "p1_low_fps": metrics["p1_low_fps"],
        "frame_ms_p95": metrics["frame_ms_p95"],
        "frames": metrics["frames"],
        "load_ms": coord.load_ms or 0,
        "peak_mem_mb": round(coord.peak_mem_mb, 1) if coord.peak_mem_mb is not None else None,
        "vsync_off": bool(vsync_off),
        "renderer": coord.renderer,
        "os": f"{platform.system()} {platform.release()} ({platform.machine()})",
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Automated 1280x720 WebGL Benchmark (Contract v1.3)")
    parser.add_argument("--seed", type=int, default=42, help="Benchmark PRNG seed (default: 42)")
    parser.add_argument("--duration", type=float, default=30.0, help="Measurement duration in seconds (default: 30)")
    parser.add_argument("--warmup", type=float, default=3.0, help="Warm-up duration in seconds (default: 3)")
    parser.add_argument("--out", type=Path, required=True, help="Output JSON path (e.g. bench.json)")
    return parser


def main(argv: list[str] | None = None) -> int:
    t0 = time.perf_counter()
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.duration <= 0:
        print("Error: --duration must be > 0", file=sys.stderr)
        return 1

    try:
        report = asyncio.run(_run_bench_async(args.seed, args.duration, args.warmup, t0))
    except Exception as exc:
        print(f"Benchmark error: {exc}", file=sys.stderr)
        return 1

    out_file = Path(args.out)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(
        f"[bench] avg_fps={report['avg_fps']} p1_low_fps={report['p1_low_fps']} "
        f"p95={report['frame_ms_p95']}ms frames={report['frames']} "
        f"load_ms={report['load_ms']} peak_mem_mb={report['peak_mem_mb']} "
        f"renderer='{report['renderer']}'"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
