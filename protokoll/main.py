"""Kommandozeile.

    python -m protokoll.main run              # Dauerbetrieb (Polling)
    python -m protokoll.main once [--full]    # einmal scannen
    python -m protokoll.main file <xml> [--out DIR]   # einzelnes PDF erzeugen
"""
import argparse
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import config
from .scanner import Scanner, generate


def _setup_logging() -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fh = RotatingFileHandler(config.app_dir() / "protokoll.log", maxBytes=2_000_000,
                             backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)
    if sys.stderr is not None:  # unter pythonw gibt es keine Konsole
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root.addHandler(sh)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="protokoll")
    ap.add_argument("--root", default=config.ROOT_DIR, help="Wurzelordner der Testdaten")
    ap.add_argument("--since", type=lambda s: datetime.strptime(s, "%Y-%m-%d"),
                    help="nur XMLs ab diesem Datum (JJJJ-MM-TT) verarbeiten")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    once = sub.add_parser("once")
    once.add_argument("--full", action="store_true", help="kompletten Wurzelordner scannen")
    f = sub.add_parser("file")
    f.add_argument("xml", type=Path)
    f.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    _setup_logging()
    if args.cmd == "file":
        print(generate(args.xml, args.out))
        return 0

    scanner = Scanner(Path(args.root), since=args.since)
    if args.cmd == "once":
        print(scanner.scan(full=args.full))
        return 0
    scanner.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
