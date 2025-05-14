import os
import hashlib
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, Canvas, Frame, Scrollbar
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
    stop_event: threading.Event,
) -> None:
    def worker() -> None:
        files_by_size: Dict[int, List[str]] = {}
        for root, _, files in os.walk(folder):
            if stop_event.is_set():
                output_callback("[Cancelled] Scanning stopped.")
                return
            for name in files:
                if stop_event.is_set():
                    output_callback("[Cancelled] Scanning stopped.")
                    return
                filepath = os.path.join(root, name)
                # logs the scanning folder
                output_callback("[Scanning] " + filepath)
                try:
                    size = os.path.getsize(filepath)
                    files_by_size.setdefault(size, []).append(filepath)
                except Exception as e:
                    output_callback(f"[Error] {filepath} - {e}")

        potential_dupes: Dict[int, List[str]] = {
            k: v for k, v in files_by_size.items() if len(v) > 1
        }
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

        done_callback(duplicates)

    threading.Thread(target=worker, daemon=True).start()


class DuplicateFinderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Duplicate File Finder")
        self.root.geometry("800x600")

        self.stop_event: Optional[threading.Event] = None
        self.result_widgets: List[tk.Widget] = []

        self.label = tk.Label(root, text="Select a folder to scan for duplicates:")
        self.label.pack(pady=10)

        self.btn_select = tk.Button(
            root, text="Select Folder", command=self.select_folder
        )
        self.btn_select.pack()

        self.btn_cancel = tk.Button(root, text="Cancel Scan", command=self.cancel_scan)
        self.btn_cancel.pack()
        self.btn_cancel.config(state=tk.DISABLED)

        # Scrollable result frame
        self.canvas = Canvas(root, borderwidth=0)
        self.scroll_y = Scrollbar(root, orient="vertical", command=self.canvas.yview)
        self.frame = Frame(self.canvas)

        self.frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.create_window((0, 0), window=self.frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scroll_y.set)

        self.canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        self.scroll_y.pack(side="right", fill="y")

    def select_folder(self) -> None:
        folder: str = filedialog.askdirectory()
        if folder:
            self.clear_results()
            self.log(f"Scanning folder: {folder}")
            self.stop_event = threading.Event()
            self.btn_cancel.config(state=tk.NORMAL)
            find_duplicates(folder, self.log, self.display_results, self.stop_event)

    def cancel_scan(self) -> None:
        if self.stop_event:
            self.stop_event.set()
            self.btn_cancel.config(state=tk.DISABLED)

    def log(self, msg: str) -> None:
        label = tk.Label(
            self.frame, text=msg, fg="gray", anchor="w", justify="left", wraplength=750
        )
        label.pack(fill="x", anchor="w", pady=2, padx=5)
        self.result_widgets.append(label)

    def clear_results(self) -> None:
        for widget in self.result_widgets:
            widget.destroy()
        self.result_widgets.clear()

    def display_results(self, duplicates: Dict[str, List[str]]) -> None:
        self.btn_cancel.config(state=tk.DISABLED)
        if not duplicates:
            self.log("No duplicate files found.")
            return

        for hash_val, files in duplicates.items():
            self.log(f"\nDuplicate Set - {hash_val[:10]}...")
            for file in files:
                self.create_file_buttons(file)

    def create_file_buttons(self, filepath: str) -> None:
        btn_frame = tk.Frame(self.frame)
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
            btn_frame, text=filepath, anchor="w", justify="left", wraplength=650
        )
        path_label.pack(side="left", padx=10)

        self.result_widgets.append(btn_frame)

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
