import csv, hashlib, os, re, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "databricks"))
import generate_synthetic as g

# Generic patterns that must never appear in the generated dataset (the real-data check lives in the private repo).
PII_PATTERNS = [r"[\w.+-]+@[\w-]+\.[\w.]+", r"\b\d{13,19}\b", r"\bsk-[A-Za-z0-9]{10,}", r"\bghp_[A-Za-z0-9]{10,}"]


def digest(folder):
    h = hashlib.sha256()
    for root, _, files in sorted(os.walk(folder)):
        for f in sorted(files):
            h.update(f.encode()); h.update(open(os.path.join(root, f), "rb").read())
    return h.hexdigest()


class Synthetic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a, cls.b = tempfile.mkdtemp(), tempfile.mkdtemp()
        g.OUT = cls.a; cls.stats = g.generate()
        g.OUT = cls.b; g.generate()

    def test_es_determinista(self):
        self.assertEqual(digest(self.a), digest(self.b))

    def test_no_hay_marcas_de_datos_reales(self):
        blob = "".join(open(os.path.join(r, f), encoding="utf-8").read()
                       for r, _, fs in os.walk(self.a) for f in fs).upper()
        for p in PII_PATTERNS:
            self.assertIsNone(re.search(p, blob), p)

    def test_incluye_las_situaciones_sembradas(self):
        rows = list(csv.DictReader(open(os.path.join(self.a, "transactions", "transactions_initial.csv"), encoding="utf-8")))
        merchants = {r["merchant"] for r in rows}
        for m in ("Electro Hogar", "Resort Booking", "Streaming Plus"):
            self.assertIn(m, merchants)
        self.assertTrue(any(r["monto_conocido"] == "0" for r in rows))   # montos sin informar
        self.assertTrue(any(r["type"] == "reembolso" for r in rows))
        self.assertTrue(any(r["origen"] == "recurrente" for r in rows))

    def test_hay_estado_de_cuenta_con_faltantes_en_mail(self):
        self.assertGreater(self.stats["statement_lines"], self.stats["initial"] * 0.9)
        self.assertEqual(self.stats["incoming_days"], 5)


if __name__ == "__main__":
    unittest.main()
