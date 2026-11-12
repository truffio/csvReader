import os
import tempfile
import unittest

from csv_model import CsvModel


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def p(self, name="f.csv"):
        return os.path.join(self.tmp.name, name)

    def write(self, content, name="f.csv", encoding="utf-8"):
        path = self.p(name)
        with open(path, "w", encoding=encoding, newline="") as f:
            f.write(content)
        return path

    def sample(self):
        m = CsvModel()
        m.headers = ["a", "b", "c"]
        m.rows = [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"]]
        return m


class TestInitNew(Base):
    def test_init(self):
        m = CsvModel()
        self.assertEqual((m.headers, m.rows, m.path, m.dirty, m.delimiter),
                         ([], [], None, False, ","))

    def test_new_defaults(self):
        m = CsvModel()
        m.new()
        self.assertEqual(m.headers, ["Column 1", "Column 2", "Column 3"])
        self.assertEqual(m.row_count, 5)
        self.assertEqual(m.column_count, 3)
        self.assertTrue(all(c == "" for r in m.rows for c in r))
        self.assertFalse(m.dirty)

    def test_new_custom_resets(self):
        m = self.sample()
        m.path = "x"
        m.dirty = True
        m.new(2, 1)
        self.assertEqual(m.headers, ["Column 1", "Column 2"])
        self.assertEqual(m.rows, [["", ""]])
        self.assertIsNone(m.path)
        self.assertFalse(m.dirty)


class TestLoadSave(Base):
    def test_roundtrip_special(self):
        m = CsvModel()
        m.headers = ["name", "note"]
        m.rows = [["a,b", 'say "hi"'], ["line1\nline2", "café 中文 \U0001F600"], ["", "x"]]
        m.save(self.p())
        m2 = CsvModel()
        m2.load(self.p())
        self.assertEqual(m2.headers, m.headers)
        self.assertEqual(m2.rows, m.rows)
        self.assertEqual(m2.path, self.p())
        self.assertFalse(m2.dirty)

    def test_load_basic_and_bom(self):
        path = self.write("﻿x,y\n1,2\n3,4\n")
        m = CsvModel()
        m.load(path)
        self.assertEqual(m.headers, ["x", "y"])
        self.assertEqual(m.rows, [["1", "2"], ["3", "4"]])

    def test_semicolon_sniff_and_save(self):
        path = self.write("a;b;c\n1;2;3\n4;5;6\n")
        m = CsvModel()
        m.load(path)
        self.assertEqual(m.delimiter, ";")
        self.assertEqual(m.headers, ["a", "b", "c"])
        self.assertEqual(m.rows[1], ["4", "5", "6"])
        m.save(self.p("out.csv"))
        with open(self.p("out.csv"), encoding="utf-8", newline="") as f:
            self.assertIn("a;b;c", f.read())

    def test_empty_file(self):
        m = CsvModel()
        m.new()
        m.load(self.write(""))
        self.assertEqual(m.headers, [])
        self.assertEqual(m.rows, [])
        self.assertFalse(m.dirty)

    def test_headers_only(self):
        m = CsvModel()
        m.load(self.write("a,b\n"))
        self.assertEqual(m.headers, ["a", "b"])
        self.assertEqual(m.rows, [])

    def test_ragged_short_rows_padded(self):
        m = CsvModel()
        m.load(self.write("a,b,c\n1\n1,2,3\n"))
        self.assertEqual(m.rows, [["1", "", ""], ["1", "2", "3"]])

    def test_ragged_long_rows_extend_headers(self):
        m = CsvModel()
        m.load(self.write("a,b\n1,2,3,4\n5\n"))
        self.assertEqual(m.headers, ["a", "b", "Column 3", "Column 4"])
        self.assertEqual(m.rows, [["1", "2", "3", "4"], ["5", "", "", ""]])
        for r in m.rows:
            self.assertEqual(len(r), len(m.headers))

    def test_save_without_path_raises(self):
        with self.assertRaises(ValueError):
            CsvModel().save()

    def test_save_uses_current_path_and_clears_dirty(self):
        m = self.sample()
        m.save(self.p())
        m.set_cell(0, 0, "changed")
        self.assertTrue(m.dirty)
        m.save()
        self.assertFalse(m.dirty)
        m2 = CsvModel()
        m2.load(self.p())
        self.assertEqual(m2.rows[0][0], "changed")

    def test_save_as_updates_path(self):
        m = self.sample()
        m.save(self.p("one.csv"))
        m.save(self.p("two.csv"))
        self.assertEqual(m.path, self.p("two.csv"))


class TestMutations(Base):
    def test_get_set_cell(self):
        m = self.sample()
        self.assertEqual(m.get_cell(1, 2), "6")
        m.set_cell(1, 2, "z")
        self.assertEqual(m.get_cell(1, 2), "z")
        self.assertTrue(m.dirty)

    def test_set_cell_same_value_not_dirty(self):
        m = self.sample()
        m.set_cell(0, 0, "1")
        self.assertFalse(m.dirty)

    def test_cell_index_errors(self):
        m = self.sample()
        for r, c in [(3, 0), (0, 3), (-1, 0), (0, -1)]:
            with self.assertRaises(IndexError):
                m.get_cell(r, c)
            with self.assertRaises(IndexError):
                m.set_cell(r, c, "x")

    def test_insert_row(self):
        m = self.sample()
        self.assertEqual(m.insert_row(), 3)
        self.assertEqual(m.insert_row(0), 0)
        self.assertEqual(m.row_count, 5)
        self.assertEqual(m.rows[0], ["", "", ""])
        self.assertEqual(m.rows[1], ["1", "2", "3"])
        self.assertTrue(m.dirty)
        with self.assertRaises(IndexError):
            m.insert_row(10)

    def test_delete_rows(self):
        m = self.sample()
        m.delete_rows([0, 2, 0])
        self.assertEqual(m.rows, [["4", "5", "6"]])
        self.assertTrue(m.dirty)

    def test_delete_rows_out_of_range(self):
        m = self.sample()
        with self.assertRaises(IndexError):
            m.delete_rows([0, 5])
        self.assertEqual(m.row_count, 3)
        self.assertFalse(m.dirty)

    def test_insert_column(self):
        m = self.sample()
        self.assertEqual(m.insert_column(), 3)
        self.assertEqual(m.headers, ["a", "b", "c", "Column 4"])
        self.assertEqual(m.insert_column("new", 0), 0)
        self.assertEqual(m.headers[0], "new")
        self.assertTrue(all(len(r) == 5 for r in m.rows))
        self.assertEqual(m.rows[0], ["", "1", "2", "3", ""])
        with self.assertRaises(IndexError):
            m.insert_column("x", 99)

    def test_insert_column_unique_name(self):
        m = CsvModel()
        m.headers = ["Column 2", "b"]
        m.rows = [["", ""]]
        m.insert_column()
        self.assertEqual(len(set(m.headers)), 3)
        self.assertEqual(m.headers[2], "Column 3")

    def test_delete_columns(self):
        m = self.sample()
        m.delete_columns([2, 0, 2])
        self.assertEqual(m.headers, ["b"])
        self.assertEqual(m.rows, [["2"], ["5"], ["8"]])
        self.assertTrue(m.dirty)
        with self.assertRaises(IndexError):
            m.delete_columns([1])

    def test_rename_column(self):
        m = self.sample()
        m.rename_column(1, "b")
        self.assertFalse(m.dirty)
        m.rename_column(1, "bee")
        self.assertEqual(m.headers[1], "bee")
        self.assertTrue(m.dirty)
        with self.assertRaises(IndexError):
            m.rename_column(5, "x")


class TestDirty(Base):
    def test_dirty_lifecycle(self):
        m = self.sample()
        self.assertFalse(m.dirty)
        m.insert_row()
        self.assertTrue(m.dirty)
        m.save(self.p())
        self.assertFalse(m.dirty)
        m.delete_rows([0])
        self.assertTrue(m.dirty)
        m.load(self.p())
        self.assertFalse(m.dirty)
        m.insert_column()
        self.assertTrue(m.dirty)
        m.new()
        self.assertFalse(m.dirty)


if __name__ == "__main__":
    unittest.main()
