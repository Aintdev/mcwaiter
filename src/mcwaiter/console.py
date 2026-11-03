from dataclasses import dataclass, field
import curses
import queue
import subprocess
import threading
from mcwaiter.helpers import require_root
from rcon.source import Client as RconClient

@dataclass(frozen=True)
class RconDetails:
    port: int = field()
    pw: str | None = field(default=None)

class ConsolePopen(subprocess.Popen):
    def __exit__(self, exc_type, exc, tb):
        self.terminate()
        return super().__exit__(exc_type, exc, tb)
    
class DummyRconClient:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def __getattr__(self, name):
        return lambda *args, **kwargs: None

class Console:
    def __init__(self, service: str, rcon_details: RconDetails | None = None):
        self.service: str = service
        self.rcon: bool = True if rcon_details else False 
        self.rcon_details: RconDetails = rcon_details

    def journal_conn(self):
        return ConsolePopen(
            ["journalctl", "-u", self.service, "-f", "-o", "cat"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

    def rcon_conn(self):
        if self.rcon:
            return RconClient("127.0.0.1", self.rcon_details.port, passwd=self.rcon_details.pw)
        return DummyRconClient()
    
    def run(self):
        with self.journal_conn() as jrn:
            with self.rcon_conn() as rcon:
                logs = queue.Queue()

                def read_output():
                    for line in jrn.stdout:
                        logs.put(line.rstrip("\n"))

                threading.Thread(target=read_output, daemon=True).start()

                curses.wrapper(console, jrn, logs, rcon)

def console(stdscr, jrn: ConsolePopen, logs: queue.Queue, rcon: RconClient):
    curses.curs_set(1)
    stdscr.timeout(50)

    rcon_on = isinstance(rcon, RconClient)

    history = []
    rcon_history = []
    rcon_history_idx = 0
    user_input = ""
    cur_idx = 0
    newest_lock = True

    while jrn.poll() is None:
        while not logs.empty():
            history.append(logs.get_nowait())
        height, width = stdscr.getmaxyx()
        stdscr.erase()

        # Server output
        cur_idx = len(history) - 1 if newest_lock else cur_idx
        visible = height - 2
        start = max(0, cur_idx - visible + 1)
        for y, line in enumerate(history[start:cur_idx + 1]):
            stdscr.addnstr(y, 0, line, width - 1)
        # Input
        prompt = f"{rcon_history_idx} cmd: " + ("" if rcon_on else "[DISABLED]")
        stdscr.addstr(height - 1, 0, prompt)
        stdscr.addnstr(
            height - 1,
            len(prompt),
            user_input,
            max(0, width - len(prompt) - 1),
        )

        stdscr.move(
            height - 1,
            min(len(prompt) + len(user_input), width - 1),
        )

        stdscr.refresh()

        try:
            key = stdscr.get_wch()
        except curses.error:
            continue

        if not rcon_on:
            pass

        elif key == curses.KEY_UP:
            if len(rcon_history) > rcon_history_idx:
                if old_input := rcon_history[-(rcon_history_idx + 1)]:
                    rcon_history_idx += 1
                    user_input = old_input

        elif key == curses.KEY_DOWN:
            if rcon_history_idx - 1 > 0:
                if old_input := rcon_history[-(rcon_history_idx - 1)]:
                    rcon_history_idx -= 1
                    user_input = old_input
            else:
                rcon_history_idx = 0
                user_input = ""

        elif key in ("\n", "\r", curses.KEY_ENTER):
            if user_input.strip():
                rcon_history_idx = 0
                rcon_history.append(user_input)
                response = rcon.run(user_input)
                for line in response.splitlines():
                    logs.put(line.rstrip("\n"))
            user_input = ""

        elif key in ("\b", "\x7f", curses.KEY_BACKSPACE):
            user_input = user_input[:-1]

        elif isinstance(key, str) and key.isprintable():
            user_input += key
