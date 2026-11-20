"""Single-port asyncio HTTP + RFC 6455 WebSocket 60Hz server for Đảo Đèn Lồng."""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import socket
import struct
import sys
import webbrowser
from pathlib import Path

from src.sim.config import ROOT_DIR, TICK_RATE, load_contract
from src.sim.engine import GameSim, InputState

WEB_DIR = ROOT_DIR / "web"
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
}


class EdgeTracker:
    """Tracks browser button transitions so quick key taps never miss a 60Hz step."""

    def __init__(self) -> None:
        self.held = False
        self.pending_presses = 0
        self.released_since_tick = False

    def reset(self) -> None:
        self.held = False
        self.pending_presses = 0
        self.released_since_tick = False

    def update_from_client(self, pressed: bool) -> None:
        pressed = bool(pressed)
        if pressed and not self.held:
            self.pending_presses = min(self.pending_presses + 1, 3)
        elif not pressed and self.held:
            self.released_since_tick = True
        self.held = pressed

    def next_sim_value(self, sim_prev: bool) -> bool:
        if not sim_prev:
            if self.pending_presses > 0:
                self.pending_presses -= 1
                return True
            if self.held:
                return True
            return False
        if self.released_since_tick or not self.held:
            self.released_since_tick = False
            return False
        return True


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


async def _ws_read_frame(reader: asyncio.StreamReader) -> tuple[int, bytes] | None:
    try:
        head = await reader.readexactly(2)
    except (asyncio.IncompleteReadError, ConnectionError):
        return None

    b1, b2 = head[0], head[1]
    opcode = b1 & 0x0F
    masked = (b2 & 0x80) != 0
    length = b2 & 0x7F

    if length == 126:
        ext = await reader.readexactly(2)
        length = struct.unpack("!H", ext)[0]
    elif length == 127:
        ext = await reader.readexactly(8)
        length = struct.unpack("!Q", ext)[0]

    if length > 2_000_000:
        raise ValueError("WebSocket frame too large")

    mask_key = await reader.readexactly(4) if masked else b""
    payload = bytearray(await reader.readexactly(length)) if length else bytearray()
    if masked:
        for i in range(length):
            payload[i] ^= mask_key[i & 3]
    return opcode, bytes(payload)


class ClientSession:
    """Manages one player WebSocket session stepping GameSim at 60Hz."""

    def __init__(self, initial_seed: int, contract: dict) -> None:
        self.seed = int(initial_seed)
        self.contract = contract
        self.sim = GameSim(seed=self.seed, night=1, contract=self.contract)
        self.paused = False
        self.move_x = 0.0
        self.move_z = 0.0
        self.cam_yaw_deg = 0.0
        self.jump_edge = EdgeTracker()
        self.interact_edge = EdgeTracker()
        self.pulse_edge = EdgeTracker()

    def reset(self, new_seed: int | None = None) -> None:
        if new_seed is not None:
            self.seed = int(new_seed)
        self.sim = GameSim(seed=self.seed, night=1, contract=self.contract)
        self.paused = False
        self.jump_edge.reset()
        self.interact_edge.reset()
        self.pulse_edge.reset()

    def step_tick(self) -> list[dict]:
        inp = InputState(
            move_x=self.move_x,
            move_z=self.move_z,
            cam_yaw_deg=self.cam_yaw_deg,
            jump=self.jump_edge.next_sim_value(self.sim._prev_jump),
            interact=self.interact_edge.next_sim_value(self.sim._prev_interact),
            pulse=self.pulse_edge.next_sim_value(self.sim._prev_pulse),
        )
        return self.sim.step(inp)


async def _send_ws_json(writer: asyncio.StreamWriter, lock: asyncio.Lock, obj: dict) -> None:
    payload = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    frame = _ws_build_frame(0x1, payload)
    async with lock:
        writer.write(frame)
        await writer.drain()


async def _handle_websocket(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    headers: dict[str, str],
    seed: int,
    contract: dict,
) -> None:
    ws_key = headers.get("sec-websocket-key")
    if not ws_key:
        writer.write(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
        await writer.drain()
        return

    accept_raw = hashlib.sha1((ws_key.strip() + WS_GUID).encode("ascii")).digest()
    accept_b64 = base64.b64encode(accept_raw).decode("ascii")
    handshake = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept_b64}\r\n\r\n"
    ).encode("ascii")
    writer.write(handshake)
    await writer.drain()

    session = ClientSession(initial_seed=seed, contract=contract)
    write_lock = asyncio.Lock()
    closed = asyncio.Event()

    await _send_ws_json(
        writer, write_lock, {"type": "frame", "state": session.sim.ui_state(), "events": []}
    )

    async def reader_loop() -> None:
        try:
            while not closed.is_set():
                frame = await _ws_read_frame(reader)
                if frame is None:
                    break
                opcode, payload = frame
                if opcode == 0x8:
                    async with write_lock:
                        writer.write(_ws_build_frame(0x8, b""))
                        await writer.drain()
                    break
                if opcode == 0x9:
                    async with write_lock:
                        writer.write(_ws_build_frame(0xA, payload))
                        await writer.drain()
                    continue
                if opcode != 0x1:
                    continue

                try:
                    msg = json.loads(payload.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue

                mtype = msg.get("type")
                if mtype == "input":
                    mv = msg.get("move")
                    if isinstance(mv, list) and len(mv) == 2:
                        session.move_x = max(-1.0, min(1.0, float(mv[0])))
                        session.move_z = max(-1.0, min(1.0, float(mv[1])))
                    if "cam_yaw_deg" in msg:
                        session.cam_yaw_deg = float(msg["cam_yaw_deg"])
                    session.jump_edge.update_from_client(bool(msg.get("jump", False)))
                    session.interact_edge.update_from_client(bool(msg.get("interact", False)))
                    session.pulse_edge.update_from_client(bool(msg.get("pulse", False)))
                elif mtype == "restart":
                    new_seed = msg.get("seed")
                    session.reset(int(new_seed) if isinstance(new_seed, int) else None)
                    await _send_ws_json(
                        writer,
                        write_lock,
                        {"type": "frame", "state": session.sim.ui_state(), "events": []},
                    )
                elif mtype == "pause":
                    session.paused = bool(msg.get("paused", False))
        except (ConnectionError, ValueError):
            pass
        finally:
            closed.set()

    async def sim_loop() -> None:
        dt = 1.0 / TICK_RATE
        loop = asyncio.get_running_loop()
        next_tick = loop.time()
        try:
            while not closed.is_set():
                now = loop.time()
                if now < next_tick:
                    await asyncio.sleep(next_tick - now)
                next_tick += dt
                if loop.time() - next_tick > 0.25:
                    next_tick = loop.time() + dt

                if not session.paused and session.sim.state == "playing":
                    events = session.step_tick()
                    await _send_ws_json(
                        writer,
                        write_lock,
                        {"type": "frame", "state": session.sim.ui_state(), "events": events},
                    )
        except ConnectionError:
            pass
        finally:
            closed.set()

    await asyncio.gather(reader_loop(), sim_loop(), return_exceptions=True)


async def _send_http_response(
    writer: asyncio.StreamWriter, status: int, reason: str, content_type: str, body: bytes
) -> None:
    headers = (
        f"HTTP/1.1 {status} {reason}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Cache-Control: no-store\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii")
    writer.write(headers + body)
    await writer.drain()


async def _handle_connection(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    seed: int,
    contract: dict,
) -> None:
    try:
        raw_head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5.0)
    except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, asyncio.TimeoutError, ConnectionError):
        writer.close()
        return

    lines = raw_head.decode("latin-1").split("\r\n")
    request_line = lines[0].split(" ")
    if len(request_line) < 2:
        writer.close()
        return

    method = request_line[0].upper()
    raw_path = request_line[1].split("?", 1)[0]
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()

    try:
        if raw_path == "/ws" and headers.get("upgrade", "").lower() == "websocket":
            await _handle_websocket(reader, writer, headers, seed, contract)
            return

        if method != "GET":
            await _send_http_response(writer, 405, "Method Not Allowed", "text/plain", b"Method Not Allowed")
            return

        if raw_path == "/api/config":
            body = json.dumps(contract, ensure_ascii=False).encode("utf-8")
            await _send_http_response(writer, 200, "OK", "application/json; charset=utf-8", body)
            return

        rel_path = "index.html" if raw_path == "/" else raw_path.lstrip("/")
        candidate = (WEB_DIR / rel_path).resolve()
        if not str(candidate).startswith(str(WEB_DIR.resolve())) or not candidate.is_file():
            await _send_http_response(writer, 404, "Not Found", "text/plain", b"Not Found")
            return

        mime = MIME_TYPES.get(candidate.suffix.lower(), "application/octet-stream")
        await _send_http_response(writer, 200, "OK", mime, candidate.read_bytes())
    except ConnectionError:
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


def _find_available_port(host: str, preferred_port: int, span: int = 20) -> int:
    for port in range(preferred_port, preferred_port + span):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found in range {preferred_port}..{preferred_port + span - 1}")


async def _serve(host: str, port: int, seed: int, no_open: bool) -> None:
    contract = load_contract()
    actual_port = _find_available_port(host, port)
    server = await asyncio.start_server(
        lambda r, w: _handle_connection(r, w, seed, contract),
        host=host,
        port=actual_port,
    )
    url = f"http://{host}:{actual_port}/"
    print(f"Đảo Đèn Lồng đang chạy tại: {url} (seed={seed})", flush=True)
    print("Nhấn Ctrl+C để dừng server.", flush=True)

    if not no_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    async with server:
        await server.serve_forever()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Đảo Đèn Lồng 3D interactive web game")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Preferred HTTP/WS port (default: 8765)")
    parser.add_argument("--seed", type=int, default=42, help="Initial PRNG seed (default: 42)")
    parser.add_argument("--no-open", action="store_true", help="Do not open browser automatically")
    args = parser.parse_args(argv)

    try:
        asyncio.run(_serve(args.host, args.port, args.seed, args.no_open))
    except KeyboardInterrupt:
        print("\nĐã dừng server.")
        return 0
    except Exception as exc:
        print(f"Server error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
