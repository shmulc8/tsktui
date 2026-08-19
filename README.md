# ⎈ tsktui

> **The `k9s` / `ncdu` for Digital Forensics & The Sleuth Kit (TSK)**  
> Fast, interactive, keyboard-driven terminal explorer for disk images, partition tables, deleted files, and forensic triage.

```
┌─ ⎈ TSK-TUI  v0.1.0  |  Disk: evidence.dd ────────────────────────────────────────────────────────┐
│ Partition: [002: Linux (0x83) (Sector 2048)]  |  Status: ALLOCATED                                │
│ <p> Partitions  <v> View  <i> Info  <e> Extract  <E> Ext All Del  <d> Del Only  <s> Search  ...   │
├───────────────────────────────────────────────────────────────────────────────────────────────────┤
│ --- /home/user ---------------------------------------------------------------------------------- │
│  Flags / Type │  Inode  │ Name                  │ Size     │ Modified Time       │ UID/GID        │
│ ──────────────┼─────────┼───────────────────────┼──────────┼─────────────────────┼─────────────── │
│  📁 DIR       │ --      │ /..                   │ --       │ --                  │ --             │
│  📁 DIR       │ 10162   │ documents/            │ 4.0 KB   │ 2024-03-28 00:52:30 │ 1000:1000      │
│  💀 [DEL]     │ 10165   │ secret_flag.txt*      │ 1.2 KB   │ 2024-03-28 01:14:10 │ 1000:1000      │
│  📄 FILE      │ 10168   │ bash_history          │ 8.4 KB   │ 2024-03-28 01:20:00 │ 1000:1000      │
│  ⚙️ VIRT      │ 1612678 │ $OrphanFiles          │ --       │ --                  │ --             │
└───────────────────────────────────────────────────────────────────────────────────────────────────┘
 Total items: 4 (Visible: 4 | 1 deleted)
```

---

## ⚡ Features

* **Instant Triage:** Fast startup (<100ms), zero case-database indexing, works over headless SSH.
* **Deleted Files Highlighting:** Deleted inodes highlighted in bold red with `d` toggle filter.
* **Fullscreen Pager (`v`):** Multi-mode viewer with colorized Hex dump, UTF-8 Text, and Inode metadata (`istat`).
* **Forensic Actions:** Single-key extraction (`e`), bulk deleted-files extraction (`E`), live hashing (`h`), and disk-wide string search (`s`).

---

## 📦 Prerequisites & Installation

### 1. Install The Sleuth Kit

`tsktui` requires SleuthKit CLI tools (`fls`, `icat`, `mmls`, `istat`, `fsstat`):

```bash
# macOS
brew install sleuthkit

# Debian / Ubuntu / Kali
sudo apt-get install sleuthkit

# Fedora / Arch
sudo dnf install sleuthkit   # Fedora
sudo pacman -S sleuthkit     # Arch
```

### 2. Install tsktui

Install directly from GitHub via `pipx` or `pip`:

```bash
pipx install git+https://github.com/shmulc8/tsktui.git
```

Or clone and run locally:

```bash
git clone https://github.com/shmulc8/tsktui.git
cd tsktui
./tsktui <path-to-disk.img>
```

---

## 💻 Usage

```bash
# Open disk or partition image
tsktui evidence.img

# Jump to specific sector offset
tsktui -o 2048 evidence.raw

# Launch directly in Deleted Files Only mode
tsktui -d evidence.dd
```

---

## ⌨️ Keybindings

| Key | Action |
| :--- | :--- |
| **`j` / `k`** or **`↓` / `↑`** | Move cursor down / up |
| **`l` / `Enter`** or **`→`** | Enter directory OR open file viewer |
| **`h` / `Backspace` / `u`** | Go up to parent directory |
| **`g` / `G`** | Jump to top / bottom of list |
| **`p`** | Switch partition / volume (`mmls`) |
| **`v`** | Fullscreen Hex / Text / Inode Viewer (`icat`) |
| **`i`** | Inode metadata popup (`istat`) |
| **`e`** | Extract file to `./extracted/` |
| **`E`** | Extract all deleted files in current directory |
| **`d`** | Toggle **Deleted Files Only** mode |
| **`s`** | Disk-wide string search (`srch_strings`) |
| **`h`** | Compute MD5 & SHA-256 hashes |
| **`/`** | Real-time substring filter (`Esc` to clear) |
| **`?`** | Help popup |
| **`q`** | Quit |

---

## 📄 License

[MIT License](LICENSE)
