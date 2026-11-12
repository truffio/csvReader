# CSV Editor

A small Tkinter mini-spreadsheet for viewing and editing CSV files.
Stdlib only, no dependencies. Requires Python 3.10+.

## Features

- Open several CSV files at once, each in its own tab (opening a file that is
  already open switches to its tab).
- Load CSV files with automatic delimiter detection.
- Edit any cell by double-clicking it, pressing Enter, or pressing F2.
- Press Tab to commit the edit and move to the next cell.
- Rename a column by double-clicking its header.
- The current cell is outlined; move it with the mouse or the arrow keys.
- Cut, copy, and paste a cell, rows, or a column (Edit menu or right-click menu;
  Ctrl+X / Ctrl+C / Ctrl+V for the current cell). Paste inserts what was cut or
  copied last: a cell value into the current cell, rows above the selected rows,
  a column to the left of the current column. Works across tabs; text copied from
  other programs pastes into the current cell.
- Insert or delete rows and columns from the Edit menu, the toolbar, or the right-click menu.
- Save, or save to a new file (Save As).
- Save All saves every modified tab.
- Close a tab with Ctrl+W, a middle-click, or the tab's right-click menu.
- Reorder tabs by dragging them.
- Unsaved-changes prompt per tab before closing a tab or exiting; modified
  tabs are marked with `*`.
- Spreadsheet-style grid lines and gray row/column headers.

## Usage

```sh
python app.py
python app.py sample.csv other.csv   # opens each file in its own tab
```

## Keyboard shortcuts

| Shortcut         | Action                          |
| ---------------- | ------------------------------- |
| Ctrl+N           | New tab                         |
| Ctrl+O           | Open file(s) in new tabs        |
| Ctrl+W           | Close tab                       |
| Ctrl+Tab         | Next tab                        |
| Ctrl+Shift+Tab   | Previous tab                    |
| Ctrl+S           | Save                            |
| Ctrl+Shift+S     | Save as                         |
| Ctrl+X           | Cut current cell                |
| Ctrl+C           | Copy current cell               |
| Ctrl+V           | Paste (cell, rows, or column)   |
| Left / Right     | Move current cell               |
| Enter / F2       | Edit current cell               |
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
