"""
Scribd Downloader UI Launcher Script
====================================
Starts Uvicorn Web Server and opens the Web UI in your browser.
"""

import os
import sys
import time
import webbrowser
import uvicorn

def main():
    print("=" * 60)
    print(" Scribd Downloader Web UI")
    print(" Starting server on http://127.0.0.1:8000 ...")
    print("=" * 60)

    # Open browser after 1.5 seconds
    def open_browser():
        time.sleep(1.5)
        webbrowser.open("http://127.0.0.1:8000")

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    # Run Uvicorn app
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False, log_level="info")

if __name__ == "__main__":
    main()
