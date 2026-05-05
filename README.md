# D2Savior

A save editor for Diablo II: Resurrected.

Supports both version 0x63 (v1.x) and 0x69 (v3.x) d2s save files.

## Features

- Parse and edit character saves (.d2s)
- Parse and edit shared stash (.d2i)
- Parse and edit standalone items (.d2i)
- View and edit character stats, skills, waypoints, quests
- View and edit item properties
- Drag & drop items between inventory slots

## Requirements

- Python 3.12+
- PySide6 >= 6.6.0

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python d2s_gui.py
```

### Command Line Parsing

```bash
python d2s_parse.py <save_file>
```

## Build

```bash
# Build executable
make build

# Build installer
make installer
```

## Testing

```bash
make tests
```

## License

[MIT](LICENSE)
