"""Obsidian 足迹 — a small, offline Tkinter application."""
from __future__ import annotations

import argparse
import json
import math
import queue
import threading
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from history import SHANGHAI, ROOT_FOLDER, Snapshot, load_history, summary
from app_icon import install_window_icon
from widgets import RoundedScrollbar

def local_vault() -> str:
    try:
        value = json.loads(Path(__file__).with_name("settings.local.json").read_text(encoding="utf-8")).get("vault", "")
        return value if isinstance(value, str) else ""
    except (OSError, ValueError, AttributeError):
        return ""


DEFAULT_VAULT = local_vault()
THEMES = {
    "靛蓝 · TPAMI": dict(bg="#eef0f6", panel="#ffffff", sidebar="#f7f8fb",
        text="#242a46", muted="#67738a", line="#dfe3ee", accent="#4a59b2",
        secondary="#5a5e8c", empty="#edf0f6", heat=["#bdc8df", "#5d74a2", "#4a59b2", "#33395b"],
        palette=["#33395b", "#5d74a2", "#4a59b2", "#5a5e8c"]),
    "浅滩 · 海盐": dict(bg="#f4eee9", panel="#fcfaf7", sidebar="#efe3da",
        text="#245053", muted="#577471", line="#dfd4cc", accent="#488883",
        secondary="#90baab", empty="#eee7e0", heat=["#e1c7ba", "#90baab", "#488883", "#245053"],
        palette=["#e4d2c5", "#e1c7ba", "#90baab", "#488883", "#245053"]),
    "海雾 · 子守歌": dict(bg="#edf1f3", panel="#f9fbfc", sidebar="#e5e9ed",
        text="#404e5b", muted="#677b8f", line="#d3dbe1", accent="#677b8f",
        secondary="#948f8c", empty="#e7ebee", heat=["#ccc9c6", "#8fa0b8", "#677b8f", "#404e5b"],
        palette=["#404e5b", "#677b8f", "#8fa0b8", "#948f8c", "#ccc9c6"]),
}
ORDER = {"创建": 0, "修改": 1, "删除": 2}


def longest_streak(days):
    best = run = 0
    previous = None
    for day in sorted(days):
        run = run + 1 if previous and day - previous == timedelta(days=1) else 1
        best = max(best, run)
        previous = day
    return best


class App:
    def __init__(self, root: tk.Tk, vault=DEFAULT_VAULT, autoload=True):
        self.root = root
        root.title("Obsidian 足迹")
        install_window_icon(root)
        root.geometry("1380x910")
        root.minsize(1120, 880)
        root.option_add("*Font", ("Microsoft YaHei UI", 10))
        self.theme = tk.StringVar(value=next(iter(THEMES)))
        self.year = tk.StringVar(value=str(datetime.now(SHANGHAI).year))
        self.folder_query = tk.StringVar()
        self.note_query = tk.StringVar()
        self.snapshot: Snapshot | None = None
        self.vault = str(vault)
        self.folder = ""
        self.daily = {}
        self.selected = None
        self.busy = False
        self.messages = queue.Queue()
        self.colors = THEMES[self.theme.get()]
        self.folder_ids = {}
        self.rows = {}
        self.cells = {}
        self.status_text = "选择一天，回看那天的笔记。"
        self._build()
        self.apply_theme()
        self.root.after(100, self._poll)
        if autoload and self.vault:
            self.root.after(150, self.reload)
        elif not self.vault:
            self.path_label.configure(text="尚未选择笔记目录")
            self.set_status("请选择笔记目录，开始回顾写作足迹。")

    def label(self, parent, text="", size=10, bold=False, role="text", **kwargs):
        widget = tk.Label(parent, text=text, font=("Microsoft YaHei UI", size, "bold" if bold else "normal"),
                          anchor="w", **kwargs)
        widget.color_role = role
        return widget

    def _build(self):
        self.top = tk.Frame(self.root)
        self.top.pack(fill="x", padx=28, pady=(18, 14))
        brand = tk.Frame(self.top)
        brand.pack(side="left")
        self.label(brand, "笔记足迹", 20, True).pack(anchor="w")
        self.label(brand, "把写过的日子，重新看见。", 9, role="muted").pack(anchor="w", pady=(4, 0))
        controls = tk.Frame(self.top)
        controls.pack(side="right")
        self.label(controls, "配色", role="muted").pack(side="left", padx=(0, 10))
        self.theme_combo = ttk.Combobox(controls, textvariable=self.theme, values=list(THEMES),
                                       state="readonly", width=17)
        self.theme_combo.pack(side="left")
        self.theme_combo.bind("<<ComboboxSelected>>", lambda _: self.apply_theme())
        self.swatches = tk.Canvas(controls, width=106, height=26, highlightthickness=0)
        self.swatches.pack(side="left", padx=12)
        self.refresh_button = ttk.Button(controls, text="重新读取", command=self.reload)
        self.refresh_button.pack(side="left")

        self.body = tk.Frame(self.root)
        self.body.pack(fill="both", expand=True, padx=28)
        self.sidebar = tk.Frame(self.body, width=228, padx=14, pady=16)
        self.sidebar.pack(side="left", fill="y", padx=(0, 20))
        self.sidebar.pack_propagate(False)
        self.label(self.sidebar, "笔记本", 13, True).pack(fill="x")
        self.path_label = self.label(self.sidebar, self.vault, 9, role="muted", wraplength=195)
        self.path_label.pack(fill="x", pady=(8, 12))
        self.choose_button = ttk.Button(self.sidebar, text="选择笔记目录…", command=self.choose_vault)
        self.choose_button.pack(fill="x", pady=(0, 18))
        self.label(self.sidebar, "筛选文件夹", 9, role="muted").pack(fill="x", pady=(0, 6))
        ttk.Entry(self.sidebar, textvariable=self.folder_query).pack(fill="x", pady=(0, 10))
        self.folder_query.trace_add("write", lambda *_: self.populate_folders())
        folder_box = tk.Frame(self.sidebar)
        folder_box.pack(fill="both", expand=True)
        self.folder_tree = ttk.Treeview(folder_box, show="tree", selectmode="browse")
        self.folder_tree.column("#0", width=180, stretch=True)
        folder_scroll = RoundedScrollbar(folder_box, orient="vertical", command=self.folder_tree.yview)
        self.folder_tree.configure(yscrollcommand=folder_scroll.set)
        folder_scroll.pack(side="right", fill="y")
        self.folder_tree.pack(fill="both", expand=True)
        self.folder_tree.bind("<<TreeviewSelect>>", self.select_folder)
        sidebar_footer = tk.Frame(self.sidebar)
        sidebar_footer.pack(side="bottom", fill="x", before=folder_box)
        self.vault_count = self.label(sidebar_footer, "", 9, role="muted", wraplength=194)
        self.vault_count.pack(fill="x", pady=(14, 6))
        self.label(sidebar_footer, "本地运行 · 严格只读\n按需读取，不驻留后台", 9,
                   role="muted").pack(fill="x", pady=(2, 0))

        self.main = tk.Frame(self.body)
        self.main.pack(side="left", fill="both", expand=True)
        self.filter_bar = tk.Frame(self.main)
        self.filter_bar.pack(fill="x", pady=(0, 14))
        self.scope_label = self.label(self.filter_bar, "全部笔记本", 13, True)
        self.scope_label.pack(side="left")
        year_box = tk.Frame(self.filter_bar)
        year_box.pack(side="right")
        self.label(year_box, "年份", role="muted").pack(side="left", padx=(0, 12))
        self.year_combo = ttk.Combobox(year_box, textvariable=self.year,
                                      values=[self.year.get()], state="readonly", width=7)
        self.year_combo.pack(side="right")
        self.year_combo.bind("<<ComboboxSelected>>", lambda _: self.update_view())
        self.stats = tk.Frame(self.main)
        self.stats.pack(fill="x", pady=(0, 16))
        self.stat_widgets = []
        for i, title in enumerate(("活跃天数", "涉及笔记", "笔记日数", "最长连续")):
            card = tk.Frame(self.stats, padx=18, pady=10)
            card.is_panel = True
            card.grid(row=0, column=i, sticky="nsew", padx=(0, 10 if i < 3 else 0))
            self.stats.columnconfigure(i, weight=1, uniform="cards")
            value = self.label(card, "—", 20, True, role="accent")
            value.pack(fill="x")
            self.label(card, title, 9, role="muted").pack(fill="x", pady=(3, 0))
            self.stat_widgets.append(value)

        self.heat_panel = tk.Frame(self.main, padx=18, pady=10)
        self.heat_panel.is_panel = True
        self.heat_panel.pack(fill="x", pady=(0, 16))
        heat_head = tk.Frame(self.heat_panel)
        heat_head.pack(fill="x")
        self.heat_title = self.label(heat_head, "年度写作足迹", 13, True)
        self.heat_title.pack(side="left")
        self.heat_hint = self.label(heat_head, "每格 = 当天不同笔记数", 9, role="muted")
        self.heat_hint.pack(side="right")
        self.heat_canvas = tk.Canvas(self.heat_panel, height=204, highlightthickness=0, takefocus=True)
        self.heat_canvas.pack(fill="x", pady=(10, 0))
        self.heat_canvas.bind("<Configure>", lambda _: self.draw_heatmap())
        self.heat_canvas.bind("<Motion>", self.hover_day)
        self.heat_canvas.bind("<Leave>", lambda _: self.set_status(self.status_text))
        self.heat_canvas.bind("<Button-1>", self.click_day)
        for key, offset in (("Left", -7), ("Right", 7), ("Up", -1), ("Down", 1)):
            self.heat_canvas.bind(f"<{key}>", lambda _, n=offset: self.move_day(n))

        self.details = tk.Frame(self.main, padx=18, pady=14)
        self.details.is_panel = True
        self.details.pack(fill="both", expand=True)
        detail_head = tk.Frame(self.details)
        detail_head.pack(fill="x", pady=(0, 12))
        self.day_label = self.label(detail_head, "当天笔记", 13, True)
        self.day_label.pack(side="left")
        search_box = tk.Frame(detail_head)
        search_box.pack(side="right")
        self.label(search_box, "搜索当天路径", 9, role="muted").pack(side="left", padx=(0, 8))
        ttk.Entry(search_box, textvariable=self.note_query, width=23).pack(side="left")
        self.note_query.trace_add("write", lambda *_: self.populate_notes())
        table_box = tk.Frame(self.details)
        table_box.pack(fill="both", expand=True)
        self.notes_tree = ttk.Treeview(table_box, columns=("name", "action", "source", "folder"),
                                      show="headings", selectmode="browse")
        for key, title, width, stretch in (("name", "笔记", 270, True), ("action", "操作", 150, False),
                                           ("source", "来源", 90, False), ("folder", "所在文件夹", 300, True)):
            self.notes_tree.heading(key, text=title, anchor="w")
            self.notes_tree.column(key, width=width, minwidth=70, stretch=stretch, anchor="w")
        scrollbar = RoundedScrollbar(table_box, orient="vertical", command=self.notes_tree.yview)
        hscroll = RoundedScrollbar(table_box, orient="horizontal", command=self.notes_tree.xview)
        self.notes_tree.configure(yscrollcommand=scrollbar.set, xscrollcommand=hscroll.set)
        scrollbar.pack(side="right", fill="y")
        hscroll.pack(side="bottom", fill="x")
        self.notes_tree.pack(fill="both", expand=True)
        self.notes_tree.bind("<<TreeviewSelect>>", self.note_details)
        self.notes_tree.bind("<Shift-MouseWheel>", lambda e: hscroll.wheel(e))
        self.note_info = tk.Text(self.details, height=2, wrap="word", relief="flat", borderwidth=0,
                                 font=("Microsoft YaHei UI", 9), padx=2, pady=7, state="disabled")
        self.note_info.pack(side="bottom", fill="x", pady=(8, 0), before=table_box)

        self.bottom = tk.Frame(self.root)
        self.bottom.pack(side="bottom", fill="x", padx=28, pady=(12, 16), before=self.body)
        self.status = self.label(self.bottom, "准备读取…", 9, role="muted")
        self.status.pack(side="left", fill="x", expand=True)
        ttk.Button(self.bottom, text="统计口径", command=self.show_rules).pack(side="right")

    def apply_theme(self):
        self.colors = c = THEMES[self.theme.get()]
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", font=("Microsoft YaHei UI", 10), background=c["panel"], foreground=c["text"])
        style.configure("TButton", padding=(12, 7), borderwidth=0, background=c["empty"])
        style.map("TButton", background=[("active", c["line"])])
        style.configure("TEntry", fieldbackground=c["panel"], foreground=c["text"],
                        bordercolor=c["line"], insertcolor=c["text"], padding=5)
        style.configure("TCombobox", fieldbackground=c["panel"], background=c["empty"],
                        foreground=c["text"], arrowcolor=c["text"], padding=5)
        style.map("TCombobox", fieldbackground=[("readonly", c["panel"])],
                  foreground=[("readonly", c["text"]), ("disabled", c["muted"])])
        style.configure("Treeview", background=c["panel"], fieldbackground=c["panel"],
                        foreground=c["text"], rowheight=31, borderwidth=0)
        style.configure("Treeview.Heading", background=c["empty"], foreground=c["muted"],
                        relief="flat", padding=(8, 8), font=("Microsoft YaHei UI", 9, "bold"))
        style.map("Treeview", background=[("selected", c["accent"])], foreground=[("selected", "#ffffff")])
        self.root.option_add("*TCombobox*Listbox.background", c["panel"])
        self.root.option_add("*TCombobox*Listbox.foreground", c["text"])

        def recolor(widget, bg):
            if widget is self.sidebar:
                bg = c["sidebar"]
            elif getattr(widget, "is_panel", False):
                bg = c["panel"]
            if isinstance(widget, (tk.Tk, tk.Frame, tk.Canvas)):
                widget.configure(background=bg)
            elif isinstance(widget, tk.Label):
                widget.configure(background=bg, foreground=c[getattr(widget, "color_role", "text")])
            elif isinstance(widget, tk.Text):
                widget.configure(background=bg, foreground=c["muted"], insertbackground=c["text"],
                                 selectbackground=c["accent"], selectforeground="#ffffff")
            if isinstance(widget, RoundedScrollbar):
                widget.set_colors(bg, c["heat"][0], c["accent"])
            for child in widget.winfo_children():
                recolor(child, bg)
        recolor(self.root, c["bg"])
        self.swatches.delete("all")
        for i, color in enumerate(c["palette"]):
            self.swatches.create_rectangle(i * 20 + 2, 5, i * 20 + 17, 21, fill=color, outline="")
        self.draw_heatmap()

    def choose_vault(self):
        path = filedialog.askdirectory(title="选择 Obsidian 笔记目录", initialdir=self.vault, mustexist=True)
        if path:
            self.vault = path
            self.folder = ""
            self.folder_query.set("")
            self.reload()

    def reload(self):
        if not self.vault:
            self.choose_vault()
            return
        if self.busy:
            return
        self.busy = True
        self.refresh_button.configure(state="disabled")
        self.choose_button.configure(state="disabled")
        self.set_status("正在读取，只访问文件时间和本地 Git 历史…")
        self.path_label.configure(text=self.vault)

        def work():
            try:
                snapshot = load_history(self.vault, lambda message: self.messages.put(("progress", message)))
                self.messages.put(("loaded", snapshot))
            except Exception as exc:
                self.messages.put(("error", str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind, value = self.messages.get_nowait()
                if kind == "progress":
                    self.set_status(value)
                    continue
                self.busy = False
                self.refresh_button.configure(state="normal")
                self.choose_button.configure(state="normal")
                if kind == "error":
                    if self.snapshot:
                        self.vault = str(self.snapshot.vault)
                        self.path_label.configure(text=self.vault)
                    self.set_status("读取失败；仍显示上次结果，可选择其他目录或重新读取。" if self.snapshot else
                                    "读取失败；可选择其他目录或重新读取。")
                    messagebox.showerror("读取失败", value)
                    continue
                self.snapshot = value
                self.year_combo.configure(values=[str(y) for y in value.years])
                if int(self.year.get()) not in value.years:
                    self.year.set(str(value.years[0]))
                if self.folder not in value.folders:
                    self.folder = ""
                self.populate_folders()
                self.update_view()
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def populate_folders(self):
        self.folder_tree.delete(*self.folder_tree.get_children())
        self.folder_ids.clear()
        self.folder_tree.insert("", "end", iid="all", text="全部笔记本", open=True)
        self.folder_ids["all"] = ""
        if not self.snapshot:
            return
        query = self.folder_query.get().strip().casefold()
        visible = {p for p in self.snapshot.folders if query in p.casefold()}
        for path in list(visible):
            parts = path.split("/")
            visible.update("/".join(parts[:i]) for i in range(1, len(parts)))
        path_ids = {}
        for index, path in enumerate(self.snapshot.folders):
            if path not in visible:
                continue
            parent = path.rsplit("/", 1)[0] if "/" in path else ""
            iid = f"f{index}"
            self.folder_tree.insert(path_ids.get(parent, ""), "end", iid=iid,
                                    text=path.rsplit("/", 1)[-1], open=bool(query))
            self.folder_ids[iid] = path
            path_ids[path] = iid
        selected_id = path_ids.get(self.folder, "all")
        # Filtering the navigation must not reset the selected statistical scope.
        if not self.folder or self.folder in path_ids:
            self.folder_tree.selection_set(selected_id)
            self.folder_tree.see(selected_id)

    def select_folder(self, _):
        selected = self.folder_tree.selection()
        if selected:
            folder = self.folder_ids.get(selected[0], "")
            if folder != self.folder:
                self.folder = folder
                self.update_view()

    def update_view(self):
        if not self.snapshot:
            return
        self.daily = self.snapshot.daily(int(self.year.get()), self.folder)
        self.scope_label.configure(text=self.folder or "全部笔记本", wraplength=650)
        values = (len(self.daily), len({n.identity for notes in self.daily.values() for n in notes}),
                  sum(len(notes) for notes in self.daily.values()), longest_streak(self.daily))
        for label, value in zip(self.stat_widgets, values):
            label.configure(text=f"{value:,}")
        self.heat_title.configure(text=f"{self.year.get()}  /  写作足迹")
        s = summary(self.snapshot, int(self.year.get()), self.folder)
        self.vault_count.configure(text=f"当前范围 {s['current_notes']:,} 篇文件\n仓库历史 {self.snapshot.commits} 次提交")
        boundary = self.snapshot.cutoff.astimezone(SHANGHAI).strftime("%Y-%m-%d %H:%M") if self.snapshot.cutoff else "无 Git 提交"
        self.status_text = f"首次提交 {boundary} · 上海时区 · 当前 HEAD 历史"
        if self.snapshot.warnings:
            self.status_text += f" · {len(self.snapshot.warnings)} 条提示（见统计口径）"
        self.set_status(self.status_text)
        if self.selected is None or self.selected.year != int(self.year.get()):
            self.selected = max(self.daily) if self.daily else date(int(self.year.get()), 1, 1)
        self.draw_heatmap()
        self.populate_notes()

    def draw_heatmap(self):
        canvas = self.heat_canvas
        canvas.delete("all")
        self.cells.clear()
        c = self.colors
        year = int(self.year.get())
        first, last = date(year, 1, 1), date(year, 12, 31)
        start = first - timedelta(days=first.weekday())
        weeks = (last - start).days // 7 + 1
        step = min(16, max(10, (canvas.winfo_width() - 50) / weeks))
        size = step - 3
        y0 = 25
        for row, text in ((0, "一"), (2, "三"), (4, "五")):
            canvas.create_text(12, y0 + row * step + size / 2, text=text, fill=c["muted"], font=("Microsoft YaHei UI", 9))
        counts = sorted({len(notes) for notes in self.daily.values()})
        self.thresholds = [counts[min(len(counts) - 1, math.ceil(len(counts) * q) - 1)] if counts else 1
                           for q in (.25, .5, .75)]
        today = datetime.now(SHANGHAI).date()
        day = first
        while day <= last:
            column = (day - start).days // 7
            row = day.weekday()
            x, y = 36 + column * step, y0 + row * step
            count = len(self.daily.get(day, []))
            level = sum(count > threshold for threshold in self.thresholds) if count else -1
            color = c["heat"][level] if count else c["empty"]
            item = canvas.create_rectangle(x, y, x + size, y + size, fill=color,
                                           outline=c["accent"] if day == self.selected else "",
                                           width=2 if day == self.selected else 0)
            self.cells[item] = day
            if day == today:
                canvas.create_oval(x + size / 2 - 1, y + size / 2 - 1, x + size / 2 + 1,
                                   y + size / 2 + 1, fill=c["text"], outline="")
            if day.day == 1:
                canvas.create_text(x, 12, text=f"{day.month}月", anchor="w", fill=c["muted"],
                                   font=("Microsoft YaHei UI", 9))
            day += timedelta(days=1)
        legend_y = y0 + 7 * step + 14
        canvas.configure(height=int(legend_y + 12))
        canvas.create_text(36, legend_y, text="点击日期查看笔记 · 方向键移动日期", anchor="w",
                           fill=c["muted"], font=("Microsoft YaHei UI", 9))
        legend_x = max(390, canvas.winfo_width() - 255)
        canvas.create_text(legend_x, legend_y, text="少", fill=c["muted"], font=("Microsoft YaHei UI", 9))
        for i, color in enumerate([c["empty"], *c["heat"]]):
            x = legend_x + 18 + i * 18
            canvas.create_rectangle(x, legend_y - 6, x + 12, legend_y + 6, fill=color, outline="")
        canvas.create_text(legend_x + 119, legend_y, text="多", fill=c["muted"], font=("Microsoft YaHei UI", 9))

    def day_at(self, event):
        for item in reversed(self.heat_canvas.find_overlapping(event.x, event.y, event.x, event.y)):
            if item in self.cells:
                return self.cells[item]
        return None

    def hover_day(self, event):
        day = self.day_at(event)
        if day:
            self.heat_canvas.configure(cursor="hand2")
            count = len(self.daily.get(day, []))
            self.set_status(f"{day:%Y-%m-%d}  ·  {count} 篇不同笔记" + ("  ·  暂无已提交的活动" if count == 0 else ""))
        else:
            self.heat_canvas.configure(cursor="")
            self.set_status(self.status_text)

    def click_day(self, event):
        day = self.day_at(event)
        if day:
            self.selected = day
            self.heat_canvas.focus_set()
            self.draw_heatmap()
            self.populate_notes()

    def move_day(self, offset):
        if self.selected:
            new = self.selected + timedelta(days=offset)
            if new.year == int(self.year.get()):
                self.selected = new
                self.draw_heatmap()
                self.populate_notes()
        return "break"

    def populate_notes(self):
        self.notes_tree.delete(*self.notes_tree.get_children())
        self.rows.clear()
        if self.selected is None:
            return
        notes = self.daily.get(self.selected, [])
        query = self.note_query.get().strip().casefold()
        visible = [n for n in notes if any(query in p.casefold() for p in n.paths)]
        weekday = "一二三四五六日"[self.selected.weekday()]
        suffix = f"{len(visible)} / {len(notes)} 篇" if query else f"{len(notes)} 篇笔记"
        self.day_label.configure(text=f"{self.selected:%Y-%m-%d}  周{weekday}  ·  {suffix}")
        for i, note in enumerate(visible):
            actions = "、".join(sorted(note.operations, key=ORDER.get))
            if note.renamed:
                actions += " · 重命名"
            iid = str(i)
            path = Path(note.path)
            self.notes_tree.insert("", "end", iid=iid, values=(path.stem, actions,
                                    " + ".join(sorted(note.sources)), path.parent.as_posix() if "/" in note.path else ROOT_FOLDER))
            self.rows[iid] = note
        self.set_note_info("选择一篇笔记查看完整路径和提交记录。" if visible else
                           "当天没有符合筛选条件的笔记活动。未提交的变更不会计入 Git 足迹。")

    def set_note_info(self, text):
        self.note_info.configure(state="normal")
        self.note_info.delete("1.0", "end")
        self.note_info.insert("1.0", text)
        self.note_info.configure(state="disabled")

    def note_details(self, _):
        selected = self.notes_tree.selection()
        if not selected or selected[0] not in self.rows:
            return
        note = self.rows[selected[0]]
        text = "路径：" + "  →  ".join(sorted(note.paths))
        if note.commits:
            text += "\n提交：" + "  ·  ".join(c[:10] for c in sorted(note.commits))
        self.set_note_info(text)

    def set_status(self, text):
        self.status.configure(text=text)

    def show_rules(self):
        text = (
            "按天对不同笔记去重，同篇笔记当天创建、修改、删除只计一次。\n\n"
            "• 首次提交之前：仅采用严格早于根提交时间的创建时间、最后修改时间。\n"
            "• 首次提交之后：只使用当前 HEAD 可达的 Git 历史，包含两台设备已合并的提交。\n"
            "• 按提交作者时间归入上海时区的自然日；首次提交也计入创建活动。\n"
            "• 普通同步合并不重复计数；合并时相对所有父提交都改变的文件计入修改。\n"
            "• Git 识别的重命名按同一笔记追踪，复制按新笔记；文件夹按事件发生时的路径筛选。\n"
            "• 笔记日数 = 每天不同笔记数之和；涉及笔记 = 所选年份内不同笔记总数。\n"
            "• 当前文件数包含未提交的 Markdown；未提交变更不计入足迹。\n"
            "• 忽略 .git、.obsidian、.trash、node_modules；文件时间扫描跳过链接／目录联接。\n"
            "• 热力图按当前范围的正活动数量分位分为四档，颜色只表示相对强度。\n\n"
            "文件时间只能提供两个时间点，不能恢复此前每一天的编辑记录。\n"
            "复制／同步可能重置文件时间。已删且未被 Git 记录的旧笔记无法恢复。\n"
            "Git 未识别的重命名按删除／创建计算；同一路径删除后重建按同一笔记计数。\n"
            "程序不打开笔记、不写仓库、不访问网络，不维护数据库或缓存。"
        )
        if self.snapshot and self.snapshot.warnings:
            text += "\n\n本次提示：\n" + "\n".join(self.snapshot.warnings[:12])
        messagebox.showinfo("统计口径", text)


def main():
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="本地只读 Obsidian 笔记足迹")
    parser.add_argument("--vault", default=DEFAULT_VAULT, help="笔记目录")
    parser.add_argument("--summary", action="store_true", help="仅输出 JSON 统计，不启动 GUI")
    parser.add_argument("--year", type=int, default=datetime.now(SHANGHAI).year)
    parser.add_argument("--folder", default="", help="筛选相对目录")
    args = parser.parse_args()
    if args.summary:
        if not args.vault:
            parser.error("请使用 --vault 指定笔记目录，或提供本地 settings.local.json 配置。")
        print(json.dumps(summary(load_history(args.vault), args.year, args.folder), ensure_ascii=False, indent=2))
        return
    # Declare DPI awareness before creating the first window.
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Afterglow.Observer")
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    App(root, args.vault)
    root.mainloop()


if __name__ == "__main__":
    main()
