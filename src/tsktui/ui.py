"""
Textual-based Terminal User Interface for The Sleuth Kit (TSK).
Styled after k9s and ncdu with vim keybindings and modal dialogs.
"""

import os
import re
import sys
import hashlib
from typing import List, Optional, Tuple, Dict, Any

from rich.text import Text

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    DataTable,
    Static,
    Label,
    Input,
    TabbedContent,
    TabPane,
    Button,
)
from textual.binding import Binding

from .backend import TSKBackend, Partition, FileEntry


def format_size(size_str: str) -> str:
    """Format size into human readable string like ncdu."""
    if not size_str or size_str == "0":
        return "0 B"
    try:
        num = int(size_str)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if num < 1024.0:
                return f"{num:3.1f} {unit}" if unit != 'B' else f"{num} B"
            num /= 1024.0
        return f"{num:.1f} PB"
    except ValueError:
        return size_str


def format_hex_dump(data: bytes, max_len: int = 32768) -> Text:
    """Formats bytes into standard ncdu/xxd hex view."""
    if not data:
        return Text("Empty file or no data available.", style="italic dim")

    data = data[:max_len]
    text = Text()
    
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        # Offset (e.g. 00000000)
        text.append(f"{i:08x}  ", style="bold cyan")
        
        # Hex representation (split into two groups of 8)
        first_8 = chunk[:8]
        second_8 = chunk[8:]
        
        for b in first_8:
            if b == 0:
                text.append(f"{b:02x} ", style="dim")
            elif 32 <= b <= 126:
                text.append(f"{b:02x} ", style="green")
            else:
                text.append(f"{b:02x} ", style="yellow")
        for _ in range(8 - len(first_8)):
            text.append("   ")
            
        text.append(" ")
        
        for b in second_8:
            if b == 0:
                text.append(f"{b:02x} ", style="dim")
            elif 32 <= b <= 126:
                text.append(f"{b:02x} ", style="green")
            else:
                text.append(f"{b:02x} ", style="yellow")
        for _ in range(8 - len(second_8)):
            text.append("   ")
            
        text.append(" |", style="bold bright_white")
        
        # ASCII representation
        for b in chunk:
            if 32 <= b <= 126:
                text.append(chr(b), style="bold white")
            else:
                text.append(".", style="dim")
        for _ in range(16 - len(chunk)):
            text.append(" ")
            
        text.append("|\n", style="bold bright_white")
        
    if len(data) == max_len:
        text.append(f"\n[... Truncated at {max_len} bytes ...]", style="bold yellow")
        
    return text


class PartitionModal(ModalScreen[Optional[Partition]]):
    """Partition / Volume selector modal (k9s namespace-like picker)."""
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("q", "cancel", "Cancel"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("enter", "select", "Select"),
    ]

    def __init__(self, partitions: List[Partition], current_start: int):
        super().__init__()
        self.partitions = partitions
        self.current_start = current_start

    def compose(self) -> ComposeResult:
        with Vertical(id="k9s_modal"):
            yield Label("⎈ Select Partition / Volume (mmls)", id="modal_title")
            yield DataTable(id="part_table")
            with Horizontal(id="modal_buttons"):
                yield Button("Select (Enter)", variant="primary", id="btn_select")
                yield Button("Cancel (Esc)", variant="default", id="btn_cancel")

    def on_mount(self) -> None:
        table = self.query_one("#part_table", DataTable)
        table.cursor_type = "row"
        table.clear(columns=True)
        table.add_columns("Slot", "Start Sector", "Length", "Type / Description", "Status")
        
        selected_idx = 0
        for idx, p in enumerate(self.partitions):
            status = Text("ALLOCATED", style="bold green") if p.is_allocated else Text("UNALLOCATED", style="dim")
            table.add_row(
                p.slot,
                str(p.start),
                f"{p.length * 512 / (1024*1024):.1f} MB" if p.length > 0 else "--",
                p.description,
                status
            )
            if p.start == self.current_start and p.is_allocated:
                selected_idx = idx
                
        table.focus()
        if self.partitions:
            table.move_cursor(row=selected_idx)

    def action_cursor_down(self) -> None:
        self.query_one("#part_table", DataTable).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#part_table", DataTable).action_cursor_up()

    def action_select(self) -> None:
        table = self.query_one("#part_table", DataTable)
        if table.cursor_row is not None and 0 <= table.cursor_row < len(self.partitions):
            self.dismiss(self.partitions[table.cursor_row])
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#btn_select")
    def on_btn_select(self) -> None:
        self.action_select()

    @on(Button.Pressed, "#btn_cancel")
    def on_btn_cancel(self) -> None:
        self.action_cancel()

    @on(DataTable.RowSelected, "#part_table")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_select()


class InfoModal(ModalScreen):
    """Item Info Modal (ncdu 'i' style metadata popup)."""
    BINDINGS = [
        ("escape", "close", "Close"),
        ("q", "close", "Close"),
        ("i", "close", "Close"),
        ("enter", "close", "Close"),
    ]

    def __init__(self, title: str, content: str):
        super().__init__()
        self.title_text = title
        self.content_text = content

    def compose(self) -> ComposeResult:
        with Vertical(id="k9s_modal"):
            yield Label(f"ℹ️ Item Details: {self.title_text}", id="modal_title")
            with VerticalScroll(id="info_scroll"):
                yield Static(Text(self.content_text), id="info_body")
            with Horizontal(id="modal_buttons"):
                yield Button("Close (Esc / i)", variant="primary", id="btn_info_close")

    def on_mount(self) -> None:
        self.query_one("#btn_info_close", Button).focus()

    def action_close(self) -> None:
        self.dismiss()

    @on(Button.Pressed, "#btn_info_close")
    def on_close_btn(self) -> None:
        self.dismiss()


class ViewFileScreen(ModalScreen):
    """Full-featured Hex/Text Viewer Screen (k9s 'v' style pager)."""
    BINDINGS = [
        ("escape", "close", "Back"),
        ("q", "close", "Back"),
        ("h", "calc_hash", "Hash"),
        ("e", "extract", "Extract"),
        ("tab", "switch_tab", "Switch Mode"),
        ("1", "mode_hex", "Hex View"),
        ("2", "mode_text", "Text View"),
        ("3", "mode_istat", "istat View"),
    ]

    def __init__(self, backend: TSKBackend, sector_offset: int, file_entry: FileEntry):
        super().__init__()
        self.backend = backend
        self.sector_offset = sector_offset
        self.file_entry = file_entry
        self.file_bytes = b""
        self.istat_text = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="viewer_container"):
            with Horizontal(id="viewer_header"):
                yield Label(f"📄 View: {self.file_entry.name} (Inode: {self.file_entry.inode})", id="viewer_title")
                yield Label("[1] Hex  [2] Text  [3] Inode  |  [e] Extract  [h] Hash  [Esc/q] Back", id="viewer_shortcuts")
            with TabbedContent(id="viewer_tabs"):
                with TabPane("Hex Dump [1]", id="tab_hex"):
                    with VerticalScroll():
                        yield Static(id="viewer_hex_content")
                with TabPane("Text (UTF-8) [2]", id="tab_text"):
                    with VerticalScroll():
                        yield Static(id="viewer_text_content")
                with TabPane("Inode Metadata (istat) [3]", id="tab_istat"):
                    with VerticalScroll():
                        yield Static(id="viewer_istat_content")
            with Horizontal(id="viewer_footer"):
                yield Label("Loading...", id="viewer_status")

    def on_mount(self) -> None:
        self.load_data()

    @work(thread=True)
    def load_data(self) -> None:
        self.file_bytes = self.backend.read_file_bytes(self.sector_offset, self.file_entry.inode, max_bytes=65536)
        self.istat_text = self.backend.get_istat(self.sector_offset, self.file_entry.inode)
        
        hex_renderable = format_hex_dump(self.file_bytes)
        
        try:
            text_renderable = self.file_bytes.decode('utf-8')
        except Exception:
            text_renderable = "[Binary file content cannot be decoded as UTF-8. Use Hex Dump.]"

        def update_ui():
            self.query_one("#viewer_hex_content", Static).update(hex_renderable)
            self.query_one("#viewer_text_content", Static).update(text_renderable)
            self.query_one("#viewer_istat_content", Static).update(Text(self.istat_text))
            size_fmt = format_size(str(len(self.file_bytes)))
            self.query_one("#viewer_status", Label).update(f"Loaded {size_fmt} | Inode {self.file_entry.inode}")

        self.app.call_from_thread(update_ui)

    def action_close(self) -> None:
        self.dismiss()

    def action_switch_tab(self) -> None:
        tabs = self.query_one("#viewer_tabs", TabbedContent)
        current = tabs.active
        if current == "tab_hex":
            tabs.active = "tab_text"
        elif current == "tab_text":
            tabs.active = "tab_istat"
        else:
            tabs.active = "tab_hex"

    def action_mode_hex(self) -> None:
        self.query_one("#viewer_tabs", TabbedContent).active = "tab_hex"

    def action_mode_text(self) -> None:
        self.query_one("#viewer_tabs", TabbedContent).active = "tab_text"

    def action_mode_istat(self) -> None:
        self.query_one("#viewer_tabs", TabbedContent).active = "tab_istat"

    def action_extract(self) -> None:
        dest_dir = os.path.abspath("./extracted")
        ok, path_or_err, hashes = self.backend.extract_file(
            self.sector_offset,
            self.file_entry.inode,
            dest_dir,
            self.file_entry.name
        )
        if ok:
            self.notify(f"Extracted to {os.path.basename(path_or_err)} (MD5: {hashes.get('md5')})", title="Saved", timeout=4)
        else:
            self.notify(f"Extraction error: {path_or_err}", severity="error", timeout=4)

    def action_calc_hash(self) -> None:
        if not self.file_bytes:
            self.notify("No bytes loaded.", severity="warning")
            return
        md5_v = hashlib.md5(self.file_bytes).hexdigest()
        sha256_v = hashlib.sha256(self.file_bytes).hexdigest()
        self.notify(f"MD5: {md5_v}\nSHA256: {sha256_v}", title="Hashes", timeout=6)


class SearchModal(ModalScreen):
    """String Search Modal (k9s '/' search style)."""
    BINDINGS = [
        ("escape", "close", "Close"),
        ("enter", "select_match", "View Match"),
    ]

    def __init__(self, backend: TSKBackend):
        super().__init__()
        self.backend = backend
        self.results: List[Dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="k9s_modal"):
            yield Label("🔍 Disk-Wide String Search (srch_strings)", id="modal_title")
            yield Input(placeholder="Type keyword and press Enter (e.g. flag, pico, password, key)...", id="search_input")
            yield Label("Enter a query above and hit Enter to search.", id="search_status")
            yield DataTable(id="search_table")
            with Horizontal(id="modal_buttons"):
                yield Button("Close (Esc)", variant="error", id="btn_search_close")

    def on_mount(self) -> None:
        table = self.query_one("#search_table", DataTable)
        table.cursor_type = "row"
        table.clear(columns=True)
        table.add_columns("Byte Offset", "Match Preview")
        self.query_one("#search_input", Input).focus()

    @on(Input.Submitted, "#search_input")
    def on_search(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if not query:
            return
        self.run_search(query)

    @work(thread=True)
    def run_search(self, query: str) -> None:
        status_label = self.query_one("#search_status", Label)
        self.app.call_from_thread(status_label.update, f"Searching for '{query}'...")
        
        results = self.backend.search_strings(query, max_results=200)
        self.results = results

        def update_ui():
            table = self.query_one("#search_table", DataTable)
            table.clear(columns=False)
            for r in results:
                table.add_row(r["offset"], r["content"])
            
            if results:
                status_label.update(f"Found {len(results)} match(es) for '{query}'. Press Enter on a row to inspect.")
                table.focus()
                table.move_cursor(row=0)
            else:
                status_label.update(f"No matches found for '{query}'.")
                
            self.notify(f"Found {len(results)} match(es) for '{query}'", timeout=3)

        self.app.call_from_thread(update_ui)

    def action_close(self) -> None:
        self.dismiss()

    def action_select_match(self) -> None:
        table = self.query_one("#search_table", DataTable)
        if table.cursor_row is not None and 0 <= table.cursor_row < len(self.results):
            r = self.results[table.cursor_row]
            self.notify(f"Offset: {r['offset']}\nContent: {r['content']}", title="Match Details", timeout=6)

    @on(Button.Pressed, "#btn_search_close")
    def on_close_btn(self) -> None:
        self.dismiss()

    @on(DataTable.RowSelected, "#search_table")
    def on_table_selected(self, event: DataTable.RowSelected) -> None:
        self.action_select_match()


class HelpModal(ModalScreen):
    """Keybindings & Help popup (ncdu '?' style)."""
    BINDINGS = [
        ("escape", "close", "Close"),
        ("q", "close", "Close"),
        ("enter", "close", "Close"),
        ("?", "close", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="k9s_modal"):
            yield Label("📖 TSK-TUI Controls & Shortcuts (ncdu / k9s style)", id="modal_title")
            with VerticalScroll(id="info_scroll"):
                yield Static("""
[bold cyan]Navigation (ncdu & vim keys):[/bold cyan]
  [yellow]↑ / ↓[/yellow] or [yellow]k / j[/yellow]          : Move cursor up / down
  [yellow]→ / l / Enter[/yellow]          : Enter directory OR open file viewer
  [yellow]← / h / Backspace / u[/yellow]  : Go to parent directory
  [yellow]g / G[/yellow]                  : Jump to top / bottom of file list

[bold cyan]Forensics & Actions (k9s style):[/bold cyan]
  [yellow]p[/yellow]                      : Open Partition / Volume selector
  [yellow]v[/yellow]                      : Open Fullscreen Hex / Text / Inode Viewer
  [yellow]i[/yellow]                      : Show Inode Info & Metadata popup (istat)
  [yellow]e[/yellow]                      : Extract currently selected file to ./extracted/
  [yellow]E[/yellow]                      : Extract ALL deleted files in current directory
  [yellow]d[/yellow]                      : Toggle "Deleted Files Only" mode
  [yellow]s[/yellow]                      : Disk-wide string search (srch_strings)
  [yellow]h[/yellow]                      : Compute & display MD5 / SHA-256 hashes
  [yellow]/[/yellow]                      : Real-time fuzzy filter
  [yellow]Esc[/yellow]                    : Clear filter / Cancel

[bold cyan]General:[/bold cyan]
  [yellow]?[/yellow]                      : Open this help screen
  [yellow]q[/yellow]                      : Quit TSK-TUI
                """, id="info_body")
            with Horizontal(id="modal_buttons"):
                yield Button("Close (Esc / ?)", variant="primary", id="btn_help_close")

    def action_close(self) -> None:
        self.dismiss()

    @on(Button.Pressed, "#btn_help_close")
    def on_close_btn(self) -> None:
        self.dismiss()


class TSKTUIApp(App):
    CSS = """
    Screen {
        background: #0d1117;
        color: #c9d1d9;
    }
    
    /* Top K9s/NCDU style Banner */
    #k9s_header {
        height: 4;
        background: #161b22;
        border-bottom: solid #30363d;
        padding: 0 1;
    }
    #banner_title {
        color: #58a6ff;
        text-style: bold;
    }
    #context_bar {
        color: #8b949e;
    }
    #action_bar {
        color: #e3b341;
        background: #21262d;
        padding: 0 1;
    }
    
    /* Path / Filter Bar */
    #path_bar {
        height: 3;
        background: #0d1117;
        border-bottom: solid #21262d;
        padding: 0 1;
        align: left middle;
    }
    #current_path_label {
        color: #7ee787;
        text-style: bold;
    }
    #quick_filter {
        width: 35;
        height: 1;
        border: none;
        background: #161b22;
        color: #58a6ff;
        padding: 0 1;
    }
    
    /* Main Table (ncdu style full screen table) */
    #main_table {
        height: 1fr;
        background: #0d1117;
        border: none;
    }
    
    /* Footer Status */
    #k9s_footer {
        height: 1;
        background: #161b22;
        color: #8b949e;
        padding: 0 1;
    }
    
    /* Modal styles */
    #k9s_modal {
        width: 85%;
        height: 80%;
        background: #161b22;
        border: double #58a6ff;
        padding: 1 2;
        align: center middle;
    }
    #modal_title {
        color: #58a6ff;
        text-style: bold;
        margin-bottom: 1;
    }
    #search_status {
        color: #8b949e;
        margin-bottom: 1;
    }
    #modal_buttons {
        height: 3;
        align: right middle;
        margin-top: 1;
    }
    #info_scroll {
        height: 1fr;
        background: #0d1117;
        border: solid #30363d;
        padding: 1;
    }
    #info_body {
        color: #c9d1d9;
    }
    #part_table, #search_table {
        height: 1fr;
        background: #0d1117;
        border: solid #30363d;
    }
    
    /* Viewer Screen */
    #viewer_container {
        width: 95%;
        height: 90%;
        background: #161b22;
        border: double #7ee787;
        padding: 1;
    }
    #viewer_header {
        height: 2;
        align: left middle;
        border-bottom: solid #30363d;
    }
    #viewer_title {
        color: #7ee787;
        text-style: bold;
    }
    #viewer_shortcuts {
        color: #e3b341;
        text-align: right;
    }
    #viewer_tabs {
        height: 1fr;
    }
    #viewer_footer {
        height: 1;
        color: #8b949e;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("?", "help", "Help"),
        Binding("p", "open_partitions", "Partitions"),
        Binding("v", "view_file", "View"),
        Binding("i", "show_info", "Info"),
        Binding("e", "extract_file", "Extract"),
        Binding("E", "extract_all_deleted", "Extract All Del"),
        Binding("d", "toggle_deleted", "Del Only"),
        Binding("s", "search", "Search"),
        Binding("h", "calc_hash", "Hash"),
        Binding("slash", "focus_filter", "Filter"),
        Binding("escape", "clear_filter", "Clear Filter", show=False),
        # ncdu / vim navigation
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("l", "enter_item", "Enter", show=False),
        Binding("enter", "enter_item", "Enter", show=False),
        Binding("right", "enter_item", "Enter", show=False),
        Binding("h", "go_parent", "Parent", show=False),
        Binding("left", "go_parent", "Parent", show=False),
        Binding("backspace", "go_parent", "Parent", show=False),
        Binding("u", "go_parent", "Parent", show=False),
        Binding("g", "go_top", "Top", show=False),
        Binding("G", "go_bottom", "Bottom", show=False),
    ]

    def __init__(self, image_path: str, initial_offset: Optional[int] = None, show_deleted: bool = False):
        super().__init__()
        self.backend = TSKBackend(image_path)
        self.initial_offset = initial_offset
        self.partitions: List[Partition] = []
        self.current_partition: Optional[Partition] = None
        self.current_offset: int = initial_offset if initial_offset is not None else 0
        self.path_stack: List[Tuple[str, str]] = []  # [(dir_name, inode)]
        self.current_files: List[FileEntry] = []
        self.show_deleted_only: bool = show_deleted
        self.filter_text: str = ""
        self.visible_files: List[FileEntry] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="k9s_header"):
            yield Label(f"⎈ TSK-TUI  v0.1.0  |  Disk: {os.path.basename(self.backend.image_path)}", id="banner_title")
            yield Label("Loading partition & context...", id="context_bar")
            yield Label(" <p> Partitions  <v> View  <i> Info  <e> Extract  <E> Ext All Del  <d> Del Only  <s> Search  </> Filter  <?> Help  <q> Quit", id="action_bar")

        with Horizontal(id="path_bar"):
            yield Label("--- / -------------------------------------------------------------", id="current_path_label")
            yield Input(placeholder="/ filter...", id="quick_filter")

        yield DataTable(id="main_table")
        yield Label("Ready", id="k9s_footer")

    def on_mount(self) -> None:
        table = self.query_one("#main_table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.clear(columns=True)
        table.add_columns("Flags / Type", "Inode", "Name", "Size", "Modified Time", "UID/GID")
        
        self.load_partitions()

    def load_partitions(self) -> None:
        self.partitions = self.backend.get_partitions()
        
        # Check if initial_offset was requested
        if self.initial_offset is not None:
            match = next((p for p in self.partitions if p.start == self.initial_offset), None)
            if match:
                self.select_partition(match)
                return

        alloc_parts = [p for p in self.partitions if p.is_allocated]
        if alloc_parts:
            self.select_partition(alloc_parts[0])
        elif self.partitions:
            self.select_partition(self.partitions[0])

    def select_partition(self, partition: Partition) -> None:
        self.current_partition = partition
        self.current_offset = partition.start
        self.path_stack = [("/", "")]
        self.update_context_bar()
        self.refresh_directory()

    def update_context_bar(self) -> None:
        if not self.current_partition:
            return
        desc = self.current_partition.description
        offset = self.current_partition.start
        slot = self.current_partition.slot
        ctx_text = f"Partition: [{slot} {desc} (Sector {offset})]  |  Status: {'ALLOCATED' if self.current_partition.is_allocated else 'UNALLOCATED'}"
        self.query_one("#context_bar", Label).update(ctx_text)

    def refresh_directory(self) -> None:
        current_dir_inode = self.path_stack[-1][1] if self.path_stack else ""
        current_path_str = "/".join([name for name, _ in self.path_stack if name != "/"])
        full_path = f"/{current_path_str}".replace("//", "/")
        
        dash_fill = "-" * max(10, 70 - len(full_path))
        self.query_one("#current_path_label", Label).update(f"--- {full_path} {dash_fill}")

        self.current_files = self.backend.list_files(
            offset=self.current_offset,
            inode=current_dir_inode or None,
            show_deleted_only=self.show_deleted_only
        )
        self.populate_table()

    def populate_table(self) -> None:
        table = self.query_one("#main_table", DataTable)
        table.clear(columns=False)

        filter_q = self.filter_text.lower()
        self.visible_files = []

        # Add '..' entry if inside subdirectory (ncdu style)
        if len(self.path_stack) > 1:
            table.add_row(
                Text("📁 DIR", style="bold cyan"),
                "--",
                Text("/..", style="bold cyan"),
                "--",
                "--",
                "--"
            )

        for f in self.current_files:
            if filter_q and filter_q not in f.name.lower() and filter_q not in f.inode:
                continue
            self.visible_files.append(f)

        for f in self.visible_files:
            if f.entry_type == 'd':
                type_flag = Text("📁 DIR", style="bold cyan")
                name_fmt = Text(f"{f.name}/", style="bold cyan")
            elif f.entry_type == 'l':
                type_flag = Text("🔗 LINK", style="magenta")
                name_fmt = Text(f"{f.name} ->", style="magenta")
            elif f.entry_type == 'v':
                type_flag = Text("⚙️ VIRT", style="yellow")
                name_fmt = Text(f"${f.name}", style="yellow")
            else:
                type_flag = Text("📄 FILE", style="green")
                name_fmt = Text(f.name, style="bright_white")

            if f.is_deleted:
                type_flag = Text("💀 [DEL]", style="bold white on red")
                name_fmt = Text(f"{f.name}*", style="bold red")

            inode_fmt = Text(f.inode, style="bold" if not f.is_deleted else "dim")
            size_fmt = format_size(f.size)
            mtime_fmt = f.mtime.split(" (")[0] if f.mtime else "--"
            ugid_fmt = f"{f.uid}:{f.gid}" if f.uid or f.gid else "--"

            table.add_row(
                type_flag,
                inode_fmt,
                name_fmt,
                size_fmt,
                mtime_fmt,
                ugid_fmt
            )

        del_cnt = sum(1 for f in self.current_files if f.is_deleted)
        del_badge = f" | [bold red]{del_cnt} deleted[/bold red]" if del_cnt > 0 else ""
        mode_badge = " [DELETED ONLY]" if self.show_deleted_only else ""
        filter_badge = f" [Filter: '{self.filter_text}']" if self.filter_text else ""
        
        self.query_one("#k9s_footer", Label).update(
            f" Total items: {len(self.current_files)} (Visible: {len(self.visible_files)}){del_badge}{mode_badge}{filter_badge}"
        )

        table.focus()
        if len(table.rows) > 0:
            table.move_cursor(row=0)

    def get_selected_file(self) -> Optional[FileEntry]:
        table = self.query_one("#main_table", DataTable)
        if table.cursor_row is None:
            return None
        
        has_parent = len(self.path_stack) > 1
        if has_parent and table.cursor_row == 0:
            return None
        idx = table.cursor_row - (1 if has_parent else 0)
        if 0 <= idx < len(self.visible_files):
            return self.visible_files[idx]
        return None

    # Navigation Actions (ncdu & k9s style)
    def action_cursor_down(self) -> None:
        self.query_one("#main_table", DataTable).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#main_table", DataTable).action_cursor_up()

    def action_go_top(self) -> None:
        table = self.query_one("#main_table", DataTable)
        if len(table.rows) > 0:
            table.move_cursor(row=0)

    def action_go_bottom(self) -> None:
        table = self.query_one("#main_table", DataTable)
        if len(table.rows) > 0:
            table.move_cursor(row=len(table.rows) - 1)

    def action_enter_item(self) -> None:
        table = self.query_one("#main_table", DataTable)
        if table.cursor_row is None:
            return
            
        has_parent = len(self.path_stack) > 1
        if has_parent and table.cursor_row == 0:
            self.action_go_parent()
            return

        file_item = self.get_selected_file()
        if not file_item:
            return

        if file_item.entry_type == 'd':
            self.path_stack.append((file_item.name, file_item.inode))
            self.filter_text = ""
            self.query_one("#quick_filter", Input).value = ""
            self.refresh_directory()
        else:
            self.action_view_file()

    def action_go_parent(self) -> None:
        if len(self.path_stack) > 1:
            self.path_stack.pop()
            self.filter_text = ""
            self.query_one("#quick_filter", Input).value = ""
            self.refresh_directory()
        else:
            self.notify("Already at root directory of partition.", timeout=1)

    # Forensic & Triage Actions
    def action_open_partitions(self) -> None:
        def on_partition_chosen(partition: Optional[Partition]) -> None:
            if partition:
                self.select_partition(partition)
                self.notify(f"Switched to partition: {partition.description}", timeout=2)

        self.push_screen(PartitionModal(self.partitions, self.current_offset), on_partition_chosen)

    def action_view_file(self) -> None:
        selected = self.get_selected_file()
        if not selected:
            self.notify("No file selected to view.", severity="warning")
            return
        self.push_screen(ViewFileScreen(self.backend, self.current_offset, selected))

    def action_show_info(self) -> None:
        selected = self.get_selected_file()
        if not selected:
            fs_info = self.backend.get_fsstat(self.current_offset)
            self.push_screen(InfoModal("File System Info (fsstat)", fs_info))
            return

        istat_out = self.backend.get_istat(self.current_offset, selected.inode)
        self.push_screen(InfoModal(f"{selected.name} (Inode {selected.inode})", istat_out))

    def action_extract_file(self) -> None:
        selected = self.get_selected_file()
        if not selected:
            self.notify("No file selected.", severity="warning")
            return
        
        dest_dir = os.path.abspath("./extracted")
        ok, path_or_err, hashes = self.backend.extract_file(
            self.current_offset,
            selected.inode,
            dest_dir,
            selected.name
        )
        if ok:
            self.notify(
                f"Extracted: {os.path.basename(path_or_err)}\nMD5: {hashes.get('md5')}",
                title="Saved to ./extracted/",
                timeout=4
            )
        else:
            self.notify(f"Extract failed: {path_or_err}", severity="error", timeout=4)

    def action_extract_all_deleted(self) -> None:
        deleted_files = [f for f in self.current_files if f.is_deleted and f.entry_type != 'd']
        if not deleted_files:
            self.notify("No deleted files found in current directory.", severity="warning")
            return

        dest_dir = os.path.abspath("./extracted/deleted")
        count = 0
        for f in deleted_files:
            ok, _, _ = self.backend.extract_file(self.current_offset, f.inode, dest_dir, f.name)
            if ok:
                count += 1

        self.notify(f"Extracted {count}/{len(deleted_files)} deleted files to {dest_dir}", title="Bulk Extraction", timeout=4)

    def action_toggle_deleted(self) -> None:
        self.show_deleted_only = not self.show_deleted_only
        self.refresh_directory()
        status = "ON" if self.show_deleted_only else "OFF"
        self.notify(f"Deleted files filter: {status}", timeout=1)

    def action_calc_hash(self) -> None:
        selected = self.get_selected_file()
        if not selected or selected.entry_type == 'd':
            self.notify("Select a regular file to compute hashes.", severity="warning")
            return

        data = self.backend.read_file_bytes(self.current_offset, selected.inode, max_bytes=-1)
        if not data:
            self.notify("File is empty or cannot read bytes.", severity="warning")
            return

        md5_v = hashlib.md5(data).hexdigest()
        sha256_v = hashlib.sha256(data).hexdigest()
        self.notify(f"MD5: {md5_v}\nSHA256: {sha256_v}", title=f"Hashes for {selected.name}", timeout=6)

    def action_search(self) -> None:
        self.push_screen(SearchModal(self.backend))

    def action_help(self) -> None:
        self.push_screen(HelpModal())

    def action_focus_filter(self) -> None:
        inp = self.query_one("#quick_filter", Input)
        inp.focus()

    def action_clear_filter(self) -> None:
        inp = self.query_one("#quick_filter", Input)
        inp.value = ""
        self.filter_text = ""
        self.populate_table()
        self.query_one("#main_table", DataTable).focus()

    @on(Input.Changed, "#quick_filter")
    def on_filter_changed(self, event: Input.Changed) -> None:
        self.filter_text = event.value
        self.populate_table()

    @on(Input.Submitted, "#quick_filter")
    def on_filter_submitted(self) -> None:
        self.query_one("#main_table", DataTable).focus()

    @on(DataTable.RowSelected, "#main_table")
    def on_table_selected(self) -> None:
        self.action_enter_item()
