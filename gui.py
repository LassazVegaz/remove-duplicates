import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, Canvas, Frame, Scrollbar, ttk
import webbrowser
from typing import Dict, List, Optional
from duplicate_finder import find_duplicates
import datetime


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

        self.log_file_path = "duplicate_finder.log"
        # Make sure to create or clear the log file when the app starts
        with open(self.log_file_path, "w", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now()}] Log started\n\n")

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
        # Format message with timestamp
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_msg = f"[{timestamp}] {msg}"

        print(full_msg)  # Print to console for debugging

        # Log to GUI
        label = tk.Label(
            self.log_frame,
            text=full_msg,
            fg="gray",
            anchor="w",
            justify="left",
            wraplength=850,
        )
        label.pack(fill="x", anchor="w", pady=2, padx=5)
        self.log_widgets.append(label)
        self.root.after(50, lambda: self.log_canvas.yview_moveto(1.0))

        # Log to file
        try:
            with open(self.log_file_path, "a", encoding="utf-8") as f:
                f.write(full_msg + "\n")
        except Exception as e:
            print(f"Failed to write log to file: {e}")

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
