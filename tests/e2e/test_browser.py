"""End-to-end tests: the real page in a real browser (Chromium via Playwright) against the real app.

Needs a browser:   pip install playwright   then   python -m playwright install chromium
If PLAYWRIGHT_BROWSERS_PATH points at a custom folder, set it before running. Without a browser these tests skip.
Gemma is replaced by a tiny fake Ollama server, so the tests are fast and need no GPU.
"""
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")
expect = playwright_sync.expect

ROOT = Path(__file__).resolve().parents[2]
DECK_KEY = "yaaddost.deck.v1"
HOUR = 3_600_000
DAY = 24 * HOUR


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ---------------------------------------------------------------- fake Ollama (the "Gemma server") --------

EVIL_QUESTION = "What does <b id='pwned'>bold</b> do?"
FAKE_CARDS = [
    {"q": "What is a deadlock?", "a": "Processes wait forever for each other's resources."},
    {"q": "Who invented the Banker's algorithm?", "a": "Edsger Dijkstra."},
    {"q": EVIL_QUESTION, "a": "Nothing: it is shown as text."},
]
DELAY = {"seconds": 0.0}   # lets one test pretend Gemma is slow


class FakeOllama(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send({"models": [{"name": "gemma4:e4b"}]})

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        time.sleep(DELAY["seconds"])
        required = (req.get("format") or {}).get("required", [])
        if required == ["cards"]:
            content = json.dumps({"cards": FAKE_CARDS})
        elif required == ["verdicts"]:
            content = json.dumps({"verdicts": [
                {"id": 1, "supported": True, "reason": "stated in the notes"},
                {"id": 2, "supported": False, "reason": "the notes never say who invented it"},
                {"id": 3, "supported": True, "reason": "ok"},
            ]})
        else:
            content = "Think of deadlock like two people each holding one chopstick."
        self._send({"message": {"content": content}})


@pytest.fixture(scope="module")
def fake_ollama():
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeOllama)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


# ---------------------------------------------------------------- the app under test --------------------------

@contextmanager
def running_app(**env):
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT, env={**os.environ, **env}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(url + "/healthz", timeout=1)
                break
            except Exception:
                time.sleep(0.25)
        else:
            raise RuntimeError("app did not start")
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture(scope="module")
def offline_app():
    with running_app(OLLAMA_URL="http://127.0.0.1:9", RATE_LIMIT_PER_MIN="0") as url:
        yield url


@pytest.fixture(scope="module")
def gemma_app(fake_ollama):
    with running_app(OLLAMA_URL=fake_ollama, RATE_LIMIT_PER_MIN="0") as url:
        yield url


@pytest.fixture(scope="module")
def browser():
    with playwright_sync.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:   # browser not installed
            pytest.skip(f"Chromium is not available: {e}")
        yield b
        b.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(viewport={"width": 1100, "height": 900})
    pg = context.new_page()
    pg.problems = []   # console errors, page errors: any of these means something is broken or blocked by the CSP
    pg.on("console", lambda m: pg.problems.append(f"console {m.type}: {m.text}") if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: pg.problems.append(f"pageerror: {e}"))
    pg.dialogs = []
    pg.on("dialog", lambda d: (pg.dialogs.append(d.message), d.accept()))
    yield pg
    context.close()


def card(i, due_in_ms=0, checked=True, q=None, a=None):
    return {"id": f"c{i}", "q": q or f"Question {i}?", "a": a or f"Answer {i}.", "ease": 2.5, "interval": 0, "reps": 0,
            "due": int(time.time() * 1000) + due_in_ms, "checked": checked}


def seed(page, cards):
    """Put a deck in the browser before the page loads (only if nothing is saved yet, so reloads keep real changes)."""
    page.add_init_script(
        f"if (!localStorage.getItem('{DECK_KEY}')) localStorage.setItem('{DECK_KEY}', {json.dumps(json.dumps(cards))});"
    )


def wait_until(page, js_expression, timeout=5.0):
    """Poll a JavaScript expression until it is truthy.

    Not page.wait_for_function: that evaluates a string inside the page, which our strict Content-Security-Policy
    (no 'unsafe-eval') can block now and then. page.evaluate goes through the debugger, so the policy stays fully on.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if page.evaluate(js_expression):
            return
        page.wait_for_timeout(50)
    raise AssertionError(f"timed out waiting for: {js_expression}")


def make_sample_cards(page):
    page.click("#sample")
    page.click("#make")


def rgb(css: str):
    return tuple(int(x, 16) for x in re.findall(r"[0-9a-fA-F]{2}", css.lstrip("#"))[:3])


def luminance(hex_color: str) -> float:
    def f(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb(hex_color)
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


# ================================================================ first use and the basic loop ================

def test_first_use_shows_a_clear_empty_state_and_hides_the_strip(offline_app, page):
    page.goto(offline_app)
    expect(page.locator("#badge")).to_have_text("Offline mode")
    expect(page.locator("#emptyTitle")).to_have_text("No cards yet")
    expect(page.locator("#dueLine")).to_have_text("No cards yet.")
    expect(page.locator("#curve")).to_be_hidden()          # an empty timeline would say nothing
    expect(page.locator("#study")).to_be_hidden()
    page.click("#emptyAction")
    expect(page.locator("#notes")).to_be_focused()         # the empty-state button leads straight to the input
    assert page.problems == []


def test_offline_cards_are_labelled_as_simple_and_unchecked(offline_app, page):
    page.goto(offline_app)
    make_sample_cards(page)
    expect(page.locator("#msg")).to_contain_text("using simple rules, because Gemma isn't connected")
    expect(page.locator("#dueLine")).to_have_text("5 cards due · 5 in your deck")
    expect(page.locator("#mark")).to_have_text("Made with simple rules, not checked")
    expect(page.locator("#curve .dot")).to_have_count(5)
    assert page.problems == []


def test_review_with_the_mouse_moves_the_dot_and_says_when_it_is_back(offline_app, page):
    page.goto(offline_app)
    make_sample_cards(page)
    expect(page.locator("#a")).to_be_hidden()
    page.click("#show")
    expect(page.locator("#a")).to_be_visible()
    expect(page.locator("#grades")).to_be_visible()
    expect(page.locator("#show")).to_be_hidden()

    page.get_by_role("button", name=re.compile("Yaad tha")).click()
    expect(page.locator("#feedback")).to_have_text("Back tomorrow.")
    expect(page.locator("#dueLine")).to_have_text("4 cards due · 5 in your deck")
    expect(page.locator("#curve .is-today .dot")).to_have_count(4)     # one dot left "today" for tomorrow's column
    expect(page.locator("#a")).to_be_hidden()                          # the next card starts with its answer hidden
    assert page.problems == []


def test_a_card_marked_again_comes_back_the_same_day(offline_app, page):
    page.goto(offline_app)
    make_sample_cards(page)
    page.click("#show")
    page.get_by_role("button", name=re.compile("Bhool gaya")).click()
    expect(page.locator("#feedback")).to_have_text("Back in 10 minutes.")
    expect(page.locator("#dueLine")).to_have_text("4 cards due · 5 in your deck")
    expect(page.locator("#curve .is-today .dot")).to_have_count(5)     # still today, just not due this minute


def test_the_dot_visibly_hops_after_grading(offline_app, page):
    page.goto(offline_app)
    make_sample_cards(page)
    page.click("#show")
    page.get_by_role("button", name=re.compile("Aasaan")).click()
    wait_until(page, "document.getAnimations().some(a => a.effect && a.effect.target && a.effect.target.classList && a.effect.target.classList.contains('dot'))", timeout=4)


def test_deck_survives_a_reload_and_keeps_its_schedule(offline_app, page):
    page.goto(offline_app)
    make_sample_cards(page)
    page.click("#show")
    page.get_by_role("button", name=re.compile("Yaad tha")).click()
    expect(page.locator("#dueLine")).to_have_text("4 cards due · 5 in your deck")
    page.reload()
    expect(page.locator("#dueLine")).to_have_text("4 cards due · 5 in your deck")
    expect(page.locator("#curve .dot")).to_have_count(5)


def test_all_caught_up_after_the_last_card(offline_app, page):
    page.goto(offline_app)
    make_sample_cards(page)
    for _ in range(5):
        page.click("#show")
        page.get_by_role("button", name=re.compile("Aasaan")).click()
        page.wait_for_timeout(120)
    expect(page.locator("#emptyTitle")).to_have_text("All caught up")
    expect(page.locator("#emptyText")).to_contain_text("Next card in")
    expect(page.locator("#study")).to_be_hidden()
    expect(page.locator("#curve")).to_be_visible()
    expect(page.locator("#dueLine")).to_have_text("Nothing due right now · 5 in your deck")


# ================================================================ keyboard ====================================

def test_the_whole_review_works_from_the_keyboard(offline_app, page):
    page.goto(offline_app)
    make_sample_cards(page)
    expect(page.locator("#study")).to_be_visible()                # wait until the cards exist
    page.locator("body").click(position={"x": 5, "y": 400})      # leave the form so shortcuts apply
    page.keyboard.press("Space")
    expect(page.locator("#a")).to_be_visible()
    page.keyboard.press("3")
    expect(page.locator("#feedback")).to_have_text("Back tomorrow.")
    expect(page.locator("#dueLine")).to_have_text("4 cards due · 5 in your deck")
    page.keyboard.press("Enter")
    page.keyboard.press("1")
    expect(page.locator("#feedback")).to_have_text("Back in 10 minutes.")
    expect(page.locator("#dueLine")).to_have_text("3 cards due · 5 in your deck")


def test_shortcut_keys_are_ignored_while_typing(offline_app, page):
    seed(page, [card(1), card(2)])
    page.goto(offline_app)
    page.click("#notes")
    page.keyboard.type("1 2 3 4   ")
    expect(page.locator("#dueLine")).to_have_text("2 cards due · 2 in your deck")
    expect(page.locator("#a")).to_be_hidden()
    expect(page.locator("#notes")).to_have_value("1 2 3 4   ")


def test_grade_keys_do_nothing_before_the_answer_is_shown(offline_app, page):
    seed(page, [card(1)])
    page.goto(offline_app)
    page.locator("body").click(position={"x": 5, "y": 400})
    page.keyboard.press("4")
    expect(page.locator("#dueLine")).to_have_text("1 card due · 1 in your deck")


# ================================================================ other inputs and states =====================

def test_clear_all_confirms_with_the_consequence_then_empties(offline_app, page):
    page.goto(offline_app)
    make_sample_cards(page)
    expect(page.locator("#study")).to_be_visible()                # wait until the cards exist
    page.click("#reset")
    assert page.dialogs == ["Delete all 5 cards? This can't be undone."]
    expect(page.locator("#emptyTitle")).to_have_text("No cards yet")
    page.reload()
    expect(page.locator("#dueLine")).to_have_text("No cards yet.")


def test_too_little_text_is_refused_politely_and_focus_moves_to_the_field(offline_app, page):
    page.goto(offline_app)
    page.fill("#notes", "too short")
    page.click("#make")
    expect(page.locator("#msg")).to_have_text("Add a few more lines of notes first.")
    expect(page.locator("#notes")).to_be_focused()
    expect(page.locator("#dueLine")).to_have_text("No cards yet.")


def test_explain_without_gemma_says_so_and_empty_input_is_handled(offline_app, page):
    page.goto(offline_app)
    page.click("#explain")
    expect(page.locator("#explainOut")).to_have_text("Type the concept you want explained.")
    page.fill("#concept", "deadlock")
    page.click("#explain")
    expect(page.locator("#explainOut")).to_contain_text("Gemma isn't connected")


def test_a_network_failure_gives_a_plain_message_and_keeps_the_page_usable(offline_app, page):
    page.goto(offline_app)
    page.route("**/api/cards", lambda route: route.abort())
    make_sample_cards(page)
    expect(page.locator("#msg")).to_have_text("Can't reach the server. Check your connection and try again.")
    expect(page.locator("#make")).to_be_enabled()
    expect(page.locator("#working")).to_be_hidden()


def test_blocked_storage_still_works_and_tells_the_student_it_wont_be_saved(offline_app, page):
    page.add_init_script("Storage.prototype.setItem = function () { throw new Error('blocked'); };")
    page.goto(offline_app)
    expect(page.locator("#storageNote")).to_contain_text("blocking storage")
    make_sample_cards(page)
    expect(page.locator("#dueLine")).to_have_text("5 cards due · 5 in your deck")     # still works for this session


def test_very_many_cards_stack_is_capped_and_labelled(offline_app, page):
    seed(page, [card(i) for i in range(30)])
    page.goto(offline_app)
    expect(page.locator("#curve .is-today .dot")).to_have_count(8)
    expect(page.locator("#curve .dot-more")).to_have_text("+22")
    assert "30 cards due today" in page.get_attribute("#curveTrack", "aria-label")


def test_one_card_and_a_very_long_question_do_not_break_the_layout(offline_app, page):
    long_q = "Why does " + "a very long question ".strip() * 1 + " " + ("supercalifragilistic" * 12) + "?"
    seed(page, [card(1, q=long_q, a="word " * 150)])
    page.goto(offline_app)
    page.click("#show")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    expect(page.locator("#dueLine")).to_have_text("1 card due · 1 in your deck")
    expect(page.locator("#progress")).to_have_text("1 of 1")


# ================================================================ with Gemma (fake) and the Verifier ==========

def test_verifier_results_and_the_checked_mark_are_shown(gemma_app, page):
    page.goto(gemma_app)
    expect(page.locator("#badge")).to_contain_text("Gemma connected")
    make_sample_cards(page)
    expect(page.locator("#msg")).to_have_text("Added 2 cards. Each one was checked against your notes.")
    expect(page.locator("#dueLine")).to_have_text("2 cards due · 2 in your deck")      # 3 written, 1 removed by the Verifier
    expect(page.locator("#mark")).to_have_text("Checked against your notes")

    expect(page.locator("#dropped")).to_be_visible()
    expect(page.locator("#droppedTitle")).to_have_text("1 card removed: not supported by your notes")
    page.click("#droppedTitle")
    expect(page.locator("#droppedList li")).to_contain_text("Who invented the Banker's algorithm?")
    expect(page.locator("#droppedList li")).to_contain_text("the notes never say who invented it")
    assert page.problems == []


def test_model_text_is_shown_as_text_and_never_becomes_html(gemma_app, page):
    page.goto(gemma_app)
    make_sample_cards(page)
    page.click("#show")
    page.get_by_role("button", name=re.compile("Yaad tha")).click()
    expect(page.locator("#dueLine")).to_have_text("1 card due · 2 in your deck")
    assert page.locator("#q").inner_text() == EVIL_QUESTION
    assert page.locator("#pwned").count() == 0
    assert page.problems == []


def test_explain_with_gemma(gemma_app, page):
    page.goto(gemma_app)
    page.fill("#concept", "deadlock")
    page.click("#explain")
    expect(page.locator("#explainOut")).to_contain_text("two people each holding one chopstick")


def test_a_slow_gemma_shows_progress_then_clears_it(fake_ollama, page):
    DELAY["seconds"] = 1.5
    try:
        with running_app(OLLAMA_URL=fake_ollama, RATE_LIMIT_PER_MIN="0") as url:
            page.goto(url)
            expect(page.locator("#badge")).to_contain_text("Gemma connected")
            make_sample_cards(page)
            expect(page.locator("#working")).to_be_visible()
            expect(page.locator("#workingText")).to_contain_text("about 30 to 45 seconds")
            expect(page.locator("#workingText")).to_contain_text("s so far")
            expect(page.locator("#make")).to_be_disabled()
            expect(page.locator("#working")).to_be_hidden(timeout=15000)
            expect(page.locator("#make")).to_be_enabled()
            expect(page.locator("#msg")).to_contain_text("Each one was checked")
    finally:
        DELAY["seconds"] = 0.0


def test_the_rate_limit_message_is_plain_and_nothing_is_lost(fake_ollama, page):
    with running_app(OLLAMA_URL=fake_ollama, RATE_LIMIT_PER_MIN="1") as url:
        page.goto(url)
        make_sample_cards(page)
        expect(page.locator("#msg")).to_contain_text("Each one was checked")
        page.click("#make")
        expect(page.locator("#msg")).to_contain_text("That's a lot of requests in a minute")
        assert "please" not in page.inner_text("#msg").lower()
        expect(page.locator("#make")).to_be_enabled()
        expect(page.locator("#dueLine")).to_have_text("2 cards due · 2 in your deck")


# ================================================================ accessibility ===============================

def test_controls_have_accessible_names_and_landmarks(offline_app, page):
    seed(page, [card(1)])
    page.goto(offline_app)
    page.click("#show")
    assert page.get_by_role("heading", level=1).count() == 1
    assert page.get_by_role("main").count() == 1
    expect(page.get_by_label("Your notes")).to_be_visible()
    expect(page.get_by_label("Concept", exact=True)).to_be_visible()
    expect(page.get_by_label("Cards", exact=True)).to_be_visible()
    expect(page.get_by_role("radiogroup", name="Language of the cards")).to_be_visible()
    expect(page.get_by_role("button", name="Dark theme")).to_have_attribute("aria-pressed", "false")
    expect(page.get_by_role("group", name="How well did you remember it?")).to_be_visible()
    for name in ("Bhool gaya", "Mushkil", "Yaad tha", "Aasaan"):
        expect(page.get_by_role("button", name=re.compile(name))).to_be_visible()
    expect(page.get_by_role("img", name=re.compile("due today"))).to_be_visible()      # the strip has a text equivalent


def test_skip_link_is_the_first_stop_and_focus_rings_are_visible(offline_app, page):
    seed(page, [card(1)])
    page.goto(offline_app)
    page.keyboard.press("Tab")
    expect(page.locator(".skip")).to_be_focused()
    page.keyboard.press("Tab")
    page.keyboard.press("Tab")                                # wordmark, status pill is not focusable, so the next stop is the review
    focused = page.evaluate("""() => { const s = getComputedStyle(document.activeElement); return [s.outlineStyle, s.outlineWidth, document.activeElement.tagName]; }""")
    assert focused[0] != "none" and focused[1] not in ("0px", ""), focused


def test_touch_targets_are_at_least_44_pixels(browser, offline_app):
    context = browser.new_context(viewport={"width": 375, "height": 800}, has_touch=True)
    page = context.new_page()
    seed(page, [card(1)])
    page.goto(offline_app)
    page.click("#show")
    small = []
    for locator in ("#show", ".grade", "#make", "#sample", "#explain", "#reset", "#count", ".seg label", "#themeToggle"):
        for box in [h.bounding_box() for h in page.locator(locator).element_handles() if h.is_visible()]:
            if box["height"] < 44 or box["width"] < 44:
                small.append((locator, round(box["width"]), round(box["height"])))
    context.close()
    assert small == [], small


# ================================================================ look and feel ===============================

PAIRS = [   # (foreground token, background token, minimum contrast) from docs/DESIGN.md
    ("--ink", "--canvas", 4.5), ("--ink", "--surface", 4.5), ("--ink-soft", "--canvas", 4.5), ("--ink-soft", "--surface", 4.5),
    ("--ink-soft", "--sunk", 4.5), ("--accent", "--canvas", 4.5), ("--accent", "--surface", 4.5), ("--accent-ink", "--accent", 4.5),
    ("--edge", "--canvas", 3.0), ("--edge", "--surface", 3.0), ("--due", "--canvas", 3.0), ("--due", "--surface", 3.0),
    ("--due-text", "--due-wash", 4.5), ("--due-text", "--canvas", 4.5), ("--good", "--canvas", 4.5), ("--good", "--surface", 4.5),
    ("--bad", "--canvas", 4.5), ("--bad", "--surface", 4.5), ("--bad", "--bad-wash", 4.5), ("--ink", "--due-wash", 4.5),
]


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_every_colour_pair_in_the_design_system_meets_its_contrast_minimum(offline_app, browser, scheme):
    context = browser.new_context(color_scheme=scheme)
    page = context.new_page()
    page.goto(offline_app)
    tokens = page.evaluate("""(names) => Object.fromEntries(names.map(n => [n, getComputedStyle(document.documentElement).getPropertyValue(n).trim()]))""",
                           sorted({n for pair in PAIRS for n in pair[:2]}))
    context.close()
    failures = [(fg, bg, round(contrast(tokens[fg], tokens[bg]), 2), need) for fg, bg, need in PAIRS if contrast(tokens[fg], tokens[bg]) < need]
    assert failures == [], f"{scheme}: {failures}"


def test_the_two_self_hosted_fonts_load_and_are_used(offline_app, page):
    seed(page, [card(1)])
    page.goto(offline_app)
    wait_until(page, "document.fonts.status === 'loaded'")
    assert page.evaluate("document.fonts.check('600 1em \"Bricolage Grotesque\"') && document.fonts.check('400 1em \"DM Sans\"')")
    assert "Bricolage Grotesque" in page.evaluate("getComputedStyle(document.querySelector('h1')).fontFamily")
    assert "DM Sans" in page.evaluate("getComputedStyle(document.body).fontFamily")
    assert page.problems == []


@pytest.mark.parametrize("width,height", [(320, 640), (375, 667), (768, 1024), (1280, 800)])
def test_no_sideways_scrolling_at_any_common_width(browser, offline_app, width, height):
    context = browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    seed(page, [card(i, due_in_ms=(i % 6) * DAY) for i in range(40)])
    page.goto(offline_app)
    page.click("#show") if page.locator("#show").is_visible() else None
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), f"page scrolls sideways at {width}px"
    context.close()


def test_reduced_motion_replaces_movement_with_a_fade(browser, offline_app):
    context = browser.new_context(reduced_motion="reduce")
    page = context.new_page()
    seed(page, [card(1)])
    page.goto(offline_app)
    wait_until(page, "!!document.querySelector('#study') && !document.querySelector('#study').hidden")
    name = page.evaluate("getComputedStyle(document.querySelector('#study')).animationName")
    context.close()
    assert name == "fade", name


def test_page_title_language_and_no_zoom_lock(offline_app, page):
    page.goto(offline_app)
    assert page.title() == "YaadDost"
    assert page.get_attribute("html", "lang") == "en"
    viewport = page.get_attribute("meta[name=viewport]", "content")
    assert "user-scalable=no" not in viewport and "maximum-scale" not in viewport


def test_no_third_party_requests_at_all(offline_app, page):
    seen = []
    page.on("request", lambda r: seen.append(r.url))
    seed(page, [card(1)])
    page.goto(offline_app)
    page.wait_for_load_state("networkidle")
    outside = [u for u in seen if not u.startswith(offline_app) and not u.startswith("data:")]
    assert outside == [], outside


# ================================================================ light and dark theme ========================

def read_tokens(page):
    names = sorted({n for pair in PAIRS for n in pair[:2]})
    return page.evaluate(
        """(names) => Object.fromEntries(names.map(n => [n, getComputedStyle(document.documentElement).getPropertyValue(n).trim()]))""", names
    )


def contrast_failures(tokens):
    return [(fg, bg, round(contrast(tokens[fg], tokens[bg]), 2), need) for fg, bg, need in PAIRS if contrast(tokens[fg], tokens[bg]) < need]


@pytest.mark.parametrize("system,saved,expected", [
    ("light", None, "light"),     # nothing saved: follow the system
    ("dark", None, "dark"),
    ("light", "dark", "dark"),    # a saved choice beats the system
    ("dark", "light", "light"),
])
def test_theme_comes_from_the_saved_choice_then_the_system_and_always_meets_contrast(browser, offline_app, system, saved, expected):
    context = browser.new_context(color_scheme=system)
    page = context.new_page()
    if saved:
        page.add_init_script(f"localStorage.setItem('yaaddost.theme', '{saved}')")
    page.goto(offline_app)
    assert page.get_attribute("html", "data-theme") == expected
    assert page.get_attribute("#themeToggle", "aria-pressed") == ("true" if expected == "dark" else "false")
    failures = contrast_failures(read_tokens(page))
    context.close()
    assert failures == [], f"{expected} theme (system {system}, saved {saved}): {failures}"


def test_the_switch_changes_the_theme_and_remembers_it(offline_app, page):
    page.goto(offline_app)
    toggle = page.get_by_role("button", name="Dark theme")
    assert page.get_attribute("html", "data-theme") == "light"
    light_bg = page.evaluate("getComputedStyle(document.body).backgroundColor")

    toggle.click()
    assert page.get_attribute("html", "data-theme") == "dark"
    expect(toggle).to_have_attribute("aria-pressed", "true")
    dark_bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
    assert dark_bg != light_bg
    assert page.evaluate("document.querySelector('meta[name=theme-color]').content") == "#2b3047"   # the phone's browser bar follows

    page.reload()
    assert page.get_attribute("html", "data-theme") == "dark"            # remembered
    page.get_by_role("button", name="Dark theme").click()
    page.reload()
    assert page.get_attribute("html", "data-theme") == "light"
    assert page.problems == []


def test_the_dark_theme_is_soft_not_black(browser, offline_app):
    context = browser.new_context(color_scheme="dark")
    page = context.new_page()
    page.goto(offline_app)
    tokens = read_tokens(page)
    context.close()
    canvas = luminance(tokens["--canvas"])
    assert 0.02 <= canvas <= 0.08, f"dark canvas {tokens['--canvas']} has luminance {canvas:.3f}: too black or too light"
    assert min(rgb(tokens["--canvas"])) >= 0x24 and tokens["--canvas"].lower() not in ("#000000", "#0a0a0a", "#111111")
    assert contrast(tokens["--ink"], tokens["--canvas"]) >= 7        # still easy to read, just gentler


def test_without_a_saved_choice_the_page_follows_a_live_system_change(browser, offline_app):
    context = browser.new_context(color_scheme="light")
    page = context.new_page()
    page.goto(offline_app)
    assert page.get_attribute("html", "data-theme") == "light"
    page.emulate_media(color_scheme="dark")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    expect(page.locator("#themeToggle")).to_have_attribute("aria-pressed", "true")
    page.get_by_role("button", name="Dark theme").click()                # now the student has chosen: light
    page.emulate_media(color_scheme="dark")
    assert page.get_attribute("html", "data-theme") == "light"           # the saved choice is not overridden
    context.close()


def test_the_theme_is_applied_by_a_blocking_script_in_the_head_so_there_is_no_flash(offline_app, page):
    page.goto(offline_app)
    info = page.evaluate("""() => { const s = document.querySelector('head script[src$="theme-init.js"]');
        return s ? [s.async, s.defer, s.type, !!s.closest('head')] : null; }""")
    assert info == [False, False, "", True], info


def test_the_switch_works_when_storage_is_blocked_and_from_the_keyboard(offline_app, page):
    page.add_init_script("Storage.prototype.setItem = function () { throw new Error('blocked'); };")
    page.goto(offline_app)
    page.locator("#themeToggle").focus()
    page.keyboard.press("Enter")
    assert page.get_attribute("html", "data-theme") == "dark"
    page.keyboard.press("Space")
    assert page.get_attribute("html", "data-theme") == "light"
    assert page.problems == []


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_the_whole_review_looks_intact_in_each_theme(browser, offline_app, theme):
    context = browser.new_context(viewport={"width": 375, "height": 800})
    page = context.new_page()
    page.add_init_script(f"localStorage.setItem('yaaddost.theme', '{theme}')")
    seed(page, [card(i, due_in_ms=(i % 5) * DAY) for i in range(12)])
    page.goto(offline_app)
    page.click("#show")
    assert page.get_attribute("html", "data-theme") == theme
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    to_hex = lambda c: "#" + "".join(f"{int(float(x)):02x}" for x in re.findall(r"[\d.]+", c)[:3])
    low = []
    for selector in ("h1", ".due-line", "#q", "#a", ".grade-name", ".grade-sub", "#mark", ".panel-hint", ".field-label", ".foot", ".btn.primary"):
        fg, bg = page.evaluate(
            """(sel) => { const el = document.querySelector(sel); const fg = getComputedStyle(el).color; let n = el, bg = 'rgb(255, 255, 255)';
                while (n) { const c = getComputedStyle(n).backgroundColor; if (c !== 'rgba(0, 0, 0, 0)' && c !== 'transparent') { bg = c; break; } n = n.parentElement; }
                return [fg, bg]; }""", selector)
        if contrast(to_hex(fg), to_hex(bg)) < 4.5:
            low.append((selector, to_hex(fg), to_hex(bg), round(contrast(to_hex(fg), to_hex(bg)), 2)))
    context.close()
    assert low == [], f"{theme}: {low}"
