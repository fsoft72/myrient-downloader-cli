# Myrient Downloader

A terminal-based (TUI) downloader for [Myrient](https://myrient.erista.me/), written in Python using the [Textual](https://textual.textualize.io/) framework.

This tool allows you to browse the Myrient file repository directly from your terminal and download entire folders recursively with resume support.

## Features

*   **Terminal User Interface**: Clean and modern TUI with mouse support.
*   **Recursive Download**: Download entire folders and their subfolders with a single keypress.
*   **Resume Support**: Automatically resumes interrupted downloads.
*   **Smart Navigation**: Browse directories with keyboard or mouse.
*   **Progress Tracking**: Real-time progress bar and status updates.
*   **Settings Persistence**: Saves your download destination preference.
*   **File Details**: Displays file sizes in the browser.

## Installation

You can install the package directly using pip:

```bash
pip install myrient-downloader-cli
```

Or build and install locally from source:

```bash
git clone https://github.com/yourusername/myrient-downloader-cli.git
cd myrient-downloader-cli
pip install .
```

## Usage

Run the application using the command line interface:

```bash
myrient-cli
```

### Controls

| Key | Action |
| :--- | :--- |
| `↑` / `↓` | Navigate the file list |
| `Enter` | Open selected folder |
| `Backspace` | Go to parent folder |
| `Ctrl+d` | **Download** current folder content (recursive) |
| `?` | Open **Settings** (change destination) |
| `Esc` | Go back / Stop active download (double press) |
| `Ctrl+q` | **Quit** application |
| `Type...` | **Type-ahead Search** (filters current view) |

## Configuration

Press `?` within the application to set your default download destination. This setting is saved to `settings.json` in the script's directory.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This tool is an unofficial client and is not affiliated with Myrient or Erista. Please respect their service terms and bandwidth.
