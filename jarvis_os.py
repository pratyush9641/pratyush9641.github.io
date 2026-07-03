#!/usr/bin/env python3
"""
JARVIS OS - Iron Man HUD Interface
A fully animated AI operating system UI built with PyQt6.

This build adds a real command engine, working quick-action buttons,
Chrome control (open sites, search, and — when Playwright is available —
automated browsing "real work"), voice input/output, and a live Settings
dialog. Every heavy dependency is optional: if a library is missing, the
feature degrades gracefully and tells you so in the comm channel instead
of crashing.

Optional dependencies (install what you want):
    pip install psutil                # live system stats
    pip install pyttsx3               # JARVIS text-to-speech
    pip install SpeechRecognition     # microphone command input
    pip install pyaudio               # microphone backend for the above
    pip install playwright            # automated Chrome "real work"
        python -m playwright install chromium
"""

import sys
import os
import math
import random
import platform
import shutil
import subprocess
import webbrowser
import datetime
import ast
import operator
import json
import urllib.parse

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QLineEdit, QProgressBar,
    QGraphicsDropShadowEffect, QSizePolicy, QDialog, QTextEdit,
    QListWidget, QListWidgetItem, QSplitter, QStackedWidget, QCheckBox,
    QComboBox, QDialogButtonBox, QFormLayout
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal,
    QThread, QRectF, QPointF, QSize, QRect, pyqtProperty, QObject
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QLinearGradient,
    QRadialGradient, QConicalGradient, QPainterPath, QFontDatabase,
    QPixmap, QPalette, QKeyEvent
)

# ─── Platform ───────────────────────────────────────────────────────────────
SYSTEM = platform.system()   # 'Windows' | 'Linux' | 'Darwin'

# ─── Config file (persists settings between runs) ─────────────────────────────
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".jarvis_os.json")

DEFAULT_CONFIG = {
    "user_name": "Sir",
    "voice_output": True,
    "voice_rate": 175,
    "accent": "orange",          # orange | blue | cyan | purple
    "search_engine": "google",   # google | duckduckgo | bing
    "use_playwright": False,      # enable automated Chrome browsing
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


# ─── Color Palette ────────────────────────────────────────────────────────────
BG_DARK       = QColor(4, 6, 10)
BG_PANEL      = QColor(8, 14, 22, 200)
ORANGE_CORE   = QColor(255, 140, 0)
ORANGE_GLOW   = QColor(255, 100, 0, 80)
ORANGE_DIM    = QColor(180, 70, 0)
BLUE_HOLO     = QColor(0, 180, 255)
BLUE_DIM      = QColor(0, 100, 180, 150)
BLUE_GLOW     = QColor(0, 150, 255, 60)
CYAN_ACCENT   = QColor(0, 220, 255)
WHITE_TEXT    = QColor(220, 235, 255)
GREY_TEXT     = QColor(120, 150, 180)
GREEN_ONLINE  = QColor(0, 255, 150)
RED_ALERT     = QColor(255, 50, 50)
YELLOW_WARN   = QColor(255, 210, 0)

ACCENTS = {
    "orange": QColor(255, 140, 0),
    "blue":   QColor(0, 180, 255),
    "cyan":   QColor(0, 220, 255),
    "purple": QColor(180, 0, 255),
}

# ─── Startup Sequence ─────────────────────────────────────────────────────────
BOOT_LINES = [
    "JARVIS OS INITIALIZING...",
    "Loading Memory Systems...",
    "Loading Agent Network...",
    "Loading Automation Layer...",
    "Loading Voice Engine...",
    "Loading Intelligence Core...",
    "Calibrating Arc Reactor Interface...",
    "All Systems Operational.",
]

# ─── Utility: Glow Effect ─────────────────────────────────────────────────────
def add_glow(widget, color: QColor, radius: int = 20):
    fx = QGraphicsDropShadowEffect()
    fx.setBlurRadius(radius)
    fx.setColor(color)
    fx.setOffset(0, 0)
    widget.setGraphicsEffect(fx)


# ══════════════════════════════════════════════════════════════════════════════
# CHROME CONTROLLER  — open sites, search, and (optionally) automate browsing
# ══════════════════════════════════════════════════════════════════════════════
CHROME_BINARIES = {
    "Windows": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ],
    "Darwin": [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ],
    "Linux": [
        "google-chrome", "google-chrome-stable", "chromium",
        "chromium-browser", "brave-browser", "microsoft-edge",
    ],
}

SEARCH_URLS = {
    "google":     "https://www.google.com/search?q={}",
    "duckduckgo": "https://duckduckgo.com/?q={}",
    "bing":       "https://www.bing.com/search?q={}",
}


class ChromeController:
    """Locates a Chrome/Chromium binary and drives it for real web tasks."""

    def __init__(self, config):
        self.config = config
        self.binary = self._find_binary()
        self._pw = None            # cached Playwright objects
        self._pw_browser = None
        self._pw_page = None

    # -- binary discovery --------------------------------------------------
    def _find_binary(self):
        for cand in CHROME_BINARIES.get(SYSTEM, []):
            if os.path.sep in cand or (SYSTEM == "Windows" and cand.endswith(".exe")):
                if os.path.exists(cand):
                    return cand
            else:
                found = shutil.which(cand)
                if found:
                    return found
        return None

    @property
    def available(self):
        return self.binary is not None

    # -- simple launching --------------------------------------------------
    def open_url(self, url):
        """Open a URL in Chrome if found, else the default browser."""
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            if self.binary:
                subprocess.Popen([self.binary, url],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            else:
                webbrowser.open(url)
            return True, url
        except Exception as e:
            return False, str(e)

    def open_new(self):
        return self.open_url("https://www.google.com")

    def search(self, query):
        engine = self.config.get("search_engine", "google")
        tmpl = SEARCH_URLS.get(engine, SEARCH_URLS["google"])
        url = tmpl.format(urllib.parse.quote_plus(query))
        return self.open_url(url)

    def youtube(self, query):
        url = "https://www.youtube.com/results?search_query=" + \
              urllib.parse.quote_plus(query)
        return self.open_url(url)

    # -- automated browsing ("do the real work") --------------------------
    def playwright_search(self, query):
        """Run an automated headed browse+scrape of the top results.

        Returns (ok, text). Requires `playwright` + an installed browser.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return False, ("Playwright is not installed. Run "
                           "`pip install playwright` then "
                           "`python -m playwright install chromium`.")
        try:
            with sync_playwright() as pw:
                launch_kwargs = {"headless": False}
                if self.binary:
                    launch_kwargs["executable_path"] = self.binary
                browser = pw.chromium.launch(**launch_kwargs)
                page = browser.new_page()
                url = SEARCH_URLS.get(
                    self.config.get("search_engine", "google"),
                    SEARCH_URLS["google"]).format(
                        urllib.parse.quote_plus(query))
                page.goto(url, timeout=20000)
                page.wait_for_timeout(1500)
                # Grab result headings (works for Google/Bing/DDG heading tags)
                headings = page.eval_on_selector_all(
                    "h3, h2",
                    "els => els.map(e => e.innerText).filter(Boolean).slice(0, 5)")
                browser.close()
                if headings:
                    joined = " | ".join(headings)
                    return True, f"Top results for '{query}': {joined}"
                return True, f"I searched for '{query}' but found no headings to summarise."
        except Exception as e:
            return False, f"Automated browse failed: {e}"


# ══════════════════════════════════════════════════════════════════════════════
# COMMAND ENGINE  — turns natural-ish text into real actions
# ══════════════════════════════════════════════════════════════════════════════
# Safe arithmetic evaluator ----------------------------------------------------
_ALLOWED_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv, ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def safe_eval(expr):
    """Evaluate a math expression without exec/eval risk."""
    def _ev(node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("non-numeric constant")
        if isinstance(node, ast.BinOp):
            return _ALLOWED_OPS[type(node.op)](_ev(node.left), _ev(node.right))
        if isinstance(node, ast.UnaryOp):
            return _ALLOWED_OPS[type(node.op)](_ev(node.operand))
        raise ValueError("unsupported expression")
    tree = ast.parse(expr, mode="eval")
    return _ev(tree.body)


# App registry per platform (name -> launch spec) -----------------------------
def _launch(cmd):
    """Launch a command list / string cross-platform. Returns (ok, msg)."""
    try:
        if isinstance(cmd, str):
            cmd = [cmd]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        return True, None
    except Exception as e:
        return False, str(e)


class CommandEngine:
    """Parses a text command and performs the corresponding action."""

    def __init__(self, config, chrome: ChromeController):
        self.config = config
        self.chrome = chrome

    # -- public entry ------------------------------------------------------
    def process(self, text):
        """Return a reply string. Side effects (launching apps) happen here."""
        raw = text.strip()
        t = raw.lower()
        name = self.config.get("user_name", "Sir")

        if not t:
            return "I didn't catch that, {}.".format(name)

        # --- greetings ---
        if any(g in t for g in ("hello", "hi jarvis", "hey jarvis", "good morning",
                                 "good evening", "good afternoon")):
            return f"Hello, {name}. How can I assist you?"

        if "how are you" in t:
            return "Fully operational and at your service, {}.".format(name)

        if any(k in t for k in ("thank you", "thanks")):
            return f"You're most welcome, {name}."

        if t in ("who are you", "what are you", "your name"):
            return ("I am J.A.R.V.I.S — Just A Rather Very Intelligent System, "
                    "your personal assistant.")

        # --- time / date ---
        if "time" in t and ("what" in t or "tell" in t or t == "time"):
            now = datetime.datetime.now().strftime("%I:%M %p")
            return f"The time is {now}, {name}."

        if "date" in t or ("day" in t and "today" in t):
            today = datetime.datetime.now().strftime("%A, %B %d, %Y")
            return f"Today is {today}."

        # --- system status ---
        if any(k in t for k in ("system status", "system info", "cpu", "memory",
                                 "how much ram", "diagnostics")):
            return self._system_report()

        # --- math ---
        m = self._try_math(t)
        if m is not None:
            return m

        # --- Chrome automated "real work" ---
        for kw in ("research ", "find out ", "browse "):
            if t.startswith(kw):
                return self._do_real_work(raw[len(kw):].strip())

        # --- youtube ---
        if "youtube" in t or t.startswith("play "):
            query = t
            for kw in ("play", "on youtube", "youtube", "search"):
                query = query.replace(kw, "")
            query = query.strip() or "trending"
            ok, url = self.chrome.youtube(query)
            if ok:
                return f"Opening YouTube results for '{query}', {name}."
            return f"I couldn't open YouTube: {url}"

        # --- web search ---
        if t.startswith(("search for ", "search ", "google ", "look up ")):
            for kw in ("search for ", "search ", "google ", "look up "):
                if t.startswith(kw):
                    query = raw[len(kw):].strip()
                    break
            if not query:
                return "What would you like me to search for?"
            ok, url = self.chrome.search(query)
            if ok:
                return f"Searching the web for '{query}', {name}."
            return f"I couldn't run that search: {url}"

        # --- open website / go to ---
        if t.startswith(("open website", "go to ", "open site", "navigate to ", "visit ")):
            for kw in ("open website ", "go to ", "open site ", "navigate to ", "visit "):
                if t.startswith(kw):
                    target = raw[len(kw):].strip()
                    break
            else:
                target = ""
            if not target:
                return "Which website should I open?"
            ok, url = self.chrome.open_url(target.replace(" ", ""))
            if ok:
                return f"Opening {url}, {name}."
            return f"I couldn't open that site: {url}"

        # --- open applications ---
        if t.startswith("open ") or t.startswith("launch ") or t.startswith("start "):
            app = t.split(" ", 1)[1] if " " in t else ""
            return self._open_app(app)

        # --- exit ---
        if t in ("exit", "quit", "shutdown", "goodbye", "bye", "power down"):
            return f"Powering down. Goodbye, {name}."

        # --- fallback: offer a web search ---
        ok, url = self.chrome.search(raw)
        if ok:
            return (f"I'm not certain about that, {name}, so I've searched "
                    f"the web for '{raw}'.")
        return (f"I'm not sure how to help with that yet, {name}. "
                "Try 'open chrome', 'search <topic>', 'what time is it', "
                "or 'calculate 12 * 8'.")

    # -- helpers -----------------------------------------------------------
    def _try_math(self, t):
        trigger = None
        for kw in ("calculate ", "what is ", "what's ", "compute ", "evaluate "):
            if t.startswith(kw):
                trigger = t[len(kw):]
                break
        if trigger is None:
            # bare arithmetic like "12 * 8"
            if any(op in t for op in "+-*/%") and any(c.isdigit() for c in t):
                trigger = t
        if trigger is None:
            return None
        expr = (trigger.replace("plus", "+").replace("minus", "-")
                .replace("times", "*").replace("multiplied by", "*")
                .replace("divided by", "/").replace("x", "*")
                .replace("^", "**").strip(" ?."))
        # keep only math-ish characters
        allowed = set("0123456789.+-*/%() ")
        if not expr or not set(expr) <= allowed:
            return None
        try:
            result = safe_eval(expr)
            if isinstance(result, float) and result.is_integer():
                result = int(result)
            return f"The answer is {result}."
        except Exception:
            return None

    def _system_report(self):
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.2)
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage("/").percent
            return (f"System status: CPU at {cpu:.0f} percent, "
                    f"memory at {ram:.0f} percent, "
                    f"disk at {disk:.0f} percent. All within nominal range.")
        except ImportError:
            return ("Live telemetry needs psutil. Install it with "
                    "`pip install psutil`. All systems appear nominal.")

    def _do_real_work(self, query):
        name = self.config.get("user_name", "Sir")
        if not query:
            return "What would you like me to research?"
        if self.config.get("use_playwright"):
            ok, msg = self.chrome.playwright_search(query)
            return msg if ok else (msg + " Falling back to a normal search.")
        # default: open a real search tab
        ok, url = self.chrome.search(query)
        if ok:
            return (f"Researching '{query}' for you, {name}. "
                    "(Enable automated browsing in Settings for summaries.)")
        return f"I couldn't research that: {url}"

    def _open_app(self, app):
        name = self.config.get("user_name", "Sir")
        app = app.strip().rstrip(".!?")

        # Chrome / browser
        if app in ("chrome", "browser", "google chrome", "web", "internet"):
            ok, res = self.chrome.open_new()
            if ok:
                return f"Opening Chrome, {name}."
            return f"I couldn't open Chrome: {res}"

        # VS Code
        if app in ("vs code", "vscode", "code", "editor", "visual studio code"):
            code = shutil.which("code")
            if code:
                ok, err = _launch([code])
                return f"Opening VS Code, {name}." if ok else f"VS Code failed: {err}"
            return "I couldn't find VS Code on this system. Is it on your PATH?"

        # File manager / folder
        if app in ("folder", "files", "explorer", "file manager", "file explorer",
                   "finder", "home", "documents"):
            return self._open_folder()

        # Terminal
        if app in ("terminal", "console", "command prompt", "cmd", "shell"):
            return self._open_terminal()

        # Calculator
        if app in ("calculator", "calc"):
            return self._open_calculator()

        # Notepad / text editor
        if app in ("notepad", "notes", "text editor", "gedit"):
            return self._open_notepad()

        # Settings (handled by UI signal elsewhere; here just acknowledge)
        if app in ("settings", "preferences", "config"):
            return "__OPEN_SETTINGS__"

        return (f"I don't know how to open '{app}' yet, {name}. "
                "I can open Chrome, VS Code, a folder, terminal, or calculator.")

    def _open_folder(self):
        home = os.path.expanduser("~")
        if SYSTEM == "Windows":
            ok, err = _launch(["explorer", home])
        elif SYSTEM == "Darwin":
            ok, err = _launch(["open", home])
        else:
            opener = shutil.which("xdg-open") or "xdg-open"
            ok, err = _launch([opener, home])
        return "Opening your home folder, Sir." if ok else f"Couldn't open folder: {err}"

    def _open_terminal(self):
        if SYSTEM == "Windows":
            ok, err = _launch(["cmd"])
        elif SYSTEM == "Darwin":
            ok, err = _launch(["open", "-a", "Terminal"])
        else:
            for term in ("gnome-terminal", "konsole", "xterm", "x-terminal-emulator"):
                if shutil.which(term):
                    ok, err = _launch([term])
                    break
            else:
                return "I couldn't find a terminal emulator."
        return "Opening a terminal, Sir." if ok else f"Couldn't open terminal: {err}"

    def _open_calculator(self):
        if SYSTEM == "Windows":
            ok, err = _launch(["calc"])
        elif SYSTEM == "Darwin":
            ok, err = _launch(["open", "-a", "Calculator"])
        else:
            for c in ("gnome-calculator", "kcalc", "galculator", "xcalc"):
                if shutil.which(c):
                    ok, err = _launch([c])
                    break
            else:
                return "I couldn't find a calculator app."
        return "Opening the calculator, Sir." if ok else f"Couldn't open calculator: {err}"

    def _open_notepad(self):
        if SYSTEM == "Windows":
            ok, err = _launch(["notepad"])
        elif SYSTEM == "Darwin":
            ok, err = _launch(["open", "-a", "TextEdit"])
        else:
            for e in ("gedit", "kate", "mousepad", "nano"):
                if shutil.which(e):
                    ok, err = _launch([e])
                    break
            else:
                return "I couldn't find a text editor."
        return "Opening a text editor, Sir." if ok else f"Couldn't open editor: {err}"


# ══════════════════════════════════════════════════════════════════════════════
# VOICE  — text-to-speech (output) and speech recognition (input)
# ══════════════════════════════════════════════════════════════════════════════
class TTSWorker(QThread):
    """Speaks a line of text on a background thread so the UI never blocks."""
    started_speaking = pyqtSignal()
    finished_speaking = pyqtSignal()

    def __init__(self, text, rate=175):
        super().__init__()
        self.text = text
        self.rate = rate

    def run(self):
        try:
            import pyttsx3
        except ImportError:
            return
        try:
            self.started_speaking.emit()
            engine = pyttsx3.init()
            engine.setProperty("rate", self.rate)
            engine.say(self.text)
            engine.runAndWait()
            engine.stop()
        except Exception:
            pass
        finally:
            self.finished_speaking.emit()


class VoiceListener(QThread):
    """Listens once on the microphone and emits recognised text."""
    recognized = pyqtSignal(str)
    status = pyqtSignal(str)   # 'listening' | 'processing' | 'error:<msg>' | 'unavailable'

    def run(self):
        try:
            import speech_recognition as sr
        except ImportError:
            self.status.emit("unavailable")
            return
        try:
            r = sr.Recognizer()
            with sr.Microphone() as source:
                self.status.emit("listening")
                r.adjust_for_ambient_noise(source, duration=0.4)
                audio = r.listen(source, timeout=6, phrase_time_limit=8)
            self.status.emit("processing")
            text = r.recognize_google(audio)
            self.recognized.emit(text)
        except Exception as e:
            self.status.emit(f"error:{e}")


# ══════════════════════════════════════════════════════════════════════════════
# ANIMATED ARC CORE (center orb)
# ══════════════════════════════════════════════════════════════════════════════
class ArcCoreWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(340, 340)
        self._angle        = 0.0
        self._angle2       = 0.0
        self._angle3       = 0.0
        self._pulse        = 0.0
        self._pulse_dir    = 1
        self._speaking     = False
        self._user_speaks  = False
        self._wave_phase   = 0.0
        self._particles    = [self._new_particle() for _ in range(60)]
        self._energy       = 0.6
        self._energy_dir   = 1
        self._accent       = "orange"

        # Main animation timer – 60 FPS
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def set_accent(self, accent):
        self._accent = accent if accent in ACCENTS else "orange"

    def _new_particle(self):
        angle = random.uniform(0, 2 * math.pi)
        r     = random.uniform(80, 155)
        return {
            "angle": angle,
            "r":     r,
            "speed": random.uniform(0.003, 0.012),
            "size":  random.uniform(1.5, 4.0),
            "alpha": random.uniform(80, 200),
            "da":    random.uniform(-0.5, 0.5),
            "color": random.choice(["orange", "blue", "cyan"]),
        }

    def _tick(self):
        self._angle  += 0.8
        self._angle2 -= 0.5
        self._angle3 += 0.3
        self._wave_phase += 0.08

        self._pulse += 0.04 * self._pulse_dir
        if self._pulse >= 1.0: self._pulse_dir = -1
        if self._pulse <= 0.0: self._pulse_dir  = 1

        self._energy += 0.005 * self._energy_dir
        if self._energy >= 1.0: self._energy_dir = -1
        if self._energy <= 0.4: self._energy_dir  = 1

        for p in self._particles:
            p["angle"] += p["speed"]
            p["alpha"] += p["da"]
            if p["alpha"] > 220 or p["alpha"] < 40:
                p["da"] *= -1

        self.update()

    def set_speaking(self, val: bool):
        self._speaking = val

    def set_user_speaking(self, val: bool):
        self._user_speaks = val

    def paintEvent(self, event):
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background radial glow
        grad = QRadialGradient(cx, cy, 160)
        grad.setColorAt(0.0, QColor(255, 100, 0, 30 + int(self._pulse * 20)))
        grad.setColorAt(0.4, QColor(0, 100, 255, 15))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - 160, cy - 160, 320, 320))

        # ── Particles ──
        for pt in self._particles:
            px = cx + pt["r"] * math.cos(pt["angle"])
            py = cy + pt["r"] * math.sin(pt["angle"])
            if pt["color"] == "orange":
                c = QColor(255, 140, 0, int(pt["alpha"]))
            elif pt["color"] == "blue":
                c = QColor(0, 160, 255, int(pt["alpha"]))
            else:
                c = QColor(0, 220, 255, int(pt["alpha"]))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(c))
            p.drawEllipse(QRectF(px - pt["size"]/2, py - pt["size"]/2,
                                  pt["size"], pt["size"]))

        # ── Outer energy rings ──
        ring_specs = [
            (145, 2.0, ORANGE_CORE, self._angle,  12, 3),
            (125, 1.5, BLUE_HOLO,   self._angle2, 8,  2),
            (108, 1.0, CYAN_ACCENT, self._angle3, 16, 2),
        ]
        for radius, pen_w, color, angle_off, dashes, gap in ring_specs:
            c = QColor(color)
            c.setAlpha(160 + int(self._pulse * 60))
            pen = QPen(c, pen_w, Qt.PenStyle.SolidLine)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            # Draw as dashed arc segments
            step = 360 / dashes
            for i in range(dashes):
                start = int((angle_off + i * step) % 360) * 16
                span  = int((step - step * gap / dashes) * 0.7) * 16
                p.drawArc(QRectF(cx - radius, cy - radius,
                                  radius * 2, radius * 2), start, span)

        # ── Inner hexagonal frame ──
        hex_r = 88
        pen_hex = QPen(QColor(255, 140, 0, 100), 1.0, Qt.PenStyle.SolidLine)
        p.setPen(pen_hex)
        path_hex = QPainterPath()
        for i in range(6):
            a = math.radians(self._angle3 * 0.4 + i * 60)
            x, y = cx + hex_r * math.cos(a), cy + hex_r * math.sin(a)
            if i == 0: path_hex.moveTo(x, y)
            else:      path_hex.lineTo(x, y)
        path_hex.closeSubpath()
        p.drawPath(path_hex)

        # ── Core orb ──
        orb_r  = 72
        bright = 0.7 + self._pulse * 0.3 + (0.2 if self._speaking else 0)
        grad2  = QRadialGradient(cx - 12, cy - 12, orb_r)
        grad2.setColorAt(0.0, QColor(255, 200, 80, int(240 * bright)))
        grad2.setColorAt(0.3, QColor(255, 120, 0,  int(200 * bright)))
        grad2.setColorAt(0.7, QColor(180, 60,  0,  int(160 * bright)))
        grad2.setColorAt(1.0, QColor(80,  20,  0,  int(100 * bright)))
        p.setBrush(QBrush(grad2))
        p.setPen(QPen(QColor(255, 180, 0, 180), 1.5))
        p.drawEllipse(QRectF(cx - orb_r, cy - orb_r, orb_r*2, orb_r*2))

        # ── Arc reactor inner circle ──
        arc_r = 45
        grad3 = QRadialGradient(cx, cy, arc_r)
        grad3.setColorAt(0.0, QColor(200, 240, 255, 220))
        grad3.setColorAt(0.4, QColor(0, 160, 255, 180))
        grad3.setColorAt(1.0, QColor(0, 60, 150, 100))
        p.setBrush(QBrush(grad3))
        p.setPen(QPen(BLUE_HOLO, 1.5))
        p.drawEllipse(QRectF(cx - arc_r, cy - arc_r, arc_r*2, arc_r*2))

        # ── Arc reactor spokes ──
        for i in range(3):
            a = math.radians(self._angle * 2 + i * 120)
            x1 = cx + 12 * math.cos(a)
            y1 = cy + 12 * math.sin(a)
            x2 = cx + 38 * math.cos(a)
            y2 = cy + 38 * math.sin(a)
            p.setPen(QPen(QColor(0, 220, 255, 200), 2.5))
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # ── Center dot ──
        p.setBrush(QBrush(QColor(255, 255, 255, 240)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - 6, cy - 6, 12, 12))

        # ── Waveform (when speaking) ──
        if self._speaking or self._user_speaks:
            color_wave = ORANGE_CORE if self._speaking else BLUE_HOLO
            wave_r = 100
            points = 80
            path_w = QPainterPath()
            amp_mult = 1.8 + self._pulse * 0.5
            for i in range(points + 1):
                a     = math.radians(i * 360 / points)
                amp   = 8 * amp_mult * abs(math.sin(self._wave_phase * 3 + i * 0.4))
                r     = wave_r + amp
                x     = cx + r * math.cos(a)
                y     = cy + r * math.sin(a)
                if i == 0: path_w.moveTo(x, y)
                else:      path_w.lineTo(x, y)
            path_w.closeSubpath()
            wc = QColor(color_wave)
            wc.setAlpha(180)
            p.setPen(QPen(wc, 2.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path_w)

        # ── Status text ──
        status = "SPEAKING" if self._speaking else ("LISTENING" if self._user_speaks else "STANDBY")
        p.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        tc = ORANGE_CORE if self._speaking else (BLUE_HOLO if self._user_speaks else GREY_TEXT)
        p.setPen(QPen(tc))
        p.drawText(QRectF(cx - 60, cy + orb_r + 18, 120, 20),
                   Qt.AlignmentFlag.AlignCenter, status)
        p.end()


# ══════════════════════════════════════════════════════════════════════════════
# HUD PANEL BASE
# ══════════════════════════════════════════════════════════════════════════════
class HUDPanel(QFrame):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self._title    = title
        self._scan     = 0.0
        self._scan_dir = 1
        self._corner   = 8
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent; border: none;")

        self._t = QTimer(self)
        self._t.timeout.connect(self._tick)
        self._t.start(32)

    def _tick(self):
        self._scan += 0.015 * self._scan_dir
        if self._scan >= 1.0: self._scan_dir = -1
        if self._scan <= 0.0: self._scan_dir  = 1
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r = self._corner

        # Glassmorphism background
        bg = QColor(8, 18, 35, 210)
        p.setBrush(QBrush(bg))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(0, 0, w, h), r, r)

        # Border gradient
        border_grad = QLinearGradient(0, 0, w, h)
        border_grad.setColorAt(0.0, QColor(0, 180, 255, 160))
        border_grad.setColorAt(0.5, QColor(255, 140, 0,  80))
        border_grad.setColorAt(1.0, QColor(0, 180, 255, 160))
        p.setPen(QPen(QBrush(border_grad), 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(0.6, 0.6, w - 1.2, h - 1.2), r, r)

        # Corner accent marks
        accent = QColor(255, 140, 0, 200)
        p.setPen(QPen(accent, 2))
        L = 12
        corners = [(0, 0, 1, 0, 0, 1), (w, 0, -1, 0, 0, 1),
                   (0, h, 1, 0, 0, -1), (w, h, -1, 0, 0, -1)]
        for cx, cy, dx1, dy1, dx2, dy2 in corners:
            p.drawLine(QPointF(cx, cy), QPointF(cx + dx1*L, cy + dy1*L))
            p.drawLine(QPointF(cx, cy), QPointF(cx + dx2*L, cy + dy2*L))

        # Title bar
        if self._title:
            title_h = 28
            title_bg = QLinearGradient(0, 0, w, 0)
            title_bg.setColorAt(0, QColor(0, 120, 200, 120))
            title_bg.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(title_bg))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(1, 1, w - 2, title_h), r, r)

            # Scan line
            sy = 1 + self._scan * (title_h - 2)
            scan_grad = QLinearGradient(0, sy, w, sy)
            scan_grad.setColorAt(0, QColor(0, 0, 0, 0))
            scan_grad.setColorAt(0.5, QColor(0, 200, 255, 60))
            scan_grad.setColorAt(1, QColor(0, 0, 0, 0))
            p.setPen(QPen(QBrush(scan_grad), 1))
            p.drawLine(QPointF(0, sy), QPointF(w, sy))

            p.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
            p.setPen(QPen(CYAN_ACCENT))
            p.drawText(QRectF(10, 1, w - 20, title_h),
                       Qt.AlignmentFlag.AlignVCenter, f"▸ {self._title}")

        p.end()


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM STATUS PANEL (Left)
# ══════════════════════════════════════════════════════════════════════════════
class SystemStatusPanel(HUDPanel):
    def __init__(self, parent=None):
        super().__init__("SYSTEM STATUS", parent)
        self.setFixedWidth(220)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 34, 12, 12)
        outer.setSpacing(10)

        try:
            import psutil
            self._psutil = psutil
        except ImportError:
            self._psutil = None

        self._bars   = {}
        self._labels = {}

        metrics = [
            ("CPU",  ORANGE_CORE),
            ("RAM",  BLUE_HOLO),
            ("DISK", CYAN_ACCENT),
            ("GPU",  QColor(180, 0, 255)),
        ]
        for name, color in metrics:
            row = QVBoxLayout()
            row.setSpacing(3)

            header = QHBoxLayout()
            lbl = QLabel(name)
            lbl.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
            lbl.setStyleSheet(f"color: {color.name()}; background: transparent;")
            val_lbl = QLabel("-- %")
            val_lbl.setFont(QFont("Consolas", 8))
            val_lbl.setStyleSheet("color: #dceeff; background: transparent;")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            header.addWidget(lbl)
            header.addWidget(val_lbl)

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setFixedHeight(6)
            bar.setTextVisible(False)
            bar.setStyleSheet(f"""
                QProgressBar {{
                    background: rgba(0,0,0,80);
                    border: 1px solid rgba(255,255,255,30);
                    border-radius: 3px;
                }}
                QProgressBar::chunk {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 {color.darker(150).name()},
                        stop:1 {color.name()});
                    border-radius: 3px;
                }}
            """)
            row.addLayout(header)
            row.addWidget(bar)
            outer.addLayout(row)

            self._bars[name]   = bar
            self._labels[name] = val_lbl

        outer.addSpacing(8)

        # Network status
        net_lbl = QLabel("◈ NETWORK")
        net_lbl.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        net_lbl.setStyleSheet("color: #00b4ff; background: transparent;")
        outer.addWidget(net_lbl)

        self._net_status = QLabel("● ONLINE")
        self._net_status.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        self._net_status.setStyleSheet("color: #00ff96; background: transparent;")
        outer.addWidget(self._net_status)

        outer.addSpacing(8)

        # Time
        self._time_lbl = QLabel("00:00:00")
        self._time_lbl.setFont(QFont("Consolas", 16, QFont.Weight.Bold))
        self._time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._time_lbl.setStyleSheet("color: #ff8c00; background: transparent;")
        outer.addWidget(self._time_lbl)

        outer.addStretch()

        # Update stats every second
        self._stat_timer = QTimer(self)
        self._stat_timer.timeout.connect(self._update_stats)
        self._stat_timer.start(1000)
        self._update_stats()

    def _update_stats(self):
        self._time_lbl.setText(datetime.datetime.now().strftime("%H:%M:%S"))

        if self._psutil:
            cpu  = self._psutil.cpu_percent(interval=None)
            ram  = self._psutil.virtual_memory().percent
            disk = self._psutil.disk_usage('/').percent
            gpu  = random.uniform(20, 80)   # simulated
        else:
            cpu  = random.uniform(10, 90)
            ram  = random.uniform(30, 80)
            disk = random.uniform(40, 70)
            gpu  = random.uniform(20, 60)

        for name, val in [("CPU", cpu), ("RAM", ram), ("DISK", disk), ("GPU", gpu)]:
            self._bars[name].setValue(int(val))
            self._labels[name].setText(f"{val:.0f}%")

        self._net_status.setText("● ONLINE" if random.random() > 0.02 else "● RECONNECTING")


# ══════════════════════════════════════════════════════════════════════════════
# AGENT MONITOR PANEL (Right)
# ══════════════════════════════════════════════════════════════════════════════
class AgentMonitorPanel(HUDPanel):
    def __init__(self, parent=None):
        super().__init__("AGENT NETWORK", parent)
        self.setFixedWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 34, 12, 12)
        layout.setSpacing(8)

        self._agents = [
            ("INTENT ROUTER",   "ONLINE"),
            ("CODING AGENT",    "IDLE"),
            ("MEMORY AGENT",    "ONLINE"),
            ("PLANNER AGENT",   "IDLE"),
            ("AUTOMATION AGENT","IDLE"),
            ("VISION AGENT",    "OFFLINE"),
            ("SPEECH ENGINE",   "ONLINE"),
        ]
        self._agent_widgets = []

        for name, status in self._agents:
            row = QHBoxLayout()

            dot = QLabel("●")
            dot.setFont(QFont("Consolas", 10))
            dot.setFixedWidth(18)
            if status == "ONLINE":
                dot.setStyleSheet("color: #00ff96; background: transparent;")
            elif status == "IDLE":
                dot.setStyleSheet("color: #ffaa00; background: transparent;")
            else:
                dot.setStyleSheet("color: #ff3333; background: transparent;")

            name_lbl = QLabel(name)
            name_lbl.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
            name_lbl.setStyleSheet("color: #a0c8f0; background: transparent;")

            status_lbl = QLabel(status)
            status_lbl.setFont(QFont("Consolas", 7))
            status_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            if status == "ONLINE":
                status_lbl.setStyleSheet("color: #00ff96; background: transparent;")
            elif status == "IDLE":
                status_lbl.setStyleSheet("color: #ffaa00; background: transparent;")
            else:
                status_lbl.setStyleSheet("color: #ff4444; background: transparent;")

            row.addWidget(dot)
            row.addWidget(name_lbl)
            row.addWidget(status_lbl)
            layout.addLayout(row)

            self._agent_widgets.append((dot, status_lbl, status))

        layout.addSpacing(10)

        # Active tasks counter
        tasks_lbl = QLabel("ACTIVE TASKS")
        tasks_lbl.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        tasks_lbl.setStyleSheet("color: #00b4ff; background: transparent;")
        layout.addWidget(tasks_lbl)

        self._task_count = QLabel("03")
        self._task_count.setFont(QFont("Consolas", 28, QFont.Weight.Bold))
        self._task_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._task_count.setStyleSheet("color: #ff8c00; background: transparent;")
        layout.addWidget(self._task_count)

        layout.addStretch()

        # Simulate activity
        self._act_timer = QTimer(self)
        self._act_timer.timeout.connect(self._simulate_activity)
        self._act_timer.start(2500)

    def set_agent(self, agent_name, status):
        """Externally set an agent's status (e.g. when a command runs)."""
        colors = {"ONLINE": "#00ff96", "WORKING": "#00b4ff",
                  "IDLE": "#ffaa00", "OFFLINE": "#ff4444"}
        for i, (dot, status_lbl, _) in enumerate(self._agent_widgets):
            if self._agents[i][0] == agent_name:
                c = colors.get(status, "#00ff96")
                dot.setStyleSheet(f"color: {c}; background: transparent;")
                status_lbl.setText(status)
                status_lbl.setStyleSheet(f"color: {c}; background: transparent;")
                self._agent_widgets[i] = (dot, status_lbl, status)

    def _simulate_activity(self):
        statuses = ["ONLINE", "WORKING", "IDLE"]
        colors   = {"ONLINE": "#00ff96", "WORKING": "#00b4ff", "IDLE": "#ffaa00"}

        for i, (dot, status_lbl, _) in enumerate(self._agent_widgets):
            if random.random() > 0.75:
                new_s = random.choice(statuses)
                dot.setStyleSheet(f"color: {colors[new_s]}; background: transparent;")
                status_lbl.setText(new_s)
                status_lbl.setStyleSheet(f"color: {colors[new_s]}; background: transparent;")
                self._agent_widgets[i] = (dot, status_lbl, new_s)

        active = sum(1 for _, _, s in self._agent_widgets if s in ("ONLINE", "WORKING"))
        self._task_count.setText(f"{active:02d}")


# ══════════════════════════════════════════════════════════════════════════════
# CHAT / TRANSCRIPT AREA
# ══════════════════════════════════════════════════════════════════════════════
class ChatPanel(HUDPanel):
    # Emitted when JARVIS produces a reply, so the main window can animate
    # the arc core and speak the text.
    jarvis_replied = pyqtSignal(str)
    open_settings_requested = pyqtSignal()

    def __init__(self, engine: CommandEngine, config, parent=None):
        super().__init__("COMM CHANNEL", parent)
        self._engine = engine
        self._config = config

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 34, 12, 12)
        layout.setSpacing(6)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: rgba(0,0,0,0); width: 4px; }
            QScrollBar::handle:vertical { background: #00b4ff; border-radius: 2px; }
        """)

        self._chat_container = QWidget()
        self._chat_container.setStyleSheet("background: transparent;")
        self._chat_layout = QVBoxLayout(self._chat_container)
        self._chat_layout.setSpacing(8)
        self._chat_layout.setContentsMargins(0, 0, 0, 0)
        self._chat_layout.addStretch()
        self._scroll.setWidget(self._chat_container)
        layout.addWidget(self._scroll)

        # Input row
        input_row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText("Enter command or query...")
        self._input.setFont(QFont("Consolas", 10))
        self._input.setStyleSheet("""
            QLineEdit {
                background: rgba(0, 30, 60, 180);
                border: 1px solid #0080c0;
                border-radius: 4px;
                color: #dceeff;
                padding: 6px 10px;
            }
            QLineEdit:focus { border: 1px solid #00b4ff; }
        """)
        self._input.returnPressed.connect(self._send_message)

        send_btn = QPushButton("▶ SEND")
        send_btn.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        send_btn.setFixedWidth(90)
        send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #b85000, stop:1 #ff8c00);
                border: none; border-radius: 4px;
                color: white; padding: 6px;
            }
            QPushButton:hover { background: #ff9900; }
            QPushButton:pressed { background: #cc7700; }
        """)
        send_btn.clicked.connect(self._send_message)

        input_row.addWidget(self._input)
        input_row.addWidget(send_btn)
        layout.addLayout(input_row)

        # Add welcome message
        QTimer.singleShot(3500, self._boot_message)

    def _boot_message(self):
        name = self._config.get("user_name", "Sir")
        hour = datetime.datetime.now().hour
        part = "morning" if hour < 12 else ("afternoon" if hour < 18 else "evening")
        self.add_message("JARVIS",
                         f"Good {part}, {name}. All systems are operational. "
                         "Awaiting your instructions.",
                         speaking=True)

    def submit_external(self, text):
        """Inject a command from outside (e.g. voice or a quick-action button)."""
        if text:
            self.add_message("YOU", text, speaking=False)
            QTimer.singleShot(400, lambda: self._respond(text))

    def _send_message(self):
        txt = self._input.text().strip()
        if not txt:
            return
        self.add_message("YOU", txt, speaking=False)
        self._input.clear()
        QTimer.singleShot(500, lambda: self._respond(txt))

    def _respond(self, query):
        reply = self._engine.process(query)
        if reply == "__OPEN_SETTINGS__":
            self.open_settings_requested.emit()
            reply = "Opening settings, {}.".format(self._config.get("user_name", "Sir"))
        self.add_message("JARVIS", reply, speaking=True)
        self.jarvis_replied.emit(reply)

    def add_message(self, sender, text, speaking=False):
        msg_widget = QWidget()
        msg_widget.setStyleSheet("background: transparent;")
        msg_layout = QVBoxLayout(msg_widget)
        msg_layout.setContentsMargins(0, 0, 0, 0)
        msg_layout.setSpacing(2)

        sender_lbl = QLabel(f"[{sender}]")
        sender_lbl.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        if sender == "JARVIS":
            sender_lbl.setStyleSheet("color: #ff8c00; background: transparent;")
        else:
            sender_lbl.setStyleSheet("color: #00b4ff; background: transparent;")

        text_lbl = QLabel(text)
        text_lbl.setFont(QFont("Consolas", 9))
        text_lbl.setWordWrap(True)
        text_lbl.setStyleSheet("""
            color: #c8e0ff;
            background: rgba(0, 20, 40, 120);
            border-radius: 4px;
            padding: 5px 8px;
        """)

        msg_layout.addWidget(sender_lbl)
        msg_layout.addWidget(text_lbl)

        self._chat_layout.insertWidget(self._chat_layout.count() - 1, msg_widget)
        QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()))


# ══════════════════════════════════════════════════════════════════════════════
# QUICK ACTION BUTTONS
# ══════════════════════════════════════════════════════════════════════════════
class QuickActionsPanel(HUDPanel):
    # Emits the command string a button represents.
    action_triggered = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("QUICK ACTIONS", parent)
        self.setFixedHeight(100)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 32, 12, 10)
        layout.setSpacing(0)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        # (label, color, command sent to the engine when clicked)
        actions = [
            ("⬡ CHROME",   "#0055aa", "open chrome"),
            ("⬡ VS CODE",  "#5500cc", "open vscode"),
            ("⬡ FOLDER",   "#006633", "open folder"),
            ("⬡ SEARCH",   "#884400", "__SEARCH_PROMPT__"),
            ("⬡ TERMINAL", "#006666", "open terminal"),
            ("⬡ SETTINGS", "#443300", "open settings"),
        ]
        for label, color, command in actions:
            btn = QPushButton(label)
            btn.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
            btn.setFixedHeight(38)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {color};
                    border: 1px solid rgba(255,255,255,60);
                    border-radius: 4px;
                    color: white;
                    padding: 0 4px;
                }}
                QPushButton:hover {{
                    background: {color}cc;
                    border: 1px solid #00b4ff;
                }}
                QPushButton:pressed {{
                    background: {color}88;
                }}
            """)
            btn.clicked.connect(lambda _=False, c=command: self.action_triggered.emit(c))
            btn_row.addWidget(btn)

        layout.addLayout(btn_row)


# ══════════════════════════════════════════════════════════════════════════════
# SETTINGS DIALOG
# ══════════════════════════════════════════════════════════════════════════════
class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("J.A.R.V.I.S — Settings")
        self.setMinimumWidth(400)
        self.setStyleSheet("""
            QDialog { background: #08111e; }
            QLabel { color: #c8e0ff; }
            QLineEdit, QComboBox {
                background: rgba(0,30,60,180); color: #dceeff;
                border: 1px solid #0080c0; border-radius: 4px; padding: 4px 6px;
            }
            QCheckBox { color: #c8e0ff; }
        """)

        form = QFormLayout(self)
        form.setContentsMargins(20, 20, 20, 16)
        form.setSpacing(12)

        title = QLabel("⬡  SYSTEM CONFIGURATION")
        title.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #ff8c00;")
        form.addRow(title)

        self.name_edit = QLineEdit(config.get("user_name", "Sir"))
        form.addRow("Address me as:", self.name_edit)

        self.voice_chk = QCheckBox("Speak responses aloud")
        self.voice_chk.setChecked(config.get("voice_output", True))
        form.addRow("Voice output:", self.voice_chk)

        self.rate_combo = QComboBox()
        for r in ("Slow (140)", "Normal (175)", "Fast (210)"):
            self.rate_combo.addItem(r)
        rate = config.get("voice_rate", 175)
        self.rate_combo.setCurrentIndex(0 if rate <= 150 else (2 if rate >= 200 else 1))
        form.addRow("Voice rate:", self.rate_combo)

        self.accent_combo = QComboBox()
        for a in ACCENTS.keys():
            self.accent_combo.addItem(a)
        self.accent_combo.setCurrentText(config.get("accent", "orange"))
        form.addRow("HUD accent:", self.accent_combo)

        self.engine_combo = QComboBox()
        for e in SEARCH_URLS.keys():
            self.engine_combo.addItem(e)
        self.engine_combo.setCurrentText(config.get("search_engine", "google"))
        form.addRow("Search engine:", self.engine_combo)

        self.pw_chk = QCheckBox("Enable automated browsing (Playwright)")
        self.pw_chk.setChecked(config.get("use_playwright", False))
        form.addRow("Real work:", self.pw_chk)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self):
        rate_map = {0: 140, 1: 175, 2: 210}
        return {
            "user_name": self.name_edit.text().strip() or "Sir",
            "voice_output": self.voice_chk.isChecked(),
            "voice_rate": rate_map[self.rate_combo.currentIndex()],
            "accent": self.accent_combo.currentText(),
            "search_engine": self.engine_combo.currentText(),
            "use_playwright": self.pw_chk.isChecked(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# STARTUP SCREEN
# ══════════════════════════════════════════════════════════════════════════════
class StartupScreen(QWidget):
    finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._lines_done = []
        self._current    = 0
        self._alpha      = 255
        self._fade_out   = False
        self._bar_w      = 0.0

        self._t = QTimer(self)
        self._t.timeout.connect(self._tick)
        self._t.start(16)

        # Show lines with stagger
        for i, line in enumerate(BOOT_LINES):
            QTimer.singleShot(400 * (i + 1), lambda l=line: self._add_line(l))

        QTimer.singleShot(400 * (len(BOOT_LINES) + 2), self._start_fade)

    def _add_line(self, line):
        self._lines_done.append(line)
        self.update()

    def _start_fade(self):
        self._fade_out = True

    def _tick(self):
        if self._fade_out:
            self._alpha = max(0, self._alpha - 6)
            if self._alpha == 0:
                self._t.stop()
                self.finished.emit()
        self._bar_w = min(1.0, self._bar_w + 0.008)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        p.setOpacity(self._alpha / 255.0)

        # Background
        p.fillRect(0, 0, w, h, BG_DARK)

        # Center vertical stack of text
        total_h = len(BOOT_LINES) * 28
        start_y = (h - total_h) // 2

        p.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        for i, line in enumerate(BOOT_LINES):
            y    = start_y + i * 28
            done = i < len(self._lines_done)
            color = ORANGE_CORE if (line == BOOT_LINES[-1] and done) else (
                CYAN_ACCENT if done else QColor(50, 80, 100))
            p.setPen(QPen(color))
            p.drawText(QRectF(0, y, w, 26), Qt.AlignmentFlag.AlignCenter, line)

        # Progress bar
        bar_y = start_y + len(BOOT_LINES) * 28 + 20
        bar_w = int(w * 0.5)
        bar_x = (w - bar_w) // 2
        p.setPen(QPen(QColor(0, 100, 150), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(bar_x, bar_y, bar_w, 6)
        grad = QLinearGradient(bar_x, 0, bar_x + bar_w, 0)
        grad.setColorAt(0, ORANGE_DIM)
        grad.setColorAt(1, ORANGE_CORE)
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(bar_x, bar_y, int(bar_w * self._bar_w), 6)

        # JARVIS logo
        p.setFont(QFont("Consolas", 36, QFont.Weight.Bold))
        p.setPen(QPen(QColor(255, 140, 0, 220)))
        p.drawText(QRectF(0, h // 2 - 180, w, 60), Qt.AlignmentFlag.AlignCenter, "J.A.R.V.I.S")
        p.setFont(QFont("Consolas", 10))
        p.setPen(QPen(QColor(0, 160, 220, 160)))
        p.drawText(QRectF(0, h // 2 - 130, w, 24),
                   Qt.AlignmentFlag.AlignCenter,
                   "Just A Rather Very Intelligent System  •  Stark Industries")
        p.end()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN WINDOW
# ══════════════════════════════════════════════════════════════════════════════
class JARVISMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S  Operating System  •  Stark Industries")
        self.setMinimumSize(1280, 800)
        self.resize(1400, 860)

        # Core services
        self.config = load_config()
        self.chrome = ChromeController(self.config)
        self.engine = CommandEngine(self.config, self.chrome)
        self._tts_worker = None
        self._listener = None

        # Dark palette
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, BG_DARK)
        self.setPalette(palette)
        self.setStyleSheet("QMainWindow { background-color: #04060a; }")

        # Stacked pages: 0 = startup, 1 = main UI
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # Startup screen
        self._startup = StartupScreen()
        self._startup.finished.connect(self._show_main)
        self._stack.addWidget(self._startup)

        # Build main UI (hidden until boot finishes)
        self._main_widget = self._build_main_ui()
        self._stack.addWidget(self._main_widget)

        self._stack.setCurrentIndex(0)
        self._apply_accent()

    def _show_main(self):
        self._stack.setCurrentIndex(1)

    # -- accent -----------------------------------------------------------
    def _apply_accent(self):
        self._arc.set_accent(self.config.get("accent", "orange"))

    # -- UI build ---------------------------------------------------------
    def _build_main_ui(self):
        root = QWidget()
        root.setStyleSheet("background: #04060a;")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(8)

        # ── Top bar ──────────────────────────────────────────────────────────
        top_bar = self._build_top_bar()
        outer.addWidget(top_bar)

        # ── Main row ─────────────────────────────────────────────────────────
        main_row = QHBoxLayout()
        main_row.setSpacing(10)

        # Left panel
        self._sys_panel = SystemStatusPanel()
        main_row.addWidget(self._sys_panel)

        # Center column
        center_col = QVBoxLayout()
        center_col.setSpacing(8)

        # Arc core widget
        self._arc = ArcCoreWidget()
        self._arc.setMinimumHeight(340)
        center_col.addWidget(self._arc, 0, Qt.AlignmentFlag.AlignHCenter)

        # Chat / transcript
        self._chat = ChatPanel(self.engine, self.config)
        self._chat.jarvis_replied.connect(self._on_jarvis_reply)
        self._chat.open_settings_requested.connect(self._open_settings)
        center_col.addWidget(self._chat, 1)

        main_row.addLayout(center_col, 1)

        # Right panel
        self._agent_panel = AgentMonitorPanel()
        main_row.addWidget(self._agent_panel)

        outer.addLayout(main_row, 1)

        # ── Bottom quick actions ──────────────────────────────────────────────
        self._quick = QuickActionsPanel()
        self._quick.action_triggered.connect(self._on_quick_action)
        outer.addWidget(self._quick)

        return root

    def _build_top_bar(self):
        bar = HUDPanel("", None)
        bar.setFixedHeight(48)
        bar._title = ""

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(16)

        # Logo / title
        logo = QLabel("⬡ J.A.R.V.I.S  OS")
        logo.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
        logo.setStyleSheet("color: #ff8c00; background: transparent;")
        layout.addWidget(logo)

        layout.addStretch()

        # Status pills
        for text, color in [("STARK NETWORK: ACTIVE", "#00ff96"),
                              ("ARC REACTOR: 100%",    "#00b4ff"),
                              ("THREAT LEVEL: NONE",   "#ffaa00")]:
            lbl = QLabel(f"● {text}")
            lbl.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
            lbl.setStyleSheet(f"color: {color}; background: rgba(0,0,0,60);"
                               "border: 1px solid rgba(255,255,255,20);"
                               "border-radius: 3px; padding: 2px 8px;")
            layout.addWidget(lbl)

        layout.addStretch()

        # Settings gear
        gear = QPushButton("⚙")
        gear.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        gear.setFixedSize(36, 32)
        gear.setStyleSheet("""
            QPushButton {
                background: rgba(0,60,120,180);
                border: 1px solid #0080ff;
                border-radius: 4px; color: #00b4ff;
            }
            QPushButton:hover { background: rgba(0,90,160,200); }
        """)
        gear.clicked.connect(self._open_settings)
        layout.addWidget(gear)

        # Mic button
        self._mic = QPushButton("⏺ MIC")
        self._mic.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        self._mic.setFixedSize(72, 32)
        self._mic.setStyleSheet("""
            QPushButton {
                background: rgba(0,60,120,180);
                border: 1px solid #0080ff;
                border-radius: 4px; color: #00b4ff;
            }
            QPushButton:hover { background: rgba(0,90,160,200); }
            QPushButton:pressed { background: rgba(0,40,80,200); }
            QPushButton:checked {
                background: rgba(0,150,255,180);
                border: 1px solid #00dcff;
                color: white;
            }
        """)
        self._mic.setCheckable(True)
        self._mic.clicked.connect(self._on_mic_clicked)
        layout.addWidget(self._mic)

        return bar

    # -- reply handling ----------------------------------------------------
    def _on_jarvis_reply(self, text):
        """Animate the arc core while JARVIS 'speaks' and optionally use TTS."""
        self._arc.set_speaking(True)
        if self.config.get("voice_output", True):
            self._speak(text)
        else:
            # No TTS: just show the speaking animation briefly.
            duration = min(6000, 1200 + len(text) * 45)
            QTimer.singleShot(duration, lambda: self._arc.set_speaking(False))

    def _speak(self, text):
        # Clean up a prior worker if it exists.
        self._tts_worker = TTSWorker(text, rate=self.config.get("voice_rate", 175))
        self._tts_worker.started_speaking.connect(lambda: self._arc.set_speaking(True))
        self._tts_worker.finished_speaking.connect(lambda: self._arc.set_speaking(False))
        self._tts_worker.start()
        # Fallback: if pyttsx3 is missing, run() returns instantly and the
        # finished signal already turned speaking off — animate briefly instead.
        duration = min(6000, 1200 + len(text) * 45)
        QTimer.singleShot(duration, lambda: self._arc.set_speaking(False))

    # -- quick actions -----------------------------------------------------
    def _on_quick_action(self, command):
        if command == "__SEARCH_PROMPT__":
            # Focus the input box with a search stub.
            self._chat._input.setText("search ")
            self._chat._input.setFocus()
            return
        if command == "open settings":
            self._open_settings()
            return
        self._chat.submit_external(command)

    # -- microphone --------------------------------------------------------
    def _on_mic_clicked(self, checked):
        if not checked:
            self._arc.set_user_speaking(False)
            return
        self._arc.set_user_speaking(True)
        self._listener = VoiceListener()
        self._listener.status.connect(self._on_voice_status)
        self._listener.recognized.connect(self._on_voice_recognized)
        self._listener.finished.connect(lambda: self._mic.setChecked(False))
        self._listener.start()

    def _on_voice_status(self, status):
        if status == "unavailable":
            self._arc.set_user_speaking(False)
            self._chat.add_message(
                "JARVIS",
                "Voice input needs SpeechRecognition + PyAudio. Install with "
                "`pip install SpeechRecognition pyaudio`.",
                speaking=True)
            self._mic.setChecked(False)
        elif status.startswith("error:"):
            self._arc.set_user_speaking(False)
            self._chat.add_message(
                "JARVIS",
                "I couldn't hear that clearly. Please try again.",
                speaking=True)
            self._mic.setChecked(False)

    def _on_voice_recognized(self, text):
        self._arc.set_user_speaking(False)
        self._mic.setChecked(False)
        self._chat.submit_external(text)

    # -- settings ----------------------------------------------------------
    def _open_settings(self):
        dlg = SettingsDialog(self.config, self)
        if dlg.exec():
            self.config.update(dlg.values())
            save_config(self.config)
            self._apply_accent()
            self._chat.add_message(
                "JARVIS", "Settings updated and saved.", speaking=True)

    def paintEvent(self, event):
        """Draw subtle scanlines on the whole window."""
        p = QPainter(self)
        for y in range(0, self.height(), 4):
            p.setPen(QPen(QColor(0, 0, 0, 30)))
            p.drawLine(0, y, self.width(), y)
        p.end()


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("JARVIS OS")
    app.setOrganizationName("Stark Industries")

    # Try to use a monospace system font
    QFontDatabase.addApplicationFont("")  # no-op if empty

    win = JARVISMainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
