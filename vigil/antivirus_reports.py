"""Consolidated antivirus reports and the shared report catalogue."""
import argparse
from dataclasses import dataclass
from datetime import datetime
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile


METADATA = "antivirus-report.json"


def report_name(value, started):
    name = value.strip() or datetime.fromisoformat(started).strftime("rapport_antivirus_%Y-%m-%d_%H-%M-%S")
    if (name in {".", ".."} or name.startswith(".") or any(c in name for c in "/\\")
            or any(ord(c) < 32 or ord(c) == 127 for c in name)):
        raise ValueError("Nom de rapport invalide / Invalid report name")
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    if len(os.fsencode(name)) > 240:
        raise ValueError("Nom de rapport trop long / Report name too long")
    return name


def read_json(path):
    try:
        if path.is_symlink():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def scan_summary(run, scan_status, operation_status, *, requires_triage=True):
    logs = sorted(path for path in run.glob("clamav_*.log") if path.is_file() and not path.is_symlink())
    issues = []
    threats = scanned = completed = 0
    for log in logs:
        scanned_count = infected_count = None
        summary = False
        with log.open(encoding="utf-8", errors="replace") as stream:
            for raw in stream:
                line = raw.rstrip()
                if line.startswith("Vigil ClamAV metadata: "):
                    continue
                if line.strip() == "----------- SCAN SUMMARY -----------":
                    summary = True
                if summary and (match := re.fullmatch(r"Scanned files:\s*(\d+)", line)):
                    scanned_count = int(match[1])
                if summary and (match := re.fullmatch(r"Infected files:\s*(\d+)", line)):
                    infected_count = int(match[1])
                if (not line.endswith(": OK") and re.search(
                        r"^(?:ERROR|WARNING)\b|\b(?:skipped|ignored|limit exceeded|encrypted)\b| ERROR$",
                        line, re.I)):
                    issues.append(line)
        if scanned_count is not None and infected_count is not None:
            completed += 1
            scanned += scanned_count
            threats += infected_count
    try:
        counts = [tuple(map(int, line.split())) for line in (run / "scan-coverage.tsv").read_text().splitlines()]
        expected = sum(total for total, _ in counts)
        if len(counts) != len(logs) or any(code not in {0, 1} for _, code in counts):
            issues.append("Sortie ClamAV incomplète ou en erreur / Incomplete or failed ClamAV output.")
        if scanned < expected:
            issues.append(f"Écart inventaire/scan / Inventory to scan gap: {expected - scanned}")
        if any(code == 1 for _, code in counts) and not threats:
            issues.append("Menace signalée sans total cohérent / Threat reported without a consistent count.")
    except (OSError, ValueError):
        expected = None
        issues.append("Comptage de couverture indisponible / Coverage counts unavailable.")
    try:
        options = (run / "scan-options.txt").read_text()
    except OSError:
        options = ""
    if "--scan-archive=no" in options:
        issues.append("Contenu des archives exclu / Archive contents excluded.")
    triage = read_json(run / "usb-triage.json")
    counts_present = triage is not None and all(
        type(triage.get(key)) is int for key in ("baseline_count", "after_count", "new_count", "hid_count")
    )
    if requires_triage and (not counts_present or triage.get("block_fail_count")):
        issues.append("Triage USB incomplet / Incomplete USB triage.")
    if not counts_present:
        triage = None
    if scan_status:
        issues.append(f"Code du script ClamAV / ClamAV script exit: {scan_status}")
    if operation_status:
        issues.append(f"Code de l’opération / Workflow exit: {operation_status}")
    if completed != len(logs):
        issues.append("Résumé ClamAV manquant / Missing ClamAV summary.")
    if not completed:
        status = "failed"
    else:
        status = "partial" if issues else "complete"
    return {"status": status, "threats": threats if completed else None, "scanned": scanned,
            "expected": expected, "issues": issues, "logs": logs, "triage": triage}


def publish_report(run, name, started, user, project, generator, scan_status, operation_status, *,
                   requires_triage=True):
    if run.resolve() != run.absolute() or run.resolve().is_relative_to("/investigation"):
        raise ValueError("Invalid antivirus report directory")
    summary = scan_summary(run, scan_status, operation_status, requires_triage=requires_triage)
    name = report_name(name, started)
    target = run / name
    metadata = {"name": name, "started": started, "status": summary["status"], "threats": summary["threats"]}
    with tempfile.TemporaryDirectory(prefix=".antivirus-", dir=run) as directory:
        staged = Path(directory)
        pdf, index = staged / "report.pdf", staged / METADATA
        generator(pdf, run, summary, started, user, project)
        index.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        for file in (pdf, index):
            with file.open("rb") as stream:
                os.fsync(stream.fileno())
        os.link(pdf, target)
        try:
            os.link(index, run / METADATA)
        except OSError:
            target.unlink()
            raise
    return target, summary["status"]


@dataclass(frozen=True)
class AntivirusReport:
    path: Path
    started: datetime | None
    status: str
    threats: int | None

    @property
    def timestamp(self):
        return self.started.timestamp() if self.started else float("-inf")

    def date_label(self):
        return self.started.astimezone().strftime("%Y-%m-%d %H:%M:%S") if self.started else "—"

    def result_label(self, tr):
        if self.status == "failed":
            return tr("Échec", "Failed")
        if self.status == "partial":
            return tr("Scan incomplet", "Incomplete scan")
        if self.status == "complete" and self.threats is not None:
            return tr(f"{self.threats} menace(s)", f"{self.threats} threat(s)")
        return tr("Résultat inconnu", "Unknown result")


def antivirus_reports(state):
    from .reporting import case_pdf_reports
    from .storage import case_storage_directory, database, find_antivirus_case

    with database(state) as connection:
        case = find_antivirus_case(connection)
    if not case:
        return []
    root = case_storage_directory(state, case)
    rows, runs = [], set()
    for run in root.glob("scan-*"):
        if run.is_symlink() or not run.is_dir():
            continue
        data = read_json(run / METADATA)
        if not data:
            continue
        try:
            started = datetime.fromisoformat(data["started"])
            name = report_name(data["name"], data["started"])
            if name != data["name"] or started.tzinfo is None:
                continue
            target = run / name
            threats, status = data.get("threats"), data["status"]
            if (target.is_file() and not target.is_symlink() and status in {"complete", "partial", "failed"}
                    and (threats is None or type(threats) is int and threats >= 0)):
                rows.append(AntivirusReport(target, started, status, threats))
                runs.add(run.name)
        except (KeyError, TypeError, ValueError):
            continue
    for path in case_pdf_reports(state, case):
        if path.parent.name in runs or not path.name.startswith("rapport_clamav_"):
            continue
        started = None
        if match := re.search(r"_(\d{2}-\d{2}-\d{4}_\d{2}h\d{2}m\d{2}s)\.pdf$", path.name):
            try:
                started = datetime.strptime(match[1], "%d-%m-%Y_%Hh%Mm%Ss")
            except ValueError:
                pass
        rows.append(AntivirusReport(path, started, "unknown", None))
    return sorted(rows, key=lambda row: (-row.timestamp, row.path.name.casefold()))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    name = sub.add_parser("name")
    name.add_argument("started")
    name.add_argument("value")
    publish = sub.add_parser("publish")
    publish.add_argument("run", type=Path)
    publish.add_argument("name")
    publish.add_argument("started")
    publish.add_argument("operator")
    publish.add_argument("project")
    publish.add_argument("scan_status", type=int)
    publish.add_argument("operation_status", type=int)
    publish.add_argument("--no-triage", action="store_true")
    args = parser.parse_args()
    if args.command == "name":
        print(report_name(args.value, args.started))
        return 0
    generator = Path(__file__).resolve().parents[1] / "scripts/pdf/vigil_pdf.py"
    spec = importlib.util.spec_from_file_location("vigil_pdf", generator)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target, status = publish_report(args.run, args.name, args.started, args.operator, args.project,
                                    module.build_antivirus_report, args.scan_status, args.operation_status,
                                    requires_triage=not args.no_triage)
    language = os.environ.get("VIGIL_LANG")
    result = {"complete": ("Scan terminé", "Scan completed"), "partial": ("Scan incomplet", "Incomplete scan"),
              "failed": ("Échec du scan", "Scan failed")}
    print(f"{result[status][language == 'en']} · {target}")
    return 0 if status == "complete" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error
