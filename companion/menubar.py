"""
RAWMASTER Companion — macOS Menu Bar App
Wraps the Flask daemon as a native menu bar app using rumps.
Users see a ⚡ icon in the menu bar — click to see status or quit.

Run: python3 menubar.py
"""
import threading
import sys
from pathlib import Path

# Make sure rawmaster is importable from parent dir
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import rumps
except ImportError:
    print("rumps not installed. Run: pip install rumps")
    sys.exit(1)

from daemon import run_server, PORT


class RAWMASTERMenuBar(rumps.App):
    def __init__(self):
        super().__init__("⚡", title=None)
        self.menu = [
            rumps.MenuItem("RAWMASTER Companion"),
            rumps.MenuItem(f"http://127.0.0.1:{PORT}"),
            None,  # separator
            rumps.MenuItem("Open in Browser", callback=self.open_browser),
            None,
            rumps.MenuItem("Quit", callback=rumps.quit_application),
        ]
        self._server_thread = None

    @rumps.clicked("Open in Browser")
    def open_browser(self, _):
        import subprocess
        subprocess.Popen(["open", f"http://127.0.0.1:{PORT}/health"])

    def start_server(self):
        self._server_thread = threading.Thread(target=run_server, daemon=True)
        self._server_thread.start()

    def run(self):
        self.start_server()
        super().run()


if __name__ == "__main__":
    from rawmaster import check_license
    check_license()
    print(f"RAWMASTER Companion starting at http://127.0.0.1:{PORT}")
    RAWMASTERMenuBar().run()
