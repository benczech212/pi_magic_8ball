import time
import sys
import subprocess
import tkinter as tk
import csv
import shutil
import zipfile
import datetime
from pathlib import Path
from tkinter import ttk, colorchooser, messagebox, filedialog

# Try importing PIL for image preview
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from .config import (
    CONFIG, save_config, AppConfig, ThemeConfig, UIConfig, BehaviorConfig, 
    TextConfig, OutcomeConfig, WaitingScreenText, ThinkingScreenText, ResultScreenText
)
from .gpio_button import ArcadeButton
from .lamp import ButtonLamp, LampConfig, LampMode

# Available common resolutions
RESOLUTIONS = [
    "1920x1080",
    "1280x720",
    "1024x768",
    "800x600",
    "800x480",
    "720x480",
    "640x480"
]

class ConfigEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Magic 8-Ball Configuration")
        self.root.geometry("900x700")

        self.config = CONFIG  # This is the loaded config object. We will mutate variables then rebuild on save.
        
        # State variables
        self.var_name = tk.StringVar(value=self.config.name)
        self.var_fullscreen = tk.BooleanVar(value=self.config.ui.fullscreen)
        
        # Resolution logic
        init_res = f"{self.config.ui.window_width}x{self.config.ui.window_height}"
        self.var_resolution = tk.StringVar(value=init_res)
        
        self.var_bg_color = tk.StringVar(value=self._fmt_col(self.config.theme.background))
        self.var_text_color = tk.StringVar(value=self._fmt_col(self.config.theme.text))
        self.var_accent_color = tk.StringVar(value=self._fmt_col(self.config.theme.accent))
        
        self.var_logo_path = tk.StringVar(value=self.config.theme.logo_path or "")
        self.var_logo_width = tk.IntVar(value=self.config.theme.logo_width or 0)
        self.var_font_path = tk.StringVar(value=self.config.theme.font_path or "")
        
        self.var_anim_sec = tk.DoubleVar(value=self.config.behavior.animation_seconds)
        self.var_settle_sec = tk.DoubleVar(value=self.config.behavior.square_settle_seconds)
        
        # Hardware vars
        self.var_btn_pin = tk.IntVar(value=self.config.gpio.button_pin)
        self.var_lamp_pin = tk.IntVar(value=self.config.gpio.lamp_pin)
        self.var_pull = tk.StringVar(value="Pull Up" if self.config.gpio.button_pull_up else "Pull Down")
        self.var_debounce = tk.StringVar(value=str(self.config.gpio.debounce_seconds))
        self.var_pwm = tk.StringVar(value=str(self.config.gpio.lamp_pwm_hz))
        self.var_idle_speed = tk.StringVar(value=str(self.config.gpio.lamp_idle_speed))

        # Notebook
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)
        
        self._build_general_tab()
        self._build_theme_tab()
        self._build_text_tab()
        self._build_outcomes_tab()
        self._build_hardware_tab()
        self._build_logs_tab()
        self._build_launch_tab()

        # Initialize Hardware
        self._init_hardware()

        # Footer
        frame_footer = ttk.Frame(root)
        frame_footer.pack(fill="x", padx=10, pady=10)
        
        btn_save = ttk.Button(frame_footer, text="Save Settings", command=self.save)
        btn_save.pack(side="right")
        
        btn_launch = ttk.Button(frame_footer, text="Launch App", command=lambda: self.launch([]))
        btn_launch.pack(side="right", padx=10)

        btn_close = ttk.Button(frame_footer, text="Exit Editor", command=root.destroy)
        btn_close.pack(side="right")

        # Start hardware loop
        self._update_hardware_loop()

    def _init_hardware(self):
        # Clean up old
        if hasattr(self, 'lamp'): self.lamp.close()
        # if hasattr(self, 'button'): self.button.close() # ArcadeButton doesn't strict close but good practice if it did

        try:
            self.lamp = ButtonLamp(
                LampConfig(
                    enabled=self.config.gpio.enabled and self.config.gpio.lamp_enabled,
                    pin=self.var_lamp_pin.get(),
                    active_high=self.config.gpio.lamp_active_high,
                    pwm_hz=int(float(self.var_pwm.get())),
                    idle_speed=float(self.var_idle_speed.get())
                )
            )
            self.button = ArcadeButton(
                self.var_btn_pin.get(), 
                float(self.var_debounce.get()),
                pull_up=(self.var_pull.get() == "Pull Up")
            )
        except Exception as e:
            print(f"Hardware init failed (likely safe on PC): {e}")

    def launch(self, args=[]):
        cmd = [sys.executable, "-m", "src.main"] + args
        print(f"Launching: {' '.join(cmd)}")
        try:
            subprocess.Popen(cmd, cwd=self.config.project_root)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch: {e}")

    def __del__(self):
        if hasattr(self, 'lamp'):
            self.lamp.close()

    def _update_hardware_loop(self):
        now = time.monotonic()
        if hasattr(self, 'lamp'):
            self.lamp.update(now)
        
        if hasattr(self, 'button'):
            is_pressed = False
            if self.button.poll_pressed():
                is_pressed = True
            
            if hasattr(self, 'lbl_btn_status') and self.lbl_btn_status.winfo_exists():
                if is_pressed:
                     self.lbl_btn_status.config(text="PRESSED", foreground="green")
                     self.root.after(200, lambda: self.lbl_btn_status.config(text="RELEASED", foreground="gray"))
        
        self.root.after(50, self._update_hardware_loop)

    def _fmt_col(self, c):
        if isinstance(c, (tuple, list)):
            return f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"
        return str(c)
        
    def _parse_hex(self, hex_str):
        hex_str = hex_str.lstrip('#')
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    
    def _make_scrollable_frame(self, parent):
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Mousewheel
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        return scrollable_frame

    def _build_general_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="General")
        
        form_frame = self._make_scrollable_frame(tab)
        inner = ttk.Frame(form_frame, padding="20")
        inner.pack(fill="both", expand=True)
        
        ttk.Label(inner, text="Device Name:").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(inner, textvariable=self.var_name, width=30).grid(row=0, column=1, sticky="w", pady=5)
        
        ttk.Label(inner, text="Resolution:").grid(row=1, column=0, sticky="w", pady=5)
        cb_res = ttk.Combobox(inner, textvariable=self.var_resolution, values=RESOLUTIONS)
        cb_res.grid(row=1, column=1, sticky="w", pady=5)
        
        ttk.Label(inner, text="Fullscreen Mode:").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Checkbutton(inner, variable=self.var_fullscreen).grid(row=2, column=1, sticky="w", pady=5)
        
        ttk.Label(inner, text="Animation Duration (s):").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Entry(inner, textvariable=self.var_anim_sec, width=10).grid(row=3, column=1, sticky="w", pady=5)

        ttk.Label(inner, text="Settle Duration (s):").grid(row=4, column=0, sticky="w", pady=5)
        ttk.Entry(inner, textvariable=self.var_settle_sec, width=10).grid(row=4, column=1, sticky="w", pady=5)

    def _build_theme_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Theme")
        
        form_frame = self._make_scrollable_frame(tab)
        inner = ttk.Frame(form_frame, padding="20")
        inner.pack(fill="both", expand=True)
        
        def pick_color(var, preview_canvas):
            color = colorchooser.askcolor(color=var.get())[1]
            if color:
                var.set(color)
                preview_canvas.config(bg=color)

        def browse_file(var, title, filetypes):
            f = filedialog.askopenfilename(title=title, filetypes=filetypes)
            if f:
                # convert to relative if possible
                try:
                    p = Path(f).resolve()
                    root = self.config.project_root.resolve()
                    if root in p.parents:
                        f = str(p.relative_to(root))
                except:
                    pass
                var.set(f)

        def make_row(row, label, var, is_color=True, browse_cmd=None):
             ttk.Label(inner, text=label).grid(row=row, column=0, sticky="w", pady=5)
             ttk.Entry(inner, textvariable=var, width=25).grid(row=row, column=1, sticky="w", pady=5)
             
             if is_color:
                 preview = tk.Canvas(inner, width=20, height=20, bg=var.get(), highlightthickness=1, highlightbackground="gray")
                 preview.grid(row=row, column=2, padx=5)
                 def update_preview(*args):
                     try: 
                          if len(var.get()) in (4, 7, 13): preview.config(bg=var.get())
                     except: pass
                 var.trace_add("write", update_preview)
                 ttk.Button(inner, text="Pick", command=lambda: pick_color(var, preview)).grid(row=row, column=3, padx=5)
             elif browse_cmd:
                 ttk.Button(inner, text="Browse", command=browse_cmd).grid(row=row, column=2, padx=5)

        make_row(0, "Background:", self.var_bg_color)
        make_row(1, "Text Color:", self.var_text_color)
        make_row(2, "Accent Color:", self.var_accent_color)
        
        ttk.Separator(inner, orient="horizontal").grid(row=3, column=0, columnspan=4, sticky="ew", pady=10)
        
        make_row(4, "Logo Path:", self.var_logo_path, is_color=False, 
                 browse_cmd=lambda: browse_file(self.var_logo_path, "Select Logo", [("Images", "*.png *.jpg")]))
        make_row(5, "Logo Width (%):", self.var_logo_width, is_color=False)
        make_row(6, "Font Path:", self.var_font_path, is_color=False,
                 browse_cmd=lambda: browse_file(self.var_font_path, "Select Font", [("Fonts", "*.ttf *.otf")]))

        # Logo Preview
        if HAS_PIL:
            ttk.Label(inner, text="Logo Preview:").grid(row=7, column=0, sticky="nw", pady=10)
            self.lbl_logo_preview = ttk.Label(inner, text="(No logo)")
            self.lbl_logo_preview.grid(row=7, column=1, columnspan=2, sticky="w", pady=10)
            
            def update_logo_preview(*args):
                path_str = self.var_logo_path.get()
                if not path_str:
                    self.lbl_logo_preview.config(image="", text="(No logo)")
                    return
                
                try:
                    p = Path(path_str)
                    if not p.is_absolute(): p = self.config.project_root / p
                    
                    if p.exists():
                        img = Image.open(p)
                        # Resize for preview (max 150h)
                        img.thumbnail((200, 150))
                        tk_img = ImageTk.PhotoImage(img)
                        self.lbl_logo_preview.config(image=tk_img, text="")
                        self.lbl_logo_preview.image = tk_img # keep ref
                    else:
                        self.lbl_logo_preview.config(image="", text="(File not found)")
                except Exception:
                    self.lbl_logo_preview.config(image="", text="(Load error)")
            
            self.var_logo_path.trace_add("write", update_logo_preview)
            # Init preview
            update_logo_preview()

    def _build_list_editor(self, parent, title, items, on_update):
        """Helper to build a list editor with Add/Edit/Remove/Move"""
        frame = ttk.LabelFrame(parent, text=title, padding=5)
        
        tree = ttk.Treeview(frame, columns=("text",), show="headings", height=5)
        tree.heading("text", text="Text")
        tree.column("text", width=300)
        
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        
        # Populate
        for x in items:
            tree.insert("", "end", values=(x,))
            
        # Controls
        ctrl = ttk.Frame(frame)
        ctrl.pack(fill="x", pady=5)
        
        entry = ttk.Entry(ctrl)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        def add_item():
            val = entry.get().strip()
            if val:
                tree.insert("", "end", values=(val,))
                entry.delete(0, "end")
                on_update(get_all())
        
        def remove_item():
            for sel in tree.selection():
                tree.delete(sel)
            on_update(get_all())
            
        def update_selected():
            sel = tree.selection()
            if not sel: return
            val = entry.get().strip()
            if val:
                tree.item(sel[0], values=(val,))
                on_update(get_all())
            
        def fill_entry(event):
            sel = tree.selection()
            if sel:
                val = tree.item(sel[0])['values'][0]
                entry.delete(0, "end")
                entry.insert(0, str(val))

        tree.bind("<<TreeviewSelect>>", fill_entry)
        
        ttk.Button(ctrl, text="Add", command=add_item, width=6).pack(side="left")
        ttk.Button(ctrl, text="Update", command=update_selected, width=8).pack(side="left")
        ttk.Button(ctrl, text="Remove", command=remove_item, width=8).pack(side="left")
        
        def get_all():
            return [str(tree.item(child)["values"][0]) for child in tree.get_children()]
            
        return frame

    def _build_text_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Text & Prompts")
        
        scroll_frame = self._make_scrollable_frame(tab)
        inner = ttk.Frame(scroll_frame, padding=10)
        inner.pack(fill="both", expand=True)
        
        # Prompts
        self.temp_prompts = list(self.config.text.prompts)
        def update_prompts(new_list): self.temp_prompts = new_list
        p_frame = self._build_list_editor(inner, "Prompts", self.config.text.prompts, update_prompts)
        p_frame.pack(fill="x", pady=10)
        
        # Waiting Subs
        self.temp_waiting = list(self.config.text.waiting_screen.subtitles)
        def update_waiting(new_list): self.temp_waiting = new_list
        w_frame = self._build_list_editor(inner, "Waiting Subtitles", self.config.text.waiting_screen.subtitles, update_waiting)
        w_frame.pack(fill="x", pady=10)

    def _build_outcomes_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Outcomes")
        
        paned = ttk.PanedWindow(tab, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=10, pady=10)
        
        frame_list = ttk.Frame(paned)
        paned.add(frame_list, weight=1)
        
        columns = ("text", "weight", "type")
        self.tree_out = ttk.Treeview(frame_list, columns=columns, show="headings")
        self.tree_out.heading("text", text="Outcome Text")
        self.tree_out.heading("weight", text="Wt")
        self.tree_out.heading("type", text="Type")
        
        self.tree_out.column("text", width=300)
        self.tree_out.column("weight", width=40)
        self.tree_out.column("type", width=80)
        
        scroll = ttk.Scrollbar(frame_list, orient="vertical", command=self.tree_out.yview)
        self.tree_out.configure(yscrollcommand=scroll.set)
        
        self.tree_out.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        
        for outcome in self.config.outcomes:
            self.tree_out.insert("", "end", values=(outcome.text, outcome.weight, outcome.type))
            
        # Detail Editor
        frame_controls = ttk.LabelFrame(paned, text="Edit Selected", padding=10)
        paned.add(frame_controls, weight=0)
        
        ttk.Label(frame_controls, text="Text:").pack(anchor="w")
        entry_text = ttk.Entry(frame_controls, width=30)
        entry_text.pack(anchor="w", pady=5)
        
        ttk.Label(frame_controls, text="Weight:").pack(anchor="w")
        entry_weight = ttk.Entry(frame_controls, width=10)
        entry_weight.pack(anchor="w", pady=5)
        
        ttk.Label(frame_controls, text="Type:").pack(anchor="w")
        var_type = tk.StringVar()
        cb_type = ttk.Combobox(frame_controls, textvariable=var_type, values=["Yes", "No", "Inconclusive"], state="readonly")
        cb_type.pack(anchor="w", pady=5)
        
        def on_select(event):
            sel = self.tree_out.selection()
            if sel:
                vals = self.tree_out.item(sel[0])['values']
                entry_text.delete(0, "end")
                entry_text.insert(0, str(vals[0]))
                
                entry_weight.delete(0, "end")
                entry_weight.insert(0, str(vals[1]))
                
                var_type.set(str(vals[2]))

        self.tree_out.bind("<<TreeviewSelect>>", on_select)
        
        def update_item():
            sel = self.tree_out.selection()
            if not sel: return
            
            t = entry_text.get().strip()
            w = entry_weight.get().strip()
            tp = var_type.get()
            
            if t:
                 self.tree_out.item(sel[0], values=(t, w, tp))
                 
        def add_item():
            t = entry_text.get().strip()
            if t:
                self.tree_out.insert("", "end", values=(t, entry_weight.get() or "1", var_type.get() or "Inconclusive"))
                
        def delete_item():
            for s in self.tree_out.selection():
                self.tree_out.delete(s)

        ttk.Button(frame_controls, text="Update", command=update_item).pack(fill="x", pady=5)
        ttk.Button(frame_controls, text="Add New", command=add_item).pack(fill="x", pady=5)
        ttk.Button(frame_controls, text="Remove Selected", command=delete_item).pack(fill="x", pady=5)

    def _build_hardware_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Hardware")
        
        scroll = self._make_scrollable_frame(tab)
        inner = ttk.Frame(scroll, padding=20)
        inner.pack(fill="both", expand=True)

        # Pins
        lf_pins = ttk.LabelFrame(inner, text="GPIO Pin Assignment", padding=10)
        lf_pins.pack(fill="x", pady=10)
        
        ttk.Label(lf_pins, text="Button Pin (BCM):").grid(row=0, column=0, sticky="w")
        ttk.Entry(lf_pins, textvariable=self.var_btn_pin, width=5).grid(row=0, column=1, sticky="w", padx=10)
        
        ttk.Label(lf_pins, text="Lamp Pin (BCM):").grid(row=1, column=0, sticky="w")
        ttk.Entry(lf_pins, textvariable=self.var_lamp_pin, width=5).grid(row=1, column=1, sticky="w", padx=10)
        
        def reset_defaults():
            self.var_btn_pin.set(17)
            self.var_lamp_pin.set(18)
            self._init_hardware() # Apply immediately
            
        ttk.Button(lf_pins, text="Reset Defaults (17/18)", command=reset_defaults).grid(row=0, column=2, rowspan=2, padx=20)

        # Lamp Settings
        lf_lamp = ttk.LabelFrame(inner, text="Lamp Control Test", padding=10)
        lf_lamp.pack(fill="x", pady=10)
        
        def set_lamp(mode):
            if hasattr(self, 'lamp'): self.lamp.set_mode(mode)

        ttk.Button(lf_lamp, text="OFF", command=lambda: set_lamp(LampMode.OFF)).pack(side="left", padx=5)
        ttk.Button(lf_lamp, text="BREATHE", command=lambda: set_lamp(LampMode.IDLE)).pack(side="left", padx=5)
        ttk.Button(lf_lamp, text="PULSE", command=lambda: set_lamp(LampMode.THINKING)).pack(side="left", padx=5)
        ttk.Button(lf_lamp, text="ON", command=lambda: set_lamp(LampMode.RESULT)).pack(side="left", padx=5)

        # Advanced
        lf_adv = ttk.LabelFrame(inner, text="Advanced", padding=10)
        lf_adv.pack(fill="x", pady=10)
        
        ttk.Label(lf_adv, text="Button Resistor:").grid(row=0, column=0, sticky="w")
        ttk.Combobox(lf_adv, textvariable=self.var_pull, values=["Pull Up", "Pull Down"], state="readonly", width=10).grid(row=0, column=1, padx=5)

        ttk.Label(lf_adv, text="Debounce (s):").grid(row=1, column=0, sticky="w")
        ttk.Entry(lf_adv, textvariable=self.var_debounce, width=8).grid(row=1, column=1, padx=5)

        ttk.Label(lf_adv, text="Lamp PWM (Hz):").grid(row=2, column=0, sticky="w")
        ttk.Entry(lf_adv, textvariable=self.var_pwm, width=8).grid(row=2, column=1, padx=5)

        ttk.Label(lf_adv, text="Idle Speed (x):").grid(row=3, column=0, sticky="w")
        ttk.Entry(lf_adv, textvariable=self.var_idle_speed, width=8).grid(row=3, column=1, padx=5)

    def _build_logs_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Logs")
        
        frame = ttk.Frame(tab, padding=10)
        frame.pack(fill="both", expand=True)
        
        # Actions
        f_actions = ttk.Frame(frame)
        f_actions.pack(fill="x", pady=5)
        
        def archive_logs():
            log_dir = self.config.paths.logs_dir
            if not log_dir.exists(): return
            
            archive_dir = log_dir / "archive"
            archive_dir.mkdir(exist_ok=True)
            
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_name = archive_dir / f"logs_{ts}.zip"
            
            try:
                with zipfile.ZipFile(zip_name, 'w') as zf:
                    for f in log_dir.glob("*.*"):
                        if f.is_file() and not f.name.endswith(".zip"):
                            zf.write(f, arcname=f.name)
                            
                # Clear plain logs (optional, or just move them?)
                # User asked to clear.
                for f in log_dir.glob("*.*"):
                    if f.is_file() and not f.name.endswith(".zip"):
                        f.unlink()
                        
                messagebox.showinfo("Archived", f"Logs archived to:\n{zip_name}\n\nCurrent logs cleared.")
                # Refresh view (simple way: just clear text boxes)
                if hasattr(self, 'txt_crash'): self.txt_crash.delete("1.0", "end")
                if hasattr(self, 'tree_csv'): 
                     for r in self.tree_csv.get_children(): self.tree_csv.delete(r)

            except Exception as e:
                messagebox.showerror("Error", f"Archive failed: {e}")

        ttk.Button(f_actions, text="Archive & Clear Logs", command=archive_logs).pack(side="left")

        # Views
        sub = ttk.Notebook(frame)
        sub.pack(fill="both", expand=True, pady=10)

        # Crash
        f_crash = ttk.Frame(sub)
        sub.add(f_crash, text="Crash Log")
        self.txt_crash = tk.Text(f_crash)
        self.txt_crash.pack(fill="both", expand=True)
        
        cp = self.config.project_root / "logs/crash.log"
        if cp.exists():
            self.txt_crash.insert("1.0", cp.read_text(encoding="utf-8", errors="replace"))

        # CSV
        f_csv = ttk.Frame(sub)
        sub.add(f_csv, text="Interactions")
        self.tree_csv = ttk.Treeview(f_csv, columns=("Time", "Outcome", "Type"), show="headings")
        self.tree_csv.heading("Time", text="Time")
        self.tree_csv.heading("Outcome", text="Outcome")
        self.tree_csv.pack(side="left", fill="both", expand=True)
        
        csv_p = self.config.paths.interactions_csv
        if not csv_p.is_absolute(): csv_p = self.config.project_root / csv_p
        
        if csv_p.exists():
            try:
                with csv_p.open("r") as f:
                     reader = csv.reader(f)
                     for r in reader:
                         self.tree_csv.insert("", "end", values=r)
            except: pass

    def _build_launch_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Launch")
        
        f = ttk.Frame(tab, padding=30)
        f.pack(fill="both")
        
        ttk.Label(f, text="Ready to Launch?", font=("Arial", 16)).pack(pady=20)
        ttk.Button(f, text="Launch Fullscreen (Normal)", command=lambda: self.launch([])).pack(fill="x", pady=5)
        ttk.Button(f, text="Launch Windowed", command=lambda: self.launch(["--windowed"])).pack(fill="x", pady=5)
        ttk.Button(f, text="Launch Debug", command=lambda: self.launch(["--debug", "--windowed"])).pack(fill="x", pady=5)

    def save(self):
        # 1. Resolution
        res_str = self.var_resolution.get() # "1920x1080"
        try:
            w, h = map(int, res_str.lower().split('x'))
        except:
            w, h = 1280, 720
            
        ui = UIConfig(
            window_width=w,
            window_height=h,
            fullscreen=self.var_fullscreen.get(),
            fps=self.config.ui.fps,
            debug=self.config.ui.debug
        )
        
        # 2. Theme
        try:
             bg = self._parse_hex(self.var_bg_color.get())
             txt = self._parse_hex(self.var_text_color.get())
             acc = self._parse_hex(self.var_accent_color.get())
        except:
             messagebox.showerror("Error", "Invalid Colors")
             return

        theme = ThemeConfig(
            background=bg, text=txt, accent=acc,
            logo_path=self.var_logo_path.get() or None,
            logo_width=self.var_logo_width.get() or None,
            font_path=self.var_font_path.get() or None
        )
        
        # 3. Text
        text = TextConfig(
            prompts=self.temp_prompts,
            waiting_screen=WaitingScreenText(
                title=self.config.text.waiting_screen.title,
                subtitles=self.temp_waiting
            ),
            thinking_screen=self.config.text.thinking_screen,
            result_screen=self.config.text.result_screen
        )
        
        # 4. Outcomes
        outcomes = []
        for child in self.tree_out.get_children():
            vals = self.tree_out.item(child)["values"]
            outcomes.append(OutcomeConfig(
                text=str(vals[0]),
                weight=int(vals[1]),
                type=str(vals[2])
            ))
            
        # 5. GPIO
        gpio = self.config.gpio # Start with existing
        # But we need to construct new one since frozen
        from .config import GPIOConfig # ensure import
        
        gpio = GPIOConfig(
            enabled=gpio.enabled,
            button_pin=self.var_btn_pin.get(),
            button_pull_up=(self.var_pull.get() == "Pull Up"),
            debounce_seconds=float(self.var_debounce.get()),
            lamp_enabled=gpio.lamp_enabled,
            lamp_pin=self.var_lamp_pin.get(),
            lamp_active_high=gpio.lamp_active_high,
            lamp_pwm_hz=int(float(self.var_pwm.get())),
            lamp_idle_speed=float(self.var_idle_speed.get())
        )
        
        behavior = BehaviorConfig(
            animation_seconds=self.var_anim_sec.get(),
            idle_return_seconds=self.config.behavior.idle_return_seconds,
            result_fade_seconds=self.config.behavior.result_fade_seconds,
            result_fadeout_seconds=self.config.behavior.result_fadeout_seconds,
            prompt_fade_seconds=self.config.behavior.prompt_fade_seconds,
            thinking_fade_seconds=self.config.behavior.thinking_fade_seconds,
            square_settle_seconds=self.var_settle_sec.get(),
            fades_enabled=self.config.behavior.fades_enabled
        )

        app_cfg = AppConfig(
            project_root=self.config.project_root,
            name=self.var_name.get(),
            ui=ui,
            theme=theme,
            gpio=gpio,
            behavior=behavior,
            paths=self.config.paths,
            text=text,
            outcomes=outcomes
        )

        try:
            save_config(app_cfg)
            messagebox.showinfo("Success", "Settings Saved!")
            # Do NOT destroy root
        except Exception as e:
            messagebox.showerror("Error", str(e))


def main():
    root = tk.Tk()
    # Apply theme if available?)
    try:
        # Just standard
        style = ttk.Style()
        style.theme_use('clam')
    except: pass
    
    app = ConfigEditor(root)
    root.mainloop()

if __name__ == "__main__":
    main()
