"""
Gera dist\\ExportarPierForces.exe com o PyInstaller (arquivo único, sem console).
Use o build_exe.bat, que prepara o ambiente (build\\venv) e chama este script.

As classes da API do ETABS (comtypes.gen) são geradas aqui, a partir do ETABSv1.tlb do
ETABS instalado nesta máquina, e embutidas no .exe. Se o ETABS do outro computador tiver
outra versão da biblioteca, o comtypes gera as classes na primeira execução (em
%APPDATA%\\Python\\...\\comtypes_cache).
"""
import glob
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = "ExportarPierForces"
DIST = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "dist"   # pasta de saída opcional


def version() -> str:
    text = (ROOT / "exportar_pier_forces.py").read_text(encoding="utf-8")
    return re.search(r'^__version__ = "([^"]+)"', text, re.M).group(1)


def generate_etabs_wrappers():
    import comtypes.client
    tlbs = glob.glob(r"C:\Program Files\Computers and Structures\ETABS *\NativeAPI\x64\ETABSv1.tlb")
    tlbs.sort(key=lambda p: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", p)])
    if not tlbs:
        print("AVISO: ETABS não encontrado nesta máquina; as classes da API serão geradas no primeiro uso.")
        return
    print(f"Gerando as classes da API a partir de {tlbs[-1]}")
    comtypes.client.GetModule(tlbs[-1])


def version_file(path: Path, ver: str):
    nums = tuple(int(x) for x in (ver.split(".") + ["0"] * 4)[:4])
    path.write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}),
  kids=[StringFileInfo([StringTable('041604B0', [
    StringStruct('FileDescription', 'Exportador de Pier Forces ETABS para TQS'),
    StringStruct('ProductName', 'Exportador de Pier Forces'),
    StringStruct('FileVersion', '{ver}'),
    StringStruct('ProductVersion', '{ver}'),
    StringStruct('OriginalFilename', '{NAME}.exe')])]),
    VarFileInfo([VarStruct('Translation', [1046, 1200])])])
""", encoding="utf-8")


def main():
    import PyInstaller.__main__
    ver = version()
    generate_etabs_wrappers()
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    vfile = build / "version_info.txt"
    version_file(vfile, ver)
    ui = build / "ui"                          # interface sem a pasta dev/ (API simulada)
    shutil.rmtree(ui, ignore_errors=True)
    shutil.copytree(ROOT / "ui", ui, ignore=shutil.ignore_patterns("dev", "*.map"))
    PyInstaller.__main__.run([
        str(ROOT / "exportar_pier_forces.py"),
        "--name", NAME,
        "--onefile",
        "--windowed",                         # sem console; a janela mostra o log
        "--collect-submodules", "comtypes",   # inclui comtypes.gen (classes do ETABSv1)
        "--collect-all", "webview",           # janela nativa (WebView2) e seus arquivos
        "--add-data", f"{ui};ui",
        "--icon", str(ROOT / "ui" / "app.ico"),
        "--version-file", str(vfile),
        "--distpath", str(DIST),
        "--workpath", str(build / "pyinstaller"),
        "--specpath", str(build),
        "--noconfirm",
        "--clean",
    ])
    print(f"\nPronto: {DIST / (NAME + '.exe')}  (versão {ver})")


if __name__ == "__main__":
    sys.exit(main())
