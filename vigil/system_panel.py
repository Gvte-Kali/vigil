"""Display current block devices and Vigil mount points in Qt."""
import json
import shutil

from PySide6.QtCore import QProcess, QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from .system_info import LSBLK_COLUMNS, ZONES, read_zones, system_metrics


def capacity(value):
    if value is None:
        return ""
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if size < 1024 or unit == "PiB":
            return f"{size:.1f} {unit}"
        size /= 1024


class SystemPanel(QWidget):
    def __init__(self, translate):
        super().__init__()
        self.tr_pair = translate
        self.devices = None
        self.zones = None
        self.metrics = (None, None, None, None)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("font-size: 19px; font-weight: 700;")
        layout.addWidget(self.summary)
        cards = QGridLayout()
        cards.setSpacing(8)
        layout.addLayout(cards)
        self.cards = []
        for index, accent in enumerate(("#57C7D4", "#BB9AF7", "#80D7A4", "#EBC47A")):
            card = QLabel()
            card.setTextFormat(Qt.TextFormat.PlainText)
            card.setWordWrap(True)
            card.setMinimumHeight(64)
            card.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            card.setStyleSheet(
                f"color: {accent}; background: #242D38; border: 1px solid #455569; "
                f"border-left: 4px solid {accent}; border-radius: 6px; padding: 6px; "
                "font-weight: 600;"
            )
            cards.addWidget(card, index // 2, index % 2)
            self.cards.append(card)
        self.protection = QLabel()
        self.protection.setWordWrap(True)
        layout.addWidget(self.protection)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setToolTipDuration(10000)
        layout.addWidget(self.tree)
        self.refresh_button = QPushButton()
        self.refresh_button.clicked.connect(self.refresh)
        layout.addWidget(self.refresh_button)
        self.process = QProcess(self)
        self.process.finished.connect(self.read_devices)
        self.process.errorOccurred.connect(self.render)
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(self.process.kill)
        self.refresh()

    def refresh(self):
        self.metrics = system_metrics()
        try:
            self.zones = read_zones()
        except OSError:
            self.zones = None
        executable = shutil.which("lsblk")
        if executable and self.process.state() == QProcess.ProcessState.NotRunning:
            self.process.start(executable, ["--json", "--tree", "--bytes", "-o", LSBLK_COLUMNS])
            self.timeout.start(5000)
        elif not executable:
            self.devices = None
        self.render()

    def read_devices(self, code, status):
        self.timeout.stop()
        self.devices = None
        if code == 0 and status == QProcess.ExitStatus.NormalExit:
            try:
                self.devices = json.loads(bytes(self.process.readAllStandardOutput()))["blockdevices"]
            except (KeyError, TypeError, ValueError):
                pass
        self.render()

    def add(self, parent, text, color="#B9CAD9"):
        item = QTreeWidgetItem(parent, [text])
        item.setToolTip(0, text)
        item.setForeground(0, QColor(color))
        return item

    def render(self, *_):
        tr = self.tr_pair
        self.refresh_button.setText(tr("Actualiser le système", "Refresh system"))
        self.summary.setText(tr("Tableau de bord", "Dashboard"))
        memory, uptime, load, cpu_count = self.metrics
        unavailable = tr("Indisponible", "Unavailable")
        values = [
            (tr("Mémoire utilisée", "Memory used"),
             f"{capacity(memory[0])} / {capacity(memory[1])}" if memory else unavailable),
            (tr("Charge système · 1 / 5 / 15 min", "System load · 1 / 5 / 15 min"),
             " / ".join(f"{sample:.2f}" for sample in load) if load else unavailable),
            (tr("Processeurs logiques", "Logical processors"),
             str(cpu_count) if cpu_count else unavailable),
            (tr("Temps de fonctionnement", "Uptime"),
             f"{uptime // 86400}d {uptime // 3600 % 24}h {uptime // 60 % 60}m"
             if uptime is not None else unavailable),
        ]
        for card, (title, value) in zip(self.cards, values):
            card.setText(f"{title}\n{value}")
        writable = readonly = unknown = 0
        pending = list(self.devices or ())
        while pending:
            device = pending.pop()
            pending.extend(device.get("children") or ())
            if device.get("type") not in {"disk", "part"}:
                continue
            ro = device.get("ro")
            if ro in (True, 1, "1"):
                readonly += 1
            elif ro in (False, 0, "0"):
                writable += 1
            else:
                unknown += 1
        if not (readonly or writable or unknown):
            protection = tr("Protection bloc : état indisponible", "Block protection: unavailable")
        elif writable or unknown:
            protection = tr(
                f"Protection bloc non confirmée pour tous : {writable} en écriture, {unknown} inconnus",
                f"Block protection is not confirmed for all devices: {writable} writable, {unknown} unknown",
            )
        else:
            protection = tr(
                f"Lecture seule bloc signalée sur les {readonly} disques et partitions visibles",
                f"Block read-only reported for all {readonly} visible disks and partitions",
            )
        self.protection.setText(protection)
        color = "#80D7A4" if readonly and not (writable or unknown) else "#EBC47A"
        self.protection.setStyleSheet(f"color: {color}; font-weight: 600;")
        self.tree.clear()
        mounts = self.add(self.tree, tr("Zones Vigil", "Vigil zones"), "#57C7D4")
        for zone in ZONES:
            entries = None if self.zones is None else self.zones[zone]
            if entries is None:
                state = tr("État indisponible", "Status unavailable")
            elif not entries:
                state = tr("Non monté", "Not mounted")
            elif any(target == zone for target, *_ in entries):
                state = tr("Monté", "Mounted")
            else:
                state = tr("Sous-montages", "Submounts")
            color = "#80D7A4" if entries else "#EBC47A"
            group = self.add(mounts, f"{zone}  ·  {state}", color)
            for target, source, filesystem, mode in entries or ():
                self.add(group, "  ·  ".join(filter(None, (source, filesystem, mode, target))))
            group.setExpanded(True)
        mounts.setExpanded(True)
        root = self.add(self.tree, tr("Disques et partitions", "Disks and partitions"), "#57C7D4")
        if self.devices is None:
            message = (tr("Lecture en cours…", "Loading…")
                       if self.process.state() != QProcess.ProcessState.NotRunning
                       else tr("Inventaire indisponible", "Inventory unavailable"))
            self.add(root, message)
        elif not self.devices:
            self.add(root, tr("Aucun périphérique bloc détecté", "No block devices detected"))
        else:
            for device in self.devices:
                self.add_device(root, device)
        root.setExpanded(True)

    def add_device(self, parent, device):
        tr = self.tr_pair
        kind = {"disk": tr("Disque", "Disk"), "part": tr("Partition", "Partition")}.get(
            device.get("type"), device.get("type")
        )
        title = "  ·  ".join(filter(None, (
            device.get("path") or device.get("name"), kind, capacity(device.get("size")),
        )))
        device_type = device.get("type")
        color = {"disk": "#57C7D4", "part": "#BB9AF7"}.get(device_type, "#DCE3EC")
        item = self.add(parent, title, color)
        ro = device.get("ro")
        mode = tr("Lecture seule", "Read-only") if ro in (True, 1, "1") else (
            tr("Écriture autorisée", "Writable") if ro in (False, 0, "0") else None
        )
        fields = (
            (tr("Mode du bloc", "Block mode"), mode),
            (tr("Modèle", "Model"), device.get("model")),
            (tr("Table", "Table"), device.get("pttype")),
            (tr("Type de partition", "Partition type"), device.get("parttype")),
            (tr("Système de fichiers", "Filesystem"), device.get("fstype")),
            (tr("Disponible", "Available"), capacity(device.get("fsavail"))),
            (tr("Utilisé", "Used"), device.get("fsuse%")),
        )
        details = [(label, value) for label, value in fields if value]
        if details:
            group = item if device_type == "part" else self.add(
                item, tr("Détails du périphérique", "Device details")
            )
            for label, value in details:
                self.add(group, f"{label}  ·  {value}")
        for child in device.get("children") or ():
            self.add_device(item, child)
        item.setExpanded(device_type == "disk")

    def stop(self):
        self.timeout.stop()
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(1000)
