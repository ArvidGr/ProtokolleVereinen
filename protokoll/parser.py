"""Einlesen der Teststand-XML in eine TestReport-Struktur."""
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


class IncompleteReport(Exception):
    """XML wird noch geschrieben oder ist defekt."""


@dataclass
class Module:
    name: str
    parameters: dict[str, str] = field(default_factory=dict)
    limits: dict[str, str] = field(default_factory=dict)
    result: dict[str, str] = field(default_factory=dict)
    channels: dict[str, list[float]] = field(default_factory=dict)
    interval_s: float = 1.0


@dataclass
class TestReport:
    path: Path
    dut_name: str
    item_no: str
    configuration: str
    sequence: str
    modules: dict[str, Module]
    result: str
    error: str
    start_time: datetime | None
    operator: str
    serial_no: str

    @property
    def passed(self) -> bool:
        return self.result.upper() == "SUCCESS"


def _params(elem: ET.Element | None) -> dict[str, str]:
    if elem is None:
        return {}
    return {p.get("Name"): p.get("Value", "") for p in elem.findall("Parameter") if p.get("Name")}


def _parse_time(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d_%H-%M-%S")
    except (TypeError, ValueError):
        return None


def _floats(data: str) -> list[float]:
    return [float(v) for v in data.split(";") if v.strip()]


def _time_from_name(path: Path) -> datetime | None:
    """Zeitstempel aus dem Dateinamen `...@2026-09-21_14-07-48.xml`."""
    return _parse_time(path.stem.rsplit("@", 1)[-1])


def load(path: Path) -> TestReport:
    """Liest eine vollständige Report-XML. Wirft IncompleteReport, wenn sie
    (noch) nicht fertig geschrieben oder defekt ist."""
    raw = path.read_bytes()
    if not raw.rstrip().endswith(b"</Report>"):
        raise IncompleteReport("kein abschließendes </Report>")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise IncompleteReport(f"XML defekt: {exc}") from exc
    posttest = root.find("Posttest")
    testresult = root.find("Testresult")
    pretest = root.find("Pretest")
    if posttest is None:
        raise IncompleteReport("Posttest fehlt")
    if testresult is None and pretest is None:
        raise IncompleteReport("Testresult fehlt")

    modules: dict[str, Module] = {}
    for tm in root.findall("TestModule"):
        mod = Module(
            name=tm.get("Name", ""),
            parameters=_params(tm.find("Parameter")),
            limits=_params(tm.find("Limits")),
            result=_params(tm.find("Result")),
        )
        meas = tm.find("Measurements")
        if meas is not None:
            mod.interval_s = float(meas.get("Interval", "1") or 1)
            for md in meas.findall("MeasurementData"):
                mod.channels[md.get("Channel", "")] = _floats(md.get("Data", ""))
        modules[mod.name] = mod

    dut = root.find("DUTSpecification")
    tb = root.find("TestbenchConfiguration")
    seq = root.find("Testsequence")
    res = _params(testresult)
    if testresult is None:  # schon der Pretest ist gescheitert
        res = {"Result": pretest.get("Result", "FAILED"), "Error": pretest.get("Error", "")}
    post = _params(posttest)
    return TestReport(
        path=path,
        dut_name=dut.get("Name", "") if dut is not None else "",
        item_no=dut.get("Description", "") if dut is not None else "",
        configuration=tb.get("Name", "") if tb is not None else "",
        sequence=seq.get("Name", "") if seq is not None else "",
        modules=modules,
        result=res.get("Result", ""),
        error=res.get("Error", ""),
        start_time=_parse_time(res.get("StartTime", "")) or _time_from_name(path),
        operator=post.get("Operator", ""),
        serial_no=post.get("Serialnumber", ""),
    )
