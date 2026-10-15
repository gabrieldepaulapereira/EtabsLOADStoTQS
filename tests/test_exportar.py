"""
Testes sem o ETABS.  Execute:  python -m unittest discover -s tests -v

O teste de integração usa a planilha e a pasta ETB de referência da Torre C (se estiverem
na pasta do projeto): um ETABS simulado serve os valores da planilha, o programa roda as
duas etapas (faces e pilar completo reatribuído numa cópia) e a pasta ETB gerada é
comparada byte a byte com a de referência.
"""
import json
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import exportar_pier_forces as m  # noqa: E402
import fake_etabs  # noqa: E402

TOWER_C_XLSX = ROOT / "Pier forces garden park tower C.xlsx"
TOWER_C_ETB = ROOT / "Pier forces garden park tower C" / "ETB"
COMBOS = ["DEAD-COMB", "ULS-NBR-1", "ULS-NBR-2", "ULS-NBR-3", "ULS-NBR-4", "SLS-1"]


def row(story, pier, case="C", loc="Top", seq=0):
    return m.Row(story, pier, case, loc, (0.0,) * 6, seq, story)


class Formatting(unittest.TestCase):
    def test_numbers(self):
        f = m.fmt_number
        self.assertEqual(f(-26.3712), "-26,37")
        self.assertEqual(f(25.5), "25,50")
        self.assertEqual(f(0.125), "0,13")
        self.assertEqual(f(2.675), "2,68")
        self.assertEqual(f(-0.004), "0,00")
        self.assertEqual(f(-1884.04), "-1884,04")
        with self.assertRaises(ValueError):
            f(float("nan"))

    def test_safe_filename(self):
        self.assertEqual(m.safe_filename("P1/2"), "P1_2")
        self.assertEqual(m.safe_filename("CON"), "_CON")


class Polygonal(unittest.TestCase):
    def test_face_names(self):
        self.assertEqual(m.face_of("P1A"), ("P1", 1))
        self.assertEqual(m.face_of("P12C"), ("P12", 3))
        self.assertEqual(m.face_of("P106b"), ("P106", 2))
        self.assertEqual(m.face_of("P8-3"), ("P8", 3))              # convenção numerada também vale
        for regular in ("P1", "P12", "CHK", "PAR", "P1-A"):
            self.assertIsNone(m.face_of(regular), regular)
        self.assertEqual(m.face_output_name("P12C"), "P12-3")
        self.assertEqual(m.face_output_name("P2"), "P2")

    def test_groups(self):
        g = m.polygonal_groups(["P1", "P8B", "P8A", "P8C", "P9A", "P10-1", "P10-2", "CHK"], quiet=True)
        self.assertEqual(list(g), ["P8", "P10"])
        self.assertEqual(g["P8"], ["P8A", "P8B", "P8C"])            # ordem das faces
        self.assertNotIn("P9", g)                                   # uma face só: pilar comum
        self.assertEqual(m.output_names(g), {"P8A": "P8-1", "P8B": "P8-2", "P8C": "P8-3",
                                             "P10-1": "P10-1", "P10-2": "P10-2"})

    def test_groups_numeric_order(self):
        g = m.polygonal_groups(["P8-2", "P8-10", "P8-1"], quiet=True)
        self.assertEqual(g["P8"], ["P8-1", "P8-2", "P8-10"])

    def test_same_face_twice(self):
        with self.assertRaises(m.UserError):                        # P1A e P1-1 viram P1-1
            m.polygonal_groups(["P1A", "P1-1", "P1B"], quiet=True)

    def test_txt(self):
        rows = {"P8-1": [row("1", "P8-1"), row("6", "P8-1"), row("52", "P8-1")],
                "P8-2": [row("6", "P8-2"), row("1", "P8-2")]}
        txt = m.build_txt("P8", ["P8-1", "P8-2"], rows)
        self.assertEqual(txt, "lance\t1\r\nP8-1\t1\r\nP8-2\t2\r\nlance\t6\r\nP8-1\t1\r\nP8-2\t2"
                              "\r\nlance\t52\r\nP8-1\t1")

    def test_txt_needs_numbers(self):
        with self.assertRaises(m.UserError):
            m.build_txt("P8", ["P8-1"], {"P8-1": [row("Story1", "P8-1")]})


class StoryMap(unittest.TestCase):
    def test_precedence(self):
        mapping = {(None, "Story1"): "1", ("P106", "Story1"): "2", ("P106-3", "Story1"): "9"}
        self.assertEqual(m.map_story(mapping, "P2", "Story1"), "1")
        self.assertEqual(m.map_story(mapping, "P106", "Story1"), "2")
        self.assertEqual(m.map_story(mapping, "P106-1", "Story1"), "2")   # face herda do pilar
        self.assertEqual(m.map_story(mapping, "P106A", "Story1"), "2")
        self.assertEqual(m.map_story(mapping, "P106-3", "Story1"), "9")   # exceção da face
        self.assertEqual(m.map_story(mapping, "P106C", "Story1"), "9")    # P106C é gravada como P106-3
        self.assertIsNone(m.map_story(mapping, "P2", "Story2"))

    def test_roundtrip(self):
        mapping = {(None, "Story2"): "6", (None, "Story1"): "1", ("P9", "Story1"): "3"}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "story_map.csv"
            m.save_story_map(path, mapping)
            self.assertEqual(m.load_story_map(path), mapping)

    def test_tower_files(self):
        for name in ("story_map_torre_A.csv", "story_map_torre_C.csv"):
            if (ROOT / name).exists():
                self.assertGreater(len(m.load_story_map(ROOT / name)), 40)

    def test_lance_conflict(self):
        rows = [replace_story(row("Story2", "P1"), "6"), replace_story(row("Story3", "P1"), "6")]
        with self.assertRaises(m.UserError):
            m.check_lance_conflicts(rows)


def replace_story(r, lance):
    return m.Row(lance, r.pier, r.case, r.location, r.values, r.seq, r.etabs_story)


class Geometry(unittest.TestCase):
    def test_pier_sections(self):
        class Sap:
            class PierLabel:
                @staticmethod
                def GetSectionProperties(name):
                    return [2, ("S2", "S1"), (30.0, 30.0), (2, 0), (0, 0), (4.0, 4.0), (0.3, 0.3), (4.0, 4.0),
                            (0.3, 0.3), ("C40", "C40"), (1.0, 1.0), (2.0, 2.0), (3.0, 0.0), (1.1, 1.1),
                            (2.1, 2.1), (6.0, 3.0), 0]
        secs = m.pier_sections(Sap, "P1A")
        self.assertEqual(secs, [{"story": "S2", "angle": 30.0, "width": 4.0, "thick": 0.3, "x": 1.0, "y": 2.0}])


class WriteEtb(unittest.TestCase):
    def test_backup_and_replace(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "ETB"
            out.mkdir()
            (out / "VELHO.csv").write_text("x")
            backup = m.write_etb(out, {"P1": [row("1", "P1")]}, {"P8": "lance\t1"})
            self.assertTrue((backup / "VELHO.csv").exists())
            self.assertEqual(sorted(p.name for p in out.iterdir()), ["P1.csv", "P8.txt"])
            self.assertEqual((out / "P8.txt").read_bytes(), b"lance\t1")
            self.assertFalse((Path(d) / "ETB_gerando").exists())


try:
    import openpyxl  # noqa: F401
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


@unittest.skipUnless(HAS_OPENPYXL, "pip install openpyxl para o teste da Torre C")
@unittest.skipUnless(TOWER_C_XLSX.exists() and TOWER_C_ETB.is_dir(), "dados da Torre C ausentes")
class TowerC(unittest.TestCase):
    """Fluxo completo com o ETABS simulado e os dados da Torre C."""

    @classmethod
    def setUpClass(cls):
        faces, whole, cls.stories = fake_etabs.load_tower_c(TOWER_C_XLSX)
        cls.groups = m.polygonal_groups(faces, quiet=True)
        cls.data = dict(faces)
        cls.data.update({p: v for p, v in whole.items() if p not in cls.groups})
        cls.full = {p: v for p, v in whole.items() if p in cls.groups}
        cls.mapping = m.load_story_map(ROOT / "story_map_torre_C.csv")

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.edb = self.tmp / "Garden-Park-C-v109.EDB"
        self.edb.write_bytes(b"modelo original")
        self.edb.with_suffix(".Y00").write_bytes(b"resultados")
        self.saved_connect = m.connect

    def tearDown(self):
        m.connect = self.saved_connect
        shutil.rmtree(self.tmp, ignore_errors=True)

    def model(self, strict_lock, letters=False):
        data = self.data
        if letters:                                        # P8-1 -> P8A: convenção de faces com letra
            data = {self.letter(k): v for k, v in data.items()}
        labels = list(data) + ["CHK", "P10"]               # P10 já existe como label, sem objetos
        groups = m.polygonal_groups(list(data), quiet=True)
        geo = fake_etabs.synthetic_geometry(groups, [p for p in data if p not in m.output_names(groups)])
        sap = fake_etabs.FakeModel(data, self.full, self.stories, COMBOS, labels, strict_lock, geometry=geo)
        app = fake_etabs.install(m, sap)
        return sap, app

    def assert_matches_reference(self, out_dir):
        refs = sorted(p.name for p in TOWER_C_ETB.iterdir() if p.suffix in (".csv", ".txt"))
        self.assertEqual(sorted(p.name for p in out_dir.iterdir()), refs)
        title = m.TABLE_TITLE.encode() + b";" * 10 + b"\r\n"
        for name in refs:
            gen, ref = (out_dir / name).read_bytes(), (TOWER_C_ETB / name).read_bytes()
            if name == "P8-7.csv" and not ref.startswith(b"TABLE"):
                gen = gen[len(title):]                     # a referência não tem a linha de título
            self.assertEqual(gen, ref, name)

    def test_strict_lock_reanalyzes_copy(self):
        sap, app = self.model(strict_lock=True)
        result = m.export_model(m.Etabs(), self.edb, self.mapping, True)
        self.assert_matches_reference(result.out_dir)
        self.assertEqual((result.csv_count, result.txt_count), (56, 8))
        self.assertTrue(result.reanalyzed)
        self.assertEqual(sap.runs, 1)
        self.assertEqual(sap.units, 6)                              # unidades restauradas
        self.assertEqual(app.exited, 1)                             # fechou o ETABS que abriu
        self.assertEqual(self.edb.read_bytes(), b"modelo original")  # original intacto
        self.assertFalse((self.tmp / m.WORK_SUBFOLDER).exists())    # cópia apagada
        self.assertEqual(Path(sap.open_log[1]).parent.name, m.WORK_SUBFOLDER)
        self.assertIn("Piers sem resultados (sem arquivo): CHK", result.warnings)

    def test_check_of_other_piers(self):
        self.model(strict_lock=True)
        with self.assertLogs(m.log, "INFO") as logs:
            m.export_model(m.Etabs(), self.edb, self.mapping, True)
        self.assertTrue(any("idênticos na cópia" in x for x in logs.output))
        self.assertFalse(any("diferentes na cópia" in x for x in logs.output))

        ref = [m.Row("S1", "P2", "C", "Top", (1.0,) * 6, 0, "S1"),
               m.Row("S1", "P2", "C", "Bottom", (2.0,) * 6, 1, "S1")]
        changed = [ref[0], m.Row("S1", "P2", "C", "Bottom", (2.5,) * 6, 1, "S1")]
        with self.assertLogs(m.log, "WARNING"):
            m.compare_other_piers(ref, changed, set())

    @staticmethod
    def letter(name):
        f = m.face_of(name)
        return f"{f[0]}{chr(ord('A') + f[1] - 1)}" if f else name

    def test_faces_with_letters(self):
        """Piers P8A, P8B... no ETABS geram P8-1.csv, P8-2.csv... idênticos à referência."""
        sap, _ = self.model(strict_lock=False, letters=True)
        self.assertIn("P8G", sap.labels)
        self.assertNotIn("P8-1", sap.labels)
        with self.assertLogs(m.log, "INFO") as logs:
            result = m.export_model(m.Etabs(), self.edb, self.mapping, True)
        self.assert_matches_reference(result.out_dir)
        self.assertTrue(any("Face P8A gravada como P8-1" in x for x in logs.output))

    def test_relaxed_lock_keeps_results(self):
        sap, _ = self.model(strict_lock=False)
        result = m.export_model(m.Etabs(), self.edb, self.mapping, True)
        self.assert_matches_reference(result.out_dir)
        self.assertFalse(result.reanalyzed)
        self.assertEqual(sap.runs, 0)

    def test_without_full(self):
        self.model(strict_lock=True)
        result = m.export_model(m.Etabs(), self.edb, self.mapping, False)
        names = {p.name for p in result.out_dir.iterdir()}
        self.assertIn("P8-1.csv", names)
        self.assertNotIn("P8.csv", names)
        self.assertFalse(any(n.endswith(".txt") for n in names))

    def test_missing_lance_fails_before_extraction(self):
        sap, _ = self.model(strict_lock=True)
        mapping = {k: v for k, v in self.mapping.items() if k != (None, "Story20")}
        with self.assertRaises(m.UserError) as ctx:
            m.export_model(m.Etabs(), self.edb, mapping, True)
        self.assertIn("Story20", str(ctx.exception))
        self.assertFalse((self.tmp / "ETB").exists())
        self.assertEqual(sap.set_pier_calls, 0)

    def test_second_run_backs_up_previous_etb(self):
        self.model(strict_lock=False)
        m.export_model(m.Etabs(), self.edb, self.mapping, True)
        self.model(strict_lock=False)
        result = m.export_model(m.Etabs(), self.edb, self.mapping, True)
        self.assertIsNotNone(result.backup)
        self.assertTrue((result.backup / "P8.txt").exists())

    def test_interface_api(self):
        """A ponte com a interface (Api): ler, validar lances, exportar, preferências e progresso."""
        self.model(strict_lock=True)
        saved = m.diagnose_api, m.settings_path
        m.diagnose_api = lambda: "teste"                       # sem COM real no teste
        m.settings_path = lambda: self.tmp / "settings.json"
        api = m.Api()

        def wait(name):
            seen, t0 = [], time.time()
            while time.time() - t0 < 120:
                for e in api.poll():
                    seen.append(e)
                    if e["t"] == "job" and e["name"] == name:
                        return e, seen
                time.sleep(0.02)
            self.fail(f"tarefa {name} não terminou")

        try:
            boot = api.boot()
            self.assertEqual(boot["version"], m.__version__)
            api.read_model(str(self.edb))
            ev, _ = wait("read")
            self.assertTrue(ev["ok"], ev)
            payload = ev["data"]
            json.dumps(payload)                                # a ponte serializa em JSON
            self.assertEqual([g["base"] for g in payload["groups"]],
                             ["P8", "P10", "P11", "P17", "P19", "P101", "P103", "P106"])
            self.assertEqual(payload["default_combos"], ["ULS-NBR-1", "ULS-NBR-2", "ULS-NBR-3", "ULS-NBR-4"])
            self.assertEqual(len(payload["stories"]), len(self.stories))
            self.assertEqual(payload["length_unit"], "m")
            p8a = next(p for p in payload["piers"] if p["name"] == "P8-1")
            self.assertEqual(len(p8a["geom"]), len(p8a["stories"]))
            g = p8a["geom"][0]
            self.assertEqual((g["angle"], g["width"], g["thick"]), (90.0, 3.4, 0.25))   # em m, não em mm

            req = {"path": str(self.edb), "combos": payload["default_combos"], "excluded": [], "full": True,
                   "mapping": {"general": {}, "exceptions": []}}
            with self.assertRaises(m.UserError):               # sem lances: recusa antes do ETABS
                api.export(req)
            req["mapping"] = m.mapping_to_json(self.mapping)
            api.export(req)
            ev, seen = wait("export")
            self.assertTrue(ev["ok"], ev)
            self.assertEqual((ev["data"]["csv"], ev["data"]["txt"]), (56, 8))
            self.assert_matches_reference(self.tmp / "ETB")
            stages = [e["stage"] for e in seen if e["t"] == "progress"]
            for st in ("conexao", "etapa1", "copia", "reatribuicao", "analise", "etapa2", "gravacao"):
                self.assertIn(st, stages)
            self.assertEqual(m.load_story_map(self.tmp / m.STORY_MAP_FILENAME), self.mapping)
            prefs = m.load_settings()["models"][m._model_key(self.edb)]
            self.assertEqual(prefs["combos"], payload["default_combos"])

            req.update(excluded=["P8", "P2"], full=False)      # excluir pilar e grupo
            api.export(req)
            ev, _ = wait("export")
            names = set(ev["data"]["files"])
            self.assertNotIn("P2.csv", names)
            self.assertFalse(any(n.startswith("P8") for n in names))
            self.assertIn("P10-1.csv", names)
        finally:
            api._shutdown()
            m.diagnose_api, m.settings_path = saved

if __name__ == "__main__":
    unittest.main()
