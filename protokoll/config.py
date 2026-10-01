"""Zentrale Einstellungen.

Alle Werte können zusätzlich über eine Datei `protokoll_config.json` neben dem
Programm (bzw. neben der .exe) überschrieben werden, z. B.:

    {"GENERATE_FOR_FAILED": false, "ROOT_DIR": "D:\\Messdaten\\Phase"}
"""
import json
import sys
from pathlib import Path

# --- Pfade -------------------------------------------------------------------
# Wurzelordner, unter dem der Teststand <Jahr>\KW<nn>\<Testordner>\ ablegt.
ROOT_DIR = r"\\192.168.91.11\zeag\E-Werkstatt\Messprotokolle_Test\Wickede\EC300KW\Phase"

# --- Verhalten ---------------------------------------------------------------
# False -> für fehlgeschlagene/abgebrochene Tests wird KEIN PDF erzeugt.
GENERATE_FOR_FAILED = True

POLL_SECONDS = 30           # Abstand zwischen zwei Scans
SETTLE_SECONDS = 30         # XML muss so lange unverändert sein, bevor sie verarbeitet wird
FULL_SCAN_MINUTES = 60      # zusätzlich regelmäßig den kompletten ROOT_DIR durchsuchen
GIVE_UP_HOURS = 24          # unvollständige/defekte XML nach dieser Zeit nicht mehr prüfen

PDF_SUFFIX = "_TestProtocol.pdf"

# --- Protokoll-Inhalt --------------------------------------------------------
TEMP_MARGIN_K = 20          # Max Temp = T_amb + TEMP_MARGIN_K
CH_VLINK = "REF Vlink"
CH_TEMP_DUT = "DUT Temp1"
CH_TEMP_AMBIENT = "REF Temp3"
CH_CURRENT = "DUT I1"

FOOTER_LINES = [
    "ZOPF Energieanlagen GmbH  |  Hans-Driesch-Str. 2  |  04179 Leipzig",
    "Tel: +49 341 241 083-0  |  info@zopf-energie.de  |  www.zopf-energie.de",
]


def app_dir() -> Path:
    """Ordner des Programms (bei PyInstaller-Exe: Ordner der .exe)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def asset_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "protokoll" / "assets" / name


def _load_overrides() -> None:
    cfg = app_dir() / "protokoll_config.json"
    if not cfg.exists():
        return
    g = globals()
    for key, value in json.loads(cfg.read_text(encoding="utf-8")).items():
        if key.isupper() and key in g:
            g[key] = value


_load_overrides()
