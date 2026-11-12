"""Tkinter mini-spreadsheet CSV editor."""
import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from csv_model import CsvModel

ROWNUM = "#"


class CsvEditorApp:
    def __init__(self, root, path=None):
        self.root = root
        self.model = CsvModel()
        self.current_col = 0
        self.editor = None
        self.edit_pos = None  # (row, col)

        self._build_menu()
        self._build_toolbar()
        self._build_grid()
        self._build_status()
        self._bind_keys()

        root.protocol("WM_DELETE_WINDOW", self.exit_app)
        root.geometry("800x500")

        if path:
            try:
                self.model.load(path)
            except Exception as e:
                messagebox.showerror("Open failed", str(e))
                self.model.new()
        else:
            self.model.new()
        self.refresh()

    # ---------- UI construction ----------
    def _build_menu(self):
        m = tk.Menu(self.root)
        f = tk.Menu(m, tearoff=0)
        f.add_command(label="New", command=self.new_file)
        f.add_command(label="Open...", accelerator="Ctrl+O", command=self.open_file)
        f.add_command(label="Save", accelerator="Ctrl+S", command=self.save)
        f.add_command(label="Save As...", accelerator="Ctrl+Shift+S", command=self.save_as)
        f.add_separator()
        f.add_command(label="Exit", command=self.exit_app)
        m.add_cascade(label="File", menu=f)

        e = tk.Menu(m, tearoff=0)
        self._fill_edit_menu(e, shortcuts=True)
        m.add_cascade(label="Edit", menu=e)
        self.root.config(menu=m)

        self.context = tk.Menu(self.root, tearoff=0)
        self._fill_edit_menu(self.context, shortcuts=False)

    def _fill_edit_menu(self, menu, shortcuts):
        menu.add_command(label="Insert Row Above", command=lambda: self.insert_row(False))
        menu.add_command(label="Insert Row Below", command=lambda: self.insert_row(True))
        menu.add_command(label="Append Row", command=self.append_row)
        menu.add_command(label="Delete Selected Rows",
                         accelerator="Delete" if shortcuts else None,
                         command=self.delete_rows)
        menu.add_separator()
        menu.add_command(label="Insert Column Left", command=lambda: self.insert_column(False))
        menu.add_command(label="Insert Column Right", command=lambda: self.insert_column(True))
        menu.add_command(label="Append Column", command=self.append_column)
        menu.add_command(label="Delete Current Column", command=self.delete_column)
        menu.add_command(label="Rename Current Column", command=self.rename_column)

    def _build_toolbar(self):
        bar = ttk.Frame(self.root)
        bar.pack(side="top", fill="x")
        for text, cmd in (("Open", self.open_file), ("Save", self.save),
                          ("+Row", self.append_row), ("−Row", self.delete_rows),
                          ("+Col", self.append_column), ("−Col", self.delete_column)):
            ttk.Button(bar, text=text, width=7, command=cmd).pack(side="left", padx=2, pady=2)

    def _build_grid(self):
        frame = ttk.Frame(self.root)
        frame.pack(side="top", fill="both", expand=True)
        self.tree = ttk.Treeview(frame, show="headings", selectmode="extended")
        vs = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        hs = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.tree.bind("<Button-1>", self.on_click, add="+")
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Button-3>", self.on_right_click)
        self.tree.bind("<Return>", lambda e: self.start_edit_current())
        self.tree.bind("<F2>", lambda e: self.start_edit_current())
        self.tree.bind("<Delete>", lambda e: self.delete_rows())

    def _build_status(self):
        self.status = tk.StringVar()
        ttk.Label(self.root, textvariable=self.status, relief="sunken",
                  anchor="w").pack(side="bottom", fill="x")

    def _bind_keys(self):
        r = self.root
        r.bind("<Control-o>", lambda e: self.open_file())
        r.bind("<Control-s>", lambda e: self.save())
        r.bind("<Control-S>", lambda e: self.save_as())
        r.bind("<Control-Shift-s>", lambda e: self.save_as())

    # ---------- refresh ----------
    def refresh(self, keep_selection=True):
        self.cancel_edit()
        sel = [int(i) for i in self.tree.selection()] if keep_selection else []
        yview = self.tree.yview()[0]
        n = self.model.column_count
        if n:
            self.current_col = max(0, min(self.current_col, n - 1))
        cols = [ROWNUM] + [f"c{i}" for i in range(n)]
        self.tree.configure(columns=cols)
        self.tree.heading(ROWNUM, text="#")
        self.tree.column(ROWNUM, width=50, minwidth=40, stretch=False, anchor="e")
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
        self.update_status()

    def update_status(self):
        m = self.model
        name = os.path.basename(m.path) if m.path else "Untitled"
        self.status.set(f"{name}  |  {m.row_count} rows × {m.column_count} cols"
                        f"  |  {'modified' if m.dirty else 'saved'}")
        self.root.title(f"CSV Editor - {name}{'*' if m.dirty else ''}")

    # ---------- cell helpers ----------
    def _cell_at(self, event):
        row = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not row or not col:
            return None, None
        ci = int(col[1:]) - 1  # 0 is rownum
        return int(row), ci - 1  # model column index; -1 for rownum

    def on_click(self, event):
        self.commit_edit()
        region = self.tree.identify_region(event.x, event.y)
        if region in ("cell", "heading"):
            ci = int(self.tree.identify_column(event.x)[1:]) - 2
            if ci >= 0:
                self.current_col = ci

    def on_right_click(self, event):
        self.commit_edit()
        row = self.tree.identify_row(event.y)
        if row and row not in self.tree.selection():
            self.tree.selection_set(row)
        _, c = self._cell_at(event)
        if c is not None and c >= 0:
            self.current_col = c
        elif self.tree.identify_region(event.x, event.y) == "heading":
            ci = int(self.tree.identify_column(event.x)[1:]) - 2
            if ci >= 0:
                self.current_col = ci
        self.context.tk_popup(event.x_root, event.y_root)

    def on_double_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "heading":
            ci = int(self.tree.identify_column(event.x)[1:]) - 2
            if ci >= 0:
                self.current_col = ci
                self.rename_column()
            return "break"
        if region == "cell":
            r, c = self._cell_at(event)
            if r is not None and c >= 0:
                self.start_edit(r, c)
            return "break"

    # ---------- in-place editing ----------
    def start_edit_current(self):
        sel = self.tree.selection()
        if sel and self.model.column_count:
            self.start_edit(int(sel[0]), self.current_col)
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
            self.update_status()

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

    # ---------- actions ----------
    def _selected_rows(self):
        return sorted(int(i) for i in self.tree.selection())

    def _select(self, r):
        if 0 <= r < self.model.row_count:
            self.tree.selection_set(str(r))
            self.tree.see(str(r))

    def insert_row(self, below):
        self.commit_edit()
        sel = self._selected_rows()
        if sel:
            idx = sel[-1] + 1 if below else sel[0]
        else:
            idx = None
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
        idx = self.current_col + 1 if right else self.current_col
        if self.model.column_count == 0:
            idx = 0
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
                                      initialvalue=self.model.headers[c], parent=self.root)
        if name is not None:
            self.model.rename_column(c, name)
            self.refresh()

    # ---------- file operations ----------
    def confirm_discard(self):
        """Return True if it is OK to proceed (saved or discarded)."""
        self.commit_edit()
        if not self.model.dirty:
            return True
        ans = messagebox.askyesnocancel("Unsaved changes",
                                        "Save changes before continuing?", parent=self.root)
        if ans is None:
            return False
        if ans:
            return self.save()
        return True

    def new_file(self):
        if self.confirm_discard():
            self.model.new()
            self.current_col = 0
            self.refresh(False)

    def open_file(self):
        if not self.confirm_discard():
            return
        path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            self.model.load(path)
        except Exception as e:
            messagebox.showerror("Open failed", str(e))
            return
        self.current_col = 0
        self.refresh(False)

    def save(self):
        self.commit_edit()
        if not self.model.path:
            return self.save_as()
        try:
            self.model.save()
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return False
        self.update_status()
        return True

    def save_as(self):
        self.commit_edit()
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return False
        try:
            self.model.save(path)
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return False
        self.update_status()
        return True

    def exit_app(self):
        if self.confirm_discard():
            self.root.destroy()


def main():
    root = tk.Tk()
    path = sys.argv[1] if len(sys.argv) > 1 else None
    CsvEditorApp(root, path)
    root.mainloop()


if __name__ == "__main__":
    main()
