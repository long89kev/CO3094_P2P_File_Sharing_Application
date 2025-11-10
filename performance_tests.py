from __future__ import annotations

import os
import sys
import time
import math
import queue
import shutil
import signal
import random
import string
import threading
import subprocess
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Callable

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable or "python"


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def write_bin(filepath: str, size_bytes: int):
    ensure_dir(os.path.dirname(filepath))
    # Write in chunks to avoid large memory use
    chunk = b"\0" * (1024 * 1024)  # 1 MiB chunk of zeros
    remaining = size_bytes
    with open(filepath, "wb") as f:
        while remaining > 0:
            n = min(len(chunk), remaining)
            f.write(chunk[:n])
            remaining -= n


def now_monotonic():
    return time.monotonic()


class ManagedProcess:
    def __init__(self, args: List[str], cwd: Optional[str] = None, name: str = "proc"):
        self.name = name
        self.proc = subprocess.Popen(
            args,
            cwd=cwd or ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
            creationflags=(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0),
        )
        self._lines: List[str] = []
        self._q: "queue.Queue[str]" = queue.Queue()
        self._t = threading.Thread(target=self._reader, daemon=True)
        self._t.start()

    def _reader(self):
        try:
            assert self.proc.stdout is not None
            for line in self.proc.stdout:
                self._lines.append(line.rstrip("\n"))
                self._q.put(line.rstrip("\n"))
        except Exception:
            pass

    def send(self, line: str):
        if self.proc.stdin:
            self.proc.stdin.write(line + "\n")
            self.proc.stdin.flush()

    def wait_for(self, pattern: str, timeout: float = 15.0, regex: bool = False) -> Optional[str]:
        end = time.time() + timeout
        compiled = re.compile(pattern) if regex else None
        lines_snapshot = list(self._lines)
        for ln in lines_snapshot:
            if (compiled.search(ln) if compiled else (pattern in ln)):
                return ln
        while time.time() < end:
            try:
                ln = self._q.get(timeout=0.2)
            except queue.Empty:
                continue
            if (compiled.search(ln) if compiled else (pattern in ln)):
                return ln
        return None

    def lines(self) -> List[str]:
        return list(self._lines)

    def kill(self):
        try:
            if os.name == "nt":
                try:
                    self.proc.send_signal(signal.CTRL_BREAK_EVENT) 
                except Exception:
                    self.proc.terminate()
            else:
                self.proc.terminate()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=5)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass


def start_server(port: int = 8000) -> ManagedProcess:
    args = [PY, os.path.join(ROOT, "server.py"), str(port)]
    srv = ManagedProcess(args, name=f"server:{port}")
    # Wait for startup text
    ok = srv.wait_for("Central Server started", timeout=10)
    if not ok:
        raise RuntimeError("Server failed to start or no output received.")
    return srv


def start_client(hostname: str, server_host: str, server_port: int, p2p_port: int, shared_folder: str) -> ManagedProcess:
    ensure_dir(shared_folder)
    args = [
        PY,
        os.path.join(ROOT, "client.py"),
        hostname,
        server_host,
        str(server_port),
        str(p2p_port),
        shared_folder,
    ]
    cli = ManagedProcess(args, name=f"client:{hostname}")
    # Wait for register success and P2P listener
    if not cli.wait_for("REGISTER_SUCCESS", timeout=30):
        raise RuntimeError(f"Client {hostname} failed to register.")
    # Do not block waiting for P2P listener; give a short grace period.
    time.sleep(2.0)
    return cli


def parse_timestamp(line: str) -> Optional[Tuple[int, int, int]]:
    # Expected format: [HH:MM:SS] message
    m = re.match(r"^\[(\d{2}):(\d{2}):(\d{2})\]", line)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def ts_to_seconds(ts: Tuple[int, int, int]) -> int:
    h, m, s = ts
    return h * 3600 + m * 60 + s


def publish(cli: ManagedProcess, local: str, shared: str, timeout: float = 60.0):
    cli.send(f"publish {local} {shared}")
    ok = cli.wait_for("PUBLISH_SUCCESS", timeout=timeout)
    if not ok:
        # Dump recent lines for troubleshooting
        recent = "\n".join(cli.lines()[-20:])
        raise RuntimeError(f"Publish of {local}->{shared} failed or timed out. Recent output:\n{recent}")


def fetch_and_measure(cli: ManagedProcess, filename: str, timeout: float = 120.0) -> Tuple[float, int]:
    start_snapshot = len(cli.lines())
    cli.send(f"fetch {filename}")
    size_line = None
    complete_line = None
    end_time = time.time() + timeout
    file_size = -1
    t0 = now_monotonic()
    while time.time() < end_time:
        cli.wait_for("", timeout=0.2)  # drain / allow reader to populate
        lines = cli.lines()[start_snapshot:]
        for l in lines:
            if size_line is None and "File size:" in l:
                size_line = l
                m = re.search(r"File size:\s*(\d+) bytes", l)
                if m:
                    file_size = int(m.group(1))
            if complete_line is None and "Download complete:" in l:
                complete_line = l
        if size_line and complete_line:
            break
    t1 = now_monotonic()
    if not size_line or not complete_line:
        raise RuntimeError(f"Did not observe size/completion logs for {filename}")
    elapsed = max(0.0, t1 - t0)
    # Guard against extremely small elapsed values (<1ms) that would produce infinity speeds.
    if elapsed < 0.001:
        elapsed = 0.001
    return elapsed, file_size


def mbps(bytes_size: int, seconds_taken: float) -> float:
    seconds_taken = max(seconds_taken, 0.001)
    return (bytes_size / (1024 * 1024)) / seconds_taken


def random_string(n: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


@dataclass
class TestResult:
    name: str
    details: Dict[str, float | int | str]


def test1_file_transfer_speed(base_port: int = 8000) -> List[TestResult]:
    print("\n=== Test 1: File Transfer Speed ===")
    results: List[TestResult] = []

    # Paths
    client1_dir = os.path.join(ROOT, "shared_files", "client1")
    client2_dir = os.path.join(ROOT, "shared_files", "client2")
    ensure_dir(client1_dir)
    ensure_dir(client2_dir)

    # File specs (bytes)
    files = [
        ("small.bin", 1 * 1024 * 1024),
        ("medium.bin", 20 * 1024 * 1024),
        ("large.bin", 100 * 1024 * 1024),
    ]

    # Create test files in client1
    for name, size in files:
        path = os.path.join(client1_dir, name)
        if not os.path.exists(path) or os.path.getsize(path) != size:
            print(f"Creating {name} ({size} bytes)...")
            write_bin(path, size)

    srv = start_server(base_port)
    try:
        c1 = start_client("client1", "localhost", base_port, 9001, client1_dir)
        c2 = start_client("client2", "localhost", base_port, 9002, client2_dir)

        # Publish (files already reside in shared folder; send just filename to avoid path spaces)
        for name, size in files:
            publish(c1, name, name)

        # Fetch sequentially on client2 and measure
        for name, size in files:
            print(f"Downloading {name} ({size} bytes) on client2...")
            t_sec, size_b = fetch_and_measure(c2, name, timeout=600.0)
            speed = mbps(size_b, t_sec)
            print(f"  -> Transfer time: {t_sec:.3f}s, Speed: {speed:.2f} MB/s")
            results.append(TestResult(
                name=f"Test1-{name}",
                details={"file_bytes": size_b, "time_s": t_sec, "speed_MBps": round(speed, 2)},
            ))
        return results
    finally:
        # Cleanup processes
        try:
            c1.kill()
        except Exception:
            pass
        try:
            c2.kill()
        except Exception:
            pass
        srv.kill()


def test2_peer_concurrency(base_port: int = 8000) -> List[TestResult]:
    print("\n=== Test 2: Peer Concurrency (Upload Test) ===")
    results: List[TestResult] = []

    client1_dir = os.path.join(ROOT, "shared_files", "client1")
    client2_dir = os.path.join(ROOT, "shared_files", "client2")
    client3_dir = os.path.join(ROOT, "shared_files", "client3")
    client4_dir = os.path.join(ROOT, "shared_files", "client4")
    for d in [client1_dir, client2_dir, client3_dir, client4_dir]:
        ensure_dir(d)

    # Ensure medium.bin exists and published by client1
    medium_path = os.path.join(client1_dir, "medium.bin")
    if not os.path.exists(medium_path) or os.path.getsize(medium_path) != 20 * 1024 * 1024:
        print("Creating medium.bin (20 MiB)...")
        write_bin(medium_path, 20 * 1024 * 1024)

    srv = start_server(base_port)
    c1 = c2 = c3 = c4 = None
    try:
        c1 = start_client("client1", "localhost", base_port, 9001, client1_dir)
        c2 = start_client("client2", "localhost", base_port, 9002, client2_dir)
        c3 = start_client("client3", "localhost", base_port, 9003, client3_dir)
        c4 = start_client("client4", "localhost", base_port, 9004, client4_dir)

        # File already in shared folder; avoid full path with spaces
        publish(c1, "medium.bin", "medium.bin")

        # Baseline from Test 1 for comparison (download medium.bin on client2 alone)
        print("Measuring baseline single-download time (client2 only)...")
        base_time, _ = fetch_and_measure(c2, "medium.bin", timeout=600.0)

        # Concurrent fetch on c2, c3, c4
        print("Starting 3 concurrent downloads of medium.bin (clients 2,3,4)...")
        times: Dict[str, float] = {}
        sizes: Dict[str, int] = {}
        lock = threading.Lock()

        def worker(cli: ManagedProcess, name: str):
            try:
                t, s = fetch_and_measure(cli, "medium.bin", timeout=600.0)
                with lock:
                    times[name] = t
                    sizes[name] = s
            except Exception as e:
                with lock:
                    times[name] = -1
                    sizes[name] = -1
                print(f"  {name} failed: {e}")

        threads = [
            threading.Thread(target=worker, args=(c2, "client2"), daemon=True),
            threading.Thread(target=worker, args=(c3, "client3"), daemon=True),
            threading.Thread(target=worker, args=(c4, "client4"), daemon=True),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for name in ["client2", "client3", "client4"]:
            t = times.get(name, -1)
            s = sizes.get(name, -1)
            print(f"  {name}: time={t:.3f}s size={s}")

        # Compare to baseline (expect ~3x slower)
        avg_concurrent = sum(v for v in times.values() if v > 0) / max(1, sum(1 for v in times.values() if v > 0))
        ratio = (avg_concurrent / base_time) if base_time > 0 else float("inf")
        print(f"Baseline: {base_time:.3f}s  | Concurrent avg: {avg_concurrent:.3f}s  | Ratio ~ {ratio:.2f}x")

        results.append(TestResult(
            name="Test2-medium-concurrency",
            details={
                "baseline_time_s": round(base_time, 3),
                "concurrent_avg_time_s": round(avg_concurrent, 3),
                "concurrency_ratio": round(ratio, 2),
            },
        ))
        return results
    finally:
        for cli in [c1, c2, c3, c4]:
            try:
                if cli:
                    cli.kill()
            except Exception:
                pass
        srv.kill()


def test3_server_load(base_port: int = 8000, clients_n: int = 10) -> List[TestResult]:
    print("\n=== Test 3: Server Load (Scalability Test) ===")
    results: List[TestResult] = []

    srv = start_server(base_port)
    clients: List[ManagedProcess] = []
    try:
        # Start N clients nearly simultaneously
        base_p2p = 9101
        for i in range(clients_n):
            name = f"load{i+1}"
            shared = os.path.join(ROOT, "shared_files", name)
            ensure_dir(shared)
            cli = start_client(name, "localhost", base_port, base_p2p + i, shared)
            clients.append(cli)

        # Prepare 5 tiny files per client and publish simultaneously
        print("Publishing 5 small files per client...")
        for idx, cli in enumerate(clients):
            name = f"load{idx+1}"
            shared = os.path.join(ROOT, "shared_files", name)
            for k in range(5):
                fname = f"{name}_f{k+1}.txt"
                fpath = os.path.join(shared, fname)
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(f"file {k+1} from {name} - {random_string(16)}\n")
                # File created inside its shared folder; use basename only for publish
                publish(cli, fname, fname)

        # Each client fetches 5 files from the next client in ring
        print("Issuing 5 fetches per client...")
        errors = 0
        def fetch_ring(i: int):
            nonlocal errors
            me = clients[i]
            target = (i + 1) % len(clients)
            target_name = f"load{target+1}"
            for k in range(5):
                fname = f"{target_name}_f{k+1}.txt"
                try:
                    t, s = fetch_and_measure(me, fname, timeout=120.0)
                except Exception as e:
                    errors += 1
        threads = [threading.Thread(target=fetch_ring, args=(i,), daemon=True) for i in range(len(clients))]
        t0 = now_monotonic()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        t1 = now_monotonic()
        dur = t1 - t0
        print(f"Completed {clients_n * 5} fetch operations across {clients_n} clients in {dur:.2f}s, errors={errors}")
        results.append(TestResult(
            name="Test3-server-load",
            details={"clients": clients_n, "total_fetches": clients_n * 5, "duration_s": round(dur, 2), "errors": errors},
        ))
        print("Note: Please observe CPU usage of server.py in Task Manager during this test.")
        return results
    finally:
        for cli in clients:
            try:
                cli.kill()
            except Exception:
                pass
        srv.kill()


def write_results_md(all_results: List[TestResult], out_path: str):
    lines = ["# P2P Performance Test Results", ""]
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    lines.append(f"Generated: {ts}")
    lines.append("")
    for r in all_results:
        lines.append(f"## {r.name}")
        for k, v in r.details.items():
            lines.append(f"- {k}: {v}")
        lines.append("")
    with open(out_path, "w", encoding="utf-8") as f:
        f.writelines(l + "\n" for l in lines)


def main():
    # Allow selecting tests via env vars to avoid long runs during quick checks
    run_t1 = os.environ.get("RUN_T1", "1") == "1"
    run_t2 = os.environ.get("RUN_T2", "1") == "1"
    run_t3 = os.environ.get("RUN_T3", "1") == "1"
    base_port = int(os.environ.get("SERVER_PORT", "8000"))

    results: List[TestResult] = []
    try:
        if run_t1:
            results.extend(test1_file_transfer_speed(base_port=base_port))
        if run_t2:
            results.extend(test2_peer_concurrency(base_port=base_port))
        if run_t3:
            results.extend(test3_server_load(base_port=base_port, clients_n=10))
    finally:
        out = os.path.join(ROOT, "TEST_RESULTS.md")
        write_results_md(results, out)
        print(f"\nResults written to {out}")


if __name__ == "__main__":
    main()
