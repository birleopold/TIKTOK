from __future__ import annotations

import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from unified_app.config import PYTHON, ROOT
from unified_app.services.hunt_downloads import (
    DOWNLOAD_ROOT,
    HuntDownloadCandidate,
    dependency_status,
    download_selected_candidates,
    ensure_download_root,
    probe_candidate,
    recent_download_candidates,
)


class HuntDownloaderApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Hunt Downloads")
        self.geometry("1280x780")
        self.minsize(980, 620)
        self.configure(bg="#f4f7fb")
        self.rows_by_item: dict[str, HuntDownloadCandidate] = {}
        self.status = tk.StringVar(value="Ready")
        self.filter_text = tk.StringVar(value="")
        self.source_type = tk.StringVar(value="All")
        self.search_label = tk.StringVar(value="")
        self.rights_confirmed = tk.BooleanVar(value=False)
        self._build()
        self._refresh()

    def _build(self) -> None:
        header = tk.Frame(self, bg="#101828", height=84)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="Hunt Downloads",
            bg="#101828",
            fg="white",
            font=("Segoe UI", 22, "bold"),
        ).pack(anchor="w", padx=20, pady=(13, 0))
        tk.Label(
            header,
            text="Select saved Hunt candidates, preview them, and keep only videos you are permitted to download.",
            bg="#101828",
            fg="#cbd5e1",
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=21)

        shell = ttk.Frame(self, padding=14)
        shell.pack(fill="both", expand=True)

        filters = ttk.Frame(shell)
        filters.pack(fill="x", pady=(0, 8))
        ttk.Label(filters, text="Filter:").pack(side="left")
        entry = ttk.Entry(filters, textvariable=self.filter_text, width=36)
        entry.pack(side="left", padx=(6, 12))
        entry.bind("<Return>", lambda _event: self._refresh())
        ttk.Label(filters, text="Type:").pack(side="left")
        ttk.Combobox(
            filters,
            textvariable=self.source_type,
            values=("All", "TikTok", "YouTube", "Web"),
            state="readonly",
            width=12,
        ).pack(side="left", padx=(6, 12))
        ttk.Button(filters, text="Refresh", command=self._refresh).pack(side="left")
        ok, dep = dependency_status()
        ttk.Label(
            filters,
            text=dep,
            foreground="#166534" if ok else "#b91c1c",
        ).pack(side="right")
        if not ok:
            ttk.Button(
                filters,
                text="Install yt-dlp",
                command=self._install_yt_dlp,
            ).pack(side="right", padx=(0, 8))

        table_shell = ttk.Frame(shell)
        table_shell.pack(fill="both", expand=True)
        columns = ("id", "type", "status", "title", "url")
        self.tree = ttk.Treeview(
            table_shell,
            columns=columns,
            show="headings",
            selectmode="extended",
        )
        widths = {"id": 55, "type": 90, "status": 100, "title": 380, "url": 510}
        for column in columns:
            self.tree.heading(column, text=column.title())
            self.tree.column(
                column,
                width=widths[column],
                stretch=column in {"title", "url"},
            )
        scroll_y = ttk.Scrollbar(table_shell, orient="vertical", command=self.tree.yview)
        scroll_x = ttk.Scrollbar(table_shell, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        table_shell.rowconfigure(0, weight=1)
        table_shell.columnconfigure(0, weight=1)
        self.tree.bind("<Double-1>", lambda _event: self._preview())

        options = ttk.Frame(shell)
        options.pack(fill="x", pady=(10, 6))
        ttk.Label(options, text="Download folder label:").pack(side="left")
        ttk.Entry(options, textvariable=self.search_label, width=32).pack(
            side="left",
            padx=(6, 14),
        )
        ttk.Checkbutton(
            options,
            text=(
                "I own these videos, have permission, or am otherwise legally "
                "allowed to download and reuse them."
            ),
            variable=self.rights_confirmed,
        ).pack(side="left", fill="x", expand=True)

        buttons = ttk.Frame(shell)
        buttons.pack(fill="x", pady=(0, 8))
        ttk.Button(buttons, text="Preview Source", command=self._preview).pack(
            side="left",
            padx=(0, 6),
        )
        ttk.Button(buttons, text="Check Video", command=self._probe).pack(
            side="left",
            padx=(0, 6),
        )
        self.download_button = ttk.Button(
            buttons,
            text="Download Selected",
            command=self._download,
        )
        self.download_button.pack(side="left", padx=(0, 6))
        ttk.Button(
            buttons,
            text="Open Downloads",
            command=self._open_downloads,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            buttons,
            text="Select All Visible",
            command=lambda: self.tree.selection_set(self.tree.get_children()),
        ).pack(side="right")

        self.output = tk.Text(
            shell,
            height=9,
            wrap="word",
            font=("Consolas", 9),
            bg="#101828",
            fg="#e7edf5",
            insertbackground="white",
            relief="flat",
            padx=10,
            pady=8,
        )
        self.output.pack(fill="x")

        tk.Label(
            self,
            textvariable=self.status,
            anchor="w",
            bg="#dbeafe",
            fg="#172033",
            padx=12,
            pady=6,
            font=("Segoe UI", 9, "bold"),
        ).pack(fill="x")

    def _write(self, message: str, clear: bool = False) -> None:
        if clear:
            self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, message.rstrip() + "\n")
        self.output.see(tk.END)
        self.status.set(message.splitlines()[-1][:180])

    def _refresh(self) -> None:
        rows = recent_download_candidates(
            source_type=self.source_type.get(),
            query=self.filter_text.get(),
        )
        self.tree.delete(*self.tree.get_children())
        self.rows_by_item.clear()
        for row in rows:
            item = self.tree.insert(
                "",
                tk.END,
                values=(row.id, row.source_type, row.status, row.title, row.url),
            )
            self.rows_by_item[item] = row
        self.status.set(f"Loaded {len(rows)} saved Hunt candidates.")

    def _selected(self) -> list[HuntDownloadCandidate]:
        return [
            self.rows_by_item[item]
            for item in self.tree.selection()
            if item in self.rows_by_item
        ]

    def _one_selected(self) -> HuntDownloadCandidate | None:
        rows = self._selected()
        if not rows:
            messagebox.showinfo("Hunt Downloads", "Select a result first.")
            return None
        return rows[0]

    def _preview(self) -> None:
        row = self._one_selected()
        if row:
            webbrowser.open(row.url)

    def _probe(self) -> None:
        row = self._one_selected()
        if not row:
            return
        self._write(f"Checking: {row.title}", clear=True)

        def worker() -> None:
            try:
                details = probe_candidate(row)
                text = "\n".join(f"{key.title()}: {value}" for key, value in details.items())
                self.after(0, lambda: self._write(text))
            except Exception as exc:
                self.after(
                    0,
                    lambda: (
                        self._write(f"Check failed: {exc}"),
                        messagebox.showwarning("Video Check", str(exc)),
                    ),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _download(self) -> None:
        rows = self._selected()
        if not rows:
            messagebox.showinfo(
                "Hunt Downloads",
                "Select one or more results with Ctrl-click or Shift-click.",
            )
            return
        if not self.rights_confirmed.get():
            messagebox.showwarning(
                "Rights confirmation required",
                (
                    "Confirm that you own the selected content, have permission, "
                    "or are otherwise legally allowed to download and reuse it."
                ),
            )
            return
        if not messagebox.askyesno(
            "Download selected videos",
            (
                f"Download {len(rows)} selected result(s)?\n\n"
                "Private, DRM-protected, unsupported, and playlist pages will be skipped."
            ),
        ):
            return

        label = self.search_label.get().strip()
        if not label:
            label = rows[0].title
            self.search_label.set(label)

        self.download_button.configure(state="disabled")
        self._write(f"Starting {len(rows)} selected download(s)...", clear=True)

        def progress(message: str) -> None:
            self.after(0, lambda: self._write(message))

        def worker() -> None:
            successes, errors = download_selected_candidates(
                rows,
                search_label=label,
                progress=progress,
            )
            self.after(
                0,
                lambda: self._finish_download(successes, errors),
            )

        threading.Thread(target=worker, daemon=True).start()

    def _finish_download(self, successes, errors) -> None:
        self.download_button.configure(state="normal")
        self._write(
            f"Completed: {len(successes)} saved, {len(errors)} skipped/failed."
        )
        for result in successes:
            self._write(f"SAVED: {result.local_path}")
        for error in errors:
            self._write(f"ERROR: {error}")
        self._refresh()
        if errors:
            messagebox.showwarning(
                "Downloads completed with notices",
                f"{len(successes)} saved and {len(errors)} skipped/failed. See the log.",
            )
        else:
            messagebox.showinfo(
                "Downloads completed",
                f"Saved {len(successes)} video(s) to:\n{ensure_download_root()}",
            )

    def _open_downloads(self) -> None:
        folder = ensure_download_root()
        try:
            subprocess.Popen(["explorer", str(folder)])
        except Exception as exc:
            messagebox.showwarning("Open Downloads", str(exc))

    def _install_yt_dlp(self) -> None:
        try:
            subprocess.Popen(
                [PYTHON, "-m", "pip", "install", "-U", "yt-dlp"],
                cwd=str(ROOT),
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
            )
            messagebox.showinfo(
                "Install yt-dlp",
                "The installer opened in a new console. Restart Hunt Downloads after it finishes.",
            )
        except Exception as exc:
            messagebox.showwarning("Install yt-dlp", str(exc))


def main() -> None:
    ensure_download_root()
    HuntDownloaderApp().mainloop()


if __name__ == "__main__":
    main()
