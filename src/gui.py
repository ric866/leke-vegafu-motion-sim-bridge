import tkinter as tk
from tkinter import ttk, scrolledtext
import socket


def get_local_interfaces():
    """Helper to get a list of available IP addresses on this machine."""
    interfaces = [
        "127.0.0.1",
        "0.0.0.0",
    ]  # 0.0.0.0 left as an option for debugging # nosec B104
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

        self.root.title("Vega Mission Control (Modular)")
        self.root.geometry("850x750")

        # --- State Variables ---
        self.system_active = False
        self.manual_mode = tk.BooleanVar(value=False)
        self.debug_mode = tk.BooleanVar(value=False)
        self.slider_m1 = tk.IntVar(value=120000)
        self.slider_m2 = tk.IntVar(value=120000)
        self.slider_m3 = tk.IntVar(value=120000)

        # --- Network Config Variables ---
        self.conf_bind_ip = tk.StringVar(value="127.0.0.1")
        self.conf_rx_port = tk.StringVar(value="10000")
        self.conf_tx_port = tk.StringVar(value="8410")
        self.conf_vega_ip = tk.StringVar(value="192.168.15.201")
        self.conf_vega_port = tk.StringVar(value="7408")
        self.conf_safe_pos = tk.StringVar(value="120000")

        # --- Dictionary of useful parameters from the IMAX PDF Manual ---
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

        # Store StringVars for the UI entries so we can update them dynamically
        self.param_vars = {addr: tk.StringVar(value="") for addr in self.pa_params}

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_tab_motion()
        self._build_tab_flash()
        self._build_tab_debug()

        self.root.after(50, self.process_queue)

    # --- TAB 1: MOTION & CONTROL ---
    def _build_tab_motion(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="1. Motion & Control")

        # Network Config Frame
        frame_config = ttk.LabelFrame(tab, text="Network Configuration", padding=10)
        frame_config.pack(fill="x", padx=10, pady=5)

        # Row 0: Local Bind Interface
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

        # Row 1: Ports
        ttk.Label(frame_config, text="FlyPT Port (In):").grid(
            row=1, column=0, sticky="e", padx=5, pady=2
        )
        ttk.Entry(frame_config, textvariable=self.conf_rx_port, width=10).grid(
            row=1, column=1, sticky="w"
        )
        ttk.Label(frame_config, text="Reply Port (Out):").grid(
            row=1, column=2, sticky="e", padx=5, pady=2
        )
        ttk.Entry(frame_config, textvariable=self.conf_tx_port, width=10).grid(
            row=1, column=3, sticky="w"
        )

        # Row 2: Controller Target
        ttk.Label(frame_config, text="Vega IP:").grid(
            row=2, column=0, sticky="e", padx=5, pady=2
        )
        ttk.Entry(frame_config, textvariable=self.conf_vega_ip, width=15).grid(
            row=2, column=1, sticky="w"
        )
        ttk.Label(frame_config, text="Vega Port:").grid(
            row=2, column=2, sticky="e", padx=5, pady=2
        )
        ttk.Entry(frame_config, textvariable=self.conf_vega_port, width=10).grid(
            row=2, column=3, sticky="w"
        )

        ttk.Button(
            frame_config, text="APPLY NETWORK SETTINGS", command=self.push_config
        ).grid(row=3, column=0, columnspan=4, pady=10)

        # Safety Button
        self.btn_safety = tk.Button(
            tab,
            text="SYSTEM STOPPED",
            bg="#ff4444",
            fg="white",
            font=("Arial", 12, "bold"),
            height=2,
            command=self.toggle_system,
        )
        self.btn_safety.pack(fill="x", padx=10, pady=10)

        # Controls
        frame_controls = ttk.LabelFrame(tab, text="Manual Override", padding=10)
        frame_controls.pack(fill="x", padx=10, pady=5)
        ttk.Checkbutton(
            frame_controls,
            text="Enable Manual Mode",
            variable=self.manual_mode,
            command=self.push_state,
        ).pack(anchor="w")

        self._create_axis_slider(frame_controls, "Axis 1", self.slider_m1)
        self._create_axis_slider(frame_controls, "Axis 2", self.slider_m2)
        self._create_axis_slider(frame_controls, "Axis 3", self.slider_m3)

        # Visualizer Placeholder
        frame_vis = ttk.LabelFrame(tab, text="Motion Visualizer", padding=10)
        frame_vis.pack(fill="both", expand=True, padx=10, pady=5)
        self.canvas = tk.Canvas(frame_vis, bg="black")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_text(
            350,
            80,
            text="Visualizer Shim - Render Here",
            fill="white",
            font=("Arial", 14),
        )

    def _create_axis_slider(self, parent, label, var):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=2)
        ttk.Label(frame, text=label, width=8).pack(side="left")
        ttk.Scale(
            frame,
            from_=0,
            to=240000,
            variable=var,
            orient="horizontal",
            command=lambda v: self.push_manual(),
        ).pack(side="left", fill="x", expand=True)

    # --- TAB 2: CONTROLLER FLASH SETTINGS ---
    def _build_tab_flash(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="2. Controller Flash")

        # Top Global Buttons
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

        # Scrollable List Setup
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

        # Populate List Headers
        ttk.Label(self.scrollable_frame, text="Hex", font=("Arial", 9, "bold")).grid(
            row=0, column=0, padx=5, pady=5, sticky="w"
        )
        ttk.Label(
            self.scrollable_frame, text="Description", font=("Arial", 9, "bold")
        ).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(self.scrollable_frame, text="Value", font=("Arial", 9, "bold")).grid(
            row=0, column=2, padx=5, pady=5, sticky="w"
        )

        # Populate List Rows
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

            # Individual Read/Write Buttons
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

    # --- TAB 3: DEBUG & LOGS ---
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

    # --- LOGIC & COMMAND PUSHING ---
    def push_config(self):
        """Send the updated network settings to the backend thread."""
        try:
            self.cmd_queue.put(
                {
                    "type": "CONFIG",
                    "bind_ip": self.conf_bind_ip.get(),
                    "rx_port": int(self.conf_rx_port.get()),
                    "tx_port": int(self.conf_tx_port.get()),
                    "vega_ip": self.conf_vega_ip.get(),
                    "vega_port": int(self.conf_vega_port.get()),
                    "safe_pos": int(self.conf_safe_pos.get()),
                }
            )
            self.log(f"Applying new config: Bind IP {self.conf_bind_ip.get()}")
        except ValueError:
            self.log("[ERROR] Port and Safe Position values must be valid integers.")

    def toggle_system(self):
        self.system_active = not self.system_active
        self.btn_safety.config(
            text="SYSTEM ACTIVE" if self.system_active else "SYSTEM STOPPED",
            bg="#44cc44" if self.system_active else "#ff4444",
        )
        self.push_state()

    def push_state(self):
        self.cmd_queue.put(
            {
                "type": "STATE",
                "active": self.system_active,
                "manual": self.manual_mode.get(),
                "debug": self.debug_mode.get(),
            }
        )

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
        self.txt_log.see(tk.END)
        self.txt_log.config(state="disabled")

    def process_queue(self):
        """Consume messages from the backend thread."""
        while not self.gui_queue.empty():
            msg = self.gui_queue.get_nowait()
            if msg["type"] == "LOG":
                self.log(msg["data"])
            elif msg["type"] == "TARGET_UPDATE" and not self.manual_mode.get():
                self.slider_m1.set(msg["m1"])
                self.slider_m2.set(msg["m2"])
                self.slider_m3.set(msg["m3"])
            elif msg["type"] == "PARAM_UPDATE":
                # Populate the entry box when the controller replies
                addr = msg["address"]
                if addr in self.param_vars:
                    self.param_vars[addr].set(str(msg["value"]))

        self.root.after(50, self.process_queue)
