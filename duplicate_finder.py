import os
import threading
import sqlite3
from typing import Callable, Dict, List
from hash_utils import hash_file


def find_duplicates(
    folder: str,
    output_callback: Callable[[str], None],
    done_callback: Callable[[Dict[str, List[str]]], None],
    update_progress: Callable[[int, int], None],
    stop_event: threading.Event,
) -> None:
    threading.Thread(
        target=lambda: _run_find_duplicates(
            folder, output_callback, done_callback, update_progress, stop_event
        ),
        daemon=True,
    ).start()


def _run_find_duplicates(
    folder: str,
    output_callback: Callable[[str], None],
    done_callback: Callable[[Dict[str, List[str]]], None],
    update_progress: Callable[[int, int], None],
    stop_event: threading.Event,
) -> None:
    try:
        with sqlite3.connect(":memory:") as conn:
            _setup_database(conn)
            total_files = _scan_files(
                folder, conn, output_callback, update_progress, stop_event
            )
            if stop_event.is_set():
                output_callback("[Cancelled] Scanning stopped.")
                return

            _hash_files(conn, output_callback, update_progress, total_files, stop_event)
            if stop_event.is_set():
                output_callback("[Cancelled] Scanning stopped.")
                return

            duplicates = _find_duplicates_from_db(conn)
            done_callback(duplicates)

    except Exception as e:
        output_callback(f"[Error] Unexpected error: {e}")
        done_callback({})


def _setup_database(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE files (
            id INTEGER PRIMARY KEY,
            path TEXT NOT NULL,
            size INTEGER NOT NULL,
            hash TEXT
        )
    """
    )
    cursor.execute("CREATE INDEX idx_size ON files (size)")
    cursor.execute("CREATE INDEX idx_hash ON files (hash)")
    conn.commit()


def _scan_files(
    folder: str,
    conn: sqlite3.Connection,
    output_callback: Callable[[str], None],
    update_progress: Callable[[int, int], None],
    stop_event: threading.Event,
) -> int:
    output_callback("[Scanning] Collecting file list...")

    all_files: List[str] = []
    for root, _, files in os.walk(folder):
        if stop_event.is_set():
            return 0
        for name in files:
            filepath = os.path.join(root, name)
            all_files.append(filepath)

    total_files = len(all_files)
    scanned = 0
    cursor = conn.cursor()

    for filepath in all_files:
        if stop_event.is_set():
            return scanned
        try:
            size = os.path.getsize(filepath)
            cursor.execute(
                "INSERT INTO files (path, size) VALUES (?, ?)", (filepath, size)
            )
        except Exception as e:
            output_callback(f"[Error] {filepath} - {e}")
        scanned += 1
        if scanned % 100 == 0:
            conn.commit()
        update_progress(scanned, total_files)

    conn.commit()
    output_callback(f"[Scanning] Finished scanning {total_files} files.")
    return total_files


def _hash_files(
    conn: sqlite3.Connection,
    output_callback: Callable[[str], None],
    update_progress: Callable[[int, int], None],
    total_files: int,
    stop_event: threading.Event,
) -> None:
    output_callback("[Hashing] Hashing files with duplicate sizes...")

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT size FROM files
        GROUP BY size
        HAVING COUNT(*) > 1
    """
    )
    size_groups = cursor.fetchall()

    group_index = 0
    scanned = 0

    for (size,) in size_groups:
        if stop_event.is_set():
            return

        group_index += 1
        output_callback(
            f"[Hashing] Group {group_index} / {len(size_groups)} (size: {size})"
        )

        cursor.execute("SELECT path FROM files WHERE size = ?", (size,))
        files = cursor.fetchall()

        for i, (file_path,) in enumerate(files, start=1):
            if stop_event.is_set():
                return
            output_callback(f"[Hashing] {i} / {len(files)} - {file_path}")
            try:
                file_hash = hash_file(file_path)
                cursor.execute(
                    "UPDATE files SET hash = ? WHERE path = ?", (file_hash, file_path)
                )
            except Exception as e:
                output_callback(f"[Error] Hashing {file_path} - {e}")
            scanned += 1
            if scanned % 100 == 0:
                conn.commit()
            update_progress(scanned, total_files)

    conn.commit()
    output_callback("[Hashing] Done hashing files.")


def _find_duplicates_from_db(conn: sqlite3.Connection) -> Dict[str, List[str]]:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT hash, GROUP_CONCAT(path)
        FROM files
        WHERE hash IS NOT NULL
        GROUP BY hash
        HAVING COUNT(*) > 1
    """
    )
    result = cursor.fetchall()

    duplicates: Dict[str, List[str]] = {}
    for file_hash, paths_str in result:
        paths = paths_str.split(",")
        duplicates[file_hash] = paths
    return duplicates
