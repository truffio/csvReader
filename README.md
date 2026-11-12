# CSV Editor

A small Tkinter mini-spreadsheet for viewing and editing CSV files.
Stdlib only, no dependencies. Requires Python 3.10+.

## Features

- Load CSV files with automatic delimiter detection.
- Edit any cell by double-clicking it, pressing Enter, or pressing F2.
- Press Tab to commit the edit and move to the next cell.
- Rename a column by double-clicking its header.
- Insert or delete rows and columns from the Edit menu, the toolbar, or the right-click menu.
- Save, or save to a new file (Save As).
- Unsaved-changes prompt before discarding edits.

## Usage

```sh
python app.py
python app.py sample.csv
```

## Keyboard shortcuts

| Shortcut         | Action                          |
| ---------------- | ------------------------------- |
| Ctrl+O           | Open file                       |
| Ctrl+S           | Save                            |
| Ctrl+Shift+S     | Save as                         |
| Enter / F2       | Edit selected cell              |
| Escape           | Cancel edit                     |
| Tab              | Commit edit and move to next cell |
| Delete           | Delete selected rows            |

## Running tests

```sh
python -m unittest -v
```

## Project layout

- `app.py`: Tkinter GUI.
- `csv_model.py`: data model (loading, editing, saving).
- `test_csv_model.py`: unit tests for the data model.
- `sample.csv`: example file with quoted fields, embedded quotes, and non-ASCII text.
