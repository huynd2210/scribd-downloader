# Scribd Downloader

<p align="center">
  <img src="assets/scribd.svg" alt="Scribd Downloader" width="180">
</p>

## Installation

```bash
git clone https://github.com/huynd2210/scribd-downloader.git
cd scribd-downloader
python -m venv .venv
```

Activate the virtual environment and install the dependencies:

```bash
pip install -r requirements.txt
```

Google Chrome must be installed.

## Usage

Start the web interface:

```bash
python run_ui.py
```

Open `http://127.0.0.1:8000`, paste a Scribd document URL, and download the PDF.

You can also use the command line:

```bash
python scribd-downloader.py
```
