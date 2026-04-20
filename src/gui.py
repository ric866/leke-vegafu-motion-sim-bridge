import tkinter as tk
from tkinter import ttk, scrolledtext
import socket
import subprocess
import sys
import os
import json


def get_local_interfaces():
    interfaces = ["127.0.0.1", "0.0.0.0"]  # nosec B104
    try:
        hostname = socket.gethostname()
        _, _, ips = socket.gethostbyname_ex(hostname)
        for ip in ips:
            if ip not in interfaces:
                interfaces.append(ip)
    except Exception:
        pass
    return interfaces


class VegaGUI:
    def __init__(self, root, gui_queue, cmd_queue):
        self.root = root
        self.gui_queue = gui_queue
        self.cmd_queue = cmd_queue

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.root.title("Vega Mission Control (Modular & Verbose)")
        self.root.geometry("850x850")

        # --- State Variables ---
        self.manual_mode = tk.BooleanVar(value=False)
        self.debug_mode = tk.BooleanVar(value=False)
        self.vis_process = None
        self._last_vis_state = False

        self.slider_m1 = tk.IntVar(value=120000)
        self.slider_m2 = tk.IntVar(value=120000)
        self.slider_m3 = tk.IntVar(value=120000)

        self.feedback_m1 = tk.StringVar(value="---")
        self.feedback_m2 = tk.StringVar(value="---")
        self.feedback_m3 = tk.StringVar(value="---")

        # --- Load Configuration ---
        self.config_file = "vega_config.json"
        cfg = self._load_config()

        self.conf_bind_ip = tk.StringVar(value=cfg["bind_ip"])
        self.conf_rx_port = tk.StringVar(value=str(cfg["rx_port"]))
        self.conf_tx_port = tk.StringVar(value=str(cfg["tx_port"]))
        self.conf_vega_ip = tk.StringVar(value=cfg["vega_ip"])
        self.conf_vega_port = tk.StringVar(value=str(cfg["vega_port"]))
        self.conf_safe_pos = tk.StringVar(value=str(cfg["safe_pos"]))

        self.conf_hz = tk.StringVar(value=str(cfg["hz"]))
        self.conf_max_delta_auto = tk.StringVar(value=str(cfg["max_delta_auto"]))
        self.conf_max_delta_manual = tk.StringVar(value=str(cfg["max_delta_manual"]))

        self.pa_params = {
            0x00: "Working Mode (0: 485, 10: CAN)",
            0x02: "Number of Motors",
            0x07: "Max Speed Limit",
            0x09: "Fixed Time Interval (ms)",
            0x40: "Rising Distance (0.1mm)",
            0x41: "Pitch of Electric Cylinder (0.1mm)",
            0x42: "Maximum Stroke (0.1mm)",
            0x50: "Position Command Filter Time (ms)",
            0x51: "Exponential Filtering Depth (0-7)",
            0x94: "Safety Speed Limit",
        }

        self.param_vars = {addr: tk.StringVar(value="") for addr in self.pa_params}

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_tab_motion()
        self._build_tab_flash()
        self._build_tab_debug()

        self.root.after(50, self.process_queue)
        self.log("[GUI] Interface Initialized Successfully.")

    def _load_config(self):
        """Loads configuration from JSON or returns defaults if none exists."""
        defaults = {
            "bind_ip": "127.0.0.1",
            "rx_port": 10000,
            "tx_port": 8410,
            "vega_ip": "192.168.15.201",
            "vega_port": 7408,
            "safe_pos": 120000,
            "hz": 20,
            "max_delta_auto": 8000,
            "max_delta_manual": 2000,
        }
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    return {**defaults, **json.load(f)}
            except Exception as e:
                print(f"[WARNING] Could not load config file, using defaults: {e}")
        return defaults

    def on_closing(self):
        if self.vis_process and self.vis_process.poll() is None:
            self.log("[SYSTEM] Shutting down orphaned visualizer process...")
            self.vis_process.terminate()
        self.root.destroy()

    def _build_tab_motion(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="1. Motion & Control")

        # --- Network & Tuning Config ---
        frame_config = ttk.LabelFrame(
            tab, text="Network & Tuning Configuration", padding=10
        )
        frame_config.pack(fill="x", padx=10, pady=5)

        ttk.Label(frame_config, text="Local Bind IP:").grid(
            row=0, column=0, sticky="e", padx=5, pady=2
        )
        cb_interfaces = ttk.Combobox(
            frame_config,
            textvariable=self.conf_bind_ip,
            values=get_local_interfaces(),
            width=15,
        )
        cb_interfaces.grid(row=0, column=1, sticky="w")
        ttk.Label(frame_config, text="FlyPT Port (In):").grid(
            row=0, column=2, sticky="e", padx=5, pady=2
        )
        ttk.Entry(frame_config, textvariable=self.conf_rx_port, width=10).grid(
            row=0, column=3, sticky="w"
        )

        ttk.Label(frame_config, text="Vega IP:").grid(
            row=1, column=0, sticky="e", padx=5, pady=2
        )
        ttk.Entry(frame_config, textvariable=self.conf_vega_ip, width=15).grid(
            row=1, column=1, sticky="w"
        )
        ttk.Label(frame_config, text="Vega Port:").grid(
            row=1, column=2, sticky="e", padx=5, pady=2
        )
        ttk.Entry(frame_config, textvariable=self.conf_vega_port, width=10).grid(
            row=1, column=3, sticky="w"
        )

        ttk.Label(frame_config, text="Reply Port (Out):").grid(
            row=2, column=0, sticky="e", padx=5, pady=2
        )
        ttk.Entry(frame_config, textvariable=self.conf_tx_port, width=10).grid(
            row=2, column=1, sticky="w"
        )
        ttk.Label(frame_config, text="Safe Position:").grid(
            row=2, column=2, sticky="e", padx=5, pady=2
        )
        ttk.Entry(frame_config, textvariable=self.conf_safe_pos, width=10).grid(
            row=2, column=3, sticky="w"
        )

        ttk.Label(frame_config, text="Loop Rate (Hz):").grid(
            row=3, column=0, sticky="e", padx=5, pady=2
        )
        ttk.Entry(frame_config, textvariable=self.conf_hz, width=10).grid(
            row=3, column=1, sticky="w"
        )

        ttk.Label(frame_config, text="Auto Max Delta:").grid(
            row=4, column=0, sticky="e", padx=5, pady=2
        )
        ttk.Entry(frame_config, textvariable=self.conf_max_delta_auto, width=10).grid(
            row=4, column=1, sticky="w"
        )
        ttk.Label(frame_config, text="Manual/Park Delta:").grid(
            row=4, column=2, sticky="e", padx=5, pady=2
        )
        ttk.Entry(frame_config, textvariable=self.conf_max_delta_manual, width=10).grid(
            row=4, column=3, sticky="w"
        )

        ttk.Button(
            frame_config, text="APPLY & SAVE SETTINGS", command=self.push_config
        ).grid(row=5, column=0, columnspan=4, pady=10)

        # --- System Controls ---
        frame_sys = ttk.LabelFrame(tab, text="System Control", padding=10)
        frame_sys.pack(fill="x", padx=10, pady=5)

        self.lbl_status = tk.Label(
            frame_sys,
            text="STOPPED",
            bg="#ff4444",
            fg="white",
            font=("Arial", 14, "bold"),
            width=12,
        )
        self.lbl_status.pack(side="left", padx=10)

        self.btn_start = tk.Button(
            frame_sys,
            text="START RIG",
            bg="#44cc44",
            fg="white",
            font=("Arial", 12, "bold"),
            command=self.req_start,
        )
        self.btn_start.pack(side="left", fill="x", expand=True, padx=5)

        self.btn_stop = tk.Button(
            frame_sys,
            text="STOP & PARK",
            bg="#ff4444",
            fg="white",
            font=("Arial", 12, "bold"),
            command=self.req_stop,
        )
        self.btn_stop.pack(side="left", fill="x", expand=True, padx=5)

        # --- Manual Controls ---
        frame_controls = ttk.LabelFrame(tab, text="Manual Override", padding=10)
        frame_controls.pack(fill="x", padx=10, pady=5)
        ttk.Checkbutton(
            frame_controls,
            text="Enable Manual Mode",
            variable=self.manual_mode,
            command=self.push_state,
        ).pack(anchor="w")

        self._create_axis_slider(
            frame_controls, "Axis 1", self.slider_m1, self.feedback_m1
        )
        self._create_axis_slider(
            frame_controls, "Axis 2", self.slider_m2, self.feedback_m2
        )
        self._create_axis_slider(
            frame_controls, "Axis 3", self.slider_m3, self.feedback_m3
        )

        # --- Visualizer Launcher ---
        frame_vis = ttk.LabelFrame(tab, text="Live 3D Motion", padding=10)
        frame_vis.pack(fill="x", padx=10, pady=5)
        ttk.Label(
            frame_vis,
            text="Launch the external 3D visualizer to monitor outgoing motion packets.",
        ).pack(pady=5)
        ttk.Button(
            frame_vis, text="Start 3D Visualizer", command=self.launch_visualizer
        ).pack(pady=5)

    def _create_axis_slider(self, parent, label, target_var, actual_var):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=2)

        ttk.Label(frame, text=label, width=8, font=("Arial", 10, "bold")).pack(
            side="left"
        )

        ttk.Label(frame, textvariable=target_var, width=8, foreground="blue").pack(
            side="right"
        )
        ttk.Label(frame, text="Tgt:", font=("Arial", 8)).pack(side="right")
        ttk.Label(frame, textvariable=actual_var, width=8, foreground="green").pack(
            side="right", padx=10
        )
        ttk.Label(frame, text="Act:", font=("Arial", 8)).pack(side="right")

        ttk.Scale(
            frame,
            from_=0,
            to=240000,
            variable=target_var,
            orient="horizontal",
            command=lambda v: self.push_manual(),
        ).pack(side="left", fill="x", expand=True, padx=10)

    def _build_tab_flash(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="2. Controller Flash")

        frame_top = ttk.Frame(tab)
        frame_top.pack(fill="x", padx=10, pady=5)
        ttk.Button(frame_top, text="READ ALL", command=self.req_read_all).pack(
            side="left", padx=5
        )
        ttk.Label(
            frame_top,
            text="Values update dynamically when controller replies.",
            foreground="gray",
        ).pack(side="left", padx=10)

        frame_container = ttk.LabelFrame(tab, text="PA Parameters", padding=5)
        frame_container.pack(fill="both", expand=True, padx=10, pady=5)

        canvas = tk.Canvas(frame_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            frame_container, orient="vertical", command=canvas.yview
        )
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Label(self.scrollable_frame, text="Hex", font=("Arial", 9, "bold")).grid(
            row=0, column=0, padx=5, pady=5, sticky="w"
        )
        ttk.Label(
            self.scrollable_frame, text="Description", font=("Arial", 9, "bold")
        ).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(self.scrollable_frame, text="Value", font=("Arial", 9, "bold")).grid(
            row=0, column=2, padx=5, pady=5, sticky="w"
        )

        row_idx = 1
        for addr, desc in self.pa_params.items():
            ttk.Label(
                self.scrollable_frame, text=f"0x{addr:02X}", foreground="blue"
            ).grid(row=row_idx, column=0, padx=5, pady=2, sticky="w")
            ttk.Label(self.scrollable_frame, text=desc).grid(
                row=row_idx, column=1, padx=5, pady=2, sticky="w"
            )
            entry = tk.Entry(
                self.scrollable_frame,
                textvariable=self.param_vars[addr],
                width=12,
                justify="center",
            )
            entry.grid(row=row_idx, column=2, padx=5, pady=2)
            ttk.Button(
                self.scrollable_frame,
                text="Read",
                width=6,
                command=lambda a=addr: self.req_read_param(a),
            ).grid(row=row_idx, column=3, padx=2)
            ttk.Button(
                self.scrollable_frame,
                text="Write",
                width=6,
                command=lambda a=addr: self.req_write_param(a),
            ).grid(row=row_idx, column=4, padx=2)
            row_idx += 1

    def _build_tab_debug(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="3. Debug & Logs")
        ttk.Checkbutton(
            tab,
            text="Verbose Logging",
            variable=self.debug_mode,
            command=self.push_state,
        ).pack(anchor="w", padx=10, pady=5)
        self.txt_log = scrolledtext.ScrolledText(
            tab, font=("Consolas", 9), state="disabled"
        )
        self.txt_log.pack(fill="both", expand=True, padx=10, pady=5)

    def launch_visualizer(self):
        if self.debug_mode.get():
            self.log("[GUI CLICK] Start 3D Visualizer Button")

        if self.vis_process and self.vis_process.poll() is None:
            self.log(
                "[SYSTEM] Visualizer is already running! If window is hidden, close it first."
            )
            return

        try:
            debug_arg = "1" if self.debug_mode.get() else "0"

            # Check if running as a PyInstaller compiled executable
            if getattr(sys, "frozen", False):
                # When frozen, sys.executable points to VegaMissionControl.exe
                # We launch a second instance of ourself, passing the secret flag
                self.vis_process = subprocess.Popen(
                    [sys.executable, "--run-visualizer", "9001", debug_arg]
                )
                self.log(
                    "[SYSTEM] Launched Live 3D Visualizer from inside compiled EXE."
                )
            else:
                # When running normally from source code (e.g., via VS Code)
                script_path = os.path.join(os.path.dirname(__file__), "visualizer.py")
                self.vis_process = subprocess.Popen(
                    [sys.executable, script_path, "9001", debug_arg]
                )
                self.log("[SYSTEM] Launched Live 3D Visualizer from script file.")

            self.push_state()
        except Exception as e:
            self.log(f"[ERROR] Could not launch visualizer: {e}")

    def push_config(self):
        if self.debug_mode.get():
            self.log("[GUI CLICK] Apply Network Settings Button")
        try:
            cfg = {
                "bind_ip": self.conf_bind_ip.get(),
                "rx_port": int(self.conf_rx_port.get()),
                "tx_port": int(self.conf_tx_port.get()),
                "vega_ip": self.conf_vega_ip.get(),
                "vega_port": int(self.conf_vega_port.get()),
                "safe_pos": int(self.conf_safe_pos.get()),
                "hz": max(1, int(self.conf_hz.get())),
                "max_delta_auto": max(1, int(self.conf_max_delta_auto.get())),
                "max_delta_manual": max(1, int(self.conf_max_delta_manual.get())),
            }

            # Save configuration to disk
            try:
                with open(self.config_file, "w") as f:
                    json.dump(cfg, f, indent=4)
                self.log(
                    f"[GUI] Configuration successfully saved to {self.config_file}"
                )
            except Exception as e:
                self.log(f"[ERROR] Failed to write config to disk: {e}")

            # Push configuration to backend
            self.cmd_queue.put({"type": "CONFIG", **cfg})

        except ValueError:
            self.log("[ERROR] Configuration values must be valid integers.")

    def req_start(self):
        if self.debug_mode.get():
            self.log("[GUI CLICK] Start Rig")
        self.cmd_queue.put({"type": "SYS_CMD", "cmd": "START"})

    def req_stop(self):
        if self.debug_mode.get():
            self.log("[GUI CLICK] Stop & Park Rig")
        self.cmd_queue.put({"type": "SYS_CMD", "cmd": "STOP"})

    def push_state(self):
        is_vis_running = (
            self.vis_process is not None and self.vis_process.poll() is None
        )
        self.cmd_queue.put(
            {
                "type": "STATE",
                "manual": self.manual_mode.get(),
                "debug": self.debug_mode.get(),
                "vis_running": is_vis_running,
            }
        )
        if self.manual_mode.get():
            self.push_manual()

    def push_manual(self):
        if self.manual_mode.get():
            self.cmd_queue.put(
                {
                    "type": "MANUAL_POS",
                    "m1": self.slider_m1.get(),
                    "m2": self.slider_m2.get(),
                    "m3": self.slider_m3.get(),
                }
            )

    def req_read_param(self, addr):
        self.cmd_queue.put({"type": "READ_PARAM", "address": addr})

    def req_write_param(self, addr):
        val_str = self.param_vars[addr].get()
        if val_str.isdigit() or (val_str.startswith("-") and val_str[1:].isdigit()):
            self.cmd_queue.put(
                {"type": "WRITE_PARAM", "address": addr, "value": int(val_str)}
            )
        else:
            self.log(f"[ERROR] Invalid value for 0x{addr:02X}. Must be an integer.")

    def req_read_all(self):
        for addr in self.pa_params:
            self.req_read_param(addr)

    def log(self, msg):
        self.txt_log.config(state="normal")
        self.txt_log.insert(tk.END, msg + "\n")
        lines = int(self.txt_log.index("end-1c").split(".")[0])
        if lines > 1000:
            self.txt_log.delete("1.0", f"{lines - 1000}.0")
        self.txt_log.see(tk.END)
        self.txt_log.config(state="disabled")

    def process_queue(self):
        while not self.gui_queue.empty():
            msg = self.gui_queue.get_nowait()
            if msg["type"] == "LOG":
                self.log(msg["data"])
            elif msg["type"] == "STATE_UPDATE":
                state = msg["state"]
                if state == "STOPPED":
                    self.lbl_status.config(text="STOPPED", bg="#ff4444", fg="white")
                elif state == "STARTING":
                    self.lbl_status.config(text="STARTING...", bg="#ffaa00", fg="black")
                elif state == "ACTIVE":
                    self.lbl_status.config(text="ACTIVE", bg="#44cc44", fg="white")
                elif state == "STOPPING":
                    self.lbl_status.config(text="PARKING...", bg="#ffaa00", fg="black")
            elif msg["type"] == "TARGET_UPDATE" and not self.manual_mode.get():
                self.slider_m1.set(msg["m1"])
                self.slider_m2.set(msg["m2"])
                self.slider_m3.set(msg["m3"])
            elif msg["type"] == "PARAM_UPDATE":
                addr = msg["address"]
                if addr in self.param_vars:
                    self.param_vars[addr].set(str(msg["value"]))
            elif msg["type"] == "FEEDBACK":
                self.feedback_m1.set(str(msg["m1"]))
                self.feedback_m2.set(str(msg["m2"]))
                self.feedback_m3.set(str(msg["m3"]))

        is_vis_running = (
            self.vis_process is not None and self.vis_process.poll() is None
        )
        if is_vis_running != self._last_vis_state:
            self._last_vis_state = is_vis_running
            self.push_state()
            if not is_vis_running and self.debug_mode.get():
                self.log(
                    "[SYSTEM] Visualizer window closed. Pausing network data stream."
                )

        self.root.after(50, self.process_queue)
