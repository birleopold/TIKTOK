from __future__ import annotations

import re
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk, simpledialog

from unified_app.adapters.launcher import open_folder
from unified_app.adapters.projects import PROJECTS
from unified_app.config import Action, PIP_HINTS, PYTHON, ROOT
from unified_app.services.content_hunt import hunt_urls, save_source, refresh_sources
from unified_app.services.content_sourcing import draft_top_candidates, export_source_digest, format_source_digest, refresh_saved_sources_deep
from unified_app.services.daily_command import export_daily_plan, format_daily_plan
from unified_app.services.db import init_db
from unified_app.services.drafts import content_pack, export_posting_plan, make_drafts, recent_drafts
from unified_app.services.jobs import recent_jobs
from unified_app.services.library import library_counts, recent_candidates, scan_local_assets
from unified_app.services.source import scan_python_files
from unified_app.services.video_tools import prepare_video_for_upload
from unified_app.services.analytics import export_analytics_report, format_analytics_report
from unified_app.services.automations import clean_rename_folder, duplicate_report, export_calendar, export_today_list, extract_audio, make_thumbnail, make_tiktok_ready, what_to_post_today
from unified_app.services.batch_campaign import build_batch_campaign
from unified_app.services.browser_cookies import format_browser_profiles, format_browser_session_health
from unified_app.services.creator_os import add_caption_style, add_hashtag_set, apply_caption_style, apply_hashtag_set, backup_app, backup_rows, caption_style_rows, create_draft_from_template, create_series, format_calendar_board, generate_thumbnail_choices, hashtag_set_rows, performance_report, record_upload_result, repurpose_long_video, series_rows, template_rows, thumbnail_rows, update_draft_field, upload_assistant, upload_result_rows
from unified_app.services.branding import add_watermark, brand_video, burn_caption, create_srt
from unified_app.services.input_detector import detect_input, format_detection
from unified_app.services.paste_go import analyze_value, run_primary_action
from unified_app.services.production_library import draft_from_item, export_library_csv, library_summary_lines, mark_uploaded, production_rows, rebuild_library, schedule_next_drafts, update_item_status
from unified_app.services.ready_package import make_ready_package
from unified_app.services.settings import DEFAULT_SETTINGS, all_settings, brand_settings, format_settings, set_setting
from unified_app.services.setup_doctor import fix_folders, format_doctor_report, install_all_requirements, install_playwright_browser, run_doctor
from unified_app.services.tiktok_profile import analyze_tiktok_profile_url, format_profile_report, recent_profile_snapshots
from unified_app.services.upload_queue import account_rows, add_to_queue, assign_queue_account, auto_assign_healthy_account, cancel_queue_item, import_browser_session, import_cookie_file, queue_ready_items, queue_rows, queue_summary_lines, run_login, run_queue_item, sync_accounts, upload_preflight
from unified_app.services.workflows import WORKFLOW_PRESETS, format_workflow, run_workflow, workflow_readiness

class UnifiedApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__(); init_db(); self.python_files = scan_python_files(); self.status = tk.StringVar(value="Ready"); self.current_detection = None
        self.title("Unified TikTok Python App"); self.geometry("1240x800"); self.minsize(1040, 660); self.configure(bg="#f8fafc"); self._build()
    def _build(self) -> None:
        style=ttk.Style(self); style.theme_use("clam")
        for name,bg in (("TFrame","#f8fafc"),("Card.TFrame","#ffffff")): style.configure(name, background=bg)
        style.configure("Title.TLabel", background="#f8fafc", foreground="#0f172a", font=("Segoe UI",18,"bold")); style.configure("Heading.TLabel", background="#ffffff", foreground="#0f172a", font=("Segoe UI",11,"bold")); style.configure("Body.TLabel", background="#ffffff", foreground="#475569", font=("Segoe UI",9)); style.configure("TButton", font=("Segoe UI",9), padding=(10,6))
        header=ttk.Frame(self, padding=(18,14)); header.pack(fill="x")
        ttk.Label(header,text="Unified TikTok Python App",style="Title.TLabel").pack(side="left")
        ttk.Label(header,text=f"{len(PROJECTS)} projects | {len(self.python_files)} Python files | no API keys",background="#f8fafc",foreground="#64748b").pack(side="right")
        nb=ttk.Notebook(self); nb.pack(fill="both",expand=True,padx=18,pady=(0,18))
        self.daily_tab=ttk.Frame(nb,padding=10); self.creator_tab=ttk.Frame(nb,padding=10); self.workflow_tab=ttk.Frame(nb,padding=10); self.tiktok_tab=ttk.Frame(nb,padding=10); self.presets_tab=ttk.Frame(nb,padding=10); self.automations_tab=ttk.Frame(nb,padding=10); self.upload_tab=ttk.Frame(nb,padding=10); self.settings_tab=ttk.Frame(nb,padding=10); self.doctor_tab=ttk.Frame(nb,padding=10); self.projects_tab=ttk.Frame(nb,padding=10); self.hunt_tab=ttk.Frame(nb,padding=10); self.drafts_tab=ttk.Frame(nb,padding=10); self.library_tab=ttk.Frame(nb,padding=10); self.jobs_tab=ttk.Frame(nb,padding=10); self.source_tab=ttk.Frame(nb,padding=10); self.help_tab=ttk.Frame(nb,padding=10)
        for tab,name in ((self.daily_tab,"Daily"),(self.creator_tab,"Creator OS"),(self.workflow_tab,"Paste & Go"),(self.tiktok_tab,"TikTok Analyzer"),(self.presets_tab,"Workflow Presets"),(self.automations_tab,"No-Key Automations"),(self.upload_tab,"Accounts & Upload Queue"),(self.settings_tab,"Brand Settings"),(self.doctor_tab,"Setup Doctor"),(self.projects_tab,"Projects"),(self.hunt_tab,"Content Hunt"),(self.drafts_tab,"Draft Queue"),(self.library_tab,"Library & Analytics"),(self.jobs_tab,"Jobs"),(self.source_tab,"Python Source"),(self.help_tab,"Run Commands")): nb.add(tab,text=name)
        self._build_daily_tab(); self._build_creator_tab(); self._build_workflow_tab(); self._build_tiktok_tab(); self._build_presets_tab(); self._build_automations_tab(); self._build_upload_tab(); self._build_settings_tab(); self._build_doctor_tab(); self._build_projects_tab(); self._build_hunt_tab(); self._build_drafts_tab(); self._build_library_tab(); self._build_jobs_tab(); self._build_source_tab(); self._build_help_tab()
        ttk.Label(self,textvariable=self.status,background="#e2e8f0",foreground="#0f172a",padding=(10,5)).pack(fill="x")

    def _build_creator_tab(self) -> None:
        top=ttk.Frame(self.creator_tab); top.pack(fill="x",pady=(0,8))
        ttk.Button(top,text="Calendar Board",command=self._creator_calendar).pack(side="left",padx=(0,6))
        ttk.Button(top,text="Upload Assistant",command=self._creator_upload_assistant).pack(side="left",padx=(0,6))
        ttk.Button(top,text="Confirm Upload",command=self._creator_confirm_upload).pack(side="left",padx=(0,6))
        ttk.Button(top,text="Draft Editor",command=self._creator_draft_editor).pack(side="left",padx=(0,6))
        ttk.Button(top,text="Performance",command=self._creator_performance).pack(side="left",padx=(0,6))
        ttk.Button(top,text="Backup",command=self._creator_backup).pack(side="right",padx=(6,0))
        tools=ttk.Frame(self.creator_tab); tools.pack(fill="x",pady=(0,8))
        ttk.Button(tools,text="Caption Library",command=self._creator_caption_styles).pack(side="left",padx=(0,6))
        ttk.Button(tools,text="Hashtag Sets",command=self._creator_hashtag_sets).pack(side="left",padx=(0,6))
        ttk.Button(tools,text="Content Templates",command=self._creator_templates).pack(side="left",padx=(0,6))
        ttk.Button(tools,text="Template Draft",command=self._creator_template_draft).pack(side="left",padx=(0,6))
        ttk.Button(tools,text="Thumbnail Picker",command=self._creator_thumbnail_picker).pack(side="left",padx=(0,6))
        ttk.Button(tools,text="Repurpose Long Video",command=self._creator_repurpose).pack(side="left",padx=(0,6))
        ttk.Button(tools,text="Series Builder",command=self._creator_series_builder).pack(side="left",padx=(0,6))
        self.creator_output=tk.Text(self.creator_tab,height=31,font=("Consolas",10),wrap="word")
        self.creator_output.pack(fill="both",expand=True)
        self._creator_calendar()

    def _creator_write(self,msg: str) -> None:
        self.creator_output.delete("1.0",tk.END); self.creator_output.insert("1.0",msg)
        self._refresh_jobs()

    def _creator_calendar(self) -> None:
        self._creator_write(format_calendar_board(7)); self.status.set("Creator calendar refreshed")

    def _creator_upload_assistant(self) -> None:
        item_id=simpledialog.askinteger("Upload Assistant","Queue item ID",initialvalue=1,minvalue=1)
        if not item_id: return
        self._creator_write(upload_assistant(item_id)); self.status.set("Upload assistant ready")

    def _creator_confirm_upload(self) -> None:
        item_id=simpledialog.askinteger("Confirm Upload","Queue item ID",initialvalue=1,minvalue=1)
        if not item_id: return
        url=simpledialog.askstring("Confirm Upload","TikTok URL after posting")
        if not url: return
        ok,msg=record_upload_result(item_id,url); self._creator_write(msg+"\n\n"+performance_report()); self.status.set(msg); self._upload_sync(); self._refresh_library()
        if not ok: messagebox.showwarning("Confirm Upload",msg)

    def _creator_caption_styles(self) -> None:
        lines=["Caption Library",""]
        for _id,name,template,notes in caption_style_rows(): lines.append(f"#{_id} {name}\n  {template}\n  {notes}")
        self._creator_write("\n".join(lines)); self.status.set("Caption library loaded")

    def _creator_hashtag_sets(self) -> None:
        lines=["Hashtag Sets",""]
        for _id,name,tags,notes in hashtag_set_rows(): lines.append(f"#{_id} {name}\n  {tags}\n  {notes}")
        self._creator_write("\n".join(lines)); self.status.set("Hashtag sets loaded")

    def _creator_templates(self) -> None:
        lines=["Content Templates",""]
        for _id,name,hook,caption,tags,notes in template_rows(): lines.append(f"#{_id} {name}\n  Hook: {hook}\n  Caption: {caption}\n  Tags: {tags}\n  {notes}")
        self._creator_write("\n".join(lines)); self.status.set("Content templates loaded")

    def _creator_template_draft(self) -> None:
        template=simpledialog.askstring("Template Draft","Template name",initialvalue="3 tips")
        if not template: return
        topic=simpledialog.askstring("Template Draft","Topic",initialvalue="phone repair")
        if not topic: return
        ok,msg=create_draft_from_template(template,topic); self._creator_write(msg); self.status.set(msg); self._refresh_drafts(); self._refresh_library()
        if not ok: messagebox.showwarning("Template Draft",msg)

    def _creator_draft_editor(self) -> None:
        draft_id=simpledialog.askinteger("Draft Editor","Draft ID",minvalue=1)
        if not draft_id: return
        field=simpledialog.askstring("Draft Editor","Field: title, hook, caption, hashtags, notes, account, status, scheduled_for",initialvalue="notes")
        if not field: return
        value=simpledialog.askstring("Draft Editor",f"New value for {field}")
        if value is None: return
        ok,msg=update_draft_field(draft_id,field,value); self._creator_write(msg); self.status.set(msg); self._refresh_drafts(); self._refresh_library()
        if not ok: messagebox.showwarning("Draft Editor",msg)

    def _creator_performance(self) -> None:
        lines=[performance_report(),"","Upload Result Tracker:"]
        rows=upload_result_rows()
        lines += [str(row) for row in rows] if rows else ["No upload results tracked yet."]
        self._creator_write("\n".join(lines)); self.status.set("Performance analytics refreshed")

    def _creator_thumbnail_picker(self) -> None:
        file=filedialog.askopenfilename(title="Choose video",filetypes=[("Video files","*.mp4 *.mov *.m4v *.webm *.avi *.mkv"),("All files","*.*")])
        if not file: return
        self.status.set("Generating thumbnail choices...")
        def worker():
            ok,msg=generate_thumbnail_choices(file); rows=thumbnail_rows(); self.after(0,lambda:(self._creator_write(msg+"\n\nChoices:\n"+"\n".join(str(r) for r in rows[:20])), self.status.set("Thumbnail choices ready" if ok else "Thumbnail generation failed")))
        threading.Thread(target=worker,daemon=True).start()

    def _creator_repurpose(self) -> None:
        file=filedialog.askopenfilename(title="Choose long video",filetypes=[("Video files","*.mp4 *.mov *.m4v *.webm *.avi *.mkv"),("All files","*.*")])
        if not file: return
        seconds=simpledialog.askinteger("Repurpose","Seconds per clip",initialvalue=45,minvalue=5,maxvalue=180) or 45
        parts=simpledialog.askinteger("Repurpose","Number of clips",initialvalue=3,minvalue=1,maxvalue=20) or 3
        self.status.set("Repurposing long video...")
        def worker():
            ok,msg=repurpose_long_video(file,seconds,parts); self.after(0,lambda:(self._creator_write(msg), self.status.set("Repurpose complete" if ok else "Repurpose failed"), self._refresh_drafts(), self._refresh_library()))
        threading.Thread(target=worker,daemon=True).start()

    def _creator_series_builder(self) -> None:
        name=simpledialog.askstring("Series Builder","Series name",initialvalue="Phone repair series")
        if not name: return
        topic=simpledialog.askstring("Series Builder","Series topic",initialvalue="phone repair tips")
        if not topic: return
        parts=simpledialog.askinteger("Series Builder","Number of parts",initialvalue=3,minvalue=1,maxvalue=30) or 3
        ok,msg=create_series(name,topic,parts); lines=[msg,"","Existing series:"]+[str(r) for r in series_rows()]
        self._creator_write("\n".join(lines)); self.status.set(msg); self._refresh_drafts(); self._refresh_library()
        if not ok: messagebox.showwarning("Series Builder",msg)

    def _creator_backup(self) -> None:
        ok,msg=backup_app(); lines=[msg,"","Backups:"]+[str(r) for r in backup_rows()]
        self._creator_write("\n".join(lines)); self.status.set("Backup created" if ok else "Backup failed")
        if not ok: messagebox.showwarning("Backup",msg)

    def _build_daily_tab(self) -> None:
        top=ttk.Frame(self.daily_tab); top.pack(fill="x",pady=(0,8))
        ttk.Button(top,text="Refresh",command=self._daily_refresh).pack(side="left",padx=(0,8))
        ttk.Button(top,text="Export Daily Plan",command=self._daily_export).pack(side="left",padx=(0,8))
        ttk.Button(top,text="Queue Ready Videos",command=self._upload_queue_ready).pack(side="left",padx=(0,8))
        ttk.Button(top,text="Open Exports",command=lambda:self._run_action(Action("Open exports","Open exports",lambda: open_folder("exports")))).pack(side="right")
        self.daily_output=tk.Text(self.daily_tab,height=35,font=("Consolas",10),wrap="word")
        self.daily_output.pack(fill="both",expand=True)
        self._daily_refresh()
    def _daily_refresh(self) -> None:
        if not hasattr(self,"daily_output"): return
        self.daily_output.delete("1.0",tk.END); self.daily_output.insert("1.0",format_daily_plan())
        self.status.set("Daily command plan refreshed")
        self._refresh_jobs()
    def _daily_export(self) -> None:
        path=export_daily_plan(); self.status.set(f"Exported {path.relative_to(ROOT)}"); self._refresh_jobs(); messagebox.showinfo("Daily Plan","Exported:\n"+str(path))

    def _build_workflow_tab(self) -> None:
        ttk.Label(self.workflow_tab,text="Paste a TikTok page/video, YouTube link, website, RSS/feed URL, or local video path.",background="#f8fafc",foreground="#475569").pack(anchor="w")
        self.workflow_input=tk.Text(self.workflow_tab,height=5,font=("Consolas",10)); self.workflow_input.pack(fill="x",pady=8)
        row=ttk.Frame(self.workflow_tab); row.pack(fill="x",pady=(0,8))
        ttk.Button(row,text="Analyze",command=self._workflow_analyze).pack(side="left",padx=(0,8))
        ttk.Button(row,text="Run Recommended Action",command=self._workflow_primary_action).pack(side="left",padx=(0,8))
        ttk.Button(row,text="Save As Source",command=self._save_workflow_sources).pack(side="left",padx=(0,8))
        ttk.Button(row,text="Make Drafts",command=self._make_drafts_ui).pack(side="left",padx=(0,8))
        ttk.Button(row,text="Choose Local Video",command=self._choose_local_video).pack(side="left",padx=(0,8))
        ttk.Button(row,text="Copy Video To Upload Folder",command=self._prepare_workflow_video).pack(side="left",padx=(0,8))
        ttk.Button(row,text="Full Ready Package",command=self._ready_package_workflow).pack(side="left",padx=(0,8))
        ttk.Button(row,text="Export Posting Plan",command=self._export_plan_ui).pack(side="left")
        self.workflow_output=tk.Text(self.workflow_tab,height=23,font=("Consolas",10),wrap="word"); self.workflow_output.pack(fill="both",expand=True)
    def _workflow_analyze(self) -> None:
        value=self.workflow_input.get("1.0",tk.END).strip()
        if not value: messagebox.showinfo("Analyze","Paste something first."); return
        self.workflow_output.delete("1.0",tk.END)
        vals=[x.strip() for x in value.splitlines() if x.strip()]
        self.status.set("Running Paste & Go analysis...")
        def worker():
            reports=[]; first_detection=None
            for item in vals:
                result=analyze_value(item)
                if first_detection is None:
                    first_detection=result.detection
                reports.append(result.report)
            self.after(0,lambda:self._workflow_finish_analysis(first_detection,reports))
        threading.Thread(target=worker,daemon=True).start()
    def _workflow_finish_analysis(self, detection, reports: list[str]) -> None:
        self.current_detection=detection
        self.workflow_output.insert("1.0","\n\n".join(reports) if reports else "No usable result.")
        self.status.set("Paste & Go analysis complete")
        self._refresh_library(); self._refresh_drafts(); self._refresh_jobs()
    def _workflow_primary_action(self) -> None:
        if self.current_detection is None:
            value=self.workflow_input.get("1.0",tk.END).strip()
            if not value:
                messagebox.showinfo("Action","Paste and analyze something first."); return
            self.current_detection=detect_input(value.splitlines()[0].strip())
        ok,msg=run_primary_action(self.current_detection)
        self.status.set(msg)
        self._refresh_library(); self._refresh_drafts(); self._refresh_jobs()
        if not ok: messagebox.showwarning("Recommended Action",msg)

    def _build_tiktok_tab(self) -> None:
        ttk.Label(self.tiktok_tab,text="Paste a TikTok profile/page link. The app saves a local profile snapshot when public data is available.",background="#f8fafc",foreground="#475569").pack(anchor="w")
        top=ttk.Frame(self.tiktok_tab); top.pack(fill="x",pady=8)
        self.tiktok_profile_input=tk.StringVar(value="https://www.tiktok.com/@example")
        ttk.Entry(top,textvariable=self.tiktok_profile_input).pack(side="left",fill="x",expand=True,padx=(0,8))
        ttk.Button(top,text="Analyze Profile",command=self._analyze_tiktok_profile_ui).pack(side="left",padx=(0,8))
        ttk.Button(top,text="Refresh Snapshots",command=self._refresh_profile_snapshots).pack(side="left")
        middle=ttk.Frame(self.tiktok_tab); middle.pack(fill="both",expand=True)
        self.tiktok_profile_output=tk.Text(middle,height=23,font=("Consolas",10),wrap="word")
        self.tiktok_profile_output.pack(side="top",fill="both",expand=True,pady=(0,8))
        self.profile_tree=ttk.Treeview(middle,columns=("id","username","name","followers","videos","url","created"),show="headings",height=7)
        for col,width in (("id",50),("username",140),("name",180),("followers",100),("videos",80),("url",420),("created",170)):
            self.profile_tree.heading(col,text=col.title()); self.profile_tree.column(col,width=width,stretch=col in {"name","url"})
        self.profile_tree.pack(fill="x")
        self._refresh_profile_snapshots()

    def _analyze_tiktok_profile_ui(self) -> None:
        value=self.tiktok_profile_input.get().strip()
        if not value:
            messagebox.showinfo("TikTok Analyzer","Paste a TikTok profile link first."); return
        self.status.set("Analyzing TikTok profile...")
        self.tiktok_profile_output.delete("1.0",tk.END)
        def worker():
            try:
                report=format_profile_report(analyze_tiktok_profile_url(value))
                self.after(0,lambda:self._finish_tiktok_profile(report))
            except Exception as exc:
                self.after(0,lambda:self._finish_tiktok_profile(f"Profile analysis failed: {exc}"))
        threading.Thread(target=worker,daemon=True).start()

    def _finish_tiktok_profile(self, report: str) -> None:
        self.tiktok_profile_output.insert("1.0",report)
        self.status.set("TikTok profile analysis complete")
        self._refresh_profile_snapshots(); self._refresh_library(); self._refresh_jobs()

    def _refresh_profile_snapshots(self) -> None:
        if not hasattr(self,"profile_tree"): return
        self.profile_tree.delete(*self.profile_tree.get_children())
        for row in recent_profile_snapshots(): self.profile_tree.insert("",tk.END,values=row)

    def _workflow_show_candidates(self,cands: list[Candidate],errs: list[str]) -> None:
        lines=[]
        for c in cands:
            pack=content_pack(c.title,c.description); lines.append(self._format_pack(f"{c.source_type.upper()}: {c.title}", c.url, pack)); lines.append(f"Media/page links found: {len(c.media_urls)}\nNote: {c.notes}\n")
        lines += ["ERROR "+e for e in errs]
        self.workflow_output.insert("1.0","\n".join(lines) if lines else "No usable result.")
        self.status.set(f"Analyzed {len(cands)} candidates; {len(errs)} errors"); self._refresh_library(); self._refresh_jobs()
    def _format_pack(self,title: str, source: str, pack: dict) -> str:
        return "\n".join([title, f"Source: {source}", "Keywords: "+", ".join(pack["keywords"]), "Hashtags: "+" ".join(pack["hashtags"]), "Hooks:", *["  - "+x for x in pack["hooks"]], "Captions:", *["  - "+x for x in pack["captions"]], ""])
    def _choose_local_video(self) -> None:
        file=filedialog.askopenfilename(title="Choose video",filetypes=[("Video files","*.mp4 *.mov *.m4v *.webm *.avi *.mkv"),("All files","*.*")])
        if file: self.workflow_input.delete("1.0",tk.END); self.workflow_input.insert("1.0",file); self._workflow_analyze()
    def _prepare_workflow_video(self) -> None:
        value=self.workflow_input.get("1.0",tk.END).strip().strip('"')
        if not value: messagebox.showinfo("Prepare","Choose or paste a local video path first."); return
        ok,msg=prepare_video_for_upload(value); self.status.set(msg); self._refresh_library(); self._refresh_jobs()
        if not ok: messagebox.showwarning("Prepare",msg)
    def _ready_package_workflow(self) -> None:
        value=self.workflow_input.get("1.0",tk.END).strip().strip('"')
        if not value: messagebox.showinfo("Ready Package","Choose or paste a local video path first."); return
        self.status.set("Creating TikTok-ready package...")
        self.workflow_output.delete("1.0",tk.END)
        def worker():
            ok,_package,msg=make_ready_package(value)
            self.after(0,lambda:self._finish_ready_package(ok,msg,self.workflow_output))
        threading.Thread(target=worker,daemon=True).start()
    def _finish_ready_package(self, ok: bool, msg: str, target: tk.Text) -> None:
        target.delete("1.0",tk.END); target.insert("1.0",msg)
        self.status.set("Ready package complete" if ok else "Ready package failed")
        self._refresh_library(); self._refresh_drafts(); self._refresh_jobs()
        if not ok: messagebox.showwarning("Ready Package",msg)
    def _export_plan_ui(self) -> None:
        days=simpledialog.askinteger("Posting Plan","How many draft slots?",initialvalue=7,minvalue=1,maxvalue=90)
        if not days: return
        path=export_posting_plan(days); self.status.set(f"Exported {path.relative_to(ROOT)}"); self._refresh_drafts(); self._refresh_jobs(); messagebox.showinfo("Posting Plan",f"Exported:\n{path}")
    def _save_workflow_sources(self) -> None:
        vals=[x.strip() for x in self.workflow_input.get("1.0",tk.END).splitlines() if x.strip()]
        saved=0
        for v in vals:
            if re.match(r"^(https?://|www\.|[A-Za-z0-9.-]+\.[A-Za-z]{2,})", v):
                ok,_=save_source(v); saved += 1 if ok else 0
        self.status.set(f"Saved {saved} sources"); self._refresh_library(); self._refresh_jobs()
    def _save_hunt_sources(self) -> None:
        vals=[x.strip() for x in self.hunt_input.get("1.0",tk.END).splitlines() if x.strip()]
        saved=0
        for v in vals:
            ok,_=save_source(v); saved += 1 if ok else 0
        self.status.set(f"Saved {saved} sources"); self._refresh_library(); self._refresh_jobs()
    def _refresh_sources_ui(self) -> None:
        self.status.set("Refreshing saved sources...")
        def worker():
            ok,failed=refresh_sources(); self.after(0,lambda:(self.status.set(f"Refreshed {ok} sources; {failed} failed"), self._refresh_library(), self._refresh_jobs()))
        threading.Thread(target=worker,daemon=True).start()
    def _make_drafts_ui(self) -> None:
        made=make_drafts(); self.status.set(f"Created or updated {made} drafts"); self._refresh_drafts(); self._refresh_library(); self._refresh_jobs()
    def _deep_refresh_sources_ui(self) -> None:
        self.status.set("Deep refreshing saved sources...")
        def worker():
            ok,failed=refresh_saved_sources_deep(); self.after(0,lambda:(self.hunt_results.delete("1.0",tk.END), self.hunt_results.insert("1.0",format_source_digest()), self.status.set(f"Expanded {ok} candidates; {failed} errors"), self._refresh_library(), self._refresh_jobs()))
        threading.Thread(target=worker,daemon=True).start()
    def _source_digest_ui(self) -> None:
        self.hunt_results.delete("1.0",tk.END); self.hunt_results.insert("1.0",format_source_digest()); self.status.set("Content sourcing digest ready")
    def _source_digest_export_ui(self) -> None:
        path=export_source_digest(); self.status.set(f"Exported {path.relative_to(ROOT)}"); self._refresh_jobs(); messagebox.showinfo("Source Digest","Exported:\n"+str(path))
    def _draft_top_ui(self) -> None:
        count=simpledialog.askinteger("Draft Top Candidates","How many top candidates?",initialvalue=5,minvalue=1,maxvalue=50)
        if not count: return
        made=draft_top_candidates(count); self.status.set(f"Created {made} drafts from top candidates"); self._refresh_drafts(); self._refresh_library(); self._refresh_jobs()
    def _build_drafts_tab(self) -> None:
        top=ttk.Frame(self.drafts_tab); top.pack(fill="x",pady=(0,8))
        ttk.Button(top,text="Make Drafts From Library",command=self._make_drafts_ui).pack(side="left",padx=(0,8))
        ttk.Button(top,text="Export Draft Plan",command=self._export_plan_ui).pack(side="left",padx=(0,8))
        ttk.Button(top,text="Refresh",command=self._refresh_drafts).pack(side="right")
        self.drafts_tree=ttk.Treeview(self.drafts_tab,columns=("id","type","title","caption","hashtags","status","created"),show="headings")
        for col,width in (("id",50),("type",80),("title",240),("caption",360),("hashtags",260),("status",80),("created",160)):
            self.drafts_tree.heading(col,text=col.title()); self.drafts_tree.column(col,width=width,stretch=col in {"title","caption","hashtags"})
        self.drafts_tree.pack(fill="both",expand=True); self._refresh_drafts()
    def _refresh_drafts(self) -> None:
        if not hasattr(self,"drafts_tree"): return
        self.drafts_tree.delete(*self.drafts_tree.get_children())
        for row in recent_drafts(): self.drafts_tree.insert("",tk.END,values=row)

    def _build_presets_tab(self) -> None:
        canvas=tk.Canvas(self.presets_tab,bg="#f8fafc",highlightthickness=0)
        scroll=ttk.Scrollbar(self.presets_tab,orient="vertical",command=canvas.yview)
        content=ttk.Frame(canvas)
        content.bind("<Configure>",lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0),window=content,anchor="nw"); canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left",fill="both",expand=True); scroll.pack(side="right",fill="y")
        ttk.Label(content,text="Choose a human workflow. Status, inputs, outputs, and steps are shown before you run anything.",background="#f8fafc",foreground="#475569").pack(anchor="w",pady=(0,8))
        for preset in WORKFLOW_PRESETS:
            status, notes = workflow_readiness(preset)
            card=ttk.Frame(content,style="Card.TFrame",padding=12); card.pack(fill="x",pady=5)
            top=ttk.Frame(card,style="Card.TFrame"); top.pack(fill="x")
            ttk.Label(top,text=preset.label,style="Heading.TLabel").pack(side="left")
            ttk.Label(top,text=status,background="#ffffff",foreground="#047857" if status=="GREEN" else "#b45309",font=("Segoe UI",9,"bold")).pack(side="left",padx=(10,0))
            ttk.Button(top,text="Details",command=lambda p=preset:self._show_workflow_details(p.id)).pack(side="right",padx=(8,0))
            ttk.Button(top,text=preset.button,command=lambda p=preset:self._run_preset(p.id)).pack(side="right")
            ttk.Label(card,text=preset.description,style="Body.TLabel",wraplength=920,justify="left").pack(anchor="w",pady=(6,4))
            ttk.Label(card,text="Inputs: "+"; ".join(preset.inputs),style="Body.TLabel",wraplength=920,justify="left").pack(anchor="w")
            ttk.Label(card,text="Outputs: "+"; ".join(preset.outputs),style="Body.TLabel",wraplength=920,justify="left").pack(anchor="w")
            ttk.Label(card,text="Next: "+preset.steps[0],style="Body.TLabel",wraplength=920,justify="left").pack(anchor="w")
            if notes and notes != ["Ready"]:
                ttk.Label(card,text="Note: "+"; ".join(notes),style="Body.TLabel",wraplength=920,justify="left").pack(anchor="w",pady=(4,0))
    def _show_workflow_details(self, workflow_id: str) -> None:
        preset=next((p for p in WORKFLOW_PRESETS if p.id==workflow_id),None)
        if not preset: return
        win=tk.Toplevel(self); win.title(preset.label); win.geometry("720x520")
        text=tk.Text(win,wrap="word",font=("Consolas",10)); text.pack(fill="both",expand=True,padx=10,pady=10)
        text.insert("1.0",format_workflow(preset)); text.configure(state="disabled")
    def _run_preset(self, workflow_id: str) -> None:
        self.status.set(f"Running workflow: {workflow_id}")
        def worker():
            ok,msg=run_workflow(workflow_id); self.after(0,lambda:self._finish_action(ok,msg))
        threading.Thread(target=worker,daemon=True).start()

    def _build_automations_tab(self) -> None:
        ttk.Label(self.automations_tab,text="Local automations that do not require API keys.",background="#f8fafc",foreground="#475569").pack(anchor="w",pady=(0,8))
        top=ttk.Frame(self.automations_tab); top.pack(fill="x",pady=(0,8))
        ttk.Button(top,text="Choose Video",command=self._automation_choose_video).pack(side="left",padx=(0,8))
        ttk.Button(top,text="Choose Folder",command=self._automation_choose_folder).pack(side="left",padx=(0,8))
        self.automation_target=tk.StringVar(value=".")
        ttk.Entry(top,textvariable=self.automation_target).pack(side="left",fill="x",expand=True)
        buttons=ttk.Frame(self.automations_tab); buttons.pack(fill="x",pady=(0,8))
        for label,cmd in (("Duplicate Report",self._automation_duplicates),("Clean Rename",self._automation_rename),("What To Post Today",self._automation_today),("Export Today",self._automation_export_today),("Export Calendar",self._automation_calendar),("Thumbnail",self._automation_thumbnail),("Extract Audio",self._automation_audio),("Make TikTok Ready",self._automation_ready),("Full Ready Package",self._automation_ready_package),("Burn Caption",self._automation_burn_caption),("Watermark",self._automation_watermark),("Brand Video",self._automation_brand),("Create SRT",self._automation_srt),("Batch Campaign",self._automation_batch_campaign)):
            ttk.Button(buttons,text=label,command=cmd).pack(side="left",padx=(0,6),pady=3)
        self.automation_output=tk.Text(self.automations_tab,height=25,font=("Consolas",10),wrap="word")
        self.automation_output.pack(fill="both",expand=True)
    def _automation_choose_video(self) -> None:
        file=filedialog.askopenfilename(title="Choose video",filetypes=[("Video files","*.mp4 *.mov *.m4v *.webm *.avi *.mkv"),("All files","*.*")])
        if file: self.automation_target.set(file)
    def _automation_choose_folder(self) -> None:
        folder=filedialog.askdirectory(title="Choose folder")
        if folder: self.automation_target.set(folder)
    def _automation_write(self,msg: str) -> None:
        self.automation_output.delete("1.0",tk.END); self.automation_output.insert("1.0",msg); self._refresh_jobs(); self._refresh_library(); self._refresh_drafts()
    def _automation_duplicates(self) -> None:
        path,groups,files=duplicate_report(self.automation_target.get()); self._automation_write(f"Duplicate report: {path}\nGroups: {groups}\nFiles: {files}")
    def _automation_rename(self) -> None:
        renamed,notes=clean_rename_folder(self.automation_target.get()); self._automation_write(f"Renamed {renamed} videos\n"+"\n".join(notes))
    def _automation_today(self) -> None:
        rows=what_to_post_today(5); self._automation_write("\n".join(str(row) for row in rows))
    def _automation_export_today(self) -> None:
        self._automation_write(str(export_today_list(5)))
    def _automation_calendar(self) -> None:
        self._automation_write(str(export_calendar(14)))
    def _automation_thumbnail(self) -> None:
        ok,msg=make_thumbnail(self.automation_target.get()); self._automation_write(msg)
        if not ok: messagebox.showwarning("Thumbnail",msg)
    def _automation_audio(self) -> None:
        ok,msg=extract_audio(self.automation_target.get()); self._automation_write(msg)
        if not ok: messagebox.showwarning("Extract Audio",msg)
    def _automation_ready(self) -> None:
        ok,msg=make_tiktok_ready(self.automation_target.get()); self._automation_write(msg)
        if not ok: messagebox.showwarning("TikTok Ready",msg)
    def _automation_ready_package(self) -> None:
        self.status.set("Creating TikTok-ready package...")
        def worker():
            ok,_package,msg=make_ready_package(self.automation_target.get())
            self.after(0,lambda:self._finish_ready_package(ok,msg,self.automation_output))
        threading.Thread(target=worker,daemon=True).start()
    def _automation_burn_caption(self) -> None:
        text=simpledialog.askstring("Burn Caption","Caption/title text",initialvalue="Watch this before you scroll")
        if not text: return
        ok,msg=burn_caption(self.automation_target.get(),text); self._automation_write(msg)
        if not ok: messagebox.showwarning("Burn Caption",msg)
    def _automation_watermark(self) -> None:
        text=simpledialog.askstring("Watermark","Watermark text",initialvalue=brand_settings().watermark)
        if not text: return
        ok,msg=add_watermark(self.automation_target.get(),text); self._automation_write(msg)
        if not ok: messagebox.showwarning("Watermark",msg)
    def _automation_brand(self) -> None:
        caption=simpledialog.askstring("Brand Video","Caption/title text",initialvalue="Watch this before you scroll")
        if not caption: return
        watermark=simpledialog.askstring("Brand Video","Watermark text",initialvalue=brand_settings().watermark) or ""
        ok,msg=brand_video(self.automation_target.get(),caption,watermark); self._automation_write(msg)
        if not ok: messagebox.showwarning("Brand Video",msg)
    def _automation_srt(self) -> None:
        text=simpledialog.askstring("Create SRT","Caption text",initialvalue="Watch this before you scroll")
        if not text: return
        ok,msg=create_srt(self.automation_target.get(),text); self._automation_write(msg)
        if not ok: messagebox.showwarning("Create SRT",msg)
    def _automation_batch_campaign(self) -> None:
        limit=simpledialog.askinteger("Batch Campaign","Maximum videos to process",initialvalue=brand_settings().batch_limit,minvalue=1,maxvalue=50)
        if not limit: return
        queue=messagebox.askyesno("Batch Campaign","Queue finished videos for upload?")
        account=""
        if queue:
            account=simpledialog.askstring("Batch Campaign","Account for queued videos",initialvalue=brand_settings().default_account) or ""
        self.status.set("Building batch campaign...")
        self.automation_output.delete("1.0",tk.END); self.automation_output.insert("1.0","Working...")
        def worker():
            ok,_result,msg=build_batch_campaign(self.automation_target.get(),limit=limit,queue=queue,account=account)
            self.after(0,lambda:self._finish_batch_campaign(ok,msg))
        threading.Thread(target=worker,daemon=True).start()
    def _finish_batch_campaign(self, ok: bool, msg: str) -> None:
        self._automation_write(msg); self.status.set("Batch campaign complete" if ok else "Batch campaign failed")
        self._refresh_library(); self._refresh_drafts(); self._refresh_jobs()
        if not ok: messagebox.showwarning("Batch Campaign",msg)

    def _build_upload_tab(self) -> None:
        ttk.Label(self.upload_tab,text="Local TikTok sessions and upload queue. Login uses the existing uploader browser flow; no API keys.",background="#f8fafc",foreground="#475569").pack(anchor="w",pady=(0,8))
        top=ttk.Frame(self.upload_tab); top.pack(fill="x",pady=(0,8))
        ttk.Button(top,text="Sync Sessions",command=self._upload_sync).pack(side="left",padx=(0,6))
        ttk.Button(top,text="Login / Re-login",command=self._upload_login).pack(side="left",padx=(0,6))
        ttk.Button(top,text="Import Cookies",command=self._upload_import_cookies).pack(side="left",padx=(0,6))
        ttk.Button(top,text="Import From Browser",command=self._upload_import_browser).pack(side="left",padx=(0,6))
        ttk.Button(top,text="Browser Health",command=self._upload_browser_health).pack(side="left",padx=(0,6))
        ttk.Button(top,text="Queue Ready Videos",command=self._upload_queue_ready).pack(side="left",padx=(0,6))
        ttk.Button(top,text="Add Video",command=self._upload_add_video).pack(side="left",padx=(0,6))
        ttk.Button(top,text="Set Account",command=self._upload_assign_account).pack(side="left",padx=(0,6))
        ttk.Button(top,text="Auto Account",command=self._upload_auto_account).pack(side="left",padx=(0,6))
        ttk.Button(top,text="Preflight",command=self._upload_preflight).pack(side="left",padx=(0,6))
        ttk.Button(top,text="Dry Run Command",command=self._upload_dry_run).pack(side="left",padx=(0,6))
        ttk.Button(top,text="Run Upload",command=self._upload_run).pack(side="left",padx=(0,6))
        ttk.Button(top,text="Cancel",command=self._upload_cancel).pack(side="left",padx=(0,6))
        self.upload_summary=tk.StringVar(value="")
        ttk.Label(self.upload_tab,textvariable=self.upload_summary,background="#f8fafc",foreground="#0f172a",font=("Segoe UI",10,"bold")).pack(anchor="w",pady=(0,8))
        ttk.Label(self.upload_tab,text="Accounts",background="#f8fafc",foreground="#0f172a",font=("Segoe UI",10,"bold")).pack(anchor="w")
        self.accounts_tree=ttk.Treeview(self.upload_tab,columns=("id","username","status","cookie","checked","notes"),show="headings",height=5)
        for col,width in (("id",50),("username",150),("status",90),("cookie",360),("checked",180),("notes",360)):
            self.accounts_tree.heading(col,text=col.title()); self.accounts_tree.column(col,width=width,stretch=col in {"cookie","notes"})
        self.accounts_tree.pack(fill="x",pady=(0,8))
        ttk.Label(self.upload_tab,text="Upload Queue",background="#f8fafc",foreground="#0f172a",font=("Segoe UI",10,"bold")).pack(anchor="w")
        self.queue_tree=ttk.Treeview(self.upload_tab,columns=("id","status","account","source","title","scheduled","library"),show="headings")
        for col,width in (("id",50),("status",90),("account",130),("source",330),("title",240),("scheduled",160),("library",100)):
            self.queue_tree.heading(col,text=col.title()); self.queue_tree.column(col,width=width,stretch=col in {"source","title"})
        self.queue_tree.pack(fill="both",expand=True,pady=(0,8))
        self.queue_output=tk.Text(self.upload_tab,height=5,font=("Consolas",9),wrap="word")
        self.queue_output.pack(fill="x")
        self._upload_sync()
    def _selected_queue_id(self) -> int:
        sel=self.queue_tree.selection() if hasattr(self,"queue_tree") else []
        if not sel:
            messagebox.showinfo("Upload Queue","Select a queue row first."); return 0
        return int(self.queue_tree.item(sel[0],"values")[0])
    def _selected_account(self) -> str:
        sel=self.accounts_tree.selection() if hasattr(self,"accounts_tree") else []
        if not sel: return ""
        return str(self.accounts_tree.item(sel[0],"values")[1])
    def _upload_write(self,msg: str) -> None:
        self.queue_output.delete("1.0",tk.END); self.queue_output.insert("1.0",msg)
    def _upload_sync(self) -> None:
        sync_accounts(); self.accounts_tree.delete(*self.accounts_tree.get_children()); self.queue_tree.delete(*self.queue_tree.get_children())
        for row in account_rows(): self.accounts_tree.insert("",tk.END,values=row)
        for row in queue_rows(): self.queue_tree.insert("",tk.END,values=(row.id,row.status,row.account,row.source_ref,row.title,row.scheduled_for,row.library_key))
        self.upload_summary.set(" | ".join(queue_summary_lines()) or "Queue empty")
        self._refresh_jobs()
    def _upload_login(self) -> None:
        username=simpledialog.askstring("TikTok Login","Account name to save locally:",initialvalue=self._selected_account())
        if not username: return
        self.status.set("Starting TikTok login flow...")
        def worker():
            ok,msg=run_login(username); self.after(0,lambda:(self._upload_write(msg), self.status.set("Login complete" if ok else "Login failed"), self._upload_sync()))
        threading.Thread(target=worker,daemon=True).start()
    def _upload_import_cookies(self) -> None:
        username=simpledialog.askstring("Import Cookies","Account name to save locally:",initialvalue=self._selected_account())
        if not username: return
        file=filedialog.askopenfilename(title="Import TikTok cookies",filetypes=[("Cookie exports","*.json *.txt *.cookie"),("All files","*.*")])
        if not file: return
        ok,msg=import_cookie_file(username,file); self._upload_write(msg); self.status.set("Cookies imported" if ok else "Cookie import needs attention"); self._upload_sync()
        if not ok: messagebox.showwarning("Import Cookies",msg)


    def _upload_browser_health(self) -> None:
        self.status.set("Checking browser TikTok sessions...")
        def worker():
            msg=format_browser_session_health()
            self.after(0,lambda:(self._upload_write(msg), self.status.set("Browser session health checked")))
        threading.Thread(target=worker,daemon=True).start()

    def _upload_auto_account(self) -> None:
        preferred=self._selected_account()
        count,msg=auto_assign_healthy_account(preferred)
        self._upload_write(msg); self.status.set(msg); self._upload_sync()
        if not count: messagebox.showwarning("Auto Account",msg)

    def _upload_preflight(self) -> None:
        item_id=self._selected_queue_id()
        if not item_id: return
        ok,msg=upload_preflight(item_id); self._upload_write(msg); self.status.set("Preflight passed" if ok else "Preflight needs fixes"); self._upload_sync()
        if not ok: messagebox.showwarning("Upload Preflight",msg)
    def _upload_import_browser(self) -> None:
        username=simpledialog.askstring("Import From Browser","Account name to save locally:",initialvalue=self._selected_account() or brand_settings().default_account)
        if not username: return
        browser=simpledialog.askstring("Import From Browser","Browser: auto, chrome, edge, brave, or firefox",initialvalue="auto") or "auto"
        self.status.set("Scanning browser TikTok session...")
        def worker():
            ok,msg=import_browser_session(username,browser)
            self.after(0,lambda:(self._upload_write(msg), self.status.set("Browser session imported" if ok else "Browser session not found"), self._upload_sync(), messagebox.showwarning("Import From Browser",msg) if not ok else None))
        threading.Thread(target=worker,daemon=True).start()
    def _upload_queue_ready(self) -> None:
        account=self._selected_account()
        if not account:
            account=simpledialog.askstring("Upload Queue","Account name for queued items",initialvalue=brand_settings().default_account) or ""
        count=queue_ready_items(account); self._upload_write(f"Queued {count} ready videos"); self._upload_sync()
    def _upload_add_video(self) -> None:
        file=filedialog.askopenfilename(title="Choose video",filetypes=[("Video files","*.mp4 *.mov *.m4v *.webm *.avi *.mkv"),("All files","*.*")])
        if not file: return
        account=self._selected_account()
        ok,msg=add_to_queue(file,account=account); self._upload_write(msg); self._upload_sync()
        if not ok: messagebox.showwarning("Upload Queue",msg)
    def _upload_assign_account(self) -> None:
        item_id=self._selected_queue_id()
        if not item_id: return
        account=self._selected_account() or simpledialog.askstring("Upload Account","Account name",initialvalue=brand_settings().default_account) or ""
        ok,msg=assign_queue_account(item_id,account); self._upload_write(msg); self._upload_sync()
        if not ok: messagebox.showwarning("Set Account",msg)
    def _upload_dry_run(self) -> None:
        item_id=self._selected_queue_id()
        if not item_id: return
        ok,msg=run_queue_item(item_id,dry_run=True); self._upload_write(msg); self._upload_sync()
        if not ok: messagebox.showwarning("Dry Run",msg)
    def _upload_run(self) -> None:
        item_id=self._selected_queue_id()
        if not item_id: return
        if not messagebox.askyesno("Run Upload","This will open/use the uploader automation for the selected queue item. Continue?"):
            return
        self.status.set("Running upload...")
        def worker():
            ok,msg=run_queue_item(item_id,dry_run=False); self.after(0,lambda:(self._upload_write(msg), self.status.set("Upload done" if ok else "Upload failed"), self._upload_sync(), self._refresh_library()))
        threading.Thread(target=worker,daemon=True).start()
    def _upload_cancel(self) -> None:
        item_id=self._selected_queue_id()
        if not item_id: return
        ok,msg=cancel_queue_item(item_id); self._upload_write(msg); self._upload_sync()
        if not ok: messagebox.showwarning("Cancel",msg)

    def _build_settings_tab(self) -> None:
        ttk.Label(self.settings_tab,text="Brand defaults used when workflows need an account, watermark, posting hour, hashtags, or batch size.",background="#f8fafc",foreground="#475569").pack(anchor="w",pady=(0,8))
        self.setting_vars={}
        grid=ttk.Frame(self.settings_tab); grid.pack(fill="x",pady=(0,8))
        values=all_settings()
        for row,key in enumerate(DEFAULT_SETTINGS):
            ttk.Label(grid,text=key.replace("_"," ").title(),background="#f8fafc",foreground="#0f172a").grid(row=row,column=0,sticky="w",padx=(0,10),pady=4)
            var=tk.StringVar(value=values.get(key,"")); self.setting_vars[key]=var
            ttk.Entry(grid,textvariable=var,width=70).grid(row=row,column=1,sticky="ew",pady=4)
        grid.columnconfigure(1,weight=1)
        row=ttk.Frame(self.settings_tab); row.pack(fill="x",pady=(0,8))
        ttk.Button(row,text="Save Settings",command=self._save_settings_ui).pack(side="left",padx=(0,8))
        ttk.Button(row,text="Refresh",command=self._refresh_settings_ui).pack(side="left",padx=(0,8))
        self.settings_output=tk.Text(self.settings_tab,height=14,font=("Consolas",10),wrap="word")
        self.settings_output.pack(fill="both",expand=True)
        self._refresh_settings_ui()
    def _save_settings_ui(self) -> None:
        for key,var in self.setting_vars.items():
            set_setting(key,var.get())
        self.status.set("Brand settings saved")
        self._refresh_settings_ui(); self._daily_refresh(); self._refresh_jobs()
    def _refresh_settings_ui(self) -> None:
        if not hasattr(self,"settings_output"): return
        values=all_settings()
        for key,var in getattr(self,"setting_vars",{}).items():
            var.set(values.get(key,""))
        self.settings_output.delete("1.0",tk.END); self.settings_output.insert("1.0",format_settings())

    def _build_doctor_tab(self) -> None:
        top=ttk.Frame(self.doctor_tab); top.pack(fill="x",pady=(0,8))
        ttk.Button(top,text="Run Checks",command=self._run_doctor_ui).pack(side="left",padx=(0,8))
        ttk.Button(top,text="Fix Folders",command=self._fix_folders_ui).pack(side="left",padx=(0,8))
        ttk.Button(top,text="Install Requirements",command=self._install_requirements_ui).pack(side="left",padx=(0,8))
        ttk.Button(top,text="Install Playwright Browser",command=self._install_playwright_ui).pack(side="left")
        self.doctor_results=tk.Text(self.doctor_tab,height=28,font=("Consolas",10),wrap="word")
        self.doctor_results.pack(fill="both",expand=True)
        self._run_doctor_ui()
    def _run_doctor_ui(self) -> None:
        self.status.set("Running setup checks...")
        self.doctor_results.delete("1.0",tk.END)
        def worker():
            checks=run_doctor(); report=format_doctor_report(checks)
            self.after(0,lambda:(self.doctor_results.insert("1.0",report), self.status.set("Setup Doctor checks complete")))
        threading.Thread(target=worker,daemon=True).start()
    def _fix_folders_ui(self) -> None:
        ok,msg=fix_folders(); self.status.set(msg); self._run_doctor_ui()
    def _install_requirements_ui(self) -> None:
        ok,msg=install_all_requirements(); self.status.set(msg); self._refresh_jobs()
    def _install_playwright_ui(self) -> None:
        ok,msg=install_playwright_browser(); self.status.set(msg); self._refresh_jobs()

    def _build_projects_tab(self) -> None:
        canvas=tk.Canvas(self.projects_tab,bg="#f8fafc",highlightthickness=0); scroll=ttk.Scrollbar(self.projects_tab,orient="vertical",command=canvas.yview); content=ttk.Frame(canvas)
        content.bind("<Configure>",lambda _e: canvas.configure(scrollregion=canvas.bbox("all"))); canvas.create_window((0,0),window=content,anchor="nw"); canvas.configure(yscrollcommand=scroll.set); canvas.pack(side="left",fill="both",expand=True); scroll.pack(side="right",fill="y")
        grouped={}
        for p in PROJECTS: grouped.setdefault(p.category,[]).append(p)
        for cat,projects in grouped.items():
            ttk.Label(content,text=cat.upper(),background="#f8fafc",foreground="#64748b",font=("Segoe UI",9,"bold")).pack(anchor="w",pady=(10,4))
            for p in projects: self._project_card(content,p)
    def _project_card(self,parent: ttk.Frame,p: Project) -> None:
        card=ttk.Frame(parent,style="Card.TFrame",padding=12); card.pack(fill="x",pady=5)
        top=ttk.Frame(card,style="Card.TFrame"); top.pack(fill="x"); ttk.Label(top,text=p.name,style="Heading.TLabel").pack(side="left"); ttk.Label(top,text=p.status,background="#ffffff",foreground="#0369a1",font=("Segoe UI",9,"bold")).pack(side="right")
        ttk.Label(card,text=p.summary,style="Body.TLabel",wraplength=920,justify="left").pack(anchor="w",pady=(6,4)); ttk.Label(card,text="Features: "+", ".join(p.features),style="Body.TLabel",wraplength=920,justify="left").pack(anchor="w")
        row=ttk.Frame(card,style="Card.TFrame"); row.pack(fill="x",pady=(10,0))
        for a in p.actions: ttk.Button(row,text=a.label,command=lambda a=a:self._run_action(a)).pack(side="left",padx=(0,8))
    def _run_action(self,a: Action) -> None:
        self.status.set(f"Running: {a.label}")
        def worker():
            ok,msg=a.runner(); self.after(0,lambda:self._finish_action(ok,msg))
        threading.Thread(target=worker,daemon=True).start()
    def _finish_action(self,ok: bool,msg: str) -> None:
        self.status.set(msg); self._refresh_jobs()
        if not ok: messagebox.showwarning("Action",msg)
    def _build_hunt_tab(self) -> None:
        ttk.Label(self.hunt_tab,text="Paste public links. The app saves metadata and candidate media/page links; review rights before reposting.",background="#f8fafc",foreground="#475569").pack(anchor="w")
        self.hunt_input=tk.Text(self.hunt_tab,height=7,font=("Consolas",10)); self.hunt_input.pack(fill="x",pady=8)
        buttons=ttk.Frame(self.hunt_tab); buttons.pack(fill="x",pady=(0,8)); ttk.Button(buttons,text="Hunt Content",command=self._hunt_content).pack(side="left",padx=(0,8)); ttk.Button(buttons,text="Save As Sources",command=self._save_hunt_sources).pack(side="left",padx=(0,8)); ttk.Button(buttons,text="Refresh Sources",command=self._refresh_sources_ui).pack(side="left",padx=(0,8)); ttk.Button(buttons,text="Deep Refresh",command=self._deep_refresh_sources_ui).pack(side="left",padx=(0,8)); ttk.Button(buttons,text="Digest",command=self._source_digest_ui).pack(side="left",padx=(0,8)); ttk.Button(buttons,text="Export Digest",command=self._source_digest_export_ui).pack(side="left",padx=(0,8)); ttk.Button(buttons,text="Draft Top",command=self._draft_top_ui).pack(side="left",padx=(0,8)); ttk.Button(buttons,text="Scan Local Videos",command=self._scan_local_assets_ui).pack(side="left",padx=(0,8)); ttk.Button(buttons,text="Make Drafts",command=self._make_drafts_ui).pack(side="left",padx=(0,8)); ttk.Button(buttons,text="Export Posting Plan",command=self._export_plan_ui).pack(side="left")
        self.hunt_results=tk.Text(self.hunt_tab,height=18,font=("Consolas",9),wrap="word"); self.hunt_results.pack(fill="both",expand=True)
    def _hunt_content(self) -> None:
        vals=[x.strip() for x in self.hunt_input.get("1.0",tk.END).splitlines() if x.strip()]
        if not vals: messagebox.showinfo("Content Hunt","Paste at least one link first."); return
        self.status.set("Hunting content candidates..."); self.hunt_results.delete("1.0",tk.END)
        def worker():
            c,e=hunt_urls(vals); self.after(0,lambda:self._show_hunt_results(c,e))
        threading.Thread(target=worker,daemon=True).start()
    def _show_hunt_results(self,cands: list[Candidate],errs: list[str]) -> None:
        lines=[]
        for c in cands:
            pack=content_pack(c.title,c.description); lines += [f"SAVED [{c.source_type}] {c.title}",f"  URL: {c.url}",f"  Media links found: {len(c.media_urls)}",f"  Hashtags: {' '.join(pack['hashtags'])}",f"  Caption: {pack['captions'][0]}",f"  Note: {c.notes}",""]
        lines += ["ERROR "+e for e in errs]
        self.hunt_results.insert("1.0","\n".join(lines) if lines else "No candidates found."); self.status.set(f"Saved {len(cands)} candidates; {len(errs)} errors"); self._refresh_library(); self._refresh_jobs()
    def _scan_local_assets_ui(self) -> None:
        count=scan_local_assets(); self.status.set(f"Scanned {count} local video assets"); self._refresh_library(); self._refresh_jobs()
    def _build_library_tab(self) -> None:
        top=ttk.Frame(self.library_tab); top.pack(fill="x",pady=(0,8))
        self.library_summary=tk.StringVar(value="")
        ttk.Label(top,textvariable=self.library_summary,background="#f8fafc",foreground="#0f172a",font=("Segoe UI",10,"bold")).pack(side="left")
        ttk.Button(top,text="Refresh",command=self._refresh_library).pack(side="right",padx=(8,0))
        ttk.Button(top,text="Export Analytics",command=self._analytics_export_ui).pack(side="right",padx=(8,0))
        ttk.Button(top,text="Open Exports",command=lambda:self._run_action(Action("Open exports","Open exports",lambda: open_folder("exports")))).pack(side="right")
        actions=ttk.Frame(self.library_tab); actions.pack(fill="x",pady=(0,8))
        ttk.Button(actions,text="Rebuild Library",command=self._library_rebuild_ui).pack(side="left",padx=(0,6))
        ttk.Button(actions,text="Schedule Next 7",command=self._library_schedule_ui).pack(side="left",padx=(0,6))
        ttk.Button(actions,text="Export CSV",command=self._library_export_ui).pack(side="left",padx=(0,6))
        ttk.Button(actions,text="Create Draft",command=self._library_draft_selected).pack(side="left",padx=(0,6))
        ttk.Button(actions,text="Set Status",command=self._library_set_status).pack(side="left",padx=(0,6))
        ttk.Button(actions,text="Mark Uploaded",command=self._library_mark_uploaded).pack(side="left",padx=(0,6))
        self.library_tree=ttk.Treeview(self.library_tab,columns=("key","type","title","status","scheduled","account","source","created"),show="headings")
        for col,width in (("key",90),("type",110),("title",260),("status",90),("scheduled",170),("account",120),("source",360),("created",170)):
            self.library_tree.heading(col,text=col.title()); self.library_tree.column(col,width=width,stretch=col in {"title","source"})
        self.library_tree.pack(fill="both",expand=True)
        self.analytics_output=tk.Text(self.library_tab,height=11,font=("Consolas",9),wrap="word")
        self.analytics_output.pack(fill="x",pady=(8,0))
        self._refresh_library()
    def _selected_library_key(self) -> str:
        sel=self.library_tree.selection() if hasattr(self,"library_tree") else []
        if not sel:
            messagebox.showinfo("Library","Select a library row first."); return ""
        return str(self.library_tree.item(sel[0],"values")[0])
    def _refresh_library(self) -> None:
        if not hasattr(self,"library_tree"): return
        counts=library_counts(); prod=" | ".join(library_summary_lines())
        base=" | ".join(f"{k}: {v}" for k,v in sorted(counts.items()))
        self.library_summary.set((base + " || " + prod)[:900])
        self.library_tree.delete(*self.library_tree.get_children())
        for row in production_rows():
            self.library_tree.insert("",tk.END,values=(row.key,row.item_type,row.title,row.status,row.scheduled_for,row.account,row.source,row.created_at))
        if hasattr(self,"analytics_output"):
            self.analytics_output.delete("1.0",tk.END); self.analytics_output.insert("1.0",format_analytics_report())
    def _analytics_export_ui(self) -> None:
        path=export_analytics_report(); self.status.set(f"Exported {path.relative_to(ROOT)}"); self._refresh_jobs(); messagebox.showinfo("Analytics Export","Exported:\n"+str(path))
    def _library_rebuild_ui(self) -> None:
        assets,drafts=rebuild_library(); self.status.set(f"Rebuilt library: {assets} assets, {drafts} drafts"); self._refresh_library(); self._refresh_drafts(); self._refresh_jobs()
    def _library_schedule_ui(self) -> None:
        count,msg=schedule_next_drafts(7); self.status.set(msg); self._refresh_library(); self._refresh_drafts(); self._refresh_jobs()
        if not count: messagebox.showwarning("Schedule",msg)
    def _library_export_ui(self) -> None:
        path=export_library_csv(); self.status.set(f"Exported {path.relative_to(ROOT)}"); self._refresh_jobs(); messagebox.showinfo("Library Export", "Exported:\n" + str(path))
    def _library_draft_selected(self) -> None:
        key=self._selected_library_key()
        if not key: return
        ok,msg=draft_from_item(key); self.status.set(msg); self._refresh_library(); self._refresh_drafts(); self._refresh_jobs()
        if not ok: messagebox.showwarning("Create Draft",msg)
    def _library_set_status(self) -> None:
        key=self._selected_library_key()
        if not key: return
        status=simpledialog.askstring("Set Status","candidate, draft, edited, ready, scheduled, uploaded, archived",initialvalue="ready")
        if not status: return
        ok,msg=update_item_status(key,status); self.status.set(msg); self._refresh_library(); self._refresh_drafts(); self._refresh_jobs()
        if not ok: messagebox.showwarning("Set Status",msg)
    def _library_mark_uploaded(self) -> None:
        key=self._selected_library_key()
        if not key: return
        account=simpledialog.askstring("Account","TikTok account/page used",initialvalue="") or ""
        ok,msg=mark_uploaded(key,account); self.status.set(msg); self._refresh_library(); self._refresh_drafts(); self._refresh_jobs()
        if not ok: messagebox.showwarning("Mark Uploaded",msg)
    def _build_jobs_tab(self) -> None:
        top=ttk.Frame(self.jobs_tab); top.pack(fill="x",pady=(0,8)); ttk.Button(top,text="Refresh",command=self._refresh_jobs).pack(side="right")
        self.jobs_tree=ttk.Treeview(self.jobs_tab,columns=("id","kind","target","status","message","created"),show="headings")
        for col,width in (("id",50),("kind",90),("target",260),("status",90),("message",360),("created",170)): self.jobs_tree.heading(col,text=col.title()); self.jobs_tree.column(col,width=width,stretch=col in {"target","message"})
        self.jobs_tree.pack(fill="both",expand=True); self._refresh_jobs()
    def _refresh_jobs(self) -> None:
        if not hasattr(self,"jobs_tree"): return
        self.jobs_tree.delete(*self.jobs_tree.get_children())
        for row in recent_jobs(): self.jobs_tree.insert("",tk.END,values=row)
    def _build_source_tab(self) -> None:
        left=ttk.Frame(self.source_tab); left.pack(side="left",fill="both",expand=True); right=ttk.Frame(self.source_tab); right.pack(side="right",fill="both",expand=True,padx=(10,0)); var=tk.StringVar(); ent=ttk.Entry(left,textvariable=var); ent.pack(fill="x",pady=(0,8)); ent.insert(0,"type to filter Python files"); lst=tk.Listbox(left,font=("Consolas",9)); lst.pack(fill="both",expand=True); prev=tk.Text(right,wrap="none",font=("Consolas",9)); prev.pack(fill="both",expand=True)
        def refresh(*_):
            needle=var.get().lower().strip(); needle="" if needle=="type to filter python files" else needle; lst.delete(0,tk.END)
            for path in self.python_files:
                if needle in str(path).lower(): lst.insert(tk.END,str(path))
        def select(_=None):
            sel=lst.curselection()
            if not sel: return
            path=ROOT/Path(lst.get(sel[0])); prev.delete("1.0",tk.END); prev.insert("1.0",path.read_text(encoding="utf-8",errors="replace")[:50000]); self.status.set(str(path))
        var.trace_add("write",refresh); lst.bind("<<ListboxSelect>>",select); refresh()
    def _build_help_tab(self) -> None:
        text=tk.Text(self.help_tab,wrap="word",font=("Consolas",10)); text.pack(fill="both",expand=True)
        text.insert("1.0", "Run:\n  "+PYTHON+" unified_tiktok_app.py\n\nCLI:\n  "+PYTHON+" unified_tiktok_app.py --list\n  "+PYTHON+" unified_tiktok_app.py --files\n  "+PYTHON+" unified_tiktok_app.py --check\n  "+PYTHON+" unified_tiktok_app.py --hunt https://www.tiktok.com/@example\n  "+PYTHON+" unified_tiktok_app.py --ideas \"your title here\"\n  "+PYTHON+" unified_tiktok_app.py --prepare C:\\path\\to\\video.mp4\n  "+PYTHON+" unified_tiktok_app.py --export-plan 7\n  "+PYTHON+" unified_tiktok_app.py --add-source https://example.com/feed.xml\n  "+PYTHON+" unified_tiktok_app.py --refresh-sources\n  "+PYTHON+" unified_tiktok_app.py --make-drafts\n  "+PYTHON+" unified_tiktok_app.py --drafts\n  "+PYTHON+" unified_tiktok_app.py --workflows\n  "+PYTHON+" unified_tiktok_app.py --workflow caption\n  "+PYTHON+" unified_tiktok_app.py --ready-package C:\\path\\to\\video.mp4\n  "+PYTHON+" unified_tiktok_app.py --tiktok-profile https://www.tiktok.com/@example\n  "+PYTHON+" unified_tiktok_app.py --profile-snapshots\n\nNo-key automations:\n  Paste & Go detects TikTok profiles/videos, YouTube links, web links, local videos, local folders, and text ideas. It analyzes, creates drafts, saves sources, and runs the recommended action.\n  Content Hunt saves public metadata and candidate media/page links. Review rights before reposting.\n\nDependency hints:\n  "+"\n  ".join(PIP_HINTS)+"\n")
        text.configure(state="disabled")

