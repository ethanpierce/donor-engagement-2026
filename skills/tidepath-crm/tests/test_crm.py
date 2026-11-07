import contextlib
import importlib.util
import io
import os
import sqlite3
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "crm.py")
DEMO = os.path.join(HERE, "..", "..", "..", "demo-data")

spec = importlib.util.spec_from_file_location("tidepath_crm", SCRIPT)
crm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(crm)


class CrmTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "crm.db")
        self.run_cmd("seed", DEMO)
        self.db = sqlite3.connect(self.db_path)
        self.db.row_factory = sqlite3.Row

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def run_cmd(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            crm.main(["--db", self.db_path, *args])
        return out.getvalue()

    def pid(self, name):
        return self.db.execute("SELECT id FROM people WHERE name=?", (name,)).fetchone()[0]

    def test_dupes_finds_rosa_variants(self):
        out = self.run_cmd("dupes")
        for name in ("Rosa Delgado", "Rosa M. Delgado", "R. Delgado"):
            self.assertIn(name, out)
        db = crm.connect(self.db_path)
        pairs = {frozenset((p["name"], q["name"])) for _, p, q, _ in crm.find_dupes(db)}
        self.assertIn(frozenset(("Rosa Delgado", "Rosa M. Delgado")), pairs)
        self.assertIn(frozenset(("Rosa Delgado", "R. Delgado")), pairs)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM audit").fetchone()[0], 0)

    def test_merge_needs_approver_and_keeps_history(self):
        keep, drop = self.pid("Rosa Delgado"), self.pid("Rosa M. Delgado")
        with self.assertRaises(SystemExit):
            self.run_cmd("merge", str(keep), str(drop), "--approved-by", " ")
        gifts = lambda: self.db.execute("SELECT COUNT(*) FROM donations").fetchone()[0]
        before = gifts()
        self.run_cmd("merge", str(keep), str(drop), "--approved-by", "Dana Whitfield")
        kids = {r[0] for r in self.db.execute(
            "SELECT p.name FROM signups s JOIN people p ON p.id=s.kid_id WHERE s.parent_id=?", (keep,))}
        self.assertEqual(kids, {"Sofia Delgado", "Mateo Delgado"})
        self.assertEqual(gifts(), before)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM donations WHERE donor_id=?", (keep,)).fetchone()[0], 2)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM donations WHERE donor_id=?", (drop,)).fetchone()[0], 0)
        a = self.db.execute("SELECT approved_by FROM audit WHERE action='merge'").fetchone()
        self.assertEqual(a[0], "Dana Whitfield")
        self.assertIn("Mateo Delgado", self.run_cmd("person", "Rosa Delgado"))

    def test_at_risk_returns_kevin(self):
        db = crm.connect(self.db_path)
        rows = crm.at_risk(db, "2026-09-28")
        kevin = [r for r in rows if r[0] == "Kevin Morales"]
        self.assertEqual(len(kevin), 1)
        self.assertIn("missed 3 sessions", kevin[0][1])
        self.assertEqual(kevin[0][3], "Elena Morales")
        self.assertNotIn("Diego Ramirez", [r[0] for r in rows])  # one miss only

    def test_duplicate_volunteer_visit_counted_once(self):
        # Planted in volunteer_hours.csv: Grace Okafor / Amara Johnson / 2026-09-19 twice.
        n = self.db.execute("SELECT COUNT(*) FROM visits WHERE volunteer_id=? AND kid_id=? AND date='2026-09-19'",
                            (self.pid("Grace Okafor"), self.pid("Amara Johnson"))).fetchone()[0]
        self.assertEqual(n, 1)
        args = ["log-volunteer", "--volunteer", "Daniel Kim", "--kid", "Mateo Delgado", "--hours", "2",
                "--date", "2026-09-26"]
        self.assertIn("Logged", self.run_cmd(*args))
        self.assertIn("Already logged", self.run_cmd(*args))
        n = self.db.execute("SELECT COUNT(*) FROM visits WHERE volunteer_id=? AND date='2026-09-26'",
                            (self.pid("Daniel Kim"),)).fetchone()[0]
        self.assertEqual(n, 1)

    def test_report_totals_reconcile(self):
        self.run_cmd("log-volunteer", "--volunteer", "Maria Alvarez", "--kid", "Kevin Morales", "--hours", "1",
                     "--date", "2026-09-26", "--urgent", "Kevin needs a laptop for school")
        self.run_cmd("log-volunteer", "--volunteer", "Maria Alvarez", "--kid", "Kevin Morales", "--hours", "1",
                     "--date", "2026-09-26")
        db = crm.connect(self.db_path)
        m, checks, _ = crm.report(db, "2026Q3")
        for name, rep, src in checks:
            self.assertEqual(rep, src, name)
        self.assertEqual(m["kids enrolled"], 25)
        self.assertEqual(m["sessions held"], 13)
        self.assertEqual(m["urgent needs resolved"], 2)
        self.assertIn("All totals reconcile.", self.run_cmd("report", "--quarter", "2026Q3"))


if __name__ == "__main__":
    unittest.main()
