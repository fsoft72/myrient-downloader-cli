#!/usr/bin/env python3
import os
import sys
import time
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote, urlparse
from pathlib import Path
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, ListView, ListItem, Label, Input, Button, ProgressBar, Static, DataTable
from textual.screen import Screen, ModalScreen
from textual.binding import Binding
from textual.worker import Worker, get_current_worker
from textual import work
from textual.reactive import reactive
from textual.message import Message
from rich.text import Text

BASE_URL = "https://myrient.erista.me/files/"
SETTINGS_FILE = "settings.json"
VERSION = "0.2.0"

class SettingsScreen(ModalScreen):
    BINDINGS = [("escape", "close_settings", "Close")]

    def __init__(self, current_dest):
        super().__init__()
        self.current_dest = current_dest

    def compose(self) -> ComposeResult:
        with Container(id="settings-dialog"):
            yield Label("Settings", id="settings-title")
            yield Label("Destination Folder:")
            yield Input(value=self.current_dest, id="dest-input")
            with Horizontal(id="settings-buttons"):
                yield Button("Save", variant="primary", id="save-btn")
                yield Button("Cancel", variant="error", id="cancel-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            new_dest = self.query_one("#dest-input", Input).value
            self.dismiss(new_dest)
        else:
            self.dismiss(None)
    
    def action_close_settings(self):
        self.dismiss(None)

class MyrientDownloader(App):
    TITLE = f"Myrient Downloader v{VERSION}"
    CSS = """
    #settings-dialog {
        padding: 1;
        border: solid green;
        width: 60;
        height: auto;
        background: $surface;
        align: center middle;
    }
    #settings-buttons {
        margin-top: 1;
        align: center middle;
    }
    Button {
        margin: 1;
    }
    DataTable {
        border: solid blue;
        height: 1fr;
    }
    #status-bar {
        height: auto;
        dock: bottom;
        background: $primary-darken-2;
        color: white;
        padding: 0 1;
    }
    ProgressBar {
        width: 100%;
        margin: 1 0;
        display: none;
    }
    .downloading ProgressBar {
        display: block;
    }
    """

    BINDINGS = [
        Binding("d", "download_folder", "Download Folder"),
        Binding("?", "open_settings", "Settings"),
        Binding("escape", "handle_esc", "Back/Stop"),
        Binding("delete", "go_up", "Up"),
        Binding("q", "handle_quit", "Quit"),
    ]

    current_url = reactive(BASE_URL)
    destination_folder = reactive(os.getcwd())
    download_queue = []
    is_downloading = reactive(False)
    is_loading_dir = reactive(False)
    current_download_worker = None
    last_esc_time = 0
    last_q_time = 0

    def watch_is_loading_dir(self, value: bool) -> None:
        progress_bar = self.query_one("#progress", ProgressBar)
        status_text = self.query_one("#status-text", Label)
        
        if value:
            if not self.is_downloading:
                progress_bar.display = True
                progress_bar.total = None # Indeterminate
                status_text.update("Loading directory...")
        else:
            if not self.is_downloading:
                progress_bar.display = False
                progress_bar.total = 100
                status_text.update("Ready")
            else:
                # Restore download status if needed
                pass

    def show_error(self, message):
        self.notify(message, severity="error")
        print(f"ERROR: {message}", file=sys.stderr)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(f"Current: {self.current_url}", id="url-label")
        yield DataTable(id="file-list", cursor_type="row")
        with Container(id="status-bar"):
            yield Label("Ready", id="status-text")
            yield ProgressBar(total=100, show_eta=True, id="progress")
        yield Footer()

    def on_mount(self):
        self.load_settings()
        table = self.query_one("#file-list", DataTable)
        table.add_columns("Name", "Size")
        self.load_directory_worker(self.current_url)

    def load_settings(self):
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)
                    self.destination_folder = settings.get("destination_folder", os.getcwd())
        except Exception as e:
            self.show_error(f"Error loading settings: {e}")

    def save_settings(self):
        try:
            settings = {"destination_folder": self.destination_folder}
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            self.show_error(f"Error saving settings: {e}")

    def parse_directory_html(self, html_content, base_url):
        soup = BeautifulSoup(html_content, 'html.parser')
        items = []
        
        # Try to find the content table first
        content_table = soup.find('table', id='list')
        
        if content_table:
            # Table parsing (preferred)
            rows = content_table.find_all('tr')
            for row in rows:
                link_td = row.find('td', class_='link')
                if not link_td:
                    continue
                    
                link = link_td.find('a')
                if not link:
                    continue
                    
                href = link.get('href')
                text = link.text.strip()
                
                size_td = row.find('td', class_='size')
                size = size_td.text.strip() if size_td else "-"
                
                if not href: continue
                if href in ['../', '/', './', '/donate/', '/non-affiliation-disclaimer/', '/dmca/']: continue
                if '?' in href: continue
                if text == "Parent Directory": continue

                full_url = urljoin(base_url, href)
                is_dir = href.endswith('/')
                
                items.append((text, is_dir, full_url, size))
        else:
            # Fallback parsing
            links = soup.find_all('a')
            for link in links:
                href = link.get('href')
                text = link.text.strip()
                
                if not href: continue
                
                classes = link.get('class', [])
                if classes and 'menu' in classes: continue
                
                if href in ['../', '/', './', '/donate/', '/non-affiliation-disclaimer/', '/dmca/']: continue
                if '?' in href: continue
                if text == "Parent Directory": continue

                full_url = urljoin(base_url, href)
                is_dir = href.endswith('/')
                
                items.append((text, is_dir, full_url, "-"))
            
        return items

    @work(thread=True)
    def load_directory_worker(self, url):
        self.app.call_from_thread(setattr, self, "is_loading_dir", True)
        try:
            response = requests.get(url)
            response.raise_for_status()
            
            items = self.parse_directory_html(response.text, url)
            
            # Sort: directories first, then files
            items.sort(key=lambda x: (not x[1], x[0]))

            def update_ui():
                table = self.query_one("#file-list", DataTable)
                table.clear()
                
                # Update URL label
                self.query_one("#url-label", Label).update(f"Current: {url}")

                self.row_data = {} # Reset the lookup
                
                for text_content, is_dir, full_url, size in items:
                    icon = "📁 " if is_dir else "📄 "
                    display_name = Text(icon)
                    display_name.append(text_content)
                    
                    row_key = table.add_row(display_name, size)
                    self.row_data[row_key] = (text_content, is_dir, full_url)
                    
                table.focus()
            
            self.app.call_from_thread(update_ui)

        except Exception as e:
            self.app.call_from_thread(self.show_error, f"Error loading directory: {e}")
        finally:
            self.app.call_from_thread(setattr, self, "is_loading_dir", False)

    def load_directory(self, url):
        # Deprecated, use load_directory_worker
        self.load_directory_worker(url)

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        row_key = event.row_key
        if row_key in self.row_data:
            name, is_dir, href = self.row_data[row_key]
            if is_dir:
                self.current_url = href
                self.load_directory_worker(self.current_url)
            else:
                self.notify("Press 'd' to download the folder content.", severity="information")

    def action_go_up(self):
        if self.current_url == BASE_URL:
            self.notify("Already at root.", severity="warning")
            return
        
        # Go up one level
        if self.current_url.endswith('/'):
            parent = self.current_url.rstrip('/')
            parent = parent.rsplit('/', 1)[0] + '/'
        else:
            parent = self.current_url.rsplit('/', 1)[0] + '/'
            
        if not parent.startswith(BASE_URL):
            parent = BASE_URL
            
        self.current_url = parent
        self.load_directory_worker(self.current_url)

    def action_handle_esc(self):
        now = time.time()
        if now - self.last_esc_time < 0.5:
            # Double ESC
            if self.is_downloading:
                self.stop_download()
        else:
            # Single ESC
            if not self.is_downloading:
                self.action_go_up()
            else:
                self.notify("Press ESC again to stop download", severity="warning")
        self.last_esc_time = now

    def action_handle_quit(self):
        now = time.time()
        if now - self.last_q_time < 0.5:
            self.exit()
        else:
            self.notify("Press 'q' again to quit", severity="information")
        self.last_q_time = now

    def action_open_settings(self):
        def set_dest(new_dest):
            if new_dest:
                self.destination_folder = new_dest
                self.save_settings()
                self.notify(f"Destination set to: {self.destination_folder}")
        
        self.push_screen(SettingsScreen(self.destination_folder), set_dest)

    def action_download_folder(self):
        if self.is_downloading:
            self.notify("Already downloading!", severity="warning")
            return

        # Collect all items in current view (files AND dirs)
        items_to_process = []
        # We can use self.row_data
        for key, value in self.row_data.items():
            name, is_dir, href = value
            items_to_process.append((name, is_dir, href))

        if not items_to_process:
            self.notify("Nothing to download in this folder.", severity="warning")
            return

        self.download_queue = items_to_process
        self.start_download_worker()

    @work(thread=True, exclusive=True)
    def start_download_worker(self):
        self.is_downloading = True
        self.query_one("#status-bar").add_class("downloading")
        progress_bar = self.query_one("#progress", ProgressBar)
        status_label = self.query_one("#status-text", Label)
        
        queue = list(self.download_queue)
        worker = get_current_worker()

        while queue:
            if worker.is_cancelled:
                break

            name, is_dir, url = queue.pop(0)

            if is_dir:
                status_label.update(Text(f"Scanning: {name}"))
                try:
                    response = requests.get(url)
                    response.raise_for_status()
                    items = self.parse_directory_html(response.text, url)
                    # Add to queue
                    for item_name, item_is_dir, item_url, _ in items:
                        queue.append((item_name, item_is_dir, item_url))
                except Exception as e:
                    self.show_error(f"Error scanning {name}: {e}")
                continue

            # It is a file
            status_label.update(Text(f"Downloading: {name} (Queue: {len(queue)})"))
            
            # Calculate path based on URL
            if not url.startswith(BASE_URL):
                continue

            rel_path = url[len(BASE_URL):]
            rel_path = unquote(rel_path)
            filepath = os.path.join(self.destination_folder, rel_path)
            
            # Ensure dir exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Resume logic
            resume_header = {}
            mode = 'wb'
            downloaded = 0
            
            if os.path.exists(filepath):
                downloaded = os.path.getsize(filepath)
                try:
                    head_resp = requests.head(url, allow_redirects=True)
                    total_size = int(head_resp.headers.get('content-length', 0))
                    
                    if downloaded >= total_size and total_size > 0:
                        # self.notify(f"Skipping {name} (already exists)")
                        continue
                        
                    if downloaded > 0:
                        resume_header = {'Range': f'bytes={downloaded}-'}
                        mode = 'ab'
                except:
                    pass

            try:
                with requests.get(url, stream=True, headers=resume_header) as r:
                    r.raise_for_status()
                    total_length = int(r.headers.get('content-length', 0))
                    
                    if mode == 'ab':
                        total_length += downloaded
                        
                    progress_bar.update(total=total_length, progress=downloaded)
                    
                    with open(filepath, mode) as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if worker.is_cancelled:
                                break
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                progress_bar.update(progress=downloaded)
            except Exception as e:
                self.show_error(f"Error downloading {name}: {e}")

        self.is_downloading = False
        self.query_one("#status-bar").remove_class("downloading")
        status_label.update("Ready")
        self.notify("Download finished!")

    def stop_download(self):
        # Cancel the worker
        self.workers.cancel_all()
        self.is_downloading = False
        self.query_one("#status-bar").remove_class("downloading")
        self.query_one("#status-text", Label).update("Download stopped.")
        self.notify("Download stopped by user.")

if __name__ == "__main__":
    app = MyrientDownloader()
    app.run()
