"""Display current block devices and Vigil mount points in Qt."""
import json
import shutil

from PySide6.QtCore import QProcess, QTimer, Qt
from PySide6.QtWidgets import QLabel, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from .system_info import LSBLK_COLUMNS, ZONES, read_zones


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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
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

    def add(self, parent, text):
        item = QTreeWidgetItem(parent, [text])
        item.setToolTip(0, text)
        return item

    def render(self, *_):
        tr = self.tr_pair
        self.refresh_button.setText(tr("Actualiser le système", "Refresh system"))
        self.summary.setText(tr("Système et stockage", "System and storage"))
        self.tree.clear()
        mounts = self.add(self.tree, tr("Zones Vigil", "Vigil zones"))
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
            group = self.add(mounts, f"{zone}  ·  {state}")
            for target, source, filesystem, mode in entries or ():
                self.add(group, "  ·  ".join(filter(None, (source, filesystem, mode, target))))
            group.setExpanded(True)
        mounts.setExpanded(True)
        root = self.add(self.tree, tr("Disques et partitions", "Disks and partitions"))
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
        item = self.add(parent, title)
        fields = (
            (tr("Modèle", "Model"), device.get("model")),
            (tr("Table", "Table"), device.get("pttype")),
            (tr("Type de partition", "Partition type"), device.get("parttype")),
            (tr("Système de fichiers", "Filesystem"), device.get("fstype")),
            (tr("Disponible", "Available"), capacity(device.get("fsavail"))),
            (tr("Utilisé", "Used"), device.get("fsuse%")),
        )
        for label, value in fields:
            if value:
                self.add(item, f"{label}  ·  {value}")
        for child in device.get("children") or ():
            self.add_device(item, child)
        item.setExpanded(True)

    def stop(self):
        self.timeout.stop()
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(1000)
