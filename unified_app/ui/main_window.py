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
from unified_app.services.db import init_db
from unified_app.services.drafts import content_pack, export_posting_plan, make_drafts, recent_drafts
from unified_app.services.jobs import recent_jobs
from unified_app.services.library import library_counts, recent_candidates, scan_local_assets
from unified_app.services.source import scan_python_files
from unified_app.services.video_tools import prepare_video_for_upload
from unified_app.services.input_detector import detect_input, format_detection
from unified_app.services.setup_doctor import fix_folders, format_doctor_report, install_all_requirements, install_playwright_browser, run_doctor

class UnifiedApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__(); init_db(); self.python_files = scan_python_files(); self.status = tk.StringVar(value="Ready")
        self.title("Unified TikTok Python App"); self.geometry("1240x800"); self.minsize(1040, 660); self.configure(bg="#f8fafc"); self._build()
    def _build(self) -> None:
        style=ttk.Style(self); style.theme_use("clam")
        for name,bg in (("TFrame","#f8fafc"),("Card.TFrame","#ffffff")): style.configure(name, background=bg)
        style.configure("Title.TLabel", background="#f8fafc", foreground="#0f172a", font=("Segoe UI",18,"bold")); style.configure("Heading.TLabel", background="#ffffff", foreground="#0f172a", font=("Segoe UI",11,"bold")); style.configure("Body.TLabel", background="#ffffff", foreground="#475569", font=("Segoe UI",9)); style.configure("TButton", font=("Segoe UI",9), padding=(10,6))
        header=ttk.Frame(self, padding=(18,14)); header.pack(fill="x")
        ttk.Label(header,text="Unified TikTok Python App",style="Title.TLabel").pack(side="left")
        ttk.Label(header,text=f"{len(PROJECTS)} projects | {len(self.python_files)} Python files | no API keys",background="#f8fafc",foreground="#64748b").pack(side="right")
        nb=ttk.Notebook(self); nb.pack(fill="both",expand=True,padx=18,pady=(0,18))
        self.workflow_tab=ttk.Frame(nb,padding=10); self.doctor_tab=ttk.Frame(nb,padding=10); self.projects_tab=ttk.Frame(nb,padding=10); self.hunt_tab=ttk.Frame(nb,padding=10); self.drafts_tab=ttk.Frame(nb,padding=10); self.library_tab=ttk.Frame(nb,padding=10); self.jobs_tab=ttk.Frame(nb,padding=10); self.source_tab=ttk.Frame(nb,padding=10); self.help_tab=ttk.Frame(nb,padding=10)
        for tab,name in ((self.workflow_tab,"Paste & Go"),(self.doctor_tab,"Setup Doctor"),(self.projects_tab,"Projects"),(self.hunt_tab,"Content Hunt"),(self.drafts_tab,"Draft Queue"),(self.library_tab,"Library & Analytics"),(self.jobs_tab,"Jobs"),(self.source_tab,"Python Source"),(self.help_tab,"Run Commands")): nb.add(tab,text=name)
        self._build_workflow_tab(); self._build_doctor_tab(); self._build_projects_tab(); self._build_hunt_tab(); self._build_drafts_tab(); self._build_library_tab(); self._build_jobs_tab(); self._build_source_tab(); self._build_help_tab()
        ttk.Label(self,textvariable=self.status,background="#e2e8f0",foreground="#0f172a",padding=(10,5)).pack(fill="x")
    def _build_workflow_tab(self) -> None:
        ttk.Label(self.workflow_tab,text="Paste a TikTok page/video, YouTube link, website, RSS/feed URL, or local video path.",background="#f8fafc",foreground="#475569").pack(anchor="w")
        self.workflow_input=tk.Text(self.workflow_tab,height=5,font=("Consolas",10)); self.workflow_input.pack(fill="x",pady=8)
        row=ttk.Frame(self.workflow_tab); row.pack(fill="x",pady=(0,8))
        ttk.Button(row,text="Analyze",command=self._workflow_analyze).pack(side="left",padx=(0,8))
        ttk.Button(row,text="Save As Source",command=self._save_workflow_sources).pack(side="left",padx=(0,8))
        ttk.Button(row,text="Make Drafts",command=self._make_drafts_ui).pack(side="left",padx=(0,8))
        ttk.Button(row,text="Choose Local Video",command=self._choose_local_video).pack(side="left",padx=(0,8))
        ttk.Button(row,text="Copy Video To Upload Folder",command=self._prepare_workflow_video).pack(side="left",padx=(0,8))
        ttk.Button(row,text="Export Posting Plan",command=self._export_plan_ui).pack(side="left")
        self.workflow_output=tk.Text(self.workflow_tab,height=23,font=("Consolas",10),wrap="word"); self.workflow_output.pack(fill="both",expand=True)
    def _workflow_analyze(self) -> None:
        value=self.workflow_input.get("1.0",tk.END).strip()
        if not value: messagebox.showinfo("Analyze","Paste something first."); return
        self.workflow_output.delete("1.0",tk.END)
        vals=[x.strip() for x in value.splitlines() if x.strip()]
        detections=[detect_input(v) for v in vals]
        self.workflow_output.insert("1.0", "\n\n".join(format_detection(d) for d in detections) + "\n\n")
        first=detections[0]
        if len(detections)==1 and first.kind == "local_folder":
            count=scan_local_assets(); self.workflow_output.insert(tk.END,f"\nScanned local assets. Indexed {count} videos.\n"); self._refresh_library(); return
        if len(detections)==1 and first.kind == "local_video":
            p=Path(first.value); pack=content_pack(p.stem, str(p)); self.workflow_output.insert(tk.END,"\n"+self._format_pack(f"Local video: {p.name}", str(p), pack)); return
        if all(d.kind in {"tiktok_profile","tiktok_video","youtube","web"} for d in detections):
            self.status.set("Analyzing pasted links...")
            def worker():
                cands,errs=hunt_urls([d.value for d in detections]); self.after(0,lambda:self._workflow_show_candidates(cands,errs))
            threading.Thread(target=worker,daemon=True).start(); return
        if len(detections)==1 and first.kind == "text":
            pack=content_pack(first.value, ""); self.workflow_output.insert(tk.END,"\n"+self._format_pack("Text idea", first.value, pack)); return
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
        buttons=ttk.Frame(self.hunt_tab); buttons.pack(fill="x",pady=(0,8)); ttk.Button(buttons,text="Hunt Content",command=self._hunt_content).pack(side="left",padx=(0,8)); ttk.Button(buttons,text="Save As Sources",command=self._save_hunt_sources).pack(side="left",padx=(0,8)); ttk.Button(buttons,text="Refresh Sources",command=self._refresh_sources_ui).pack(side="left",padx=(0,8)); ttk.Button(buttons,text="Scan Local Videos",command=self._scan_local_assets_ui).pack(side="left",padx=(0,8)); ttk.Button(buttons,text="Make Drafts",command=self._make_drafts_ui).pack(side="left",padx=(0,8)); ttk.Button(buttons,text="Export Posting Plan",command=self._export_plan_ui).pack(side="left")
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
        top=ttk.Frame(self.library_tab); top.pack(fill="x",pady=(0,8)); self.library_summary=tk.StringVar(value=""); ttk.Label(top,textvariable=self.library_summary,background="#f8fafc",foreground="#0f172a",font=("Segoe UI",10,"bold")).pack(side="left"); ttk.Button(top,text="Refresh",command=self._refresh_library).pack(side="right",padx=(8,0)); ttk.Button(top,text="Open Exports",command=lambda:self._run_action(Action("Open exports","Open exports",lambda: open_folder("exports")))).pack(side="right")
        self.library_tree=ttk.Treeview(self.library_tab,columns=("id","type","title","url","status","created"),show="headings")
        for col,width in (("id",50),("type",90),("title",320),("url",420),("status",90),("created",170)): self.library_tree.heading(col,text=col.title()); self.library_tree.column(col,width=width,stretch=col in {"title","url"})
        self.library_tree.pack(fill="both",expand=True); self._refresh_library()
    def _refresh_library(self) -> None:
        if not hasattr(self,"library_tree"): return
        counts=library_counts(); self.library_summary.set(" | ".join(f"{k}: {v}" for k,v in sorted(counts.items()))); self.library_tree.delete(*self.library_tree.get_children())
        for row in recent_candidates(): self.library_tree.insert("",tk.END,values=row)
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
        text.insert("1.0", "Run:\n  "+PYTHON+" unified_tiktok_app.py\n\nCLI:\n  "+PYTHON+" unified_tiktok_app.py --list\n  "+PYTHON+" unified_tiktok_app.py --files\n  "+PYTHON+" unified_tiktok_app.py --check\n  "+PYTHON+" unified_tiktok_app.py --hunt https://www.tiktok.com/@example\n  "+PYTHON+" unified_tiktok_app.py --ideas \"your title here\"\n  "+PYTHON+" unified_tiktok_app.py --prepare C:\\path\\to\\video.mp4\n  "+PYTHON+" unified_tiktok_app.py --export-plan 7\n  "+PYTHON+" unified_tiktok_app.py --add-source https://example.com/feed.xml\n  "+PYTHON+" unified_tiktok_app.py --refresh-sources\n  "+PYTHON+" unified_tiktok_app.py --make-drafts\n  "+PYTHON+" unified_tiktok_app.py --drafts\n\nNo-key automations:\n  Paste & Go detects links/local videos, hunts metadata, generates hooks/captions/hashtags, and prepares local videos for the upload folder.\n  Content Hunt saves public metadata and candidate media/page links. Review rights before reposting.\n\nDependency hints:\n  "+"\n  ".join(PIP_HINTS)+"\n")
        text.configure(state="disabled")

