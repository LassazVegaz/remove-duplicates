import os
import hashlib
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, Canvas, Frame, Scrollbar, ttk
import webbrowser
from typing import Callable, Dict, List, Optional


def hash_file(filepath: str, chunk_size: int = 8192) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def find_duplicates(
    folder: str,
    output_callback: Callable[[str], None],
    done_callback: Callable[[Dict[str, List[str]]], None],
    update_progress: Callable[[int, int], None],
    stop_event: threading.Event,
) -> None:
    def worker() -> None:
        all_files: List[str] = []
        for root, _, files in os.walk(folder):
            if stop_event.is_set():
                output_callback("[Cancelled] Scanning stopped.")
                return
            for name in files:
                filepath = os.path.join(root, name)
                all_files.append(filepath)

        total_files = len(all_files)
        scanned = 0
        files_by_size: Dict[int, List[str]] = {}

        for filepath in all_files:
            if stop_event.is_set():
                output_callback("[Cancelled] Scanning stopped.")
                return
            # logs the scanning file
            output_callback("[Scanning] " + filepath)
            try:
                size = os.path.getsize(filepath)
                files_by_size.setdefault(size, []).append(filepath)
            except Exception as e:
                output_callback(f"[Error] {filepath} - {e}")
            scanned += 1
            update_progress(scanned, total_files)

        potential_dupes = {k: v for k, v in files_by_size.items() if len(v) > 1}
        duplicates: Dict[str, List[str]] = {}

        for size, files in potential_dupes.items():
            if stop_event.is_set():
                output_callback("[Cancelled] Scanning stopped.")
                return
            hashes: Dict[str, str] = {}
            for file in files:
                if stop_event.is_set():
                    output_callback("[Cancelled] Scanning stopped.")
                    return
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

    threading.Thread(target=worker, daemon=True).start()


class DuplicateFinderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Duplicate File Finder")
        self.root.geometry("900x700")

        self.stop_event: Optional[threading.Event] = None
        self.result_widgets: List[tk.Widget] = []
        self.log_widgets: List[tk.Widget] = []

        # Controls
        control_frame = tk.Frame(root)
        control_frame.pack(pady=10)

        tk.Label(control_frame, text="Select a folder to scan for duplicates:").pack(
            side="left", padx=5
        )
        tk.Button(control_frame, text="Select Folder", command=self.select_folder).pack(
            side="left", padx=5
        )
        self.btn_cancel = tk.Button(
            control_frame, text="Cancel Scan", command=self.cancel_scan
        )
        self.btn_cancel.pack(side="left", padx=5)
        self.btn_cancel.config(state=tk.DISABLED)

        # Progress
        self.progress_label = tk.Label(root, text="", anchor="w")
        self.progress_label.pack(fill="x", padx=10)
        self.progress_bar = ttk.Progressbar(
            root, orient="horizontal", length=100, mode="determinate"
        )
        self.progress_bar.pack(fill="x", padx=10, pady=(0, 10))

        # Logs
        log_container = tk.Frame(root)
        log_container.pack(fill="x", padx=10)
        tk.Label(log_container, text="Logs:").pack(anchor="w")
        self.log_canvas = Canvas(log_container, height=120)
        self.log_scroll_y = Scrollbar(
            log_container, orient="vertical", command=self.log_canvas.yview
        )
        self.log_frame = Frame(self.log_canvas)
        self.log_frame.bind(
            "<Configure>",
            lambda e: self.log_canvas.configure(
                scrollregion=self.log_canvas.bbox("all")
            ),
        )
        self.log_canvas.create_window((0, 0), window=self.log_frame, anchor="nw")
        self.log_canvas.configure(yscrollcommand=self.log_scroll_y.set)
        self.log_canvas.pack(side="left", fill="x", expand=True)
        self.log_scroll_y.pack(side="right", fill="y")

        # Results
        result_container = tk.Frame(root)
        result_container.pack(fill="both", expand=True, padx=10, pady=(10, 10))
        tk.Label(result_container, text="Duplicate Files:").pack(anchor="w")
        self.result_canvas = Canvas(result_container)
        self.result_scroll_y = Scrollbar(
            result_container, orient="vertical", command=self.result_canvas.yview
        )
        self.result_scroll_x = Scrollbar(
            result_container, orient="horizontal", command=self.result_canvas.xview
        )
        self.result_frame = Frame(self.result_canvas)
        self.result_frame.bind(
            "<Configure>",
            lambda e: self.result_canvas.configure(
                scrollregion=self.result_canvas.bbox("all")
            ),
        )
        self.result_canvas.create_window((0, 0), window=self.result_frame, anchor="nw")
        self.result_canvas.configure(
            yscrollcommand=self.result_scroll_y.set,
            xscrollcommand=self.result_scroll_x.set,
        )
        self.result_canvas.pack(side="left", fill="both", expand=True)
        self.result_scroll_y.pack(side="right", fill="y")
        self.result_scroll_x.pack(side="bottom", fill="x")

        self.result_canvas.bind_all(
            "<MouseWheel>",
            lambda e: self.result_canvas.yview_scroll(
                int(-1 * (e.delta / 120)), "units"
            ),
        )

    def select_folder(self) -> None:
        folder: str = filedialog.askdirectory()
        if folder:
            self.clear_results()
            self.log(f"Scanning folder: {folder}")
            self.stop_event = threading.Event()
            self.btn_cancel.config(state=tk.NORMAL)
            self.progress_bar["value"] = 0
            self.progress_label.config(text="")
            find_duplicates(
                folder,
                self.log,
                self.display_results,
                self.update_progress,
                self.stop_event,
            )

    def cancel_scan(self) -> None:
        if self.stop_event:
            self.stop_event.set()
            self.btn_cancel.config(state=tk.DISABLED)

    def log(self, msg: str) -> None:
        label = tk.Label(
            self.log_frame,
            text=msg,
            fg="gray",
            anchor="w",
            justify="left",
            wraplength=850,
        )
        label.pack(fill="x", anchor="w", pady=2, padx=5)
        self.log_widgets.append(label)
        self.root.after(50, lambda: self.log_canvas.yview_moveto(1.0))

    def clear_results(self) -> None:
        for widget in self.result_widgets:
            widget.destroy()
        for widget in self.log_widgets:
            widget.destroy()
        self.result_widgets.clear()
        self.log_widgets.clear()

    def update_progress(self, current: int, total: int) -> None:
        progress_percent = int((current / total) * 100)
        self.root.after(0, lambda: self.progress_bar.config(value=progress_percent))
        self.root.after(
            0,
            lambda: self.progress_label.config(
                text=f"Scanning file {current} of {total} ({progress_percent}%)"
            ),
        )

    def display_results(self, duplicates: Dict[str, List[str]]) -> None:
        self.btn_cancel.config(state=tk.DISABLED)
        self.progress_label.config(text="Scan complete.")
        if not duplicates:
            self.log("No duplicate files found.")
            return

        for hash_val, files in duplicates.items():
            group_label = tk.Label(
                self.result_frame,
                text=f"\nDuplicate Set - {hash_val[:10]}...",
                fg="blue",
            )
            group_label.pack(anchor="w", padx=5)
            self.result_widgets.append(group_label)
            for file in files:
                self.create_file_buttons(file)

    def create_file_buttons(self, filepath: str) -> None:
        btn_frame = tk.Frame(self.result_frame)
        btn_frame.pack(anchor="w", fill="x", padx=20, pady=2)

        view_btn = tk.Button(
            btn_frame, text="View", command=lambda: self.view_file(filepath)
        )
        view_btn.pack(side="left")

        del_btn = tk.Button(
            btn_frame,
            text="Delete",
            command=lambda: self.delete_file(filepath, btn_frame),
        )
        del_btn.pack(side="left")

        path_label = tk.Label(
            btn_frame, text=filepath, anchor="w", justify="left", wraplength=700
        )
        path_label.pack(side="left", padx=10)

        self.result_widgets.append(btn_frame)
        self.root.after(50, lambda: self.result_canvas.yview_moveto(1.0))

    def view_file(self, filepath: str) -> None:
        try:
            webbrowser.open(filepath)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open file:\n{e}")

    def delete_file(self, filepath: str, widget: tk.Widget) -> None:
        confirm = messagebox.askyesno(
            "Delete", f"Are you sure you want to delete:\n{filepath}"
        )
        if confirm:
            try:
                os.remove(filepath)
                self.log(f"[Deleted] {filepath}")
                widget.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Could not delete file:\n{e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = DuplicateFinderApp(root)
    root.mainloop()
