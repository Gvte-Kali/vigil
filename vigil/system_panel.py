"""Display current block devices and Vigil mount points in Qt."""
import json
import shutil

from PySide6.QtCore import QProcess, QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGridLayout, QLabel, QProgressBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from .system_info import LSBLK_COLUMNS, ZONES, cpu_ticks, read_zones, system_metrics


def capacity(value):
    if value is None:
        return ""
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if size < 1024 or unit == "PiB":
            return f"{size:.1f} {unit}"
        size /= 1024


class SystemPanel(QWidget):
    def __init__(self, translate, icon=None):
        super().__init__()
        self.tr_pair = translate
        self.icon = icon
        self.devices = None
        self.zones = None
        self.metrics = (None, None, None, None)
        self.cpu_previous = None
        self.cpu_percent = None
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
        self.gauges = {}
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
            box = QVBoxLayout()
            box.setSpacing(3)
            box.addWidget(card)
            if index in (0, 2):
                gauge = QProgressBar()
                gauge.setTextVisible(False)
                gauge.setMaximumHeight(5)
                gauge.setStyleSheet(
                    "QProgressBar { background: #303B48; border: 0; border-radius: 2px; }"
                    f"QProgressBar::chunk {{ background: {accent}; border-radius: 2px; }}"
                )
                box.addWidget(gauge)
                self.gauges[index] = gauge
            cards.addLayout(box, index // 2, index % 2)
            self.cards.append(card)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setToolTipDuration(10000)
        layout.addWidget(self.tree)
        self.process = QProcess(self)
        self.process.finished.connect(self.read_devices)
        self.process.errorOccurred.connect(self.render_inventory)
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(self.process.kill)
        self.resources_timer = QTimer(self)
        self.resources_timer.timeout.connect(self.refresh_resources)
        self.resources_timer.start(5000)
        self.inventory_timer = QTimer(self)
        self.inventory_timer.timeout.connect(self.refresh_inventory)
        self.inventory_timer.start(2000)
        self.render()
        self.refresh()

    def refresh(self):
        self.refresh_resources()
        self.refresh_inventory()

    def refresh_resources(self):
        self.metrics = system_metrics()
        try:
            current = cpu_ticks()
        except (OSError, ValueError):
            current = None
        self.cpu_percent = None
        if current is not None and self.cpu_previous is not None:
            elapsed = current[0] - self.cpu_previous[0]
            idle = current[1] - self.cpu_previous[1]
            if elapsed > 0 and 0 <= idle <= elapsed:
                self.cpu_percent = round(100 * (elapsed - idle) / elapsed)
        self.cpu_previous = current
        self.render_resources()

    def refresh_inventory(self):
        old_zones = self.zones
        try:
            self.zones = read_zones()
        except OSError:
            self.zones = None
        executable = shutil.which("lsblk")
        if executable and self.process.state() == QProcess.ProcessState.NotRunning:
            self.process.start(executable, ["--json", "--tree", "--bytes", "-o", LSBLK_COLUMNS])
            self.timeout.start(4500)
        elif not executable and self.devices is not None:
            self.devices = None
            self.render_inventory()
        if old_zones != self.zones:
            self.render_inventory()

    def read_devices(self, code, status):
        self.timeout.stop()
        previous = self.devices
        self.devices = None
        if code == 0 and status == QProcess.ExitStatus.NormalExit:
            try:
                self.devices = json.loads(bytes(self.process.readAllStandardOutput()))["blockdevices"]
            except (KeyError, TypeError, ValueError):
                pass
        if previous != self.devices or self.devices is None:
            self.render_inventory()

    def add(self, parent, text, color="#B9CAD9"):
        item = QTreeWidgetItem(parent, [text])
        item.setToolTip(0, text)
        item.setForeground(0, QColor(color))
        return item

    def render(self):
        self.render_resources()
        self.render_inventory()

    def render_resources(self):
        tr = self.tr_pair
        self.summary.setText(tr("Ressources et périphériques", "Resources and devices"))
        memory, uptime, load, cpu_count = self.metrics
        unavailable = tr("Indisponible", "Unavailable")
        values = [
            (tr("Mémoire utilisée", "Memory used"),
             f"{capacity(memory[0])} / {capacity(memory[1])}" if memory else unavailable),
            (tr("Charge système · 1 / 5 / 15 min", "System load · 1 / 5 / 15 min"),
             " / ".join(f"{sample:.2f}" for sample in load) if load else unavailable),
            (tr("Utilisation CPU", "CPU usage"),
             f"{self.cpu_percent} % · {cpu_count} {tr('cœurs logiques', 'logical cores')}"
             if self.cpu_percent is not None else
             (f"{cpu_count} {tr('cœurs logiques', 'logical cores')}" if cpu_count else unavailable)),
            (tr("Temps de fonctionnement", "Uptime"),
             f"{uptime // 86400}d {uptime // 3600 % 24}h {uptime // 60 % 60}m"
             if uptime is not None else unavailable),
        ]
        for card, (title, value) in zip(self.cards, values):
            card.setText(f"{title}\n{value}")
        self.gauges[0].setValue(round(100 * memory[0] / memory[1]) if memory else 0)
        self.gauges[2].setValue(self.cpu_percent or 0)

    def tree_items(self):
        stack = [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]
        while stack:
            item = stack.pop()
            yield item
            stack.extend(item.child(i) for i in range(item.childCount()))

    def render_inventory(self, *_):
        tr = self.tr_pair
        expanded = {key: item.isExpanded() for item in self.tree_items()
                    if (key := item.data(0, Qt.ItemDataRole.UserRole))}
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
            if self.icon:
                group.setIcon(0, self.icon("plug", color))
            for target, source, filesystem, mode in entries or ():
                self.add(group, "  ·  ".join(filter(None, (source, filesystem, mode, target))))
            group.setData(0, Qt.ItemDataRole.UserRole, zone)
            group.setExpanded(True)
        mounts.setData(0, Qt.ItemDataRole.UserRole, "zones")
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
        root.setData(0, Qt.ItemDataRole.UserRole, "disk-list")
        root.setExpanded(True)
        for item in self.tree_items():
            key = item.data(0, Qt.ItemDataRole.UserRole)
            if key in expanded:
                item.setExpanded(expanded[key])

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
        if self.icon:
            item.setIcon(0, self.icon("hard-drive" if device_type == "disk" else "database", color))
        key = device.get("path") or device.get("name")
        item.setData(0, Qt.ItemDataRole.UserRole, key)
        ro = device.get("ro")
        mode = tr("Lecture seule", "Read-only") if ro in (True, 1, "1") else (
            tr("Écriture autorisée", "Writable") if ro in (False, 0, "0") else None
        )
        fields = (
            (tr("Mode du bloc", "Block mode"), mode),
            (tr("Modèle", "Model"), device.get("model")),
            (tr("Connexion", "Transport"), device.get("tran")),
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
            if group is not item and key:
                group.setData(0, Qt.ItemDataRole.UserRole, f"{key}/details")
            for label, value in details:
                self.add(group, f"{label}  ·  {value}")
        for child in device.get("children") or ():
            self.add_device(item, child)
        item.setExpanded(device_type == "disk")

    def stop(self):
        self.resources_timer.stop()
        self.inventory_timer.stop()
        self.timeout.stop()
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(1000)
