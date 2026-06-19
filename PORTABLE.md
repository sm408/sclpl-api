# SCLPLAPI — Portable Setup

SCLPLAPI is fully portable. Just zip the folder and run it anywhere Python 3.11+ is available.

## Quick Start

### Windows
```
1. Unzip sclplapi.zip
2. Double-click sclplapi.bat
3. Follow the setup wizard
```

### Linux / macOS
```
1. Unzip sclplapi.zip
2. chmod +x sclplapi.sh
3. ./sclplapi.sh
```

### Manual (Any Platform)
```
1. Unzip sclplapi.zip
2. cd sclplapi
3. pip install -e ".[all]"
4. python -m app
```

## What's Included

```
sclplapi/
├── app/                    # Core application
│   ├── core/               # Engine, models, contracts
│   ├── services/           # HTTP, export, history
│   ├── storage/            # SQLite database
│   ├── ui/                 # TUI, CLI, launcher
│   ├── web/                # Web GUI (FastAPI)
│   └── utils/              # Shared utilities
├── functions/              # Python extension functions
├── plugins/                # Plugin packages
├── examples/               # Example workflows
├── boilerplates/           # Starter templates
├── tools/                  # Development utilities
├── tests/                  # Test suite
├── docs/                   # Documentation
├── data/                   # Runtime data (SQLite)
├── sclplapi.bat            # Windows launcher
├── sclplapi.sh             # Linux/macOS launcher
├── pyproject.toml          # Python package config
└── requirements.txt        # Dependencies list
```

## Requirements

- Python 3.11 or later
- Internet connection (first run only, for installing dependencies)
- No other tools required (no Node.js, no Docker)

## First Run

The first time you run SCLPLAPI:

1. Dependencies are installed automatically
2. A setup wizard asks for your preferences
3. Settings are saved to `~/.sclplapi/settings.json`
4. A local database is created in `data/`

## Subsequent Runs

After the first run, just double-click the launcher or run:
```bash
python -m app
```

## Offline Use

After the first run, SCLPLAPI works completely offline. All data stays local.

## Updating

To update to the latest version:
```bash
sclplapi update
```

Or manually:
```bash
git pull
pip install -e ".[all]"
```

## Troubleshooting

**"Python not found"**
- Install Python 3.11+ from https://python.org
- Make sure Python is in your PATH

**"Module not found"**
- Run: `pip install -e ".[all]"`

**"Permission denied" (Linux/macOS)**
- Run: `chmod +x sclplapi.sh`

**Database errors**
- Delete `data/sclplapi.db` and restart

## Moving to Another Machine

1. Zip the entire `sclplapi/` folder
2. Copy to the new machine
3. Unzip and run the launcher
4. Dependencies install automatically on first run

Your workflows, functions, and settings are all in the folder (except settings which are in `~/.sclplapi/`).
