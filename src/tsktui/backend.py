"""
Backend interface for The Sleuth Kit (TSK) command-line utilities.
Wraps mmls, fls, icat, istat, fsstat, and srch_strings via subprocess.
"""

import os
import re
import subprocess
import hashlib
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any


@dataclass
class Partition:
    """Represents a volume/partition detected by mmls or raw filesystem check."""
    slot: str
    start: int
    end: int
    length: int
    description: str
    is_allocated: bool


@dataclass
class FileEntry:
    """Represents a filesystem entry (file, directory, deleted file) from fls."""
    entry_type: str       # 'd' (dir), 'r' (file), 'v' (virtual), 'l' (symlink), '-' (unknown)
    is_deleted: bool
    inode: str            # Inode identifier (e.g. "10161", "12")
    is_realloc: bool
    name: str
    mtime: str = ""
    atime: str = ""
    ctime: str = ""
    crtime: str = ""
    size: str = ""
    uid: str = ""
    gid: str = ""


class TSKBackend:
    """Wrapper around The Sleuth Kit CLI binaries for forensic disk analysis."""

    def __init__(self, image_path: str):
        self.image_path = os.path.abspath(image_path)
        if not os.path.exists(self.image_path):
            raise FileNotFoundError(f"Disk image not found: {self.image_path}")

    def run_cmd(self, cmd: List[str]) -> Tuple[int, str, str]:
        """Runs a command returning returncode, stdout, stderr as text."""
        try:
            p = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors="replace"
            )
            stdout, stderr = p.communicate()
            return p.returncode, stdout, stderr
        except Exception as e:
            return -1, "", str(e)

    def run_cmd_bytes(self, cmd: List[str]) -> Tuple[int, bytes, bytes]:
        """Runs a command returning returncode, stdout, stderr as raw bytes."""
        try:
            p = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = p.communicate()
            return p.returncode, stdout, stderr
        except Exception as e:
            return -1, b"", str(e).encode()

    def get_partitions(self) -> List[Partition]:
        """Detect partitions using mmls. Fallback to raw filesystem if no table."""
        code, out, _ = self.run_cmd(["mmls", self.image_path])
        partitions: List[Partition] = []

        if code == 0 and out:
            lines = out.splitlines()
            for line in lines:
                m = re.match(r'^\s*(\d+):\s+(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(.+)$', line)
                if m:
                    slot_num, slot_type, start, end, length, desc = m.groups()
                    is_alloc = "Unallocated" not in desc and "Meta" not in slot_type and "Table" not in desc
                    partitions.append(Partition(
                        slot=f"{slot_num}: {slot_type}",
                        start=int(start),
                        end=int(end),
                        length=int(length),
                        description=desc.strip(),
                        is_allocated=is_alloc
                    ))

        if not partitions:
            # Fallback: check if raw filesystem at sector 0
            code_fs, fs_out, _ = self.run_cmd(["fsstat", self.image_path])
            fs_name = "Raw File System"
            if code_fs == 0:
                for line in fs_out.splitlines():
                    if "File System Type:" in line:
                        fs_name = line.split(":", 1)[1].strip()
                        break
            file_size = os.path.getsize(self.image_path)
            partitions.append(Partition(
                slot="000: Raw",
                start=0,
                end=0,
                length=file_size // 512,
                description=fs_name,
                is_allocated=True
            ))

        return partitions

    def get_fsstat(self, offset: int = 0) -> str:
        """Runs fsstat to obtain filesystem metadata and statistics."""
        cmd = ["fsstat"]
        if offset > 0:
            cmd.extend(["-o", str(offset)])
        cmd.append(self.image_path)
        _, out, err = self.run_cmd(cmd)
        return out if out else err

    def list_files(self, offset: int = 0, inode: Optional[str] = None, show_deleted_only: bool = False) -> List[FileEntry]:
        """Lists files and directories in a partition/directory using fls."""
        cmd = ["fls", "-p", "-l"]
        if offset > 0:
            cmd.extend(["-o", str(offset)])
        if show_deleted_only:
            cmd.append("-d")
        cmd.append(self.image_path)
        if inode:
            cmd.append(str(inode))

        code, out, _ = self.run_cmd(cmd)
        if code != 0:
            return []

        entries: List[FileEntry] = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue

            is_deleted = " * " in line or line.startswith("*") or "* " in line[:10]
            
            type_match = re.match(r'^([a-zA-Z\-\+]/[a-zA-Z\-\+])', line)
            entry_type = 'r'
            if type_match:
                prefix = type_match.group(1)
                if 'd' in prefix:
                    entry_type = 'd'
                elif 'v' in prefix or 'V' in prefix:
                    entry_type = 'v'
                elif 'l' in prefix:
                    entry_type = 'l'
                else:
                    entry_type = 'r'

            inode_match = re.search(r'(\d+)(\(realloc\))?:', line)
            if not inode_match:
                continue

            inode_str = inode_match.group(1)
            is_realloc = bool(inode_match.group(2))

            after_colon = line[inode_match.end():].strip()
            parts = after_colon.split('\t')

            name = parts[0].strip() if parts else ""
            mtime = parts[1].strip() if len(parts) > 1 else ""
            atime = parts[2].strip() if len(parts) > 2 else ""
            ctime = parts[3].strip() if len(parts) > 3 else ""
            crtime = parts[4].strip() if len(parts) > 4 else ""
            size = parts[5].strip() if len(parts) > 5 else ""
            uid = parts[6].strip() if len(parts) > 6 else ""
            gid = parts[7].strip() if len(parts) > 7 else ""

            if name in (".", ".."):
                continue

            entries.append(FileEntry(
                entry_type=entry_type,
                is_deleted=is_deleted,
                inode=inode_str,
                is_realloc=is_realloc,
                name=name,
                mtime=mtime,
                atime=atime,
                ctime=ctime,
                crtime=crtime,
                size=size,
                uid=uid,
                gid=gid
            ))

        return entries

    def get_istat(self, offset: int = 0, inode: str = "") -> str:
        """Runs istat to inspect inode metadata."""
        if not inode:
            return "No inode specified."
        cmd = ["istat"]
        if offset > 0:
            cmd.extend(["-o", str(offset)])
        cmd.extend([self.image_path, str(inode)])
        _, out, err = self.run_cmd(cmd)
        return out if out else err

    def read_file_bytes(self, offset: int = 0, inode: str = "", max_bytes: int = 65536) -> bytes:
        """Extracts file content to memory via icat with strict byte limit."""
        if not inode:
            return b""
        cmd = ["icat"]
        if offset > 0:
            cmd.extend(["-o", str(offset)])
        cmd.extend([self.image_path, str(inode)])
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if max_bytes > 0:
                data = p.stdout.read(max_bytes) if p.stdout else b""
                try:
                    p.terminate()
                except Exception:
                    pass
                return data
            else:
                data, _ = p.communicate()
                return data
        except Exception:
            return b""

    def extract_file(self, offset: int, inode: str, dest_dir: str, file_name: str) -> Tuple[bool, str, Dict[str, str]]:
        """
        Securely streams and extracts a file to dest_dir with path traversal
        protection and live hashing (O(1) memory usage).
        """
        try:
            dest_dir_abs = os.path.abspath(dest_dir)
            os.makedirs(dest_dir_abs, exist_ok=True)

            # Sanitize filename and strictly prevent path traversal
            clean_name = os.path.basename(file_name) or f"inode_{inode}.bin"
            clean_name = re.sub(r'[^\w\.\-\_]', '_', clean_name)
            dest_path_abs = os.path.abspath(os.path.join(dest_dir_abs, f"{inode}_{clean_name}"))

            if not dest_path_abs.startswith(dest_dir_abs):
                return False, "Security error: Invalid destination path traversal detected", {}

            cmd = ["icat"]
            if offset > 0:
                cmd.extend(["-o", str(offset)])
            cmd.extend([self.image_path, str(inode)])
            
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            md5_obj = hashlib.md5()
            sha256_obj = hashlib.sha256()
            bytes_written = 0

            with open(dest_path_abs, "wb") as f:
                if p.stdout:
                    while True:
                        chunk = p.stdout.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        md5_obj.update(chunk)
                        sha256_obj.update(chunk)
                        bytes_written += len(chunk)

            _, err = p.communicate()
            if p.returncode != 0:
                if os.path.exists(dest_path_abs) and bytes_written == 0:
                    try:
                        os.remove(dest_path_abs)
                    except OSError:
                        pass
                return False, f"icat error: {err.decode(errors='replace')}", {}

            return True, dest_path_abs, {
                "md5": md5_obj.hexdigest(),
                "sha256": sha256_obj.hexdigest(),
                "size": str(bytes_written)
            }
        except Exception as e:
            return False, str(e), {}

    def search_strings(self, keyword: str, max_results: int = 200) -> List[Dict[str, Any]]:
        """Searches for keyword across disk strings safely with bounded limits."""
        cmd = ["srch_strings", "-a", "-t", "d", self.image_path]
        try:
            p = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors="replace"
            )
            results: List[Dict[str, Any]] = []
            if p.stdout:
                for line in p.stdout:
                    if keyword.lower() in line.lower():
                        parts = line.strip().split(" ", 1)
                        if len(parts) == 2:
                            offset_str, match_str = parts
                            results.append({"offset": offset_str, "content": match_str[:160]})
                        else:
                            results.append({"offset": "0", "content": line.strip()[:160]})
                        if len(results) >= max_results:
                            break
            try:
                p.terminate()
                p.wait(timeout=1.0)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
            return results
        except Exception as e:
            return [{"offset": "0", "content": f"Error executing srch_strings: {e}"}]
