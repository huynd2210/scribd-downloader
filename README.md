# Scribd Downloader

<p align="center">
  <img width="988" height="665" alt="image" src="https://github.com/user-attachments/assets/8d2094c5-b749-40eb-8b4a-fc3919650eb7" />

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

Open `http://127.0.0.1:8000`, paste one or more Scribd URLs (one per line), and download the PDFs.

You can also use the command line:

```bash
python scribd-downloader.py
```
