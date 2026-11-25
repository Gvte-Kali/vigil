"""Native Textual file and directory selection."""
import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, DataTable, DirectoryTree, Input, Select, Static

from .destination import destination_info, read_mounts, writable_destination
from .tui_widgets import icon


@dataclass(frozen=True)
class PickerOptions:
    mode: Literal["directory", "open", "save"]
    extensions: tuple[str, ...] = ()
    writable: bool = False
    acquisition: bool = False
    required_bytes: int | None = None


class FolderTree(DirectoryTree):
    show_hidden = False

    def filter_paths(self, paths):
        return (path for path in paths if path.is_dir() and (self.show_hidden or not path.name.startswith(".")))


class PickerTable(DataTable):
    COMPONENT_CLASSES = DataTable.COMPONENT_CLASSES | {"picker-table--directory", "picker-table--file"}

    async def _on_click(self, event: events.Click) -> None:
        row = event.style.meta.get("row", -1)
        column = event.style.meta.get("column", -1)
        if row >= 0 and column >= 0 and event.chain == 1:
            self.move_cursor(row=row, column=column, animate=False)
            event.prevent_default()
            event.stop()


class FileSystemPicker(ModalScreen[Path | None]):
    """Browse filesystem paths without requiring a graphical session."""

    BINDINGS = [("escape", "cancel", "Annuler / Cancel")]

    def __init__(self, title, tr, options, *, initial=None, case_directory=None):
        super().__init__()
        self.title_text, self.tr, self.options = title, tr, options
        self.case_directory = case_directory
        initial = Path(initial or Path.home()).expanduser()
        self.current = initial if initial.is_dir() else initial.parent
        if not self.current.is_dir():
            self.current = Path.home()
        self.chosen_name = initial.name if initial != self.current else ""
        self.history = []
        self.rows = {}
        self.selected = None

    def compose(self) -> ComposeResult:
        t = self.tr
        with VerticalScroll(classes="dialog filesystem-picker"):
            yield Static(Text(self.title_text), classes="heading")
            yield Select([(t("Emplacements", "Locations"), "locations")],
                         value="locations", allow_blank=False, id="picker-locations")
            with Horizontal(id="picker-navigation"):
                yield Button(t("Précédent", "Back"), id="picker-back", disabled=True)
                yield Button(t("Parent", "Up"), id="picker-parent")
                yield Button(t("Actualiser", "Refresh"), id="picker-refresh")
            yield Input(str(self.current), id="picker-path")
            with Horizontal(id="picker-filter"):
                yield Input(placeholder=t("Rechercher dans le dossier", "Search this folder"), id="picker-search")
                yield Checkbox(t("Cachés", "Hidden"), id="picker-hidden")
            with Horizontal(id="picker-body"):
                yield FolderTree(self.current, id="picker-tree")
                yield PickerTable(cursor_type="row", id="picker-files")
            if self.options.mode == "save":
                yield Input(self.chosen_name, placeholder=t("Nom du fichier", "File name"), id="picker-name")
            if self.options.writable or self.options.mode == "save":
                with Horizontal(id="picker-mkdir"):
                    yield Input(placeholder=t("Nom du nouveau dossier", "New folder name"), id="picker-directory-name")
                    yield Button(t("Créer dossier", "Create folder"), id="picker-create")
            yield Static(id="picker-selection")
            yield Static(id="picker-meta")
            yield Static(id="picker-error")
            with Horizontal(classes="actions", id="picker-actions"):
                yield Button(t("Annuler", "Cancel"), id="picker-cancel")
                yield Button(t("Valider", "Confirm"), id="picker-confirm", variant="primary")

    async def on_mount(self):
        self.query_one(DataTable).add_columns(self.tr("Nom", "Name"), self.tr("Type", "Kind"))
        places = await asyncio.to_thread(self.favorites)
        self.query_one("#picker-locations", Select).set_options(places)
        await self.navigate(self.current, remember=False)
        table = self.query_one(DataTable)
        if self.chosen_name and self.options.mode == "open":
            path = self.current / self.chosen_name
            if path in self.rows:
                table.move_cursor(row=table.get_row_index(str(path)), animate=False)
                self.selected = path
                await self.update_selection()
        table.focus()

    def favorites(self):
        t = self.tr
        home = Path.home()
        folders = [("locations", t("Emplacements", "Locations")),
                   (home, t("Dossier personnel", "Home")), (home / "Bureau", "Bureau"),
                   (home / "Desktop", "Desktop"), (home / "Documents", "Documents"),
                   (Path("/"), t("Racine", "Root")), (Path("/stockage"), t("Stockage Vigil", "Vigil storage"))]
        if self.case_directory:
            folders.append((self.case_directory, t("Dossier de l’affaire", "Case folder")))
        for mount in read_mounts():
            path = mount.target
            if path != Path("/") and (mount.source.startswith("/dev/") or any(
                path.is_relative_to(base) for base in ("/media", "/mnt", "/run/media", "/investigation", "/stockage")
            )):
                folders.append((path, str(path)))
        result, seen = [(folders[0][1], "locations")], set()
        for path, label in folders[1:]:
            if path in seen or not path.is_dir() or not os.access(path, os.R_OK | os.X_OK):
                continue
            seen.add(path)
            result.append((f"{label} · {path}" if str(path) != label else label, str(path)))
        return result

    def matches(self, path):
        return not self.options.extensions or path.name.casefold().endswith(self.options.extensions)

    def list_entries(self, path, hidden):
        rows = []
        with os.scandir(path) as entries:
            for entry in entries:
                if not hidden and entry.name.startswith("."):
                    continue
                try:
                    directory = entry.is_dir()
                    if directory or (self.options.mode != "directory" and entry.is_file() and self.matches(Path(entry.name))):
                        rows.append((Path(entry.path), directory))
                except OSError:
                    continue
        return sorted(rows, key=lambda row: (not row[1], row[0].name.casefold(), row[0].name))

    async def navigate(self, path, *, remember=True):
        path = Path(path).expanduser()
        if not path.is_absolute():
            path = self.current / path
        hidden = self.query_one(Checkbox).value
        try:
            path = path.resolve(strict=True)
            rows = await asyncio.to_thread(self.list_entries, path, hidden)
        except (OSError, ValueError) as error:
            self.show_error(error)
            return False
        if remember and path != self.current:
            self.history.append(self.current)
        self.current, self.rows, self.selected = path, dict(rows), None
        self.query_one("#picker-back", Button).disabled = not self.history
        self.query_one("#picker-path", Input).value = str(path)
        tree = self.query_one(FolderTree)
        tree.show_hidden = hidden
        if Path(tree.path) == path:
            tree.reload()
        else:
            tree.path = path
        self.render_rows()
        self.show_error("")
        await self.update_selection()
        return True

    def render_rows(self):
        table = self.query_one(DataTable)
        table.clear()
        query = self.query_one("#picker-search", Input).value.casefold()
        for path, directory in self.rows.items():
            if query not in path.name.casefold():
                continue
            kind = self.tr("Dossier", "Folder") if directory else self.tr("Fichier", "File")
            glyph = icon("cases" if directory else "report")
            name = Text(f"{glyph} {path.name}", style=table.get_component_rich_style(
                "picker-table--directory" if directory else "picker-table--file"
            ))
            table.add_row(name, Text(kind), key=str(path))

    def candidate(self):
        if self.options.mode == "save":
            name = self.query_one("#picker-name", Input).value.strip()
            return self.current / name if name else self.current
        return self.selected or self.current

    async def update_selection(self):
        value = self.candidate()
        self.query_one("#picker-selection", Static).update(Text(str(value), no_wrap=True, overflow="ellipsis"))
        if self.options.acquisition:
            t = self.tr
            required = self.options.required_bytes
            needed = self.size_label(required) if required is not None else t("après choix de la source", "after source selection")
            try:
                directory = value if value.is_dir() else value.parent
                info = await asyncio.to_thread(destination_info, directory)
                mode = "RO" if info.investigation or not info.writable else "RW"
                text = f"{info.filesystem} · {mode} · {t('Disponible', 'Available')} : {self.size_label(info.available)}"
            except (OSError, ValueError):
                text = t("Informations du système de fichiers indisponibles", "Filesystem information unavailable")
            self.query_one("#picker-meta", Static).update(Text(f"{text}\n{t('Nécessaire', 'Required')} : {needed}"))

    def size_label(self, size):
        unit = self.tr("Gio", "GiB")
        return f"{size / 2**30:.2f} {unit}"

    def show_error(self, error):
        self.query_one("#picker-error", Static).update(Text(str(error)))

    async def on_data_table_row_highlighted(self, event):
        path = Path(event.row_key.value)
        if path in self.rows:
            self.selected = path
            await self.update_selection()

    async def on_data_table_row_selected(self, event):
        path = Path(event.row_key.value)
        if self.rows.get(path):
            await self.navigate(path)
        elif self.options.mode == "open" and path in self.rows:
            await self.confirm(path)

    async def on_directory_tree_directory_selected(self, event):
        await self.navigate(event.path)

    async def on_select_changed(self, event):
        if event.value not in {"locations", Select.NULL}:
            await self.navigate(event.value)
            event.select.value = "locations"

    async def on_checkbox_changed(self, event):
        await self.navigate(self.current, remember=False)

    async def on_input_changed(self, event):
        if event.input.id == "picker-search":
            self.selected = None
            self.render_rows()
            await self.update_selection()
        elif event.input.id == "picker-name":
            await self.update_selection()

    async def on_input_submitted(self, event):
        if event.input.id == "picker-path":
            path = Path(event.value).expanduser()
            if not path.is_absolute():
                path = self.current / path
            if path.is_dir():
                await self.navigate(path)
            elif self.options.mode == "open":
                await self.confirm(path)
            elif self.options.mode == "save":
                if await self.navigate(path.parent):
                    self.query_one("#picker-name", Input).value = path.name
            else:
                self.show_error(self.tr("Dossier introuvable.", "Directory not found."))
        elif event.input.id == "picker-name":
            await self.confirm()
        elif event.input.id == "picker-directory-name":
            await self.create_folder()

    async def on_button_pressed(self, event):
        event.stop()
        match event.button.id:
            case "picker-cancel":
                self.action_cancel()
            case "picker-back":
                if self.history and await self.navigate(self.history[-1], remember=False):
                    self.history.pop()
                    self.query_one("#picker-back", Button).disabled = not self.history
            case "picker-parent":
                await self.navigate(self.current.parent)
            case "picker-refresh":
                await self.navigate(self.current, remember=False)
            case "picker-create":
                await self.create_folder()
            case "picker-confirm":
                await self.confirm()

    def action_cancel(self):
        self.dismiss(None)

    def validate(self, path):
        if self.options.mode == "save":
            name = self.query_one("#picker-name", Input).value.strip()
            if name in {"", ".", ".."} or Path(name).name != name:
                raise ValueError(self.tr("Indiquez un nom de fichier.", "Enter a file name."))
            info = writable_destination(self.current)
            if self.options.required_bytes is not None and info.available < self.options.required_bytes:
                raise ValueError(self.tr("Espace libre insuffisant.", "Insufficient free space."))
            path = info.path / name
            if os.path.lexists(path):
                raise FileExistsError(self.tr("Ce fichier existe déjà.", "This file already exists."))
            if not self.matches(path):
                raise ValueError(self.tr("Extension de fichier non admise.", "Unsupported file extension."))
            return path
        if self.options.writable:
            info = writable_destination(path)
            if self.options.required_bytes is not None and info.available < self.options.required_bytes:
                raise ValueError(self.tr("Espace libre insuffisant.", "Insufficient free space."))
            return info.path
        path = path.resolve(strict=True)
        if self.options.mode == "directory" and path.is_dir():
            return path
        if self.options.mode == "open" and path.is_file() and self.matches(path) and os.access(path, os.R_OK):
            return path
        raise ValueError(self.tr("Sélection incompatible ou inaccessible.", "Incompatible or inaccessible selection."))

    async def confirm(self, path=None):
        try:
            result = self.validate(path or self.candidate())
        except (OSError, ValueError) as error:
            self.show_error(error)
            return
        self.dismiss(result)

    async def create_folder(self):
        field = self.query_one("#picker-directory-name", Input)
        name = field.value.strip()
        if name in {"", ".", ".."} or Path(name).name != name:
            self.show_error(self.tr("Indiquez un nom de dossier.", "Enter a directory name."))
            return
        try:
            fd = os.open(self.current, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            try:
                writable_destination(self.current, fd=fd)
                os.mkdir(name, mode=0o700, dir_fd=fd)
            finally:
                os.close(fd)
        except (OSError, ValueError) as error:
            self.show_error(error)
            return
        field.clear()
        await self.navigate(self.current / name)
