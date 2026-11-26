"""Reusable presentation widgets for the Vigil terminal workspace."""
import os
import sys

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Grid, Vertical
from textual.widgets import Button, ProgressBar, Static

ICONS = {
    "menu": ("☰", "="), "dashboard": ("⌂", "#"), "cases": ("▤", "[]"),
    "quick": ("›", ">"), "configuration": ("⚙", "@"),
    "scan": ("⊕", "+"), "update": ("↻", "+"), "report": ("≡", "#"),
    "mount": ("↑", "^"), "unmount": ("↓", "v"), "clone": ("⇄", "="),
    "raw": ("◇", "*"), "ok": ("●", "+"), "warning": ("▲", "!"),
}


def supports_unicode():
    encoding = (getattr(sys.__stdout__, "encoding", None) or "").lower().replace("-", "")
    return (encoding.startswith("utf") and os.environ.get("TERM") != "dumb"
            and "VIGIL_ASCII" not in os.environ)


def icon(name):
    unicode_icon, ascii_icon = ICONS[name]
    return unicode_icon if supports_unicode() else ascii_icon


class NavigationItem(Button):
    def __init__(self, label, page):
        super().__init__(label, id=f"nav-{page}", classes="navigation-item")
        self.page = page
        self.tooltip = label

    def render(self):
        return Text(f"{icon(self.page)}  {self.label}", no_wrap=True, overflow="ellipsis")


class ActionCard(Button):
    def __init__(self, title, description, glyph, *, id, classes=""):
        super().__init__(title, id=id, classes=f"action-card {classes}")
        self.description = description
        self.glyph = glyph
        self.tooltip = f"{title} · {description}"

    def render(self):
        text = Text(overflow="fold")
        text.append(f"{icon(self.glyph)}  {self.label}\n", style="bold")
        text.append(self.description, style=self.get_component_rich_style("action-card--description"))
        return text

    COMPONENT_CLASSES = Button.COMPONENT_CLASSES | {"action-card--description"}


class SectionPanel(Vertical):
    def __init__(self, title, *widgets, id=None, classes="", glyph=None, description=""):
        super().__init__(id=id, classes=f"section-panel {classes}")
        self.section_title = f"{icon(glyph)}  {title}" if glyph else title
        self.section_description = description
        self.section_widgets = widgets

    def compose(self) -> ComposeResult:
        yield Static(Text(self.section_title), classes="heading")
        if self.section_description:
            yield Static(Text(self.section_description), classes="section-description")
        yield from self.section_widgets


class CardGrid(Grid):
    def on_resize(self, event):
        width = event.size.width
        self.set_class(width < 50, "single-column")
        self.set_class(50 <= width < 77, "two-columns")


class MetricCard(Vertical):
    def __init__(self, title, metric):
        super().__init__(classes="metric-card")
        self.metric = metric
        self.metric_title = title

    def compose(self) -> ComposeResult:
        yield Static(Text(self.metric_title), classes="metric-label")
        yield ProgressBar(total=100, show_eta=False, id=f"{self.metric}-progress")


class StatusIndicator(Static):
    def show(self, label, detail, *, active):
        self.set_class(active, "status-ok")
        self.set_class(not active, "status-warning")
        self.update(Text(f"{icon('ok' if active else 'warning')} {label}  ·  {detail}", overflow="fold"))
