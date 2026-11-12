"""Tkinter mini-spreadsheet CSV editor with one tab per file."""
import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from csv_model import CsvModel

ROWNUM = "#"
FILETYPES = [("CSV files", "*.csv"), ("All files", "*.*")]

GRID_COLOR = "#d4d4d4"
HEADER_BG = "#ececec"
HEADER_ACTIVE_BG = "#dcdcdc"
HEADER_SELECTED_BG = "#cfd9e6"
ROW_SELECTED_BG = "#cfe2f8"  # light, so the current-cell outline shows on it
CURSOR_COLOR = "#2f6db3"     # current-cell outline
TAB_BG = "#c5d0de"          # inactive file tab
TAB_ACTIVE_BG = "#adbdd2"    # inactive tab under the mouse
TAB_FG = "#1f2d3d"
TAB_SELECTED_BG = "#2f6db3"  # current file tab
TAB_SELECTED_FG = "#ffffff"


def setup_style(root):
    """Gray column headings. Native themes (e.g. vista) ignore heading colors,
    so build the heading from the 'default' theme's elements."""
    s = ttk.Style(root)
    for el in ("cell", "border"):
        try:
            s.element_create(f"Grid.Treeheading.{el}", "from", "default")
        except tk.TclError:
            pass  # already created
    s.layout("Grid.Treeview.Heading", [
        ("Grid.Treeheading.cell", {"sticky": "nswe"}),
        ("Grid.Treeheading.border", {"sticky": "nswe", "children": [
            ("Treeheading.padding", {"sticky": "nswe", "children": [
                ("Treeheading.image", {"side": "right", "sticky": ""}),
                ("Treeheading.text", {"sticky": "we"})]})]})])
    s.configure("Grid.Treeview.Heading", background=HEADER_BG,
                relief="raised", borderwidth=1, bordercolor=GRID_COLOR,
                lightcolor=HEADER_BG, darkcolor=GRID_COLOR)
    s.map("Grid.Treeview.Heading",
          background=[("active", HEADER_ACTIVE_BG)],
          relief=[("pressed", "sunken")])

    s.map("Grid.Treeview",
          background=[("selected", ROW_SELECTED_BG)],
          foreground=[("selected", "black")])

    # File tabs: same trick, so the tab handles can be colored.
    try:
        s.element_create("Sheets.Notebook.tab", "from", "default")
    except tk.TclError:
        pass
    s.layout("Sheets.TNotebook.Tab", [
        ("Sheets.Notebook.tab", {"sticky": "nswe", "children": [
            ("Notebook.padding", {"side": "top", "sticky": "nswe", "children": [
                ("Notebook.label", {"side": "top", "sticky": ""})]})]})])
    s.configure("Sheets.TNotebook.Tab", background=TAB_BG, foreground=TAB_FG,
                padding=(12, 4), borderwidth=1, lightcolor=TAB_BG, bordercolor=GRID_COLOR)
    s.map("Sheets.TNotebook.Tab",
          background=[("selected", TAB_SELECTED_BG), ("active", TAB_ACTIVE_BG)],
          foreground=[("selected", TAB_SELECTED_FG)],
          lightcolor=[("selected", TAB_SELECTED_BG)],
          expand=[("selected", (1, 2, 1, 0))])
    s.configure("Sheets.TNotebook", tabmargins=(2, 4, 2, 0))


class SheetTab(ttk.Frame):
    """One spreadsheet tab: a CsvModel plus its grid view and editing state."""

    def __init__(self, app, master, untitled_name):
        super().__init__(master)
        self.app = app
        self.model = CsvModel()
        self.untitled_name = untitled_name
        self.current_col = 0
        self.editor = None
        self.edit_pos = None  # (row, col)
        self._build_grid()

    @property
    def display_name(self):
        return os.path.basename(self.model.path) if self.model.path else self.untitled_name

    def _changed(self):
        self.app.on_tab_changed(self)

    # ---------- grid construction ----------
    def _build_grid(self):
        self.tree = ttk.Treeview(self, show="headings", selectmode="extended",
                                 style="Grid.Treeview")
        vs = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        hs = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=lambda *a: (vs.set(*a), self._schedule_gridlines()),
                            xscrollcommand=lambda *a: (hs.set(*a), self._schedule_gridlines()))
        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.tree.bind("<Button-1>", self.on_click, add="+")
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Button-3>", self.on_right_click)
        self.tree.bind("<Return>", lambda e: self.start_edit_current())
        self.tree.bind("<F2>", lambda e: self.start_edit_current())
        self.tree.bind("<Delete>", lambda e: self.delete_rows())
        self.tree.bind("<Left>", lambda e: self._move_col(-1))
        self.tree.bind("<Right>", lambda e: self._move_col(1))

        # Grid lines and gray row numbers: ttk.Treeview supports neither, so
        # overlay 1px frames and labels, redrawn on scroll/resize/selection.
        self._lines = []
        self._rownum_labels = []
        self._cursor = [tk.Frame(self.tree, bg=CURSOR_COLOR, bd=0, highlightthickness=0)
                        for _ in range(4)]  # top, bottom, left, right edges
        for f in self._cursor:
            self._bind_forwarding(f)
        self._gridlines_pending = False
        for seq in ("<Configure>", "<B1-Motion>", "<ButtonRelease-1>", "<<TreeviewSelect>>"):
            self.tree.bind(seq, lambda e: self._schedule_gridlines(), add="+")

    # ---------- grid lines ----------
    def _schedule_gridlines(self):
        if not self._gridlines_pending:
            self._gridlines_pending = True
            self.after_idle(self._draw_gridlines)

    def _forward(self, event, sequence):
        """Pass mouse events that land on an overlay through to the tree."""
        if sequence == "<MouseWheel>":
            self.tree.yview_scroll(int(-event.delta / 120), "units")
            return
        self.tree.event_generate(sequence,
                                 x=event.x_root - self.tree.winfo_rootx(),
                                 y=event.y_root - self.tree.winfo_rooty(),
                                 rootx=event.x_root, rooty=event.y_root, state=event.state)

    def _bind_forwarding(self, widget):
        for seq in ("<Button-1>", "<Double-1>", "<Button-3>", "<MouseWheel>"):
            widget.bind(seq, lambda e, s=seq: self._forward(e, s))

    def _line(self, i):
        while len(self._lines) <= i:
            ln = tk.Frame(self.tree, bg=GRID_COLOR, bd=0, highlightthickness=0)
            self._bind_forwarding(ln)
            self._lines.append(ln)
        return self._lines[i]

    def _rownum_label(self, i):
        while len(self._rownum_labels) <= i:
            lb = tk.Label(self.tree, bg=HEADER_BG, bd=0, anchor="center",
                          font=ttk.Style(self).lookup("Treeview", "font") or "TkDefaultFont")
            self._bind_forwarding(lb)
            self._rownum_labels.append(lb)
        return self._rownum_labels[i]

    def _columns_width(self):
        return sum(self.tree.column(c, "width") for c in self.tree["columns"]) or 1

    def _draw_gridlines(self):
        self._gridlines_pending = False
        tree = self.tree
        if not tree.winfo_exists():
            return
        width, height = tree.winfo_width(), tree.winfo_height()
        items = tree.get_children()
        n = nl = 0
        # The top visible row sits directly under the header, so its bbox
        # gives both the header height and the row height.
        bbox = None
        if items:
            top = min(int(round(tree.yview()[0] * len(items))), len(items) - 1)
            for top in range(top, min(top + 3, len(items))):
                bbox = tree.bbox(items[top])
                if bbox:
                    break
        if bbox:
            header_h, row_h = bbox[1], bbox[3]
            last_bbox = tree.bbox(items[-1])
            bottom = (last_bbox[1] + last_bbox[3]) if last_bbox else height
            total = self._columns_width()
            x_off = int(tree.xview()[0] * total)
            line_w = min(width, max(total - x_off, 0))
            # Gray row-number cells.
            num_w = tree.column(ROWNUM, "width")
            selected = set(tree.selection())
            y, idx = header_h, top
            while y < min(bottom, height) and idx < len(items):
                lb = self._rownum_label(nl)
                lb.configure(text=str(idx + 1),
                             bg=HEADER_SELECTED_BG if items[idx] in selected else HEADER_BG)
                lb.place(x=-x_off, y=y, width=max(num_w - 1, 0), height=row_h - 1)
                nl += 1
                idx += 1
                y += row_h
            # Horizontal line under each visible row.
            y = header_h + row_h - 1
            while y < bottom:
                self._line(n).place(x=0, y=y, width=line_w, height=1)
                n += 1
                y += row_h
            # Vertical line at each column boundary.
            x = -x_off
            for col in tree["columns"]:
                x += tree.column(col, "width")
                if 0 <= x - 1 < width:
                    self._line(n).place(x=x - 1, y=header_h, width=1,
                                        height=max(bottom - header_h, 0))
                    n += 1
        for ln in self._lines[n:]:
            ln.place_forget()
        for lb in self._rownum_labels[nl:]:
            lb.place_forget()
        self._draw_cursor()
        if self.editor is not None:
            self.editor.lift()

    def _draw_cursor(self):
        """2px outline around the current cell."""
        cell = self.current_cell
        bbox = self.tree.bbox(str(cell[0]), f"#{cell[1] + 2}") if cell else None
        if not bbox:
            for f in self._cursor:
                f.place_forget()
            return
        x, y, w, h = bbox
        x -= 1  # cover the grid line on the left so the outline is symmetric
        w += 1
        t = 2
        for f, (fx, fy, fw, fh) in zip(self._cursor, (
                (x, y - 1, w, t), (x, y + h - t, w, t),
                (x, y - 1, t, h + 1), (x + w - t, y - 1, t, h + 1))):
            f.place(x=fx, y=fy, width=fw, height=fh)
            f.lift()

    @property
    def current_row(self):
        """Row with keyboard focus if it is selected, else the first selected row."""
        sel = self.tree.selection()
        if not sel:
            return None
        focus = self.tree.focus()
        return int(focus) if focus in sel else int(sel[0])

    @property
    def current_cell(self):
        r = self.current_row
        if r is None or not (0 <= self.current_col < self.model.column_count) \
                or r >= self.model.row_count:
            return None
        return r, self.current_col

    def _move_col(self, step):
        if self.model.column_count:
            self.current_col = max(0, min(self.current_col + step, self.model.column_count - 1))
            self._scroll_to_col(self.current_col)
            self._schedule_gridlines()
        return "break"

    def _scroll_to_col(self, col):
        """Scroll horizontally so column col is visible."""
        widths = [self.tree.column(c, "width") for c in self.tree["columns"]]
        total = sum(widths) or 1
        left = sum(widths[:col + 1])
        right = left + widths[col + 1]
        lo, hi = self.tree.xview()
        view_l, view_r = lo * total, hi * total
        if left < view_l:
            self.tree.xview_moveto(left / total)
        elif right > view_r:
            self.tree.xview_moveto((right - (view_r - view_l)) / total)

    # ---------- refresh ----------
    def refresh(self, keep_selection=True):
        self.cancel_edit()
        sel = [int(i) for i in self.tree.selection()] if keep_selection else []
        yview = self.tree.yview()[0]
        n = self.model.column_count
        if n:
            self.current_col = max(0, min(self.current_col, n - 1))
        self.tree.configure(columns=[ROWNUM] + [f"c{i}" for i in range(n)])
        self.tree.heading(ROWNUM, text="#")
        self.tree.column(ROWNUM, width=50, minwidth=40, stretch=False, anchor="center")
        for i in range(n):
            self.tree.heading(f"c{i}", text=self.model.headers[i])
            self.tree.column(f"c{i}", width=120, minwidth=50, stretch=False)
        self.tree.delete(*self.tree.get_children())
        for r, row in enumerate(self.model.rows):
            self.tree.insert("", "end", iid=str(r), values=[r + 1] + list(row))
        valid = [str(i) for i in sel if i < self.model.row_count]
        if valid:
            self.tree.selection_set(valid)
        self.tree.yview_moveto(yview)
        self._changed()

    # ---------- cell helpers ----------
    def _col_index(self, x):
        """Model column index under x; -1 for the row-number column."""
        col = self.tree.identify_column(x)
        return int(col[1:]) - 2 if col else -2

    def on_click(self, event):
        self.commit_edit()
        if self.tree.identify_region(event.x, event.y) in ("cell", "heading"):
            ci = self._col_index(event.x)
            if ci >= 0:
                self.current_col = ci
                self._schedule_gridlines()

    def on_right_click(self, event):
        self.commit_edit()
        row = self.tree.identify_row(event.y)
        if row and row not in self.tree.selection():
            self.tree.selection_set(row)
        if self.tree.identify_region(event.x, event.y) in ("cell", "heading"):
            ci = self._col_index(event.x)
            if ci >= 0:
                self.current_col = ci
        if row:
            self.tree.focus(row)
        self._schedule_gridlines()
        self.app.context.tk_popup(event.x_root, event.y_root)

    def on_double_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        ci = self._col_index(event.x)
        if region == "heading":
            if ci >= 0:
                self.current_col = ci
                self.rename_column()
            return "break"
        if region == "cell":
            row = self.tree.identify_row(event.y)
            if row and ci >= 0:
                self.start_edit(int(row), ci)
            return "break"

    # ---------- in-place editing ----------
    def start_edit_current(self):
        cell = self.current_cell
        if cell:
            self.start_edit(*cell)
        return "break"

    def start_edit(self, row, col):
        self.commit_edit()
        if not (0 <= row < self.model.row_count and 0 <= col < self.model.column_count):
            return
        self.tree.see(str(row))
        self.tree.update_idletasks()
        bbox = self.tree.bbox(str(row), f"#{col + 2}")
        if not bbox:
            return
        x, y, w, h = bbox
        self.current_col = col
        self.tree.selection_set(str(row))
        self.tree.focus(str(row))
        self.edit_pos = (row, col)
        self.editor = ttk.Entry(self.tree)
        self.editor.insert(0, self.model.get_cell(row, col))
        self.editor.select_range(0, "end")
        self.editor.place(x=x, y=y, width=w, height=h)
        self.editor.focus_set()
        self.editor.bind("<Return>", lambda e: self._finish(False))
        self.editor.bind("<Escape>", lambda e: self._finish(True))
        self.editor.bind("<Tab>", lambda e: self._tab())
        self.editor.bind("<FocusOut>", lambda e: self.commit_edit())

    def commit_edit(self):
        if self.editor is None:
            return
        ed, (r, c) = self.editor, self.edit_pos
        self.editor = None
        value = ed.get()
        ed.destroy()
        if r < self.model.row_count and c < self.model.column_count \
                and value != self.model.get_cell(r, c):
            self.model.set_cell(r, c, value)
            self.tree.set(str(r), f"c{c}", value)
            self._changed()

    def cancel_edit(self):
        if self.editor is not None:
            ed, self.editor = self.editor, None
            ed.destroy()

    def _finish(self, cancel):
        if cancel:
            self.cancel_edit()
        else:
            self.commit_edit()
        self.tree.focus_set()
        return "break"

    def _tab(self):
        r, c = self.edit_pos
        self.commit_edit()
        c += 1
        if c >= self.model.column_count:
            c = 0
            r += 1
        if r >= self.model.row_count:
            r = 0
        self.start_edit(r, c)
        return "break"

    # ---------- row / column actions ----------
    def _selected_rows(self):
        return sorted(int(i) for i in self.tree.selection())

    def _select(self, r, count=1):
        rows = [str(i) for i in range(r, r + count) if 0 <= i < self.model.row_count]
        if rows:
            self.tree.selection_set(rows)
            self.tree.focus(rows[0])
            self.tree.see(rows[0])

    # ---------- cut / copy / paste ----------
    def copy_cell(self, cut=False):
        self.commit_edit()
        cell = self.current_cell
        if not cell:
            return
        value = self.model.get_cell(*cell)
        self.app.set_clipboard("cell", value, value)
        if cut and value:
            self.model.set_cell(*cell, "")
            self.tree.set(str(cell[0]), f"c{cell[1]}", "")
            self._changed()

    def copy_rows(self, cut=False):
        self.commit_edit()
        sel = self._selected_rows()
        if not sel:
            return
        rows = [list(self.model.rows[i]) for i in sel]
        self.app.set_clipboard("rows", rows, "\n".join("\t".join(r) for r in rows))
        if cut:
            self.delete_rows()

    def copy_column(self, cut=False):
        self.commit_edit()
        c = self.current_col
        if not (0 <= c < self.model.column_count):
            return
        col = {"name": self.model.headers[c], "values": [r[c] for r in self.model.rows]}
        self.app.set_clipboard("column", col, "\n".join([col["name"]] + col["values"]))
        if cut:
            self.delete_column()

    def paste(self):
        """Paste whatever was cut/copied last: a cell value into the current
        cell, rows above the selected rows, a column left of the current one."""
        self.commit_edit()
        kind, data = self.app.get_clipboard()
        m = self.model
        if kind in ("cell", "text"):
            cell = self.current_cell
            if cell:
                m.set_cell(*cell, data)
                self.tree.set(str(cell[0]), f"c{cell[1]}", data)
                self._changed()
        elif kind == "rows":
            sel = self._selected_rows()
            idx = sel[0] if sel else m.row_count
            while m.column_count < max(len(r) for r in data):
                m.insert_column()
            for k, row in enumerate(data):
                m.insert_row(idx + k)
                for c, v in enumerate(row):
                    m.set_cell(idx + k, c, v)
            self.refresh(False)
            self._select(idx, len(data))
        elif kind == "column":
            idx = min(self.current_col, m.column_count) if m.column_count else 0
            while m.row_count < len(data["values"]):
                m.insert_row()
            m.insert_column(data["name"], idx)
            for r, v in enumerate(data["values"]):
                m.set_cell(r, idx, v)
            self.current_col = idx
            self.refresh()

    def insert_row(self, below):
        self.commit_edit()
        sel = self._selected_rows()
        idx = (sel[-1] + 1 if below else sel[0]) if sel else None
        new = self.model.insert_row(idx)
        self.refresh(False)
        self._select(new)

    def append_row(self):
        self.commit_edit()
        new = self.model.insert_row(None)
        self.refresh(False)
        self._select(new)

    def delete_rows(self):
        self.commit_edit()
        sel = self._selected_rows()
        if not sel:
            return
        self.model.delete_rows(sel)
        self.refresh(False)
        self._select(min(sel[0], self.model.row_count - 1))

    def insert_column(self, right):
        self.commit_edit()
        idx = 0 if self.model.column_count == 0 else \
            (self.current_col + 1 if right else self.current_col)
        self.current_col = self.model.insert_column(None, idx)
        self.refresh()

    def append_column(self):
        self.commit_edit()
        self.current_col = self.model.insert_column(None, None)
        self.refresh()

    def delete_column(self):
        self.commit_edit()
        if self.model.column_count == 0:
            return
        self.model.delete_columns([self.current_col])
        self.refresh()

    def rename_column(self):
        self.commit_edit()
        c = self.current_col
        if not (0 <= c < self.model.column_count):
            return
        name = simpledialog.askstring("Rename Column", "New column name:",
                                      initialvalue=self.model.headers[c], parent=self)
        if name is not None:
            self.model.rename_column(c, name)
            self.refresh()

    # ---------- file operations ----------
    def load(self, path):
        self.model.load(path)
        self.current_col = 0
        self.refresh(False)

    def new(self):
        self.model.new()
        self.current_col = 0
        self.refresh(False)

    def save(self):
        self.commit_edit()
        if not self.model.path:
            return self.save_as()
        try:
            self.model.save()
        except Exception as e:
            messagebox.showerror("Save failed", str(e), parent=self)
            return False
        self._changed()
        return True

    def save_as(self):
        self.commit_edit()
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".csv", filetypes=FILETYPES,
            initialfile=self.display_name if self.model.path else "")
        if not path:
            return False
        try:
            self.model.save(path)
        except Exception as e:
            messagebox.showerror("Save failed", str(e), parent=self)
            return False
        self._changed()
        return True

    def confirm_discard(self):
        """Return True if it is OK to drop this tab's contents."""
        self.commit_edit()
        if not self.model.dirty:
            return True
        ans = messagebox.askyesnocancel(
            "Unsaved changes", f"Save changes to {self.display_name}?", parent=self)
        if ans is None:
            return False
        return self.save() if ans else True

    @property
    def is_pristine(self):
        """An untouched, never-saved tab that Open may reuse."""
        return self.model.path is None and not self.model.dirty


class CsvEditorApp:
    def __init__(self, root, paths=()):
        self.root = root
        setup_style(root)
        self._build_menu()
        self._build_toolbar()
        self._build_status()
        self._build_notebook()
        self._bind_keys()

        root.protocol("WM_DELETE_WINDOW", self.exit_app)
        root.geometry("900x550")

        if isinstance(paths, str):
            paths = [paths]
        for p in paths:
            self.open_path(p)
        if not self.tabs:
            self.new_tab()

    # ---------- tabs ----------
    @property
    def tabs(self):
        return [self.root.nametowidget(t) for t in self.notebook.tabs()]

    @property
    def current(self):
        sel = self.notebook.select()
        return self.root.nametowidget(sel) if sel else None

    @property
    def model(self):
        return self.current.model

    def _add_tab(self):
        used = {t.untitled_name for t in self.tabs if t.model.path is None}
        n = 1
        while f"Untitled {n}" in used:
            n += 1
        tab = SheetTab(self, self.notebook, f"Untitled {n}")
        self.notebook.add(tab, text=tab.untitled_name)
        self.notebook.select(tab)
        return tab

    def new_tab(self):
        tab = self._add_tab()
        tab.new()
        return tab

    def open_path(self, path):
        """Open path in a tab: switch to it if already open, reuse a pristine
        current tab, otherwise create a new one."""
        full = os.path.abspath(path)
        for tab in self.tabs:
            if tab.model.path and os.path.abspath(tab.model.path) == full:
                self.notebook.select(tab)
                return tab
        cur = self.current
        reuse = cur is not None and cur.is_pristine
        tab = cur if reuse else self._add_tab()
        try:
            tab.load(path)
        except Exception as e:
            messagebox.showerror("Open failed", f"{path}\n\n{e}", parent=self.root)
            if not reuse:
                self.notebook.forget(tab)
                tab.destroy()
                self.on_tab_switched()
            return None
        return tab

    def close_tab(self, tab=None):
        tab = tab or self.current
        if tab is None:
            return False
        self.notebook.select(tab)
        if not tab.confirm_discard():
            return False
        self.notebook.forget(tab)
        tab.destroy()
        if not self.tabs:
            self.new_tab()
        self.on_tab_switched()
        return True

    def on_tab_changed(self, tab):
        """Called by a tab whenever its name, size, or dirty state may change."""
        m = tab.model
        self.notebook.tab(tab, text=f"{tab.display_name}{' *' if m.dirty else ''}")
        if tab is self.current:
            self.update_status()

    def on_tab_switched(self, event=None):
        if self.current is not None:
            self.current.commit_edit()
            self.update_status()

    def update_status(self):
        tab = self.current
        if tab is None:
            return
        m = tab.model
        where = m.path or tab.display_name
        self.status.set(f"{where}  |  {m.row_count} rows × {m.column_count} cols"
                        f"  |  {'modified' if m.dirty else 'saved'}"
                        f"  |  tab {self.tabs.index(tab) + 1} of {len(self.tabs)}")
        self.root.title(f"CSV Editor - {tab.display_name}{'*' if m.dirty else ''}")

    # ---------- UI construction ----------
    def _build_menu(self):
        m = tk.Menu(self.root)
        f = tk.Menu(m, tearoff=0)
        f.add_command(label="New Tab", accelerator="Ctrl+N", command=self.new_tab)
        f.add_command(label="Open...", accelerator="Ctrl+O", command=self.open_file)
        f.add_command(label="Save", accelerator="Ctrl+S", command=self.save)
        f.add_command(label="Save As...", accelerator="Ctrl+Shift+S", command=self.save_as)
        f.add_command(label="Save All", command=self.save_all)
        f.add_separator()
        f.add_command(label="Close Tab", accelerator="Ctrl+W", command=self.close_tab)
        f.add_separator()
        f.add_command(label="Exit", command=self.exit_app)
        m.add_cascade(label="File", menu=f)

        e = tk.Menu(m, tearoff=0)
        self._fill_edit_menu(e, shortcuts=True)
        m.add_cascade(label="Edit", menu=e)
        self.root.config(menu=m)

        self.context = tk.Menu(self.root, tearoff=0)
        self._fill_edit_menu(self.context, shortcuts=False)

        self.tab_menu = tk.Menu(self.root, tearoff=0)
        self.tab_menu.add_command(label="Close Tab", command=lambda: self.close_tab(self._menu_tab))
        self.tab_menu.add_command(label="Close Other Tabs", command=self.close_other_tabs)
        self._menu_tab = None

    def _act(self, method, *args):
        """Build a command that calls a SheetTab method on the current tab."""
        return lambda: getattr(self.current, method)(*args) if self.current else None

    def _fill_edit_menu(self, menu, shortcuts):
        key = (lambda k: k) if shortcuts else (lambda k: None)
        menu.add_command(label="Cut Cell", accelerator=key("Ctrl+X"),
                         command=self._act("copy_cell", True))
        menu.add_command(label="Copy Cell", accelerator=key("Ctrl+C"),
                         command=self._act("copy_cell"))
        menu.add_command(label="Paste", accelerator=key("Ctrl+V"), command=self._act("paste"))
        menu.add_separator()
        menu.add_command(label="Cut Rows", command=self._act("copy_rows", True))
        menu.add_command(label="Copy Rows", command=self._act("copy_rows"))
        menu.add_command(label="Insert Row Above", command=self._act("insert_row", False))
        menu.add_command(label="Insert Row Below", command=self._act("insert_row", True))
        menu.add_command(label="Append Row", command=self._act("append_row"))
        menu.add_command(label="Delete Selected Rows",
                         accelerator="Delete" if shortcuts else None,
                         command=self._act("delete_rows"))
        menu.add_separator()
        menu.add_command(label="Cut Column", command=self._act("copy_column", True))
        menu.add_command(label="Copy Column", command=self._act("copy_column"))
        menu.add_command(label="Insert Column Left", command=self._act("insert_column", False))
        menu.add_command(label="Insert Column Right", command=self._act("insert_column", True))
        menu.add_command(label="Append Column", command=self._act("append_column"))
        menu.add_command(label="Delete Current Column", command=self._act("delete_column"))
        menu.add_command(label="Rename Current Column", command=self._act("rename_column"))

    def _build_toolbar(self):
        bar = ttk.Frame(self.root)
        bar.pack(side="top", fill="x")
        for text, cmd in (("New", self.new_tab), ("Open", self.open_file),
                          ("Save", self.save), ("Close", self.close_tab),
                          ("+Row", self._act("append_row")), ("−Row", self._act("delete_rows")),
                          ("+Col", self._act("append_column")), ("−Col", self._act("delete_column"))):
            ttk.Button(bar, text=text, width=7, command=cmd).pack(side="left", padx=2, pady=2)

    def _build_status(self):
        self.status = tk.StringVar()
        ttk.Label(self.root, textvariable=self.status, relief="sunken",
                  anchor="w").pack(side="bottom", fill="x")

    def _build_notebook(self):
        self.notebook = ttk.Notebook(self.root, style="Sheets.TNotebook")
        self.notebook.pack(side="top", fill="both", expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_switched)
        self.notebook.bind("<Button-2>", self._on_tab_middle_click)
        self.notebook.bind("<Button-3>", self._on_tab_right_click)
        # Drag tabs to reorder them.
        self._drag_tab = None
        self._drag_x = 0
        self.notebook.bind("<ButtonPress-1>", self._on_tab_press, add="+")
        self.notebook.bind("<B1-Motion>", self._on_tab_drag, add="+")
        self.notebook.bind("<ButtonRelease-1>", self._on_tab_release, add="+")

    def _on_tab_press(self, event):
        self._drag_tab = self._tab_at(event)
        self._drag_x = event.x

    def _on_tab_drag(self, event):
        tab = self._drag_tab
        if tab is None:
            return
        self.notebook.configure(cursor="sb_h_double_arrow")
        target = self._tab_at(event)
        if target is None or target is tab:
            return
        src, dst = self.tabs.index(tab), self.tabs.index(target)
        moving_right = event.x > self._drag_x
        self._drag_x = event.x
        # Only move in the direction of travel, so swapping with a wider tab
        # (which ends up under the pointer) doesn't bounce back and forth.
        if (dst > src) == moving_right:
            self.notebook.insert(dst, tab)
            self.update_status()

    def _on_tab_release(self, event):
        if self._drag_tab is not None:
            self._drag_tab = None
            self.notebook.configure(cursor="")

    def _tab_at(self, event):
        try:
            idx = self.notebook.index(f"@{event.x},{event.y}")
        except tk.TclError:
            return None
        return self.tabs[idx] if self.notebook.identify(event.x, event.y) else None

    def _on_tab_middle_click(self, event):
        tab = self._tab_at(event)
        if tab is not None:
            self.close_tab(tab)

    def _on_tab_right_click(self, event):
        tab = self._tab_at(event)
        if tab is not None:
            self._menu_tab = tab
            self.tab_menu.tk_popup(event.x_root, event.y_root)

    def _bind_keys(self):
        r = self.root
        r.bind("<Control-n>", lambda e: self.new_tab())
        r.bind("<Control-o>", lambda e: self.open_file())
        r.bind("<Control-s>", lambda e: self.save())
        r.bind("<Control-S>", lambda e: self.save_as())
        r.bind("<Control-w>", lambda e: self.close_tab())
        # Cell clipboard; text fields (the cell editor) keep their own Ctrl+X/C/V.
        for k, method, args in (("x", "copy_cell", (True,)), ("c", "copy_cell", ()),
                                ("v", "paste", ())):
            r.bind(f"<Control-{k}>",
                   lambda e, m=method, a=args: None if isinstance(e.widget, tk.Entry | ttk.Entry)
                   else self._act(m, *a)())
        r.bind("<Control-Tab>", lambda e: self._cycle(1))
        r.bind("<Control-Shift-Tab>", lambda e: self._cycle(-1))
        # Some Tk builds report Ctrl+Shift+Tab as ISO_Left_Tab.
        try:
            r.bind("<Control-ISO_Left_Tab>", lambda e: self._cycle(-1))
        except tk.TclError:
            pass

    def _cycle(self, step):
        tabs = self.tabs
        if len(tabs) > 1:
            i = tabs.index(self.current)
            self.notebook.select(tabs[(i + step) % len(tabs)])
        return "break"

    # ---------- clipboard (shared by all tabs) ----------
    _clip = (None, None, None)  # (kind, data, text placed on the system clipboard)

    def set_clipboard(self, kind, data, text):
        self._clip = (kind, data, text)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def get_clipboard(self):
        """Return (kind, data). If the system clipboard was changed by another
        program since our last cut/copy, its text is pasted as a cell value."""
        kind, data, text = self._clip
        try:
            system = self.root.clipboard_get()
        except tk.TclError:
            system = None
        if system is not None and system.replace("\r\n", "\n") != (text or "").replace("\r\n", "\n"):
            return "text", system.rstrip("\r\n")
        return kind, data

    # ---------- file operations ----------
    def open_file(self):
        paths = filedialog.askopenfilenames(parent=self.root, filetypes=FILETYPES)
        for p in paths:
            self.open_path(p)

    def save(self):
        return self.current.save() if self.current else False

    def save_as(self):
        return self.current.save_as() if self.current else False

    def save_all(self):
        for tab in self.tabs:
            if tab.model.dirty:
                self.notebook.select(tab)
                if not tab.save():
                    return False
        return True

    def close_other_tabs(self):
        keep = self._menu_tab or self.current
        for tab in self.tabs:
            if tab is not keep and not self.close_tab(tab):
                return
        self.notebook.select(keep)

    def exit_app(self):
        for tab in self.tabs:
            if tab.model.dirty:
                self.notebook.select(tab)
                if not tab.confirm_discard():
                    return
        self.root.destroy()


def main():
    root = tk.Tk()
    CsvEditorApp(root, sys.argv[1:])
    root.mainloop()


if __name__ == "__main__":
    main()
