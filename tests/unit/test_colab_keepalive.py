"""The Colab tunnel and keep-alive cells, tested without Colab.

The cells are read straight from colab/gemma_server.ipynb and run against fake processes, a fake clock and fake
HTTP answers, so what is tested is the code that really ships in the notebook.
"""
import ast
import json
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

NOTEBOOK = Path(__file__).resolve().parents[2] / "colab" / "gemma_server.ipynb"


def cell_source(marker: str) -> str:
    cells = json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]
    hits = ["".join(c["source"]) for c in cells if c["cell_type"] == "code" and marker in "".join(c["source"])]
    assert len(hits) == 1, f"expected exactly one cell containing {marker!r}, found {len(hits)}"
    return hits[0]


class FakeProc:
    def __init__(self):
        self.returncode = None

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = -15

    def die(self):
        self.returncode = 1


class World:
    """Fake machine: which processes exist, whether Ollama answers, what the tunnel log says."""

    def __init__(self, tmp_path, monkeypatch):
        self.tmp = tmp_path
        self.ollama_up = True
        self.metrics_answers = True            # does cloudflared's /ready answer at all
        self.tunnel_writes_url = True
        self.cloudflared_starts = 0
        self.ollama_starts = 0
        self.sleeps = []
        self.clock = 0.0
        self.on_sleep = None
        self.procs = []

        ns = {"KEEPALIVE_AUTORUN": False, "__name__": "cell"}
        exec(cell_source("def start_tunnel"), ns)
        exec(cell_source("KEEP-ALIVE"), ns)
        ns["TUNNEL_LOG"] = str(tmp_path / "tunnel.log")
        ns["OLLAMA_LOG"] = str(tmp_path / "ollama.log")
        ns["_status"] = self.status
        self.ns = ns

        monkeypatch.setattr(subprocess, "Popen", self.popen)
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: None)      # the pkill
        monkeypatch.setattr(time, "sleep", self.sleep)
        monkeypatch.setattr(time, "monotonic", lambda: self.clock)
        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("real network call"))

    # -- fakes ------------------------------------------------------------------
    def status(self, url, timeout=3):
        if "11434" in url:
            return 200 if self.ollama_up else None
        if "20241" in url:
            alive = self.ns["tunnel"]["proc"] is not None and self.ns["tunnel"]["proc"].poll() is None
            return 200 if (alive and self.metrics_answers) else None
        raise AssertionError(url)

    def popen(self, cmd, stdout=None, stderr=None, **kw):
        proc = FakeProc()
        self.procs.append(proc)
        if cmd[0] == "ollama":
            self.ollama_starts += 1
            self.ollama_up = True
        else:
            assert "--metrics" in cmd and "--http-host-header" in cmd
            self.cloudflared_starts += 1
            if self.tunnel_writes_url:
                stdout.write(f"https://tunnel-{self.cloudflared_starts}.trycloudflare.com\nRegistered tunnel connection\n")
                stdout.flush()
        return proc

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.clock += seconds
        if self.on_sleep:
            self.on_sleep(len(self.sleeps), seconds)

    # -- helpers ----------------------------------------------------------------
    def start_tunnel(self):
        return self.ns["start_tunnel"]()

    def supervise(self, **kw):
        return self.ns["supervise"](**kw)

    def long_sleeps(self):
        return [s for s in self.sleeps if s >= 20]


@pytest.fixture
def world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


# ---------------------------------------------------------------- the cells themselves ---------------------

def test_cells_are_valid_python_and_ship_no_secrets_or_names():
    for marker in ("def start_tunnel", "KEEP-ALIVE"):
        src = cell_source(marker)
        ast.parse(src)
        assert "trycloudflare.com\"" not in src.replace("https://[-a-z0-9]+\\.trycloudflare\\.com", "")
        # the two names are assembled from pieces so this file does not contain them itself
        forbidden = ("cla" + "ude", "anthro" + "pic")
        assert not any(word in src.lower() for word in forbidden)


def test_notebook_order_is_tunnel_then_check_then_keepalive_last():
    cells = json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]
    code = ["".join(c["source"]) for c in cells if c["cell_type"] == "code"]
    order = [next(i for i, s in enumerate(code) if m in s) for m in ("def start_tunnel", "Gemma (local)", "KEEP-ALIVE")]
    assert order == sorted(order) and order[-1] == len(code) - 1


# ---------------------------------------------------------------- starting a tunnel -----------------------------

def test_start_tunnel_returns_the_url_and_runs_cloudflared_with_the_right_flags(world):
    assert world.start_tunnel() == "https://tunnel-1.trycloudflare.com"
    assert world.ns["tunnel_ok"]() is True


def test_start_tunnel_gives_up_with_none_when_no_url_ever_appears(world):
    world.tunnel_writes_url = False
    assert world.start_tunnel() is None
    assert len(world.sleeps) >= 60                      # it waited, but not forever


def test_tunnel_is_not_healthy_once_the_process_dies(world):
    world.start_tunnel()
    world.procs[-1].die()
    assert world.ns["tunnel_ok"]() is False


def test_falls_back_to_the_log_when_the_metrics_port_is_silent(world):
    world.metrics_answers = False
    assert world.start_tunnel() == "https://tunnel-1.trycloudflare.com"   # healthy because the log says so


# ---------------------------------------------------------------- keep-alive loop -------------------------------

def test_steady_state_does_nothing_but_an_occasional_heartbeat(world, capsys):
    world.supervise(max_ticks=15)
    out = capsys.readouterr().out
    assert world.cloudflared_starts == 1 and world.ollama_starts == 0
    assert out.count("OLLAMA_URL =") == 1 and "still running" in out
    assert world.long_sleeps() == [20] * 15


def test_dead_tunnel_is_replaced_and_the_new_url_is_announced(world, capsys):
    def kill_tunnel_once(n, s):
        if s == 20 and world.cloudflared_starts == 1:       # the first normal check interval
            world.procs[-1].die()

    world.on_sleep = kill_tunnel_once
    world.supervise(max_ticks=3)
    out = capsys.readouterr().out
    assert world.cloudflared_starts == 2
    assert "the tunnel is down, starting a new one" in out
    assert "OLLAMA_URL = https://tunnel-1.trycloudflare.com" in out
    assert "OLLAMA_URL = https://tunnel-2.trycloudflare.com" in out
    assert (world.tmp / "tunnel.log").read_text().count("trycloudflare") == 1      # log was reset for the new tunnel


def test_dead_ollama_is_restarted(world, capsys):
    def kill_ollama_once(n, s):
        if s == 20 and world.ollama_starts == 0:
            world.ollama_up = False
    world.on_sleep = kill_ollama_once
    world.supervise(max_ticks=2)
    assert world.ollama_starts == 1 and "ollama stopped, restarting" in capsys.readouterr().out
    assert world.cloudflared_starts == 1                 # the tunnel was fine, so it was left alone


def test_ollama_that_is_down_at_the_start_is_started(world, capsys):
    world.ollama_up = False
    world.supervise(max_ticks=1)
    assert world.ollama_starts == 1 and "starting ollama" in capsys.readouterr().out


def test_a_tunnel_that_is_up_but_has_no_known_address_counts_as_failed(world, capsys):
    world.tunnel_writes_url = False
    world.supervise(max_ticks=2)
    assert world.cloudflared_starts == 3                 # initial attempt plus one retry per tick
    assert "OLLAMA_URL =" not in capsys.readouterr().out


def test_failed_tunnel_starts_back_off_instead_of_hammering_cloudflare(world, capsys):
    world.tunnel_writes_url = False
    world.supervise(max_ticks=4)
    waits = world.long_sleeps()
    assert waits == [30, 60, 90, 120]
    assert max(waits) <= 300
    assert "will retry" in capsys.readouterr().out


def test_it_recovers_after_a_failed_attempt(world, capsys):
    world.tunnel_writes_url = False
    world.on_sleep = lambda n, s: setattr(world, "tunnel_writes_url", True) if s == 30 else None
    world.supervise(max_ticks=3)
    out = capsys.readouterr().out
    assert "OLLAMA_URL = https://tunnel-" in out
    assert world.long_sleeps()[-1] == 20                 # back to the normal check interval after success


def test_time_limit_stops_the_loop_so_the_free_gpu_is_not_burned(world, capsys):
    result = world.supervise(check_every=20, max_minutes=2)
    assert result == "time_limit"
    assert "stopping to save your free GPU time" in capsys.readouterr().out
    assert sum(world.long_sleeps()) <= 2 * 60 + 20


def test_url_is_saved_to_a_file_for_convenience(world, monkeypatch):
    saved = {}
    real_open = open

    def fake_open(path, mode="r", *a, **k):
        if str(path) == "/content/ollama_url.txt":
            class F:
                def write(self, s): saved["url"] = s
                def __enter__(self): return self
                def __exit__(self, *e): pass
            return F()
        return real_open(path, mode, *a, **k)

    monkeypatch.setitem(world.ns, "open", fake_open)
    world.supervise(max_ticks=1)
    assert saved["url"] == "https://tunnel-1.trycloudflare.com"


# ---------------------------------------------------------------- the editable settings -------------------------

def test_defaults_protect_the_free_gpu_quota():
    ns = {"KEEPALIVE_AUTORUN": False}
    exec(cell_source("def start_tunnel"), ns)
    exec(cell_source("KEEP-ALIVE"), ns)
    assert ns["MAX_MINUTES"] == 90 and ns["RELEASE_GPU"] is True
