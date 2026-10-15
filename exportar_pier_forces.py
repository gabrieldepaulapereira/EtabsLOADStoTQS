"""
EXPORTAR PIER FORCES DO ETABS PARA O TQS  (pasta ETB)
=====================================================

O QUE FAZ
  Lê pela API do ETABS os esforços da tabela Pier Forces nas combinações ULS-NBR-# e
  grava, na pasta "ETB" ao lado do modelo, os arquivos lidos pelo TQS:
    - um CSV por Pier (P1.csv, P2.csv, ...);
    - para cada pilar poligonal (Piers P8A, P8B, P8C... = faces 1, 2, 3 do pilar P8):
        P8-1.csv, P8-2.csv...  uma face por arquivo (a letra vira o número da face);
        P8.csv  esforços do pilar completo. As faces são reatribuídas ao Pier "P8" numa
                CÓPIA do modelo e os esforços são extraídos de novo. O modelo original
                nunca é alterado;
        P8.txt  lances do TQS em que cada face existe e a faixa de cada face.

COMO USAR
  Abra ExportarPierForces.exe (ou executar.bat, para rodar este .py). A janela guia em 5 passos:
    1. Modelo       escolha o .EDB analisado e clique em "Ler modelo no ETABS";
    2. Combinações  as ULS-NBR-# já vêm marcadas;
    3. Pilares      pilares poligonais e demais Piers (clique para excluir);
    4. Lances TQS   o lance do TQS de cada Story do ETABS (salvo em story_map.csv);
    5. Exportar     gera a pasta ETB e mostra o progresso de cada etapa.
  A interface fica em ui/ (HTML/CSS/JS, aberta numa janela nativa pelo pywebview).

Requisitos para rodar o .py: Windows, ETABS (testado com a API do 22/23), Python 3.10+ 64 bits
e os pacotes comtypes e pywebview (pip install comtypes pywebview).

Linha de comando (sem janela):
  --modelo ARQ.EDB    exporta esse modelo (lances lidos do story_map.csv ao lado dele)
  --pasta DIR         exporta o .EDB analisado que estiver em DIR
  --cli               exporta o .EDB analisado da pasta deste arquivo
  --sem-completo      não gera os pilares poligonais completos (P8.csv) nem os .txt
  --listar            mostra Piers, combinações e Load Cases do modelo e sai
  --comparar DIR      depois de exportar, compara a pasta ETB com arquivos de referência
  --diagnostico       confere a instalação (API do ETABS registrada?) sem abrir o ETABS
"""

__version__ = "1.0.0"

# =============================================================================
# CONFIGURAÇÃO  (edite aqui)
# =============================================================================

# Linha de comando sem --modelo: nome do .EDB a usar. None = escolha automática.
MODEL_FILENAME = None

# Pasta de saída lida pelo TQS, criada ao lado do modelo. Se ela já existir, é
# renomeada para "ETB_anterior_<data>" (o TQS lê tudo o que estiver dentro dela).
OUTPUT_SUBFOLDER = "ETB"

# Combinações: lista explícita > regex > prefixo. Tudo None = todas as combinações.
COMBINATION_LIST = None            # ex.: ["ULS-NBR-1", "ULS-NBR-2"]
COMBINATION_REGEX = r"^ULS-NBR-\d+$"
COMBINATION_PREFIX = None

# Piers: lista explícita > regex > prefixo. Tudo None = todos os Piers.
PIER_LIST = None                   # ex.: ["P2", "P8-1", "P8-2"]
PIER_REGEX = None
PIER_PREFIX = None
PIER_EXCLUDE = []                  # ex.: ["CHK"]

# Pilares poligonais: cada face é um Pier do ETABS com o nome do pilar + letra
# (P1A, P1B, P1C = faces 1, 2, 3 do pilar P1), gravada como P1-1.csv, P1-2.csv, P1-3.csv.
# Também é aceito o nome já numerado (P1-1, P1-2...). None desliga essa convenção.
FACE_LETTER_REGEX = r"^(?P<base>.*\d)(?P<face>[A-Za-z])$"
FACE_NUMBER_REGEX = r"^(?P<base>.+)-(?P<face>\d+)$"
EXPORT_FULL_POLYGONAL = True       # gera <pilar>.csv (pilar completo) e <pilar>.txt
WORK_SUBFOLDER = "_pier_completo_tmp"   # cópia de trabalho do modelo (apagada no fim)
COPY_RESULTS_TO_WORK = True        # copia também os resultados (.Y00...), para tentar não reanalisar
KEEP_WORK_COPY = False             # True = mantém a cópia de trabalho para conferência

# Correspondência Story do ETABS -> lance do TQS (arquivo ao lado do modelo, ETABS;SAIDA;PIER).
STORY_MAP_FILENAME = "story_map.csv"
STORY_MAP_STRICT = True            # True = erro se algum Story usado não tiver lance

# Unidades de saída: 12 = Ton_m_C (tonf, tonf-m), 6 = kN_m_C (kN, kN-m), 8 = kgf_m_C.
OUTPUT_EUNITS = 12
FORCE_LABEL, MOMENT_LABEL = "tonf", "tonf-m"

# Formato dos arquivos (igual ao exportado pelo Excel em português).
FIELD_SEPARATOR = ";"
DECIMAL_SEPARATOR = ","
DECIMALS = 2
CSV_ENCODING = "cp1252"            # use "utf-8-sig" se houver caracteres fora do cp1252
TXT_ENCODING = "cp1252"

# ETABS
ETABS_PROGRAM_PATH = None          # ex.: r"C:\Program Files\Computers and Structures\ETABS 22\ETABS.exe"
CLOSE_ETABS_IF_STARTED = True      # fecha o ETABS ao final se ele foi aberto por este programa
RUN_ANALYSIS_IF_NEEDED = False     # roda a análise do modelo original se ele não tiver resultados

# =============================================================================
# (não é preciso editar nada abaixo desta linha)
# =============================================================================

import argparse  # noqa: E402
import csv  # noqa: E402
import io  # noqa: E402
import logging  # noqa: E402
import math  # noqa: E402
import os  # noqa: E402
import queue  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
from collections import Counter, OrderedDict, defaultdict  # noqa: E402
from contextlib import contextmanager  # noqa: E402
from dataclasses import dataclass, field, replace  # noqa: E402
from datetime import datetime  # noqa: E402
from decimal import ROUND_HALF_UP, Decimal  # noqa: E402
from pathlib import Path  # noqa: E402

import json  # noqa: E402

log = logging.getLogger("pier_forces")

# Progresso por etapa, para a interface (a linha de comando não usa).
_progress_sink = None


def progress(stage: str, done: int | None = None, total: int | None = None, text: str = ""):
    if _progress_sink is not None:
        _progress_sink({"stage": stage, "done": done, "total": total, "text": text})

ETABS_PROG_ID = "CSI.ETABS.API.ETABSObject"
HELPER_PROG_ID = "ETABSv1.Helper"
CASE_FINISHED = 4                                  # cAnalyze.GetCaseStatus
CNAME_LOAD_COMBO = 1                               # eCNameType
OBJECT_ITEM = 0                                    # eItemType.Objects
UNITS_NAMES = {5: "kN_mm_C", 6: "kN_m_C", 7: "kgf_mm_C", 8: "kgf_m_C", 9: "N_mm_C",
               10: "N_m_C", 11: "Ton_mm_C", 12: "Ton_m_C", 13: "kN_cm_C", 14: "kgf_cm_C",
               15: "N_cm_C", 16: "Ton_cm_C", 1: "lb_in_F", 2: "lb_ft_F", 3: "kip_in_F",
               4: "kip_ft_F"}
PIER_FORCE_FIELDS = ("Story", "Pier", "LoadCase", "Location", "P", "V2", "V3", "T", "M2", "M3")
TABLE_TITLE = "TABLE:  Pier Forces"
TEXT_COLUMNS = ("Story", "Pier", "Output Case", "Case Type", "Location")
VALUE_COLUMNS = ("P", "V2", "V3", "T", "M2", "M3")
WORK_MARKER = "CRIADO_POR_EXPORTAR_PIER_FORCES.txt"


class UserError(Exception):
    """Erro com mensagem destinada ao usuário (sem traceback)."""


# =============================================================================
# 1. Pasta e modelo
# =============================================================================

def program_dir() -> Path:
    """Pasta deste programa (funciona também se for empacotado como .exe)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def has_results(edb: Path) -> bool:
    """O ETABS grava os resultados em arquivos <nome>.Y00, <nome>.Y ... ao lado do .EDB."""
    return any(edb.with_suffix(ext).exists() for ext in (".Y00", ".Y"))


def is_interactive() -> bool:
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def model_candidates(folder: Path) -> list[Path]:
    """Os .EDB da pasta, os analisados primeiro se houver, do mais recente ao mais antigo."""
    models = sorted((p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".edb"),
                    key=lambda p: p.stat().st_mtime, reverse=True)
    return [m for m in models if has_results(m)] or models


def guess_model(folder: Path) -> Path | None:
    """Modelo sugerido na janela: o único .EDB analisado da pasta, se houver só um."""
    try:
        if MODEL_FILENAME and (folder / MODEL_FILENAME).is_file():
            return folder / MODEL_FILENAME
        candidates = model_candidates(folder)
    except OSError:
        return None
    return candidates[0] if len(candidates) == 1 else None


def find_model(folder: Path) -> Path:
    if MODEL_FILENAME:
        path = folder / MODEL_FILENAME
        if not path.is_file():
            raise UserError(f"MODEL_FILENAME = {MODEL_FILENAME!r} não existe em {folder}")
        return path

    candidates = model_candidates(folder)
    if not candidates:
        raise UserError(f"Nenhum arquivo .EDB encontrado em:\n  {folder}")
    if len(candidates) == 1:
        return candidates[0]

    lines = [f"  {i}) {m.name}  ({datetime.fromtimestamp(m.stat().st_mtime):%d/%m/%Y %H:%M})"
             f"{'  [com resultados]' if has_results(m) else ''}"
             for i, m in enumerate(candidates, 1)]
    if not is_interactive():
        raise UserError("Há mais de um modelo possível na pasta:\n" + "\n".join(lines) +
                        "\nUse --modelo ou defina MODEL_FILENAME no início deste arquivo.")
    print("\nModelos encontrados na pasta:\n" + "\n".join(lines))
    while True:
        try:
            answer = input(f"Qual modelo usar? [1-{len(candidates)}, Enter = 1]: ")
        except EOFError:
            raise UserError("Sem resposta no console. Use --modelo ou defina MODEL_FILENAME.") from None
        answer = answer.strip().lstrip("\ufeff")
        if not answer:
            return candidates[0]
        if answer.isdigit() and 1 <= int(answer) <= len(candidates):
            return candidates[int(answer) - 1]
        print("Opção inválida.")


# =============================================================================
# 2. API do ETABS (COM)
#    Convenção do comtypes para parâmetros ByRef: a chamada devolve
#    [saída_1, ..., saída_n, código_de_retorno]; código 0 = sucesso.
#    Todos os métodos usados foram conferidos no ETABSv1.tlb do ETABS 22 e 23.
# =============================================================================

def _com_errors():
    try:
        from comtypes import COMError
        return (COMError, OSError)
    except ImportError:
        return (OSError,)


def _describe(exc) -> str:
    hr = getattr(exc, "hresult", None)
    if hr is None and exc.args and isinstance(exc.args[0], int):
        hr = exc.args[0]
    return f"{type(exc).__name__}" + (f" (HRESULT 0x{hr & 0xFFFFFFFF:08X})" if isinstance(hr, int) else "") + f": {exc}"


def call(description, func, *args):
    try:
        return func(*args)
    except _com_errors() as exc:
        raise UserError(f"Falha de comunicação com o ETABS em {description}: {_describe(exc)}.\n"
                        "Verifique se o ETABS continua aberto e sem nenhuma janela de diálogo aberta.") from exc


def split_ret(result, n_out, method):
    if not isinstance(result, (list, tuple)) or len(result) != n_out + 1:
        raise UserError(f"{method}: retorno inesperado da API ({result!r:.80}). "
                        "Versão da API do ETABS incompatível?")
    *outs, ret = result
    return outs, int(ret)


def as_list(value) -> list:
    return [] if value is None else list(value)


def check(ret, description):
    if int(ret) != 0:
        raise UserError(f"{description} retornou código {ret} (esperado 0).")


def same_file(a, b) -> bool:
    if not a or not b:
        return False
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def model_filename(sap) -> str:
    """Caminho do modelo aberto, ou "" se não houver arquivo (o ETABS devolve "(Untitled)")."""
    try:
        name = str(sap.GetModelFilename(True) or "").strip()
    except _com_errors():
        return ""
    return name if os.path.isabs(name) else ""


def is_empty_model(sap) -> bool:
    try:
        return int(sap.PointObj.Count()) == 0
    except _com_errors():
        return False


def etabs_pids() -> list[int]:
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq ETABS.exe", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True, errors="replace", timeout=30,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [int(r[1]) for r in csv.reader(io.StringIO(out))
            if len(r) >= 2 and r[0].strip().lower() == "etabs.exe" and r[1].isdigit()]


def create_helper():
    if sys.platform != "win32":
        raise UserError("A API do ETABS só funciona no Windows.")
    try:
        import comtypes.client
    except ImportError:
        raise UserError("O pacote 'comtypes' não está instalado. Abra o Prompt de Comando e rode:\n"
                        "  pip install comtypes") from None
    try:
        helper = comtypes.client.CreateObject(HELPER_PROG_ID)
    except _com_errors() as exc:
        raise UserError(f"Não foi possível acessar a API do ETABS ({_describe(exc)}).\n"
                        "Execute como administrador o RegisterETABS.exe da pasta de instalação "
                        r"(ex.: C:\Program Files\Computers and Structures\ETABS 22\RegisterETABS.exe).") from exc
    try:
        import comtypes.gen.ETABSv1 as etabs_v1
        return helper.QueryInterface(etabs_v1.cHelper)
    except (ImportError, AttributeError) + _com_errors() as exc:
        where = (r"%APPDATA%\Python\...\comtypes_cache" if getattr(sys, "frozen", False)
                 else "'comtypes\\gen' da instalação do Python")
        raise UserError(f"Falha ao carregar a biblioteca ETABSv1 ({exc}). Se você trocou de versão do "
                        f"ETABS, apague a pasta {where}.") from exc


def etabs_installs() -> list[Path]:
    base = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Computers and Structures"
    try:
        return sorted(base.glob("ETABS*/ETABS.exe"), key=lambda p: natural_key(p.parent.name))
    except OSError:
        return []


def diagnose_api() -> str:
    """Confere se a API do ETABS está acessível, sem iniciar o ETABS."""
    installs = etabs_installs()
    log.info("Exportador de Pier Forces %s | Python %s%s", __version__, sys.version.split()[0],
             " (executável)" if getattr(sys, "frozen", False) else "")
    log.info("ETABS instalados: %s", ", ".join(p.parent.name for p in installs) or "nenhum encontrado")
    version = call("cHelper.GetOAPIVersionNumber", create_helper().GetOAPIVersionNumber)
    pids = etabs_pids()
    log.info("API do ETABS OK (versão %s). ETABS abertos agora: %s", version,
             ", ".join(map(str, pids)) if pids else "nenhum")
    return str(version)


@dataclass
class Session:
    etabs: object
    sap: object
    pid: int | None
    started_by_us: bool


def open_file(sap, edb: Path):
    check(call("File.OpenFile", sap.File.OpenFile, str(edb)), f"File.OpenFile({edb.name})")
    if not same_file(model_filename(sap), edb):
        raise UserError(f"O ETABS não confirmou a abertura de {edb}.")


def start_etabs(helper) -> Session:
    if ETABS_PROGRAM_PATH:
        if not Path(ETABS_PROGRAM_PATH).is_file():
            raise UserError(f"ETABS_PROGRAM_PATH não encontrado: {ETABS_PROGRAM_PATH}")
        etabs = call("cHelper.CreateObject", helper.CreateObject, ETABS_PROGRAM_PATH)
    else:
        etabs = call("cHelper.CreateObjectProgID", helper.CreateObjectProgID, ETABS_PROG_ID)
    if etabs is None:
        raise UserError("A API não conseguiu iniciar o ETABS.")
    check(call("cOAPI.ApplicationStart", etabs.ApplicationStart), "cOAPI.ApplicationStart")
    return Session(etabs, etabs.SapModel, None, True)


def connect(edb: Path, allow_existing: bool = True) -> Session:
    """
    1) instância que já está com este EDB aberto -> usa;
    2) instância aberta sem modelo -> abre o EDB nela;
    3) senão, inicia um novo ETABS (instâncias com outros modelos NUNCA são alteradas).
    allow_existing=False pula 1) e 2) e sempre inicia um ETABS novo.
    """
    helper = create_helper()
    pids = etabs_pids() if allow_existing else []
    empty = None
    if pids:
        log.info("Instâncias do ETABS abertas (PID): %s", ", ".join(map(str, pids)))
    for pid in pids:
        try:
            etabs = helper.GetObjectProcess(ETABS_PROG_ID, pid)
        except AttributeError:            # API antiga sem GetObjectProcess
            try:
                etabs = helper.GetObject(ETABS_PROG_ID)
            except _com_errors():
                etabs = None
        except _com_errors():
            etabs = None
        if etabs is None:
            log.warning("  PID %s não respondeu à API (ocupado ou carregando).", pid)
            continue
        sap = etabs.SapModel
        name = model_filename(sap)
        if same_file(name, edb):
            log.info("O modelo já está aberto no ETABS (PID %s); usando essa instância.", pid)
            return Session(etabs, sap, pid, False)
        if not name and empty is None and is_empty_model(sap):
            empty = Session(etabs, sap, pid, False)

    if empty is not None:
        log.info("Abrindo o modelo na instância do ETABS sem modelo (PID %s)...", empty.pid)
        session = empty
    else:
        if pids:
            log.info("Nenhuma instância aberta está com este modelo; as instâncias abertas não serão "
                     "alteradas. Iniciando outro ETABS...")
        else:
            log.info("Iniciando o ETABS...")
        session = start_etabs(helper)
    log.info("Abrindo %s ...", edb.name)
    open_file(session.sap, edb)
    return session


def close(session: Session | None):
    if session and session.started_by_us and CLOSE_ETABS_IF_STARTED:
        log.info("Fechando o ETABS aberto por este programa (sem salvar)...")
        try:
            session.etabs.ApplicationExit(False)
        except _com_errors() as exc:
            log.warning("Não foi possível fechar o ETABS: %s", _describe(exc))


class Etabs:
    """Sessões do ETABS usadas pelo programa; fecha no fim só as que ele mesmo iniciou."""

    def __init__(self):
        self.sessions: list[Session] = []

    def open_model(self, edb: Path, own_instance: bool = False) -> Session:
        for s in self.sessions:
            if same_file(model_filename(s.sap), edb):
                return s
        ours = [s for s in self.sessions if s.started_by_us]
        if ours:
            log.info("Abrindo %s no ETABS iniciado por este programa...", edb.name)
            open_file(ours[0].sap, edb)
            return ours[0]
        if own_instance:
            log.info("Iniciando um ETABS só para a cópia de trabalho (as instâncias abertas não são usadas)...")
        session = connect(edb, allow_existing=not own_instance)
        self.sessions.append(session)
        return session

    def close_all(self):
        for s in self.sessions:
            close(s)
        self.sessions.clear()


def name_list(obj, description) -> list[str]:
    outs, ret = split_ret(call(description, obj.GetNameList), 2, description)
    check(ret, description)
    return [str(x) for x in as_list(outs[1])]


def case_status(sap) -> dict[str, int]:
    outs, ret = split_ret(call("Analyze.GetCaseStatus", sap.Analyze.GetCaseStatus), 3,
                          "Analyze.GetCaseStatus")
    check(ret, "Analyze.GetCaseStatus")
    return {str(n): int(s) for n, s in zip(as_list(outs[1]), as_list(outs[2]))}


def is_locked(sap) -> bool:
    return bool(call("GetModelIsLocked", sap.GetModelIsLocked))


def combo_items(sap, combo) -> list[tuple[int, str]]:
    desc = f"RespCombo.GetCaseList('{combo}')"
    outs, ret = split_ret(call(desc, sap.RespCombo.GetCaseList, combo), 4, desc)
    check(ret, desc)
    return [(int(t), str(n)) for t, n in zip(as_list(outs[1]), as_list(outs[2]))]


def story_elevations(sap) -> dict[str, float]:
    result = {}
    for name in name_list(sap.Story, "Story.GetNameList"):
        try:
            outs, ret = split_ret(sap.Story.GetElevation(name), 1, "Story.GetElevation")
            if ret == 0:
                result[name] = float(outs[0])
        except (UserError,) + _com_errors():
            pass
    return result


def pier_sections(sap, pier) -> list[dict]:
    """
    Seção do Pier em cada Story em que ele tem objetos (PierLabel.GetSectionProperties; [] se falhar):
    story, angle (graus, do eixo X global ao eixo local 2 do Pier), width (ao longo do eixo 2),
    thick, x, y (centro de gravidade na base do Story), nas unidades atuais da API.
    Retorno: [NumberStories, StoryName[], AxisAngle[], NumAreaObjs[], NumLineObjs[], WidthBot[],
              ThicknessBot[], WidthTop[], ThicknessTop[], MatProp[], CGBotX[], CGBotY[], CGBotZ[],
              CGTopX[], CGTopY[], CGTopZ[], ret]
    """
    try:
        outs, ret = split_ret(sap.PierLabel.GetSectionProperties(pier), 16,
                              "PierLabel.GetSectionProperties")
    except (UserError,) + _com_errors():
        return []
    if ret != 0:
        return []
    cols = [as_list(o) for o in outs[1:]]
    n = len(cols[0])
    if any(len(c) != n for c in cols):
        return [{"story": str(st), "angle": 0.0, "width": 0.0, "thick": 0.0, "x": 0.0, "y": 0.0} for st in cols[0]]
    (story, angle, areas, lines, w_bot, t_bot, w_top, t_top, _mat,
     x_bot, y_bot, _z_bot, x_top, y_top, _z_top) = cols
    out = []
    for i in range(n):
        if int(areas[i]) + int(lines[i]) <= 0:
            continue
        bot = float(w_bot[i]) > 0
        out.append({"story": str(story[i]), "angle": float(angle[i]),
                    "width": float(w_bot[i] if bot else w_top[i]), "thick": float(t_bot[i] if bot else t_top[i]),
                    "x": float(x_bot[i] if bot else x_top[i]), "y": float(y_bot[i] if bot else y_top[i])})
    return out


@contextmanager
def units(sap, eunits):
    """Define as unidades da API durante a extração e restaura as originais ao sair."""
    original = int(call("GetPresentUnits", sap.GetPresentUnits))
    if original != eunits:
        check(call("SetPresentUnits", sap.SetPresentUnits, eunits), "SetPresentUnits")
        log.info("Unidades: %s -> %s (temporário)", UNITS_NAMES.get(original, original),
                 UNITS_NAMES.get(eunits, eunits))
    if int(call("GetPresentUnits", sap.GetPresentUnits)) != eunits:
        raise UserError(f"O ETABS não aceitou as unidades {UNITS_NAMES.get(eunits, eunits)}.")
    try:
        yield
    finally:
        if original != eunits:
            try:
                sap.SetPresentUnits(original)
                log.info("Unidades restauradas: %s", UNITS_NAMES.get(original, original))
            except _com_errors():
                log.warning("Não foi possível restaurar as unidades originais.")


def log_output_options(sap):
    setup, found = sap.Results.Setup, []
    for name in ("MultiValuedCombo", "NLStatic", "MultiStepStatic"):
        try:
            outs, ret = split_ret(getattr(setup, f"GetOption{name}")(), 1, name)
            if ret == 0:
                found.append(f"{name}={outs[0]}")
        except (UserError, AttributeError) + _com_errors():
            pass
    if found:
        log.info("Opções de output do modelo: %s", ", ".join(found))


def pier_forces(sap, combo) -> dict[str, list]:
    """
    Results.PierForce para UMA combinação (as demais são desmarcadas antes).
    Retorno: [NumberResults, Story[], Pier[], LoadCase[], Location[], P[], V2[], V3[], T[], M2[], M3[], ret]
    """
    setup = sap.Results.Setup
    check(call("DeselectAllCasesAndCombosForOutput", setup.DeselectAllCasesAndCombosForOutput),
          "Results.Setup.DeselectAllCasesAndCombosForOutput")
    check(call("SetComboSelectedForOutput", setup.SetComboSelectedForOutput, combo, True),
          f"Results.Setup.SetComboSelectedForOutput('{combo}')")
    desc = f"Results.PierForce ['{combo}']"
    outs, ret = split_ret(call(desc, sap.Results.PierForce), 11, desc)
    n = int(outs[0] or 0)
    cols = {f: as_list(a) for f, a in zip(PIER_FORCE_FIELDS, outs[1:])}
    if ret != 0 or n == 0:
        return {f: [] for f in PIER_FORCE_FIELDS}
    if any(len(v) != n for v in cols.values()):
        raise UserError(f"{desc}: vetores com tamanhos diferentes de NumberResults={n}.")
    if set(cols["LoadCase"]) != {combo}:
        raise UserError(f"{desc}: a API devolveu outros casos {sorted(set(cols['LoadCase']) - {combo})}.")
    return cols


# =============================================================================
# 3. Processamento (nenhum valor de esforço é alterado)
# =============================================================================

@dataclass(frozen=True, slots=True)
class Row:
    story: str
    pier: str
    case: str
    location: str
    values: tuple          # P, V2, V3, T, M2, M3 exatamente como devolvidos pela API
    seq: int               # posição na resposta da API (mantém Top/Bottom e Max/Min na ordem)
    etabs_story: str


@dataclass
class ModelInfo:
    edb: Path
    version: str
    piers: list[str]
    combos: list[str]
    stories: list[str]                 # de cima para baixo
    elevations: dict[str, float]
    pier_stories: dict[str, list[str]]
    pier_geometry: dict[str, list[dict]] = field(default_factory=dict)   # ver pier_sections()


def natural_key(text: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text)]


def select(available, names=None, regex=None, prefix=None, exclude=(), what="itens"):
    available = list(dict.fromkeys(available))
    if names:
        for n in names:
            if n not in available:
                log.warning("%s pedido não existe no modelo: %s", what, n)
        chosen = [n for n in dict.fromkeys(names) if n in available]
    elif regex:
        try:
            chosen = [n for n in available if re.search(regex, n)]
        except re.error as exc:
            raise UserError(f"Expressão regular inválida ({what}): {regex!r} - {exc}") from exc
    elif prefix:
        chosen = [n for n in available if n.startswith(prefix)]
    else:
        chosen = available
    return [n for n in chosen if n not in set(exclude or ())]


def select_for_export(info: ModelInfo, combo_regex=None, combos=None, piers=None) -> tuple[list[str], list[str]]:
    """Piers e combinações a exportar. Listas explícitas (escolhidas na janela) têm prioridade."""
    if combos is not None or piers is not None:
        chosen_p = select(info.piers, names=piers, what="Pier") if piers is not None else \
            select(info.piers, PIER_LIST, PIER_REGEX, PIER_PREFIX, PIER_EXCLUDE, "Pier")
        chosen_c = select(info.combos, names=combos, what="Combinação") if combos is not None else \
            select(info.combos, COMBINATION_LIST, COMBINATION_REGEX, COMBINATION_PREFIX, what="Combinação")
        if not chosen_p:
            raise UserError("Nenhum Pier selecionado.")
        if not chosen_c:
            raise UserError("Nenhuma combinação selecionada.")
        return chosen_p, chosen_c
    piers = select(info.piers, PIER_LIST, PIER_REGEX, PIER_PREFIX, PIER_EXCLUDE, "Pier")
    if combo_regex:
        combos = select(info.combos, regex=combo_regex, what="Combinação")
    else:
        combos = select(info.combos, COMBINATION_LIST, COMBINATION_REGEX, COMBINATION_PREFIX,
                        what="Combinação")
    if not piers:
        raise UserError("Nenhum Pier selecionado (confira PIER_LIST / PIER_REGEX / PIER_PREFIX "
                        "e se o modelo tem Pier Labels).")
    if not combos:
        raise UserError(f"Nenhuma combinação selecionada ({combo_regex or COMBINATION_REGEX!r}). "
                        "Rode com --listar para ver os nomes das combinações.")
    return piers, combos


def face_of(pier: str) -> tuple[str, int] | None:
    """P8C -> ("P8", 3); P8-3 -> ("P8", 3); None se o Pier não for face de pilar poligonal."""
    if FACE_LETTER_REGEX:
        m = re.match(FACE_LETTER_REGEX, pier)
        if m:
            return m["base"], ord(m["face"].upper()) - ord("A") + 1
    if FACE_NUMBER_REGEX:
        m = re.match(FACE_NUMBER_REGEX, pier)
        if m:
            return m["base"], int(m["face"])
    return None


def face_output_name(pier: str) -> str:
    """Nome gravado para a TQS: P8C -> P8-3 (arquivo, coluna Pier e .txt)."""
    f = face_of(pier)
    return f"{f[0]}-{f[1]}" if f else pier


def face_faixa(output_name: str) -> int:
    """
    Faixa do TQS de uma face, gravada no .txt.
    Por enquanto = número da face (P8-3 -> 3), como em todos os .txt de referência.
    A regra real do TQS ainda será investigada.
    """
    return int(output_name.rsplit("-", 1)[1])


def polygonal_groups(piers, quiet=False) -> "OrderedDict[str, list[str]]":
    """{pilar: [faces em ordem]} para os Piers com 2 ou mais faces (P1A, P1B... ou P1-1, P1-2...)."""
    found = defaultdict(list)
    for p in piers:
        info = face_of(p)
        if info:
            found[info[0]].append(p)
    groups = OrderedDict()
    for base in sorted(found, key=natural_key):
        faces = sorted(found[base], key=lambda p: (face_of(p)[1], p))
        numbers = [face_of(f)[1] for f in faces]
        dup = sorted({f for f in faces if numbers.count(face_of(f)[1]) > 1})
        if dup:
            raise UserError(f"O pilar {base} tem faces com o mesmo número: {', '.join(dup)} "
                            f"(todas viram {face_output_name(dup[0])}). Renomeie os Piers no ETABS.")
        if len(faces) < 2:
            if not quiet:
                log.warning("%s é a única face de %s; tratado como pilar comum.", faces[0], base)
            continue
        groups[base] = faces
    return groups


def output_names(groups) -> dict[str, str]:
    """{Pier do ETABS: nome gravado} das faces dos pilares poligonais."""
    return {f: face_output_name(f) for faces in groups.values() for f in faces}


def load_story_map(path: Path) -> dict:
    text = None
    for enc in ("utf-8-sig", "cp1252"):
        try:
            text = path.read_text(encoding=enc)
            break
        except UnicodeDecodeError:
            pass
    lines = [ln for ln in (text or "").splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if not lines:
        raise UserError(f"{path.name} está vazio ou ilegível.")
    delim = ";" if ";" in lines[0] else ","
    mapping, conflicts = {}, []
    for row in list(csv.reader(lines, delimiter=delim))[1:]:
        if len(row) < 2 or not row[0].strip() or not row[1].strip():
            continue
        pier = row[2].strip() if len(row) > 2 else ""
        key = (pier or None, row[0].strip())
        if key in mapping and mapping[key] != row[1].strip():
            conflicts.append(f"{key[1]} ({key[0] or 'todos'})")
        mapping.setdefault(key, row[1].strip())
    if conflicts:
        raise UserError(f"{path.name}: Story com mais de um valor: {', '.join(conflicts)}")
    return mapping


def save_story_map(path: Path, mapping: dict):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(["ETABS", "SAIDA", "PIER"])
    buf.write("# Story do ETABS -> lance do TQS. Linhas com PIER valem só para aquele pilar\r\n"
              "# e também para as faces dele (PIER = P8 vale para P8A, P8B... ou P8-1, P8-2...).\r\n")
    for (pier, story), value in mapping.items():
        if pier is None:
            w.writerow([story, value])
    for (pier, story), value in mapping.items():
        if pier is not None:
            w.writerow([story, value, pier])
    path.write_text(buf.getvalue(), encoding="utf-8-sig", newline="")


def map_story(mapping: dict, pier: str, story: str):
    """
    Lance do Story para o Pier: exceção da face (pelo nome do ETABS, P8C, ou pelo gravado, P8-3)
    > exceção do pilar (P8) > geral.
    """
    face = face_of(pier)
    names = [pier] + ([face_output_name(pier), face[0]] if face else [])
    for key in [(n, story) for n in names] + [(None, story)]:
        if key in mapping:
            return mapping[key]
    return None


def missing_story_map(info: ModelInfo, piers, mapping: dict) -> dict[str, list[str]]:
    """{Story: [Piers]} dos Stories com objetos de Pier que não têm lance."""
    missing = defaultdict(list)
    for p in piers:
        for s in info.pier_stories.get(p, []):
            if map_story(mapping, p, s) is None:
                missing[s].append(p)
    return dict(missing)


def apply_story_map(rows, mapping):
    missing = sorted({f"{r.etabs_story} ({r.pier})" for r in rows
                      if map_story(mapping, r.pier, r.etabs_story) is None})
    if missing:
        msg = "Stories sem lance do TQS: " + ", ".join(missing[:20])
        if STORY_MAP_STRICT:
            raise UserError(msg + "\nPreencha os lances (story_map.csv) ou use STORY_MAP_STRICT = False.")
        log.warning("%s (mantido o nome do ETABS)", msg)
    return [replace(r, story=map_story(mapping, r.pier, r.etabs_story) or r.etabs_story) for r in rows]


def check_lance_conflicts(rows):
    """Dois Stories do ETABS no mesmo lance do TQS, para o mesmo Pier, é erro de mapeamento."""
    by = defaultdict(set)
    for r in rows:
        by[(r.pier, r.story)].add(r.etabs_story)
    bad = [f"{p}: {', '.join(sorted(s))} -> {lance}" for (p, lance), s in by.items() if len(s) > 1]
    if bad:
        raise UserError("Stories diferentes do ETABS mapeados para o mesmo lance do TQS:\n  "
                        + "\n  ".join(bad[:10]))


def sort_rows(rows, elevations, combo_order):
    """Story de cima para baixo > combinação (ordem da seleção) > ordem da API."""
    appearance = list(dict.fromkeys(r.etabs_story for r in rows))
    stories = sorted((s for s in appearance if s in elevations), key=lambda s: -elevations[s])
    stories += [s for s in appearance if s not in elevations]
    s_rank = {s: i for i, s in enumerate(stories)}
    c_rank = {c: i for i, c in enumerate(combo_order)}
    return sorted(rows, key=lambda r: (s_rank[r.etabs_story], c_rank.get(r.case, 1 << 30), r.seq))


# =============================================================================
# 4. Arquivos de saída (CSV e TXT)
# =============================================================================

def fmt_number(value: float) -> str:
    """Arredonda "meio para cima" como o Excel, vírgula decimal, sem "-0,00"."""
    if not math.isfinite(value):
        raise ValueError(f"valor inválido: {value!r}")
    d = Decimal(repr(float(value))).quantize(Decimal(1).scaleb(-DECIMALS), rounding=ROUND_HALF_UP)
    if d == 0:
        d = abs(d)
    return f"{d:.{DECIMALS}f}".replace(".", DECIMAL_SEPARATOR)


def safe_filename(name: str) -> str:
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip().rstrip(".") or "_"
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10))}
    return "_" + clean if clean.upper() in reserved else clean


def write_csv(path: Path, rows):
    n = len(TEXT_COLUMNS) + len(VALUE_COLUMNS)
    try:
        with open(path, "w", encoding=CSV_ENCODING, newline="") as fh:
            w = csv.writer(fh, delimiter=FIELD_SEPARATOR, lineterminator="\r\n")
            w.writerow([TABLE_TITLE] + [""] * (n - 1))
            w.writerow(TEXT_COLUMNS + VALUE_COLUMNS)
            w.writerow([""] * len(TEXT_COLUMNS) + [FORCE_LABEL] * 3 + [MOMENT_LABEL] * 3)
            for r in rows:
                w.writerow([r.story, r.pier, r.case, "Combination", r.location]
                           + [fmt_number(v) for v in r.values])
    except UnicodeEncodeError as exc:
        raise UserError(f"{path.name}: caractere {exc.object[exc.start:exc.end]!r} não existe em "
                        f"{CSV_ENCODING}. Use CSV_ENCODING = 'utf-8-sig'.") from None


def build_txt(base: str, faces, rows_by_pier) -> str:
    """
    Arquivo <pilar>.txt: para cada lance do TQS (de baixo para cima), as faces que existem
    nele e a faixa de cada uma. `faces` e as chaves de rows_by_pier são os nomes gravados
    (P8-1, P8-2...). Separador TAB, CRLF, sem quebra de linha no fim:
        lance<TAB>1
        P8-1<TAB>1
        P8-2<TAB>2
        lance<TAB>6
        ...
    """
    lances = defaultdict(set)
    for face in faces:
        for r in rows_by_pier.get(face, []):
            try:
                lances[int(r.story)].add(face)
            except ValueError:
                raise UserError(f"{base}.txt: o Story '{r.story}' da face {face} não é um número de "
                                "lance do TQS. Preencha os lances no passo \"Lances TQS\" "
                                "(story_map.csv).") from None
    lines = []
    for lance in sorted(lances):
        lines.append(f"lance\t{lance}")
        lines += [f"{face}\t{face_faixa(face)}" for face in faces if face in lances[lance]]
    return "\r\n".join(lines)


def write_etb(out_dir: Path, csv_files: dict, txt_files: dict) -> Path | None:
    """
    Grava tudo numa pasta temporária e só então troca pela pasta ETB, que nunca fica pela
    metade. A pasta ETB anterior é renomeada para ETB_anterior_<data>. Devolve esse nome.
    """
    tmp = out_dir.with_name(out_dir.name + "_gerando")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    backup = None
    try:
        used = set()
        for pier, rows in csv_files.items():
            base = name = safe_filename(pier)
            k = 2
            while name.lower() in used:
                name, k = f"{base}_{k}", k + 1
            used.add(name.lower())
            if name != pier:
                log.warning("Pier '%s' gravado como '%s.csv'.", pier, name)
            write_csv(tmp / f"{name}.csv", rows)
        for base, text in txt_files.items():
            (tmp / f"{safe_filename(base)}.txt").write_bytes(text.encode(TXT_ENCODING))
        if out_dir.exists():
            if any(out_dir.iterdir()):
                backup = out_dir.with_name(f"{out_dir.name}_anterior_{datetime.now():%Y%m%d_%H%M%S}")
                try:
                    out_dir.rename(backup)
                except PermissionError:
                    raise UserError(f"Não foi possível substituir a pasta {out_dir.name}: algum arquivo "
                                    "dela está aberto (Excel? TQS?). Feche e rode novamente.") from None
            else:
                out_dir.rmdir()
        tmp.rename(out_dir)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return backup


# =============================================================================
# 5. Extração
# =============================================================================

def read_model(sap, edb: Path) -> ModelInfo:
    try:
        version = str(split_ret(sap.GetVersion(), 2, "GetVersion")[0][0])
    except (UserError,) + _com_errors():
        version = "?"
    log.info("ETABS %s | modelo analisado (travado): %s", version, "sim" if is_locked(sap) else "não")
    piers = name_list(sap.PierLabel, "PierLabel.GetNameList")
    combos = name_list(sap.RespCombo, "RespCombo.GetNameList")
    with units(sap, OUTPUT_EUNITS):                      # cotas e geometria na unidade de saída
        elevations = story_elevations(sap)
        geometry = {p: pier_sections(sap, p) for p in piers}
    order = name_list(sap.Story, "Story.GetNameList")
    stories = sorted((s for s in order if s in elevations), key=lambda s: -elevations[s])
    stories += [s for s in order if s not in elevations]
    p_stories = {p: [g["story"] for g in geometry[p]] for p in piers}
    log.info("Encontrados %d Piers, %d combinações e %d Stories.", len(piers), len(combos), len(stories))
    return ModelInfo(edb, version, piers, combos, stories, elevations, p_stories, geometry)


def check_analysis(sap, combos):
    status = case_status(sap)
    if not any(s == CASE_FINISHED for s in status.values()):
        if not RUN_ANALYSIS_IF_NEEDED:
            raise UserError("O modelo não tem resultados de análise. Rode a análise no ETABS (F5), "
                            "salve, e execute novamente (ou use RUN_ANALYSIS_IF_NEEDED = True).")
        run_analysis(sap)
        status = case_status(sap)
    not_run = sorted(c for c, s in status.items() if s != CASE_FINISHED)
    if not not_run:
        return
    log.info("Load Cases sem análise concluída: %s", ", ".join(not_run))
    for combo in combos:
        pending, stack, seen = set(), [combo], set()
        while stack:
            name = stack.pop()
            if name in seen:
                continue
            seen.add(name)
            try:
                for kind, item in combo_items(sap, name):
                    if kind == CNAME_LOAD_COMBO:
                        stack.append(item)
                    elif item in not_run:
                        pending.add(item)
            except UserError:
                pass
        if pending:
            log.warning("Combinação %s depende de casos não analisados: %s", combo, ", ".join(sorted(pending)))


def run_analysis(sap):
    log.info("Rodando a análise (pode demorar)...")
    progress("analise", text="RunAnalysis")
    t0 = time.perf_counter()
    check(call("Analyze.RunAnalysis", sap.Analyze.RunAnalysis), "Analyze.RunAnalysis")
    if not any(s == CASE_FINISHED for s in case_status(sap).values()):
        raise UserError("A análise terminou sem nenhum caso concluído.")
    log.info("Análise concluída em %.0f s.", time.perf_counter() - t0)


def extract(sap, combos, wanted=None, seq0=0, stage="etapa1") -> tuple[list[Row], list[str]]:
    """Pier Forces das combinações, uma chamada por combinação. wanted=None = todos os Piers."""
    rows, no_results, seq = [], [], seq0
    with units(sap, OUTPUT_EUNITS):
        for i, combo in enumerate(combos, 1):
            progress(stage, i - 1, len(combos), combo)
            t0 = time.perf_counter()
            cols = pier_forces(sap, combo)
            n = len(cols["Story"])
            if n == 0:
                no_results.append(combo)
                log.warning("[%d/%d] %s: SEM resultados", i, len(combos), combo)
                continue
            for k in range(n):
                pier = str(cols["Pier"][k])
                if wanted is None or pier in wanted:
                    story = str(cols["Story"][k])
                    rows.append(Row(story, pier, combo, str(cols["Location"][k]),
                                    tuple(float(cols[f][k]) for f in VALUE_COLUMNS), seq + k, story))
            seq += n
            log.info("[%d/%d] %s: %d resultados (%.1fs)", i, len(combos), combo, n,
                     time.perf_counter() - t0)
    progress(stage, len(combos), len(combos), "")
    return rows, no_results


def prepare_work_copy(edb: Path) -> Path:
    """Copia o .EDB (e, se possível, os arquivos de resultado) para a pasta de trabalho."""
    work = edb.parent / WORK_SUBFOLDER
    if work.exists():
        if not (work / WORK_MARKER).exists():
            raise UserError(f"A pasta {work} já existe e não foi criada por este programa. "
                            "Renomeie-a ou mude WORK_SUBFOLDER.")
        shutil.rmtree(work)
    work.mkdir()
    (work / WORK_MARKER).write_text("Cópia temporária do modelo criada pelo exportar_pier_forces.py.\n"
                                    "Pode ser apagada.\n", encoding="utf-8")
    target = work / edb.name
    progress("copia", text=edb.name)
    shutil.copy2(edb, target)
    if not COPY_RESULTS_TO_WORK:
        return target
    extras = [p for p in edb.parent.iterdir()
              if p.is_file() and p.stem.lower() == edb.stem.lower() and p.suffix.lower() != ".edb"]
    size = sum(p.stat().st_size for p in extras) / 2**20
    log.info("Copiando o modelo e %d arquivo(s) de resultado (%.0f MB) para %s ...",
             len(extras), size, work.name)
    copied = []
    try:
        for i, p in enumerate(extras):
            progress("copia", i, len(extras), p.name)
            shutil.copy2(p, work / p.name)
            copied.append(work / p.name)
    except OSError as exc:
        log.warning("Não foi possível copiar os resultados (%s); a cópia será reanalisada.", exc)
        for p in copied:
            p.unlink(missing_ok=True)
    return target


def remove_work_copy(work: Path):
    if not (work / WORK_MARKER).exists():
        return
    for attempt in range(5):
        try:
            shutil.rmtree(work)
            log.info("Cópia de trabalho apagada.")
            return
        except OSError as exc:
            if attempt == 4:
                log.warning("Não foi possível apagar a cópia de trabalho %s (%s). Pode apagá-la à mão.",
                            work, exc)
            time.sleep(2)


def reassign_faces(sap, groups) -> bool:
    """
    Na CÓPIA do modelo: todo objeto (área ou barra) com Pier = face passa a ter Pier = pilar.
    O ETABS aceita trocar Pier Labels com o modelo analisado (os resultados continuam valendo).
    Se mesmo assim ele recusar, a cópia é destravada e reanalisada; devolve True nesse caso.
    """
    face_base = {f: base for base, faces in groups.items() for f in faces}
    state = {"unlocked": False}

    def modify(desc, func, *args):
        ret = int(call(desc, func, *args))
        if ret != 0 and not state["unlocked"] and is_locked(sap):
            log.info("O ETABS não aceitou alterar o Pier Label com o modelo analisado; destravando a "
                     "cópia (os resultados dela serão recalculados).")
            check(call("SetModelIsLocked", sap.SetModelIsLocked, False), "SetModelIsLocked(False)")
            state["unlocked"] = True
            ret = int(call(desc, func, *args))
        check(ret, desc)

    targets, per_face = [], Counter()
    for kind, obj in (("AreaObj", sap.AreaObj), ("FrameObj", sap.FrameObj)):
        names = name_list(obj, f"{kind}.GetNameList")
        log.info("Lendo o Pier de %d objeto(s) %s...", len(names), kind)
        for i, name in enumerate(names, 1):
            if i % 500 == 1:
                progress("reatribuicao", i - 1, len(names), f"Lendo {kind}")
            outs, ret = split_ret(call(f"{kind}.GetPier", obj.GetPier, name), 1, f"{kind}.GetPier")
            pier = str(outs[0]) if ret == 0 else ""
            if pier in face_base:
                targets.append((kind, obj, name, face_base[pier]))
                per_face[pier] += 1
            if i % 20000 == 0:
                log.info("  %d/%d", i, len(names))
    for f in face_base:
        if not per_face[f]:
            log.warning("Nenhum objeto com o Pier %s foi encontrado.", f)

    labels = set(name_list(sap.PierLabel, "PierLabel.GetNameList"))
    for base in groups:
        if base not in labels:
            modify(f"PierLabel.SetPier('{base}')", sap.PierLabel.SetPier, base)
    for i, (kind, obj, name, base) in enumerate(targets):
        if i % 100 == 0:
            progress("reatribuicao", i, len(targets), f"Reatribuindo -> {base}")
        modify(f"{kind}.SetPier('{name}', '{base}')", obj.SetPier, name, base, OBJECT_ITEM)
    progress("reatribuicao", len(targets), len(targets), "")
    for base, faces in groups.items():
        log.info("  %s <- %s (%d objetos)", base, ", ".join(faces), sum(per_face[x] for x in faces))
    return state["unlocked"]


def _same_values(a, b) -> bool:
    return all(abs(x - y) <= 1e-6 + 1e-6 * max(abs(x), abs(y)) for x, y in zip(a, b))


def compare_other_piers(ref_rows, new_rows, skip):
    """Os Piers que não foram reatribuídos precisam ter os mesmos esforços na cópia."""
    def by_pier(rows):
        # a ordem dos blocos Story/Pier na resposta da API pode mudar; dentro de cada
        # Story/combinação a ordem (Top/Bottom, Max/Min) precisa ser a mesma
        d = defaultdict(lambda: defaultdict(list))
        for r in sorted(rows, key=lambda r: r.seq):
            if r.pier not in skip:
                d[r.pier][(r.etabs_story, r.case)].append((r.location, r.values))
        return d

    def same(a, b):
        return a.keys() == b.keys() and all(
            len(a[k]) == len(b[k]) and all(x[0] == y[0] and _same_values(x[1], y[1])
                                           for x, y in zip(a[k], b[k])) for k in a)

    ref, new = by_pier(ref_rows), by_pier(new_rows)
    bad = [p for p in ref if not same(ref[p], new.get(p, {}))]
    if bad:
        log.warning("Conferência: %d Pier(s) com esforços diferentes na cópia do modelo: %s. "
                    "O modelo salvo pode estar diferente do que está aberto no ETABS.",
                    len(bad), ", ".join(bad[:10]))
    else:
        log.info("Conferência: os %d Piers não reatribuídos têm esforços idênticos na cópia.", len(ref))


def extract_full_piers(etabs: Etabs, work_edb: Path, groups, combos, ref_rows) -> tuple[list[Row], bool]:
    """Etapa 2: reatribui as faces ao pilar na cópia e extrai os esforços do pilar completo."""
    session = etabs.open_model(work_edb, own_instance=True)
    sap = session.sap
    reanalyzed = reassign_faces(sap, groups)
    if reanalyzed or not is_locked(sap) or not any(
            s == CASE_FINISHED for s in case_status(sap).values()):
        run_analysis(sap)
        reanalyzed = True
    bases = set(groups)
    seq0 = max((r.seq for r in ref_rows), default=0) + 1
    rows, _ = extract(sap, combos, None, seq0, "etapa2")
    if not reanalyzed and not bases & {r.pier for r in rows}:
        log.info("A cópia não devolveu os pilares completos sem reanalisar; reanalisando...")
        if is_locked(sap):
            check(call("SetModelIsLocked", sap.SetModelIsLocked, False), "SetModelIsLocked(False)")
        run_analysis(sap)
        reanalyzed = True
        rows, _ = extract(sap, combos, None, seq0, "etapa2")

    faces = {f for g in groups.values() for f in g}
    left = sorted({r.pier for r in rows} & faces, key=natural_key)
    if left:
        raise UserError("Reatribuição incompleta: a cópia ainda tem esforços em " + ", ".join(left))
    missing = sorted(bases - {r.pier for r in rows}, key=natural_key)
    if missing:
        raise UserError("A cópia não devolveu esforços para os pilares completos: " + ", ".join(missing))
    compare_other_piers(ref_rows, rows, faces | bases)
    return [r for r in rows if r.pier in bases], reanalyzed


@contextmanager
def log_to_file(folder: Path):
    handler = None
    try:
        handler = logging.FileHandler(folder / "exportar_pier_forces.log", mode="w", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
        log.addHandler(handler)
    except OSError:
        handler = None
    try:
        yield
    finally:
        if handler:
            log.removeHandler(handler)
            handler.close()


@dataclass
class ExportResult:
    out_dir: Path
    csv_count: int
    txt_count: int
    backup: Path | None
    reanalyzed: bool
    warnings: list[str] = field(default_factory=list)


def export_model(etabs: Etabs, edb: Path, mapping: dict | None, full_polygonal: bool | None = None,
                 combo_regex: str | None = None, combos: list[str] | None = None,
                 piers: list[str] | None = None) -> ExportResult:
    full_polygonal = EXPORT_FULL_POLYGONAL if full_polygonal is None else full_polygonal
    folder = edb.parent
    warnings = []
    with log_to_file(folder):
        log.info("Modelo: %s", edb)
        if not has_results(edb):
            log.warning("Não há arquivos de resultado (.Y00/.Y) ao lado do modelo; ele pode não estar analisado.")
        work_dir, reanalyzed = None, False
        try:
            progress("conexao", text=edb.name)
            session = etabs.open_model(edb)
            sap = session.sap
            info = read_model(sap, edb)
            piers, combos = select_for_export(info, combo_regex, combos, piers)
            log.info("Selecionados: %d Piers, %d combinações (%s).", len(piers), len(combos),
                     ", ".join(combos[:6]) + (" ..." if len(combos) > 6 else ""))
            if mapping:
                missing = missing_story_map(info, piers, mapping)
                if missing and STORY_MAP_STRICT:
                    raise UserError("Stories sem lance do TQS:\n  " + "\n  ".join(
                        f"{s} ({', '.join(p[:6])}{' ...' if len(p) > 6 else ''})" for s, p in missing.items()))
            elif full_polygonal and polygonal_groups(piers, quiet=True):
                raise UserError("Os arquivos .txt dos pilares poligonais precisam dos lances do TQS. "
                                f"Preencha os lances (crie {STORY_MAP_FILENAME} ao lado do modelo).")
            else:
                log.warning("Sem %s: a coluna Story terá o nome do ETABS.", STORY_MAP_FILENAME)
            check_analysis(sap, combos)
            log_output_options(sap)

            log.info("ETAPA 1: esforços dos Piers como estão assinalados no modelo")
            rows, no_results = extract(sap, combos, set(piers))
            if not rows:
                raise UserError("Nenhum resultado de Pier Force para as combinações selecionadas.")
            present = {r.pier for r in rows}
            groups = polygonal_groups([p for p in piers if p in present]) if full_polygonal else {}
            if groups:
                log.info("Pilares poligonais: %s", "; ".join(f"{b} ({', '.join(g)})" for b, g in groups.items()))
                for base in groups:
                    if base in present:
                        log.warning("O Pier %s já tinha objetos no modelo; %s.csv virá do pilar completo "
                                    "(faces + objetos que já eram %s).", base, base, base)
                log.info("ETAPA 2: pilares completos, numa cópia do modelo (o original não é alterado)")
                work_edb = prepare_work_copy(edb)
                work_dir = work_edb.parent
                full_rows, reanalyzed = extract_full_piers(etabs, work_edb, groups, combos, rows)
                rows = [r for r in rows if r.pier not in groups] + full_rows
        finally:
            etabs.close_all()
            if work_dir and not KEEP_WORK_COPY:
                remove_work_copy(work_dir)

        rows = sort_rows(rows, info.elevations, combos)
        if mapping:
            rows = apply_story_map(rows, mapping)
            check_lance_conflicts(rows)
        # faces: P8A -> P8-1 (nome do arquivo, coluna Pier e .txt)
        renamed = output_names(groups)
        taken = {r.pier for r in rows if r.pier not in renamed}
        clash = sorted({v for v in renamed.values() if v in taken})
        if clash:
            raise UserError("O nome gravado de uma face coincide com outro Pier do modelo: " + ", ".join(clash))
        for etabs_name, out_name in renamed.items():
            if etabs_name != out_name:
                log.info("Face %s gravada como %s.", etabs_name, out_name)
        rows = [replace(r, pier=renamed.get(r.pier, r.pier)) for r in rows]

        per_loc = Counter((r.pier, r.etabs_story, r.case, r.location) for r in rows)
        multi = sorted({k[2] for k, v in per_loc.items() if v > 1})
        if multi:
            log.info("Combinações com 2 pares Top/Bottom por Story (envelope Max/Min, na ordem da API): %s",
                     ", ".join(multi))
        unbalanced = sorted({k[:3] for k in per_loc
                             if per_loc[k[:3] + ("Top",)] != per_loc[k[:3] + ("Bottom",)]})
        if unbalanced:
            log.warning("%d grupo(s) Pier/Story/Combinação com número diferente de Top e Bottom, ex.: %s",
                        len(unbalanced), unbalanced[:3])

        grouped = defaultdict(list)
        for r in rows:
            grouped[r.pier].append(r)
        csv_files = OrderedDict((p, grouped[p]) for p in sorted(grouped, key=natural_key))
        txt_files = OrderedDict((base, build_txt(base, [renamed[f] for f in faces], grouped))
                                for base, faces in groups.items())

        out_dir = folder / OUTPUT_SUBFOLDER
        progress("gravacao", text=str(out_dir))
        backup = write_etb(out_dir, csv_files, txt_files)
        print()
        log.info("Exportação concluída: %d CSV(s) e %d TXT(s) em %s", len(csv_files), len(txt_files), out_dir)
        if backup:
            log.info("A pasta %s anterior foi renomeada para %s.", out_dir.name, backup.name)
        empty = [p for p in piers if p not in grouped and p not in renamed]
        if empty:
            warnings.append(f"Piers sem resultados (sem arquivo): {', '.join(empty)}")
        if no_results:
            warnings.append(f"Combinações SEM resultados: {', '.join(no_results)}")
        for w in warnings:
            log.warning("%s", w)
        return ExportResult(out_dir, len(csv_files), len(txt_files), backup, reanalyzed, warnings)


# =============================================================================
# 6. Comparação opcional com arquivos de referência (--comparar DIR)
# =============================================================================

def compare_with(reference_dir: Path, output_dir: Path) -> int:
    if not reference_dir.is_dir():
        raise UserError(f"Pasta de referência não encontrada: {reference_dir}")
    empty_line = FIELD_SEPARATOR * (len(TEXT_COLUMNS) + len(VALUE_COLUMNS) - 1)
    ok = bad = 0
    print(f"\nComparando {output_dir} com {reference_dir}")
    refs = sorted([*reference_dir.glob("*.csv"), *reference_dir.glob("*.txt")], key=lambda p: natural_key(p.name))
    for ref in refs:
        gen = output_dir / ref.name
        if not gen.exists():
            print(f"  {ref.name}: não gerado")
            bad += 1
            continue
        enc = CSV_ENCODING if ref.suffix.lower() == ".csv" else TXT_ENCODING
        g = [ln for ln in gen.read_text(enc).splitlines() if ln != empty_line]
        r = [ln for ln in ref.read_text("cp1252", errors="replace").splitlines() if ln != empty_line]
        diff = [(a, b) for a, b in zip(g, r) if a != b]
        if not diff and len(g) == len(r):
            print(f"  {ref.name}: idêntico")
            ok += 1
            continue
        bad += 1
        only_story = all(a.split(";")[1:] == b.split(";")[1:] for a, b in diff) and len(g) == len(r)
        hint = " (só a coluna Story difere -> confira os lances)" if only_story else ""
        print(f"  {ref.name}: {len(diff)} linha(s) diferentes, linhas {len(g)} x {len(r)}{hint}")
        for a, b in diff[:3]:
            print(f"      gerado:     {a}\n      referência: {b}")
    extra = sorted(p.name for p in output_dir.iterdir() if not (reference_dir / p.name).exists())
    if extra:
        print(f"  Gerados sem referência: {', '.join(extra)}")
    print(f"Idênticos: {ok} | com diferenças: {bad}")
    return 0 if bad == 0 else 1


# =============================================================================
# 7. Interface (janela nativa com HTML: pywebview + WebView2 do Edge)
#    A interface fica em ui/ (index.html, app.css, app.js). A classe Api é a
#    ponte: o JavaScript chama window.pywebview.api.<método>() e consulta poll().
# =============================================================================

APP_NAME = "ExportarPierForces"


def ui_dir() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "ui"


def settings_path() -> Path:
    return Path(os.environ.get("APPDATA") or Path.home()) / APP_NAME / "settings.json"


def load_settings() -> dict:
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(data: dict):
    path = settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        log.warning("Não foi possível salvar as preferências (%s).", exc)


def _model_key(path) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def model_card(path: Path) -> dict:
    """Resumo do arquivo .EDB para a tela inicial."""
    st = path.stat()
    return {"path": str(path), "name": path.name, "folder": str(path.parent),
            "size_mb": round(st.st_size / 2**20, 1),
            "modified": datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y %H:%M"),
            "analyzed": has_results(path),
            "story_map": (path.parent / STORY_MAP_FILENAME).is_file(),
            "etb": (path.parent / OUTPUT_SUBFOLDER).is_dir()}


def mapping_to_json(mapping: dict | None) -> dict:
    mapping = mapping or {}
    return {"general": {s: v for (p, s), v in mapping.items() if p is None},
            "exceptions": [{"pier": p, "story": s, "lance": v}
                           for (p, s), v in mapping.items() if p is not None]}


def mapping_from_json(data: dict) -> dict:
    mapping = {}
    for story, value in (data.get("general") or {}).items():
        if str(value).strip():
            mapping[(None, str(story))] = str(value).strip()
    for i, e in enumerate(data.get("exceptions") or [], 1):
        p, s, v = (str(e.get(k) or "").strip() for k in ("pier", "story", "lance"))
        if not (p or s or v):
            continue
        if not (p and s and v):
            raise UserError(f"Exceção {i} incompleta: preencha Pilar, Story e Lance (ou remova a linha).")
        if mapping.get((p, s), v) != v:
            raise UserError(f"Exceção repetida com lances diferentes: {p} / {s}.")
        mapping[(p, s)] = v
    return mapping


def length_unit() -> str:
    """Unidade de comprimento de OUTPUT_EUNITS (Ton_m_C -> m)."""
    parts = UNITS_NAMES.get(OUTPUT_EUNITS, "").split("_")
    return parts[1] if len(parts) > 1 else ""


def model_payload(info: ModelInfo) -> dict:
    """Tudo o que a interface precisa saber do modelo lido."""
    with_objects = {p for p, s in info.pier_stories.items() if s}
    usable = [p for p in info.piers if p in with_objects] if with_objects else list(info.piers)
    groups = polygonal_groups(usable, quiet=True)
    in_group = {f: base for base, faces in groups.items() for f in faces}
    default_combos = select(info.combos, COMBINATION_LIST, COMBINATION_REGEX, COMBINATION_PREFIX)
    return {
        "path": str(info.edb), "version": info.version,
        "stories": [{"name": s, "elev": info.elevations.get(s)} for s in info.stories],
        "piers": [{"name": p, "stories": info.pier_stories.get(p, []), "group": in_group.get(p),
                   "out": face_output_name(p) if p in in_group else p,
                   "geom": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in g.items()}
                            for g in info.pier_geometry.get(p, [])],
                   "has_objects": (p in with_objects) if with_objects else True} for p in info.piers],
        "groups": [{"base": b, "faces": faces, "outs": [face_output_name(f) for f in faces]}
                   for b, faces in groups.items()],
        "combos": info.combos, "default_combos": default_combos,
        "default_rule": COMBINATION_REGEX or COMBINATION_PREFIX or "",
        "length_unit": length_unit(),
    }


class QueueLogHandler(logging.Handler):
    def __init__(self, events):
        super().__init__()
        self.events = events

    def emit(self, record):
        self.events.put(("log", record.levelno, record.getMessage(), record.created))


class Worker(threading.Thread):
    """Executa as tarefas do ETABS fora da interface (toda a API COM fica nesta thread)."""

    def __init__(self, events):
        super().__init__(daemon=True)
        self.jobs = queue.Queue()
        self.events = events
        self.etabs = Etabs()
        self.busy = False

    def run(self):
        com = None
        try:
            import comtypes
            comtypes.CoInitialize()
            com = comtypes
        except (ImportError, OSError):
            pass
        while True:
            job = self.jobs.get()
            if job is None:
                break
            name, func = job
            self.busy = True
            try:
                self.events.put(("ok", name, func(self), None))
            except UserError as exc:
                log.error("%s", exc)
                self.etabs.close_all()
                self.events.put(("erro", name, str(exc), None))
            except Exception as exc:  # noqa: BLE001 - mostrado ao usuário
                log.exception("Erro inesperado:")
                self.etabs.close_all()
                self.events.put(("erro", name, f"Erro inesperado: {exc}", None))
            finally:
                self.busy = False
        self.etabs.close_all()
        if com:
            com.CoUninitialize()


class Api:
    """Métodos chamados pelo JavaScript (window.pywebview.api.*). Atributos com _ não são expostos."""

    def __init__(self):
        global _progress_sink
        self._events = queue.Queue()
        self._worker = Worker(self._events)
        self._worker.start()
        self._handler = QueueLogHandler(self._events)
        log.addHandler(self._handler)
        _progress_sink = self._on_progress
        self._window = None
        self._info: ModelInfo | None = None
        self._settings = load_settings()

    def _on_progress(self, data: dict):
        self._events.put(("progress", data, None, None))

    # ---- início ----------------------------------------------------------------
    def boot(self) -> dict:
        self._worker.jobs.put(("diag", lambda w: {"api": diagnose_api(),
                                                 "installs": [p.parent.name for p in etabs_installs()]}))
        guess = guess_model(program_dir())
        recent = [model_card(Path(p)) for p in self._settings.get("recent", []) if Path(p).is_file()][:6]
        if guess and not any(same_file(r["path"], guess) for r in recent):
            recent.insert(0, model_card(guess))
        return {"version": __version__, "recent": recent, "theme": self._settings.get("theme", "dark"),
                "output": OUTPUT_SUBFOLDER, "story_map": STORY_MAP_FILENAME}

    def set_theme(self, theme: str):
        self._settings["theme"] = "light" if theme == "light" else "dark"
        save_settings(self._settings)

    # ---- modelo ----------------------------------------------------------------
    def _dialog(self, directory: str, file_types=()):
        import webview
        dialog = getattr(webview, "FileDialog", None)
        mode = dialog.OPEN if dialog else webview.OPEN_DIALOG
        paths = self._window.create_file_dialog(mode, directory=directory, file_types=file_types)
        if not paths:
            return None
        return Path(paths[0] if isinstance(paths, (list, tuple)) else paths)

    @staticmethod
    def _start_dir(current: str) -> str:
        p = Path(current) if current else None
        return str(p.parent) if p and p.parent.is_dir() else str(program_dir())

    def pick_model(self, current: str = "") -> dict | None:
        path = self._dialog(self._start_dir(current), ("Modelo do ETABS (*.EDB;*.edb)", "Todos os arquivos (*.*)"))
        return self.model_card(str(path)) if path else None

    def model_card(self, path: str) -> dict:
        p = Path(path)
        if not p.is_file() or p.suffix.lower() != ".edb":
            raise UserError(f"Arquivo .EDB não encontrado: {path}")
        return model_card(p)

    def read_model(self, path: str) -> bool:
        edb = Path(path)

        def job(w):
            info = read_model(w.etabs.open_model(edb).sap, edb)
            self._info = info
            payload = model_payload(info)
            map_file = edb.parent / STORY_MAP_FILENAME
            mapping = {}
            if map_file.is_file():
                try:
                    mapping = load_story_map(map_file)
                    log.info("Lances carregados de %s (%d entradas).", map_file.name, len(mapping))
                except UserError as exc:
                    log.warning("%s", exc)
            payload["mapping"] = mapping_to_json(mapping)
            payload["prefs"] = self._settings.get("models", {}).get(_model_key(edb), {})
            self._remember(edb)
            return payload

        self._worker.jobs.put(("read", job))
        return True

    def _remember(self, edb: Path):
        recent = [p for p in self._settings.get("recent", []) if not same_file(p, edb)]
        self._settings["recent"] = [str(edb)] + recent[:7]
        save_settings(self._settings)

    def import_story_map(self, current: str = "") -> dict | None:
        path = self._dialog(self._start_dir(current), ("story_map (*.csv)", "Todos os arquivos (*.*)"))
        if not path:
            return None
        mapping = load_story_map(path)
        log.info("Lances importados de %s (%d entradas).", path, len(mapping))
        return mapping_to_json(mapping)

    # ---- exportação ------------------------------------------------------------
    def export(self, req: dict) -> dict:
        edb = Path(req["path"])
        if self._info is None or not same_file(self._info.edb, edb):
            raise UserError('Leia o modelo antes de exportar (passo "Modelo").')
        mapping = mapping_from_json(req.get("mapping") or {})
        excluded = set(req.get("excluded") or [])
        groups = polygonal_groups(self._info.piers, quiet=True)
        for base in list(excluded):
            excluded.update(groups.get(base, []))
        piers = [p for p in self._info.piers if p not in excluded]
        combos = list(req.get("combos") or [])
        full = bool(req.get("full", True))
        missing = missing_story_map(self._info, piers, mapping)
        if missing:
            raise UserError("Faltam lances do TQS para: " + ", ".join(list(missing)[:12]))
        save_story_map(edb.parent / STORY_MAP_FILENAME, mapping)
        self._settings.setdefault("models", {})[_model_key(edb)] = {
            "combos": combos, "excluded": sorted(set(req.get("excluded") or [])), "full": full}
        save_settings(self._settings)

        def job(w):
            t0 = time.perf_counter()
            r = export_model(w.etabs, edb, mapping, full, combos=combos, piers=piers)
            files = sorted((p.name for p in r.out_dir.iterdir()), key=natural_key)
            return {"out_dir": str(r.out_dir), "csv": r.csv_count, "txt": r.txt_count,
                    "backup": r.backup.name if r.backup else None, "reanalyzed": r.reanalyzed,
                    "warnings": r.warnings, "files": files, "seconds": round(time.perf_counter() - t0, 1)}

        self._worker.jobs.put(("export", job))
        return {"queued": True}

    # ---- eventos e utilidades --------------------------------------------------
    def poll(self) -> list:
        out = []
        try:
            while len(out) < 500:
                kind, a, b, c = self._events.get_nowait()
                if kind == "log":
                    lvl = "error" if a >= logging.ERROR else "warn" if a >= logging.WARNING else "info"
                    out.append({"t": "log", "lvl": lvl, "msg": b,
                                "time": datetime.fromtimestamp(c).strftime("%H:%M:%S")})
                elif kind == "progress":
                    out.append({"t": "progress", **a})
                else:
                    out.append({"t": "job", "name": a, "ok": kind == "ok", "data": b})
        except queue.Empty:
            pass
        return out

    def busy(self) -> bool:
        return self._worker.busy or not self._worker.jobs.empty()

    def open_folder(self, path: str):
        p = Path(path)
        if p.exists():
            os.startfile(p)  # noqa: S606 - Windows

    def _shutdown(self):
        global _progress_sink
        _progress_sink = None
        log.removeHandler(self._handler)
        busy = self._worker.busy
        self._worker.jobs.put(None)
        if not busy:
            self._worker.join(60)


def run_gui() -> int:
    try:
        import webview
    except ImportError:
        raise UserError("A interface precisa do pacote pywebview (pip install pywebview). "
                        "Sem ele, use a linha de comando: --modelo ARQ.EDB") from None
    index = ui_dir() / "index.html"
    if not index.is_file():
        raise UserError(f"Arquivos da interface não encontrados: {index.parent}")
    api = Api()
    theme = api._settings.get("theme", "dark")
    window = webview.create_window(
        f"Pier Forces · ETABS → TQS  v{__version__}", url=str(index), js_api=api,
        width=1320, height=860, min_size=(1080, 700),
        background_color="#F5F6F8" if theme == "light" else "#0B0F17")
    api._window = window
    try:
        webview.start(http_server=True, debug=bool(os.environ.get("PIER_UI_DEBUG")))
    finally:
        api._shutdown()
    return 0


# =============================================================================
# 8. Programa principal
# =============================================================================

def run_cli(args) -> int:
    if args.modelo:
        edb = Path(args.modelo).resolve()
        if not edb.is_file():
            raise UserError(f"Modelo não encontrado: {edb}")
    else:
        folder = Path(args.pasta).resolve() if args.pasta else program_dir()
        if not folder.is_dir():
            raise UserError(f"Pasta não encontrada: {folder}")
        edb = find_model(folder)
    etabs = Etabs()
    if args.listar:
        try:
            sap = etabs.open_model(edb).sap
            info = read_model(sap, edb)
            print("\nPIERS:\n  " + "\n  ".join(info.piers))
            print("\nCOMBINAÇÕES:\n  " + "\n  ".join(info.combos))
            print("\nLOAD CASES:\n  " + "\n  ".join(name_list(sap.LoadCases, "LoadCases.GetNameList")))
            groups = polygonal_groups(info.piers, quiet=True)
            if groups:
                print("\nPILARES POLIGONAIS (faces -> arquivos):\n  " + "\n  ".join(
                    f"{b}: " + ", ".join(f if f == face_output_name(f) else f"{f} -> {face_output_name(f)}" for f in g)
                    for b, g in groups.items()))
        finally:
            etabs.close_all()
        return 0
    map_path = edb.parent / STORY_MAP_FILENAME
    mapping = load_story_map(map_path) if map_path.is_file() else None
    if mapping:
        log.info("Usando %s (%d entradas) para os lances do TQS.", map_path.name, len(mapping))
    result = export_model(etabs, edb, mapping, not args.sem_completo)
    if args.comparar:
        return compare_with(Path(args.comparar), result.out_dir)
    return 0


def attach_parent_console():
    """
    O .exe é de janela (sem console). Chamado com argumentos a partir de um Prompt de Comando,
    mostra a saída nesse Prompt.
    """
    if sys.stdout is not None or sys.platform != "win32":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        if kernel32.AttachConsole(-1):                     # -1 = console do processo pai
            stream = open("CONOUT$", "w", encoding=f"cp{kernel32.GetConsoleOutputCP()}",
                          errors="replace", buffering=1)
            sys.stdout = sys.stderr = stream
            print()
    except (OSError, LookupError, AttributeError):
        pass


def show_fatal(message: str):
    """Erro antes de a janela abrir, no .exe sem console: mostra numa caixa de mensagem do Windows."""
    if sys.stdout is None and sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, "Exportador de Pier Forces", 0x10)
        except (OSError, AttributeError):
            pass


def main(argv=None) -> int:
    if len(sys.argv if argv is None else argv) > (1 if argv is None else 0):
        attach_parent_console()
    ap = argparse.ArgumentParser(description="Exporta Pier Forces do ETABS para a pasta ETB do TQS. "
                                             "Sem argumentos, abre a janela.")
    ap.add_argument("--diagnostico", action="store_true",
                    help="confere a instalação (API do ETABS) sem abrir o ETABS")
    ap.add_argument("--versao", action="version", version=f"%(prog)s {__version__}")
    ap.add_argument("--modelo", help="arquivo .EDB a exportar (sem janela)")
    ap.add_argument("--pasta", help="pasta com o .EDB a exportar (sem janela)")
    ap.add_argument("--cli", action="store_true", help="sem janela, usando o .EDB da pasta deste arquivo")
    ap.add_argument("--sem-completo", action="store_true",
                    help="não gera os pilares poligonais completos nem os .txt")
    ap.add_argument("--listar", action="store_true", help="lista Piers, combinações e Load Cases")
    ap.add_argument("--comparar", metavar="DIR", help="compara a pasta ETB gerada com os arquivos de DIR")
    args = ap.parse_args(argv)
    gui = not (args.modelo or args.pasta or args.cli or args.listar or args.comparar or args.diagnostico)

    log.setLevel(logging.INFO)
    log.handlers[:] = []
    if sys.stdout is not None:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)-7s %(message)s", "%H:%M:%S"))
        log.addHandler(handler)
    try:
        if args.diagnostico:
            diagnose_api()
            code = 0
        else:
            code = run_gui() if gui else run_cli(args)
    except UserError as exc:
        log.error("%s", exc)
        show_fatal(str(exc))
        code = 1
    except KeyboardInterrupt:
        log.error("Interrompido.")
        code = 1
    except Exception as exc:  # noqa: BLE001 - mostrado ao usuário
        log.exception("Erro inesperado:")
        show_fatal(f"Erro inesperado: {exc}")
        code = 1
    finally:
        logging.shutdown()
    return code


if __name__ == "__main__":
    sys.exit(main())
