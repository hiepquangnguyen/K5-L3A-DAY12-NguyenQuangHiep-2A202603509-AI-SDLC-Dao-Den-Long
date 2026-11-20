"""Phase 4 (TICKET-04 / Contract v1.3) tests for bench, soak, leaderboard, and packaging."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.bench import compute_bench_metrics
from src.play import _handle_connection
from src.sim.config import load_contract
from src.sim.engine import GameSim, InputState, dist_xz
from src.sim.leaderboard import (
    LeaderboardError,
    add_entry,
    export_leaderboard,
    load_entries,
)
from src.soak import run_soak

ROOT = Path(__file__).resolve().parents[1]


class TestPhase4Release(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()

    def test_contract_v1_3_metadata_and_commands(self) -> None:
        self.assertEqual(self.contract["contract_version"], "1.3")
        self.assertEqual(self.contract["bench_cmd"], "python3 -m src.bench")
        self.assertEqual(self.contract["soak_cmd"], "python3 -m src.soak")

    def test_benchmark_scene_and_frozen_rules(self) -> None:
        sim1 = GameSim.create_benchmark(seed=42, contract=self.contract)
        sim2 = GameSim.create_benchmark(seed=42, contract=self.contract)

        self.assertTrue(sim1.bench_mode)
        self.assertEqual(len(sim1.shades), 200)
        self.assertEqual(len(sim1.motes), 100)
        self.assertTrue(all(s.state == "wander" for s in sim1.shades))

        lit_lanterns = [l for l in sim1.lanterns if l.id in ("L1", "L2", "L3")]
        unlit_lanterns = [l for l in sim1.lanterns if l.id in ("L4", "L5")]
        self.assertEqual(len(lit_lanterns), 3)
        self.assertEqual(len(unlit_lanterns), 2)
        for lantern in lit_lanterns:
            self.assertTrue(lantern.lit)
            self.assertEqual(lantern.fuel_60, 6000)
        for lantern in unlit_lanterns:
            self.assertFalse(lantern.lit)
            self.assertEqual(lantern.fuel_60, 0)

        for shade in sim1.shades:
            for lantern in lit_lanterns:
                self.assertGreaterEqual(dist_xz(shade.x, shade.z, lantern.x, lantern.z), 6.2)

        idle = InputState()
        for _ in range(180):
            sim1.step(idle)
            sim2.step(idle)

        snap1 = sim1.snapshot()
        snap2 = sim2.snapshot()
        self.assertEqual(snap1, snap2)
        self.assertEqual(sim1.state, "playing")
        self.assertEqual(len(sim1.shades), 200)
        self.assertTrue(all(s.state == "wander" for s in sim1.shades))
        self.assertEqual(len(sim1.motes), 100)
        for lantern in sim1.lanterns[:3]:
            self.assertEqual(lantern.fuel_60, 6000)
        self.assertEqual((sim1.player.x, sim1.player.y, sim1.player.z), (0.0, 0.0, 0.0))
        self.assertEqual(sim1.player.flames, 3)

    def test_bench_metric_formulas(self) -> None:
        dt_ms = [10.0] * 99 + [50.0]
        metrics = compute_bench_metrics(dt_ms)
        self.assertEqual(metrics["frames"], 100)
        self.assertEqual(metrics["avg_fps"], 96.2)
        self.assertEqual(metrics["p1_low_fps"], 20.0)
        self.assertEqual(metrics["frame_ms_p95"], 10.0)

        # N=101 -> k = ceil(1.01) = 2 slowest frames (40ms, 60ms) -> mean = 50ms -> p1_low = 20.0
        dt_101 = [10.0] * 99 + [40.0, 60.0]
        metrics_101 = compute_bench_metrics(dt_101)
        self.assertEqual(metrics_101["frames"], 101)
        self.assertEqual(metrics_101["p1_low_fps"], 20.0)

        with self.assertRaises(ValueError):
            compute_bench_metrics([])

    def test_soak_3_nights_no_crashes_and_bounded_memory(self) -> None:
        report = run_soak(seed=7, nights=3)
        self.assertEqual(report["nights"], 3)
        self.assertEqual(report["crashes"], 0)
        self.assertEqual(len(report["results"]), 3)
        self.assertTrue(all(res in ("won", "lost") for res in report["results"]))
        self.assertIsNotNone(report["mem_start_mb"])
        self.assertIsNotNone(report["mem_end_mb"])
        self.assertGreater(report["mem_start_mb"], 0.0)
        self.assertGreater(report["mem_end_mb"], 0.0)
        self.assertLessEqual(report["mem_end_mb"], 1.2 * report["mem_start_mb"])

    def test_leaderboard_validation_sorting_persistence_and_cli_export(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            lb_file = td_path / "leaderboard.json"
            export_file = td_path / "out.json"
            prev_env = os.environ.get("DDL_LEADERBOARD_PATH")
            os.environ["DDL_LEADERBOARD_PATH"] = str(lb_file)
            try:
                for bad_name in ("ab", "1234567890123", "bad name", "bad<>", "a b"):
                    with self.assertRaises(LeaderboardError):
                        add_entry(bad_name, score=100, nights_won=1, seed=1)

                add_entry("Mây_Đêm1", score=500, nights_won=3, seed=10, achieved_at="2026-11-20T10:00:00+07:00")
                add_entry("Player_1", score=500, nights_won=2, seed=11, achieved_at="2026-11-20T09:00:00+07:00")

                for idx in range(10):
                    add_entry(
                        f"Tester_{idx}",
                        score=100 + idx * 55,
                        nights_won=1 + (idx % 3),
                        seed=20 + idx,
                        achieved_at=f"2026-11-20T11:{idx:02d}:00+07:00",
                    )

                loaded = load_entries()
                self.assertEqual(len(loaded), 10)
                self.assertEqual(loaded[0]["score"], 595)
                self.assertEqual(loaded[-1]["score"], 210)

                # Verify tie-break on equal score (500): earlier achieved_at (Player_1) comes before Mây_Đêm1
                tied_500 = [e["name"] for e in loaded if e["score"] == 500]
                self.assertEqual(tied_500, ["Player_1", "Mây_Đêm1"])

                # Verify CLI --export-leaderboard prints valid JSON {"entries": [...]}
                env = os.environ.copy()
                env["DDL_LEADERBOARD_PATH"] = str(lb_file)
                proc = subprocess.run(
                    [sys.executable, "-m", "src.play", "--export-leaderboard", str(export_file)],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(proc.returncode, 0, msg=proc.stderr)
                exported_disk = json.loads(export_file.read_text(encoding="utf-8"))
                self.assertEqual(exported_disk, {"entries": loaded})

                # Also verify direct helper matches disk payload
                helper_out = td_path / "helper_out.json"
                helper_payload = export_leaderboard(helper_out)
                self.assertEqual(helper_payload, exported_disk)
            finally:
                if prev_env is None:
                    os.environ.pop("DDL_LEADERBOARD_PATH", None)
                else:
                    os.environ["DDL_LEADERBOARD_PATH"] = prev_env

    def test_http_leaderboard_strict_validation_and_get_post(self) -> None:
        async def _http_req(port: int, method: str, path: str, body: bytes = b"") -> tuple[int, dict]:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            hdrs = f"{method} {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n"
            if method == "POST":
                hdrs += f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n"
            writer.write((hdrs + "\r\n").encode("ascii") + body)
            await writer.drain()
            raw = await reader.read()
            writer.close()
            head_raw, _, body_raw = raw.partition(b"\r\n\r\n")
            status_code = int(head_raw.decode("latin-1").splitlines()[0].split()[1])
            return status_code, json.loads(body_raw.decode("utf-8"))

        async def _run_scenario(lb_file: Path) -> None:
            server = await asyncio.start_server(
                lambda r, w: _handle_connection(r, w, 42, self.contract),
                host="127.0.0.1",
                port=0,
            )
            port = server.sockets[0].getsockname()[1]
            try:
                for bad_body in (
                    b'{"name": null, "score": 100, "nights_won": 1, "seed": 1}',
                    b'{"name": 123, "score": 100, "nights_won": 1, "seed": 1}',
                    b'{"name": "May_1", "score": true, "nights_won": 1, "seed": 1}',
                    b'{"name": "May_1", "score": 1e309, "nights_won": 1, "seed": 1}',
                ):
                    code, _ = await _http_req(port, "POST", "/api/leaderboard", bad_body)
                    self.assertEqual(code, 400, msg=f"Expected 400 for {bad_body!r}")

                ok_body = b'{"name": "May_1", "score": 450, "nights_won": 2, "seed": 42}'
                code, post_data = await _http_req(port, "POST", "/api/leaderboard", ok_body)
                self.assertEqual(code, 200)
                self.assertEqual(post_data["saved"]["name"], "May_1")
                self.assertEqual(len(post_data["entries"]), 1)

                code, get_data = await _http_req(port, "GET", "/api/leaderboard")
                self.assertEqual(code, 200)
                self.assertEqual(len(get_data["entries"]), 1)
                self.assertEqual(get_data["entries"][0]["score"], 450)
                self.assertTrue(lb_file.is_file())
            finally:
                server.close()
                await server.wait_closed()

        with tempfile.TemporaryDirectory() as td:
            lb_file = Path(td) / "http_lb.json"
            prev_env = os.environ.get("DDL_LEADERBOARD_PATH")
            os.environ["DDL_LEADERBOARD_PATH"] = str(lb_file)
            try:
                asyncio.run(_run_scenario(lb_file))
            finally:
                if prev_env is None:
                    os.environ.pop("DDL_LEADERBOARD_PATH", None)
                else:
                    os.environ["DDL_LEADERBOARD_PATH"] = prev_env


if __name__ == "__main__":
    unittest.main()
