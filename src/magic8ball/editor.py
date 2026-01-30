import tkinter as tk
from tkinter import ttk, colorchooser, messagebox
from .config import CONFIG, save_config, AppConfig, ThemeConfig, UIConfig, BehaviorConfig, TextConfig, OutcomeConfig

class ConfigEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Magic 7-Ball Configuration")
        self.root.geometry("800x600")

        self.config = CONFIG  # This is the loaded config object. We will mutate a copy or just read from it and build a new one on save.
        
        # We need to store mutable state for the form widgets
        self.var_name = tk.StringVar(value=self.config.name)
        self.var_fullscreen = tk.BooleanVar(value=self.config.ui.fullscreen)
        self.var_bg_color = tk.StringVar(value=self._fmt_col(self.config.theme.background))
        self.var_text_color = tk.StringVar(value=self._fmt_col(self.config.theme.text))
        self.var_accent_color = tk.StringVar(value=self._fmt_col(self.config.theme.accent))
        
        self.var_anim_sec = tk.DoubleVar(value=self.config.behavior.animation_seconds)
        self.var_settle_sec = tk.DoubleVar(value=self.config.behavior.square_settle_seconds)
        
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)
        
        self._build_general_tab()
        self._build_theme_tab()
        self._build_text_tab()
        self._build_outcomes_tab()

        # Footer
        frame_footer = ttk.Frame(root)
        frame_footer.pack(fill="x", padx=10, pady=10)
        
        btn_save = ttk.Button(frame_footer, text="Save Settings", command=self.save)
        btn_save.pack(side="right")
        
        btn_cancel = ttk.Button(frame_footer, text="Cancel", command=root.destroy)
        btn_cancel.pack(side="right", padx=10)

    def _fmt_col(self, c):
        if isinstance(c, (tuple, list)):
            return f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"
        return str(c)
        
    def _parse_hex(self, hex_str):
        hex_str = hex_str.lstrip('#')
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

    def _build_general_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="General")
        
        form_frame = ttk.Frame(tab, padding="20")
        form_frame.pack(fill="both", expand=True)
        
        ttk.Label(form_frame, text="Device Name:").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(form_frame, textvariable=self.var_name, width=30).grid(row=0, column=1, sticky="w", pady=5)
        
        ttk.Label(form_frame, text="Fullscreen Mode:").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Checkbutton(form_frame, variable=self.var_fullscreen).grid(row=1, column=1, sticky="w", pady=5)
        
        ttk.Label(form_frame, text="Animation Duration (s):").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(form_frame, textvariable=self.var_anim_sec, width=10).grid(row=2, column=1, sticky="w", pady=5)

        ttk.Label(form_frame, text="Settle Duration (s):").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Entry(form_frame, textvariable=self.var_settle_sec, width=10).grid(row=3, column=1, sticky="w", pady=5)

    def _build_theme_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Theme")
        
        form_frame = ttk.Frame(tab, padding="20")
        form_frame.pack(fill="both", expand=True)
        
        def pick_color(var):
            color = colorchooser.askcolor(color=var.get())[1]
            if color:
                var.set(color)

        # Background
        ttk.Label(form_frame, text="Background Color:").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(form_frame, textvariable=self.var_bg_color, width=10).grid(row=0, column=1, sticky="w", pady=5)
        ttk.Button(form_frame, text="Pick", command=lambda: pick_color(self.var_bg_color)).grid(row=0, column=2, padx=5)
        
        # Text
        ttk.Label(form_frame, text="Text Color:").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(form_frame, textvariable=self.var_text_color, width=10).grid(row=1, column=1, sticky="w", pady=5)
        ttk.Button(form_frame, text="Pick", command=lambda: pick_color(self.var_text_color)).grid(row=1, column=2, padx=5)
        
        # Accent
        ttk.Label(form_frame, text="Accent Color:").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(form_frame, textvariable=self.var_accent_color, width=10).grid(row=2, column=1, sticky="w", pady=5)
        ttk.Button(form_frame, text="Pick", command=lambda: pick_color(self.var_accent_color)).grid(row=2, column=2, padx=5)

    def _build_text_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Text & Prompts")
        
        form_frame = ttk.Frame(tab, padding="20")
        form_frame.pack(fill="both", expand=True)

        ttk.Label(form_frame, text="Prompts (one per line):").pack(anchor="w")
        self.txt_prompts = tk.Text(form_frame, height=10)
        self.txt_prompts.pack(fill="x", pady=5)
        self.txt_prompts.insert("1.0", "\n".join(self.config.text.prompts))
        
        ttk.Label(form_frame, text="Waiting Subtitles (one per line):").pack(anchor="w", pady=10)
        self.txt_waiting = tk.Text(form_frame, height=10)
        self.txt_waiting.pack(fill="x", pady=5)
        self.txt_waiting.insert("1.0", "\n".join(self.config.text.waiting_screen.subtitles))

    def _build_outcomes_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Outcomes")
        
        # Split into list and edit area
        paned = ttk.PanedWindow(tab, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=10, pady=10)
        
        frame_list = ttk.Frame(paned)
        paned.add(frame_list, weight=1)
        
        columns = ("text", "weight")
        self.tree = ttk.Treeview(frame_list, columns=columns, show="headings")
        self.tree.heading("text", text="Outcome Text")
        self.tree.heading("weight", text="Weight")
        self.tree.column("text", width=300)
        self.tree.column("weight", width=50)
        
        scroll = ttk.Scrollbar(frame_list, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        
        # Populate
        for outcome in self.config.outcomes:
            self.tree.insert("", "end", values=(outcome.text, outcome.weight))
            
        # Controls
        frame_controls = ttk.Frame(paned, padding=10)
        paned.add(frame_controls, weight=0)
        
        ttk.Label(frame_controls, text="Text:").pack(anchor="w")
        self.entry_outcome_text = ttk.Entry(frame_controls, width=40)
        self.entry_outcome_text.pack(anchor="w", pady=5)
        
        ttk.Label(frame_controls, text="Weight:").pack(anchor="w")
        self.entry_outcome_weight = ttk.Entry(frame_controls, width=10)
        self.entry_outcome_weight.insert(0, "1")
        self.entry_outcome_weight.pack(anchor="w", pady=5)
        
        def add_item():
            txt = self.entry_outcome_text.get().strip()
            w = self.entry_outcome_weight.get().strip()
            if txt:
                self.tree.insert("", "end", values=(txt, w))
                self.entry_outcome_text.delete(0, "end")
                
        def delete_item():
            selected = self.tree.selection()
            for s in selected:
                self.tree.delete(s)
                
        ttk.Button(frame_controls, text="Add Outcome", command=add_item).pack(fill="x", pady=5)
        ttk.Button(frame_controls, text="Remove Selected", command=delete_item).pack(fill="x", pady=5)

    def save(self):
        # 1. Reconstruct config objects
        
        # General
        new_name = self.var_name.get()
        # Theme
        try:
            bg = self._parse_hex(self.var_bg_color.get())
            txt = self._parse_hex(self.var_text_color.get())
            accent = self._parse_hex(self.var_accent_color.get())
        except Exception:
            messagebox.showerror("Error", "Invalid color hex code.")
            return

        theme = ThemeConfig(background=bg, text=txt, accent=accent)
        
        # UI
        # We reuse existing width/height/debug/fps unless we added fields (we didn't for brevity)
        ui = UIConfig(
            window_width=self.config.ui.window_width,
            window_height=self.config.ui.window_height,
            fullscreen=self.var_fullscreen.get(),
            fps=self.config.ui.fps,
            debug=self.config.ui.debug
        )
        
        # Behavior
        behavior = BehaviorConfig(
            animation_seconds=self.var_anim_sec.get(),
            idle_return_seconds=self.config.behavior.idle_return_seconds, # kept existing
            result_fade_seconds=self.config.behavior.result_fade_seconds,
            result_fadeout_seconds=self.config.behavior.result_fadeout_seconds,
            prompt_fade_seconds=self.config.behavior.prompt_fade_seconds,
            thinking_fade_seconds=self.config.behavior.thinking_fade_seconds,
            square_settle_seconds=self.var_settle_sec.get(),
            fades_enabled=self.config.behavior.fades_enabled
        )
        
        # Text
        prompts = [x for x in self.txt_prompts.get("1.0", "end").split("\n") if x.strip()]
        waiting_subs = [x for x in self.txt_waiting.get("1.0", "end").split("\n") if x.strip()]
        
        text = TextConfig(
            prompts=prompts,
            waiting_screen=WaitingScreenText(title=self.config.text.waiting_screen.title, subtitles=waiting_subs),
            thinking_screen=self.config.text.thinking_screen,
            result_screen=self.config.text.result_screen
        )
        
        # Outcomes
        outcomes = []
        for child in self.tree.get_children():
            vals = self.tree.item(child)["values"]
            t = str(vals[0])
            try:
                w = int(vals[1])
            except:
                w = 1
            outcomes.append(OutcomeConfig(text=t, weight=w))
            
        # Rebuild AppConfig (using defaults for parts we didn't edit)
        new_config = AppConfig(
            project_root=self.config.project_root,
            name=new_name,
            ui=ui,
            theme=theme,
            gpio=self.config.gpio, # Passthrough
            behavior=behavior,
            paths=self.config.paths, # Passthrough
            text=text,
            outcomes=outcomes
        )
        
        try:
            save_config(new_config)
            messagebox.showinfo("Success", "Configuration saved successfully!")
            self.root.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config: {e}")

def main():
    root = tk.Tk()
    app = ConfigEditor(root)
    root.mainloop()

if __name__ == "__main__":
    main()
