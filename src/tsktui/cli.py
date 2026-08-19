"""
Command-line interface entry point for tsktui.
"""

import os
import sys
import shutil
import argparse
from rich.console import Console
from rich.panel import Panel

from . import __version__
from .ui import TSKTUIApp


def check_sleuthkit_installed() -> bool:
    """Verifies that The Sleuth Kit CLI tools are installed in PATH."""
    required_binaries = ["fls", "icat", "mmls", "istat", "fsstat"]
    missing = [b for b in required_binaries if not shutil.which(b)]
    return len(missing) == 0


def print_missing_tsk_error() -> None:
    console = Console()
    console.print(Panel("""
[bold red]Error: The Sleuth Kit (TSK) tools were not found in your PATH.[/bold red]

tsktui requires `fls`, `icat`, `mmls`, `istat`, and `fsstat` to analyze disk images.

[bold cyan]Installation instructions:[/bold cyan]
  • [yellow]macOS (Homebrew):[/yellow]     brew install sleuthkit
  • [yellow]Debian / Ubuntu:[/yellow]      sudo apt-get install sleuthkit
  • [yellow]Fedora / RHEL:[/yellow]        sudo dnf install sleuthkit
  • [yellow]Arch Linux:[/yellow]           sudo pacman -S sleuthkit
  • [yellow]Alpine Linux:[/yellow]         apk add sleuthkit
  • [yellow]Windows (WSL):[/yellow]        wsl -- sudo apt-get install sleuthkit
    """, title="⚠️ Missing Prerequisite: sleuthkit", border_style="red"))


def main() -> None:
    """Main CLI entrypoint."""
    if not check_sleuthkit_installed():
        print_missing_tsk_error()
        sys.exit(1)

    parser = argparse.ArgumentParser(
        prog="tsktui",
        description="⎈ tsktui: Interactive Terminal User Interface for The Sleuth Kit & DFIR Triage (ncdu/k9s style)",
        epilog="Examples:\n  tsktui disk.img\n  tsktui -o 2048 disk.raw\n  tsktui -d evidence.dd",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "image",
        help="Path to disk image, partition, or raw evidence file (e.g. .img, .dd, .raw, .001)"
    )
    parser.add_argument(
        "-o", "--offset",
        type=int,
        default=None,
        help="Initial sector offset for partition (e.g. 2048)"
    )
    parser.add_argument(
        "-d", "--deleted",
        action="store_true",
        help="Start with Deleted Files Only mode enabled"
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"%(prog)s {__version__}"
    )

    args = parser.parse_args()

    if not os.path.exists(args.image):
        console = Console()
        console.print(f"[bold red]Error:[/bold red] File not found: [yellow]{args.image}[/yellow]", file=sys.stderr)
        sys.exit(1)

    app = TSKTUIApp(args.image, initial_offset=args.offset, show_deleted=args.deleted)
    app.run()


if __name__ == "__main__":
    main()
