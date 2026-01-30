import time
import sys
import subprocess
import tkinter as tk
import csv
from pathlib import Path
from tkinter import ttk, colorchooser, messagebox
from .config import (
    CONFIG, save_config, AppConfig, ThemeConfig, UIConfig, BehaviorConfig, 
    TextConfig, OutcomeConfig, WaitingScreenText, ThinkingScreenText, ResultScreenText
)
from .gpio_button import ArcadeButton
from .lamp import ButtonLamp, LampConfig, LampMode

class ConfigEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Magic 8-Ball Configuration")
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
        self._build_hardware_tab()
        self._build_logs_tab()
        self._build_launch_tab()

        # Initialize Hardware
        self.lamp = ButtonLamp(
            LampConfig(
                enabled=self.config.gpio.enabled and self.config.gpio.lamp_enabled,
                pin=self.config.gpio.lamp_pin,
                active_high=self.config.gpio.lamp_active_high,
                pwm_hz=self.config.gpio.lamp_pwm_hz
            )
        )
        self.button = ArcadeButton(self.config.gpio.button_pin, self.config.gpio.debounce_seconds)

        # Footer
        frame_footer = ttk.Frame(root)
        frame_footer.pack(fill="x", padx=10, pady=10)
        
        btn_save = ttk.Button(frame_footer, text="Save Settings", command=self.save)
        btn_save.pack(side="right")
        
        btn_launch = ttk.Button(frame_footer, text="Launch", command=lambda: self.launch([]))
        btn_launch.pack(side="right", padx=10)

        btn_close = ttk.Button(frame_footer, text="Close", command=root.destroy)
        btn_close.pack(side="right")

        # Start hardware loop
        self._update_hardware_loop()

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
            # Poll button for debug visibility
            # Since poll_pressed eats the event, we just check if it triggered
            is_pressed = False
            if self.button.poll_pressed():
                is_pressed = True
            
            # Update UI indicator if the tab is visible (optimization)
            # But for simplicity, just update if widget exists
            if hasattr(self, 'lbl_btn_status'):
                if is_pressed:
                     self.lbl_btn_status.config(text="PRESSED", foreground="green")
                     # Reset after a short delay so user sees the flash
                     self.root.after(200, lambda: self.lbl_btn_status.config(text="RELEASED", foreground="gray"))
        
        self.root.after(50, self._update_hardware_loop)

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
        
        
        def pick_color(var, preview_canvas):
            color = colorchooser.askcolor(color=var.get())[1]
            if color:
                var.set(color)
                preview_canvas.config(bg=color)

        def make_row(row, label, var):
             ttk.Label(form_frame, text=label).grid(row=row, column=0, sticky="w", pady=5)
             ttk.Entry(form_frame, textvariable=var, width=10).grid(row=row, column=1, sticky="w", pady=5)
             
             # Preview square
             preview = tk.Canvas(form_frame, width=20, height=20, bg=var.get(), highlightthickness=1, highlightbackground="gray")
             preview.grid(row=row, column=2, padx=5)
             
             # Update preview if text entry changes
             def update_preview(*args):
                 try: 
                      # Basic hex len check or rely on canvas ignoring bad colors
                      if len(var.get()) in (4, 7, 13): # #123, #123456...
                          preview.config(bg=var.get())
                 except: pass
             var.trace_add("write", update_preview)

             ttk.Button(form_frame, text="Pick", command=lambda: pick_color(var, preview)).grid(row=row, column=3, padx=5)

        make_row(0, "Background Color:", self.var_bg_color)
        make_row(1, "Text Color:", self.var_text_color)
        make_row(2, "Accent Color:", self.var_accent_color)

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
        
        columns = ("text", "weight", "type")
        self.tree = ttk.Treeview(frame_list, columns=columns, show="headings")
        self.tree.heading("text", text="Outcome Text")
        self.tree.heading("weight", text="Weight")
        self.tree.heading("type", text="Type")
        
        self.tree.column("text", width=300)
        self.tree.column("weight", width=50)
        self.tree.column("type", width=100)
        
        scroll = ttk.Scrollbar(frame_list, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        
        # Populate
        for outcome in self.config.outcomes:
            self.tree.insert("", "end", values=(outcome.text, outcome.weight, outcome.type))
            
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

        ttk.Label(frame_controls, text="Type:").pack(anchor="w")
        self.var_outcome_type = tk.StringVar(value="Inconclusive")
        self.cb_outcome_type = ttk.Combobox(frame_controls, textvariable=self.var_outcome_type, values=["Yes", "No", "Inconclusive"], state="readonly")
        self.cb_outcome_type.pack(anchor="w", pady=5)
        
        def add_item():
            txt = self.entry_outcome_text.get().strip()
            w = self.entry_outcome_weight.get().strip()
            typ = self.var_outcome_type.get()
            if txt:
                self.tree.insert("", "end", values=(txt, w, typ))
                self.entry_outcome_text.delete(0, "end")
                
        def delete_item():
            selected = self.tree.selection()
            for s in selected:
                self.tree.delete(s)
                
        ttk.Button(frame_controls, text="Add Outcome", command=add_item).pack(fill="x", pady=5)
        ttk.Button(frame_controls, text="Remove Selected", command=delete_item).pack(fill="x", pady=5)
        
    def _build_hardware_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Hardware Test")
        
        frame = ttk.Frame(tab, padding="20")
        frame.pack(fill="both", expand=True)

        # 1. Lamp Control
        lf_lamp = ttk.LabelFrame(frame, text="Lamp Control", padding=10)
        lf_lamp.pack(fill="x", pady=10)
        
        ttk.Label(lf_lamp, text="Test the LED output (GPIO " + str(self.config.gpio.lamp_pin) + "):").pack(anchor="w", pady=(0, 10))
        
        f_buttons = ttk.Frame(lf_lamp)
        f_buttons.pack(fill="x")
        
        def set_lamp(mode):
            if hasattr(self, 'lamp'):
                self.lamp.set_mode(mode)

        ttk.Button(f_buttons, text="OFF", command=lambda: set_lamp(LampMode.OFF)).pack(side="left", padx=5)
        ttk.Button(f_buttons, text="IDLE (Breathe)", command=lambda: set_lamp(LampMode.IDLE)).pack(side="left", padx=5)
        ttk.Button(f_buttons, text="THINKING (Pulse)", command=lambda: set_lamp(LampMode.THINKING)).pack(side="left", padx=5)
        ttk.Button(f_buttons, text="RESULT (On)", command=lambda: set_lamp(LampMode.RESULT)).pack(side="left", padx=5)

        # 2. Button Input
        lf_btn = ttk.LabelFrame(frame, text="Button Input", padding=10)
        lf_btn.pack(fill="x", pady=10)
        
        ttk.Label(lf_btn, text="Press the physical Arcade Button (GPIO " + str(self.config.gpio.button_pin) + ").").pack(anchor="w")
        
        f_status = ttk.Frame(lf_btn, padding=10)
        f_status.pack(fill="x")
        
        ttk.Label(f_status, text="Status: ").pack(side="left")
        self.lbl_btn_status = ttk.Label(f_status, text="RELEASED", font=("Arial", 14, "bold"), foreground="gray")
        self.lbl_btn_status.pack(side="left", padx=10)

        # 3. Advanced GPIO Settings
        lf_adv = ttk.LabelFrame(frame, text="Advanced GPIO", padding=10)
        lf_adv.pack(fill="x", pady=10)

        # Button Pull Up/Down
        f_pull = ttk.Frame(lf_adv)
        f_pull.pack(fill="x", pady=5)
        ttk.Label(f_pull, text="Button Resistor:").pack(side="left")
        self.var_pull = tk.StringVar(value="Pull Up" if self.config.gpio.button_pull_up else "Pull Down")
        cb_pull = ttk.Combobox(f_pull, textvariable=self.var_pull, values=["Pull Up", "Pull Down"], state="readonly", width=12)
        cb_pull.pack(side="left", padx=10)
        
        def revert_pull():
            val = "Pull Up" if self.config.gpio.button_pull_up else "Pull Down"
            self.var_pull.set(val)
            # setting var triggers the bind if we use <<VirtualEvent>>? 
            # ComboboxSelected only fires on user interaction usually. 
            # We should manually call update if we set programmatically, OR just let update_hardware_params handle it if we call it.
            update_hardware_params()

        ttk.Button(f_pull, text="Revert", command=revert_pull, width=6).pack(side="left", padx=5)
        ttk.Label(f_pull, text="(Try switching if button triggers randomly)").pack(side="left", padx=5)

        # Debounce
        f_deb = ttk.Frame(lf_adv)
        f_deb.pack(fill="x", pady=5)
        ttk.Label(f_deb, text="Debounce (sec):").pack(side="left")
        self.var_debounce = tk.StringVar(value=str(self.config.gpio.debounce_seconds))
        ttk.Entry(f_deb, textvariable=self.var_debounce, width=8).pack(side="left", padx=10)
        
        def revert_debounce():
            self.var_debounce.set(str(self.config.gpio.debounce_seconds))
            # trace will trigger update

        ttk.Button(f_deb, text="Revert", command=revert_debounce, width=6).pack(side="left", padx=5)
        ttk.Label(f_deb, text="(Increase to 0.3+ if noisy)").pack(side="left", padx=5)

        # Lamp PWM
        f_pwm = ttk.Frame(lf_adv)
        f_pwm.pack(fill="x", pady=5)
        ttk.Label(f_pwm, text="Lamp PWM (Hz):").pack(side="left")
        self.var_pwm = tk.StringVar(value=str(self.config.gpio.lamp_pwm_hz))
        ttk.Entry(f_pwm, textvariable=self.var_pwm, width=8).pack(side="left", padx=10)
        ttk.Label(f_pwm, text="(Adjust if lamp flickers)").pack(side="left", padx=5)

        # Update button when settings change (so they can test immediately)
        def update_hardware_params(event=None):
            try:
                # Re-init button with new settings
                is_pull_up = (self.var_pull.get() == "Pull Up")
                new_db = float(self.var_debounce.get())
                
                # Check if changed to avoid unnecessary re-init if only PWM changed
                # Actually simpler to just re-init safely.
                if hasattr(self, 'button'):
                    # Safe cleanup
                    self.button.close()
                    
                    # Re-create
                    self.button = ArcadeButton(
                        self.config.gpio.button_pin, 
                        debounce_seconds=new_db,
                        pull_up=is_pull_up
                    )
                
                # Update Lamp PWM instantly
                new_pwm = int(self.var_pwm.get())
                if hasattr(self, 'lamp') and self.lamp._led is not None:
                     self.lamp._led.frequency = new_pwm

            except ValueError:
                pass
        
        cb_pull.bind("<<ComboboxSelected>>", update_hardware_params)
        cb_pull.bind("<<ComboboxSelected>>", update_hardware_params, add="+")
        
        # Bind Debounce and PWM to update on write
        self.var_debounce.trace_add("write", lambda *args: update_hardware_params())
        self.var_pwm.trace_add("write", lambda *args: update_hardware_params())

    def _build_logs_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Logs")

        # Two sub-tabs for Crash Log and Interaction Log
        sub_nb = ttk.Notebook(tab)
        sub_nb.pack(fill="both", expand=True, padx=5, pady=5)

        # Crash Log
        f_crash = ttk.Frame(sub_nb)
        sub_nb.add(f_crash, text="Crash Log")
        txt_crash = tk.Text(f_crash, wrap="word")
        txt_crash.pack(fill="both", expand=True)
        
        # Load crash log content
        crash_path = self.config.project_root / "logs/crash.log"
        if crash_path.exists():
            try:
                txt_crash.insert("1.0", crash_path.read_text(encoding="utf-8"))
            except Exception as e:
                txt_crash.insert("1.0", f"Error reading log: {e}")
        else:
            txt_crash.insert("1.0", "(No crash log found)")

        # Interactions Log (CSV)
        f_csv = ttk.Frame(sub_nb)
        sub_nb.add(f_csv, text="Interactions Log")
        
        # Treeview for CSV
        columns = ("Timestamp", "Outcome", "Type")
        tree_csv = ttk.Treeview(f_csv, columns=columns, show="headings")
        tree_csv.heading("Timestamp", text="Timestamp")
        tree_csv.heading("Outcome", text="Outcome")
        tree_csv.heading("Type", text="Type") # Though current CSV might not have type, we can infer or just show raw cols
        
        tree_csv.column("Timestamp", width=150)
        tree_csv.column("Outcome", width=300)
        tree_csv.column("Type", width=100)
        
        scroll_csv = ttk.Scrollbar(f_csv, orient="vertical", command=tree_csv.yview)
        tree_csv.configure(yscrollcommand=scroll_csv.set)
        
        tree_csv.pack(side="left", fill="both", expand=True)
        scroll_csv.pack(side="right", fill="y")
        
        # Load CSV
        csv_path = self.config.paths.interactions_csv
        # resolve if relative
        if not csv_path.is_absolute():
             csv_path = self.config.project_root / csv_path
        
        if csv_path.exists():
            try:
                with csv_path.open("r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    # Skip header if heuristic suggests
                    # Or just show everything.
                    # Standard format: timestamp, outcome
                    for row in reader:
                        # Ensure row fits columns
                        # Start simple
                        row_vals = row + [""] * (3 - len(row))
                        tree_csv.insert("", "end", values=row_vals[:3])
            except Exception as e:
                pass # Fail silently or show error in tree? 

    def _build_launch_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Launch")
        
        frame = ttk.Frame(tab, padding="20")
        frame.pack(fill="both", expand=True)
        
        ttk.Label(frame, text="Test the Application", font=("Arial", 16, "bold")).pack(pady=(0, 20))
        ttk.Label(frame, text="Launch the Magic 8-Ball in different modes to test your configuration.").pack(pady=(0, 20))

        # Buttons
        f_btns = ttk.Frame(frame)
        f_btns.pack(fill="x", pady=5)

        ttk.Button(f_btns, text="Normal Launch", command=lambda: self.launch([])).pack(fill="x", pady=5)
        ttk.Button(f_btns, text="Debug Mode (Overlays + Logs)", command=lambda: self.launch(["--debug"])).pack(fill="x", pady=5)
        ttk.Button(f_btns, text="Windowed Mode", command=lambda: self.launch(["--windowed"])).pack(fill="x", pady=5)
        ttk.Button(f_btns, text="No GPIO (Keyboard Only)", command=lambda: self.launch(["--no-gpio", "--debug"])).pack(fill="x", pady=5)



    def save(self):
        # 1. Reconstruct config objects
        try:
            # Parse Advanced GPIO
            pull_up = (self.var_pull.get() == "Pull Up")
            debounce = float(self.var_debounce.get())
            pwm = int(self.var_pwm.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid numeric value in GPIO settings.")
            return
        
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
            # Retrieve type if exists (it should now)
            typ = "Inconclusive"
            if len(vals) > 2:
                typ = str(vals[2])
            
            outcomes.append(OutcomeConfig(text=t, weight=w, type=typ))
            
        # Rebuild AppConfig (using defaults for parts we didn't edit)
        from .config import GPIOConfig

        new_gpio = GPIOConfig(
            enabled=self.config.gpio.enabled,
            button_pin=self.config.gpio.button_pin,
            button_pull_up=pull_up,
            debounce_seconds=debounce,
            lamp_enabled=self.config.gpio.lamp_enabled,
            lamp_pin=self.config.gpio.lamp_pin,
            lamp_active_high=self.config.gpio.lamp_active_high,
            lamp_pwm_hz=pwm
        )

        new_config = AppConfig(
            project_root=self.config.project_root,
            name=new_name,
            ui=ui,
            theme=theme,
            gpio=new_gpio,
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
