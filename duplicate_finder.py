import os
import threading
from typing import Callable, Dict, List
from hash_utils import hash_file


def find_duplicates(
    folder: str,
    output_callback: Callable[[str], None],
    done_callback: Callable[[Dict[str, List[str]]], None],
    update_progress: Callable[[int, int], None],
    stop_event: threading.Event,
) -> None:
    def worker() -> None:
        output_callback("[Scanning] Getting total files count")

        all_files: List[str] = []
        for root, _, files in os.walk(folder):
            if stop_event.is_set():
                output_callback("[Cancelled] Scanning stopped.")
                return
            output_callback(f"[Scanning] {root}")

            for name in files:
                filepath = os.path.join(root, name)
                all_files.append(filepath)

        total_files = len(all_files)
        scanned = 0
        files_by_size: Dict[int, List[str]] = {}

        output_callback(f"[Scanning] Found {total_files} files")
        output_callback("[Scanning] Searching for duplicates")

        for filepath in all_files:
            if stop_event.is_set():
                output_callback("[Cancelled] Scanning stopped.")
                return
            output_callback("[Scanning] " + filepath)

            try:
                size = os.path.getsize(filepath)
                files_by_size.setdefault(size, []).append(filepath)
            except Exception as e:
                output_callback(f"[Error] {filepath} - {e}")
            scanned += 1
            update_progress(scanned, total_files)

        size_groups = len(files_by_size)
        output_callback("[Scanning] Searching for duplicates done")
        output_callback("[Hashing] Hashing files to group duplicates")
        output_callback(f"[Hashing] Groups of same size files found: {size_groups}")

        potential_dupes = {k: v for k, v in files_by_size.items() if len(v) > 1}
        duplicates: Dict[str, List[str]] = {}
        groups_counter = 0

        for size, files in potential_dupes.items():
            if stop_event.is_set():
                output_callback("[Cancelled] Scanning stopped.")
                return
            groups_counter += 1
            output_callback(f"[Hashing] Size group: {groups_counter} of {size_groups}")
            output_callback(f"[Hashing] Size group: {size} - {len(files)} files")

            files_counter = 0
            files_count = len(files)
            hashes: Dict[str, str] = {}
            for file in files:
                if stop_event.is_set():
                    output_callback("[Cancelled] Scanning stopped.")
                    return
                files_counter += 1
                output_callback(f"[Hashing] {files_counter} of {files_count}")

                try:
                    h = hash_file(file)
                    if h in hashes:
                        duplicates.setdefault(h, [hashes[h]]).append(file)
                    else:
                        hashes[h] = file
                except Exception as e:
                    output_callback(f"[Error] Hashing {file} - {e}")
                scanned += 1
                update_progress(scanned, total_files)

        done_callback(duplicates)

    def error_safe_worker() -> None:
        try:
            worker()
        except Exception as e:
            output_callback("[Error] An unexpected error occurred.")
            output_callback(f"[Error] {e}")
            done_callback({})

    threading.Thread(target=error_safe_worker, daemon=True).start()
