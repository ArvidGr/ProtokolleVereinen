"""Findet fertige Test-XMLs ohne PDF und erzeugt die Protokolle."""
import json
import logging
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from . import config
from .parser import IncompleteReport, load
from .report import build_pdf

log = logging.getLogger("protokoll")


def pdf_path_for(xml: Path) -> Path:
    return xml.with_name(xml.stem + config.PDF_SUFFIX)


def generate(xml: Path, out_dir: Path | None = None) -> Path:
    """Erzeugt das PDF für eine XML (atomar über .tmp-Datei)."""
    report = load(xml)
    target = (out_dir / (xml.stem + config.PDF_SUFFIX)) if out_dir else pdf_path_for(xml)
    tmp = target.with_suffix(".pdf.tmp")
    build_pdf(report, tmp)
    os.replace(tmp, target)
    return target


class Scanner:
    def __init__(self, root: Path, since: datetime | None = None):
        self.root = root
        self.since = since.timestamp() if since else None
        self.state_file = config.app_dir() / "skipped.json"
        self.skipped: dict[str, dict] = self._load_state()
        self.warned: set[str] = set()
        self.last_full_scan = 0.0

    # --- Zustand (nur für aufgegebene/absichtlich übersprungene XMLs) ---------
    def _load_state(self) -> dict:
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_state(self) -> None:
        try:
            self.state_file.write_text(json.dumps(self.skipped, indent=1), encoding="utf-8")
        except OSError as exc:
            log.warning("Konnte %s nicht schreiben: %s", self.state_file, exc)

    def _is_skipped(self, xml: Path, mtime: float) -> bool:
        entry = self.skipped.get(str(xml))
        if not entry or entry["mtime"] != mtime:
            return False  # neu oder inzwischen geändert -> erneut prüfen
        return not (entry["reason"] == "failed" and config.GENERATE_FOR_FAILED)

    def _skip(self, xml: Path, mtime: float, reason: str) -> None:
        self.skipped[str(xml)] = {"mtime": mtime, "reason": reason}
        self._save_state()

    # --- Kandidaten -----------------------------------------------------------
    def _recent_dirs(self) -> list[Path]:
        dirs = []
        today = date.today()
        for d in (today, today - timedelta(days=7)):
            week = d.isocalendar()
            for year in {d.year, week.year}:
                p = self.root / str(year) / f"KW{week.week:02d}"
                if p not in dirs:
                    dirs.append(p)
        return dirs

    def _candidates(self, full: bool):
        if full:
            # nur <Jahr>\KW<nn>\<Testordner>\*.xml – andere Ordner (z. B. "Änderungen") ignorieren
            for year in self.root.glob("[0-9][0-9][0-9][0-9]"):
                yield from year.glob("KW*/*/*.xml")
            return
        for d in self._recent_dirs():
            if d.is_dir():
                yield from d.glob("*/*.xml")

    # --- Scan -----------------------------------------------------------------
    def scan(self, full: bool | None = None) -> dict[str, int]:
        now = time.time()
        if full is None:
            full = now - self.last_full_scan >= config.FULL_SCAN_MINUTES * 60
        if full:
            self.last_full_scan = now
        stats = {"created": 0, "waiting": 0, "skipped": 0, "errors": 0}
        for xml in self._candidates(full):
            try:
                self._handle(xml, now, stats)
            except OSError as exc:
                stats["errors"] += 1
                log.warning("Zugriffsfehler bei %s: %s", xml, exc)
        return stats

    def _handle(self, xml: Path, now: float, stats: dict) -> None:
        if pdf_path_for(xml).exists():
            return
        mtime = xml.stat().st_mtime
        if self.since and mtime < self.since:
            return
        if self._is_skipped(xml, mtime):
            stats["skipped"] += 1
            return
        if now - mtime < config.SETTLE_SECONDS:
            stats["waiting"] += 1
            return
        try:
            report = load(xml)
        except IncompleteReport as exc:
            if now - mtime > config.GIVE_UP_HOURS * 3600:
                log.warning("Aufgegeben (seit >%sh unvollständig): %s – %s",
                            config.GIVE_UP_HOURS, xml, exc)
                self._skip(xml, mtime, "incomplete")
                stats["skipped"] += 1
            else:
                if str(xml) not in self.warned:
                    self.warned.add(str(xml))
                    log.info("Warte auf vollständige XML: %s – %s", xml.name, exc)
                stats["waiting"] += 1
            return

        if not report.passed and not config.GENERATE_FOR_FAILED:
            log.info("FAILED, kein PDF (GENERATE_FOR_FAILED=False): %s", xml.name)
            self._skip(xml, mtime, "failed")
            stats["skipped"] += 1
            return

        try:
            target = generate(xml)
        except OSError:
            raise
        except Exception:  # Fehler im Report darf den Dienst nicht stoppen
            log.exception("PDF-Erzeugung fehlgeschlagen: %s", xml)
            self._skip(xml, mtime, "error")
            stats["errors"] += 1
            return
        log.info("PDF erstellt (%s, SN %s): %s", report.result, report.serial_no, target)
        stats["created"] += 1

    def run_forever(self) -> None:
        log.info("Überwache %s (alle %ss)", self.root, config.POLL_SECONDS)
        while True:
            try:
                if not self.root.exists():
                    log.warning("Wurzelordner nicht erreichbar: %s", self.root)
                else:
                    stats = self.scan()
                    if stats["created"] or stats["errors"]:
                        log.info("Scan: %s", stats)
            except Exception:
                log.exception("Unerwarteter Fehler im Scan")
            time.sleep(config.POLL_SECONDS)
