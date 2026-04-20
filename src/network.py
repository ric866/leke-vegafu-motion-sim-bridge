import socket
import threading
import time
import select
import struct
import json
import os
from protocol import IMAXProtocol


class NetworkBackend:
    def __init__(self, gui_queue, cmd_queue):
        self.gui_queue = gui_queue
        self.cmd_queue = cmd_queue
        self.running = True
        self.scale_factor = 240000 / 65535.0
        self.vis_port = 9001

        self.config_file = "vega_config.json"
        self.config = self._load_initial_config()

        self.thread = threading.Thread(target=self._network_worker, daemon=True)

    def _load_initial_config(self):
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
            except Exception:
                pass
        return defaults

    def start(self):
        self.gui_queue.put(
            {"type": "LOG", "data": "[NET] Backend thread start requested."}
        )
        self.thread.start()

    def stop(self):
        self.gui_queue.put(
            {"type": "LOG", "data": "[NET] Backend thread stop requested."}
        )
        self.running = False

    def _network_worker(self):
        self.gui_queue.put(
            {"type": "LOG", "data": "[NET] Network worker loop initializing sockets."}
        )
        sock_rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock_tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock_vis = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        out_m1 = out_m2 = out_m3 = self.config["safe_pos"]
        manual = debug = vis_running = False
        last_log_time = 0

        sys_state = "STOPPED"
        current_m = [0, 0, 0]
        last_active_target = [self.config["safe_pos"]] * 3
        silence_countdown = 0

        try:
            sock_rx.bind((self.config["bind_ip"], self.config["rx_port"]))
            sock_tx.bind((self.config["bind_ip"], self.config["tx_port"]))
            sock_rx.setblocking(False)
            sock_tx.setblocking(False)
            self.gui_queue.put(
                {
                    "type": "LOG",
                    "data": f"[NET] Bound RX to {self.config['bind_ip']}:{self.config['rx_port']} and TX to {self.config['tx_port']}",
                }
            )
        except Exception as e:
            self.gui_queue.put({"type": "LOG", "data": f"[NET BIND ERROR] {e}"})

        while self.running:
            try:
                loop_start = time.time()
                should_send_motion = False

                # --- 1. Process GUI Commands ---
                while not self.cmd_queue.empty():
                    cmd = self.cmd_queue.get()
                    if debug:
                        self.gui_queue.put(
                            {
                                "type": "LOG",
                                "data": f"[NET CMD RX] Processed Command: {cmd['type']}",
                            }
                        )

                    if cmd["type"] == "CONFIG":
                        self.config.update(
                            {
                                k: cmd[k]
                                for k in [
                                    "bind_ip",
                                    "rx_port",
                                    "tx_port",
                                    "vega_ip",
                                    "vega_port",
                                    "safe_pos",
                                    "hz",
                                    "max_delta_auto",
                                    "max_delta_manual",
                                ]
                            }
                        )
                        sock_rx.close()
                        sock_tx.close()
                        sock_rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        sock_tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        try:
                            sock_rx.bind(
                                (self.config["bind_ip"], self.config["rx_port"])
                            )
                            sock_tx.bind(
                                (self.config["bind_ip"], self.config["tx_port"])
                            )
                            sock_rx.setblocking(False)
                            sock_tx.setblocking(False)
                            self.gui_queue.put(
                                {
                                    "type": "LOG",
                                    "data": f"[NET] Sockets RECONFIGURED (Bind: {self.config['bind_ip']})",
                                }
                            )
                        except Exception as e:
                            self.gui_queue.put(
                                {"type": "LOG", "data": f"[NET REBIND FAIL] {e}"}
                            )

                    elif cmd["type"] == "SYS_CMD":
                        if cmd["cmd"] == "START" and sys_state == "STOPPED":
                            sys_state = "STARTING"
                            self.gui_queue.put(
                                {"type": "STATE_UPDATE", "state": sys_state}
                            )
                            if debug:
                                self.gui_queue.put(
                                    {
                                        "type": "LOG",
                                        "data": "[NET STATE] System STARTING...",
                                    }
                                )
                        elif cmd["cmd"] == "STOP" and sys_state in [
                            "ACTIVE",
                            "STARTING",
                        ]:
                            sys_state = "STOPPING"
                            self.gui_queue.put(
                                {"type": "STATE_UPDATE", "state": sys_state}
                            )
                            if debug:
                                self.gui_queue.put(
                                    {
                                        "type": "LOG",
                                        "data": "[NET STATE] System STOPPING (Parking)...",
                                    }
                                )

                    elif cmd["type"] == "STATE":
                        manual, debug = cmd["manual"], cmd.get("debug", False)
                        vis_running = cmd.get("vis_running", False)

                    elif cmd["type"] == "MANUAL_POS":
                        out_m1, out_m2, out_m3 = cmd["m1"], cmd["m2"], cmd["m3"]

                    elif cmd["type"] == "READ_PARAM":
                        pkt = IMAXProtocol.pack_read_register(cmd["address"])
                        try:
                            sock_tx.sendto(
                                pkt, (self.config["vega_ip"], self.config["vega_port"])
                            )
                        except Exception:
                            pass

                    elif cmd["type"] == "WRITE_PARAM":
                        pkt = IMAXProtocol.pack_write_register(
                            cmd["address"], cmd["value"]
                        )
                        try:
                            sock_tx.sendto(
                                pkt, (self.config["vega_ip"], self.config["vega_port"])
                            )
                        except Exception:
                            pass

                # --- 2. Read Network ---
                try:
                    readable, _, _ = select.select([sock_rx, sock_tx], [], [], 0)
                except Exception:
                    readable = []

                flypt_data = False
                raw_in = [0, 0, 0]

                for s in readable:
                    if s is sock_rx:
                        try:
                            while True:
                                data, addr = s.recvfrom(1024)
                                if len(data) >= 8 and data[0] == 0xFF:
                                    raw_in[0] = (data[2] << 8) | data[3]
                                    raw_in[1] = (data[4] << 8) | data[5]
                                    raw_in[2] = (data[6] << 8) | data[7]
                                    flypt_data = True
                        except Exception:
                            pass

                    elif s is sock_tx:
                        last_feedback = None
                        try:
                            while True:
                                data, addr = s.recvfrom(1024)
                                if len(data) >= 16 and data[0:2] == b"\x55\xaa":
                                    func_code = (data[2] << 8) | data[3]
                                    if func_code in (0x1102, 0x1202):
                                        reg_addr = (data[8] << 8) | data[9]
                                        reg_val = struct.unpack(">I", data[12:16])[0]
                                        self.gui_queue.put(
                                            {
                                                "type": "PARAM_UPDATE",
                                                "address": reg_addr,
                                                "value": reg_val,
                                            }
                                        )
                                    elif func_code == 0x1302 and len(data) >= 28:
                                        last_feedback = data
                                elif len(data) >= 40 and data[0] == 0x55:
                                    last_feedback = data
                        except Exception:
                            pass

                        if last_feedback:
                            vals = struct.unpack(">Iiii", last_feedback[12:28])
                            self.gui_queue.put(
                                {
                                    "type": "FEEDBACK",
                                    "m1": vals[1],
                                    "m2": vals[2],
                                    "m3": vals[3],
                                }
                            )

                # --- 3. Determine Targets & Run State Machine ---
                if flypt_data:
                    last_active_target = [
                        int(raw_in[0] * self.scale_factor),
                        int(raw_in[1] * self.scale_factor),
                        int(raw_in[2] * self.scale_factor),
                    ]
                if manual:
                    last_active_target = [out_m1, out_m2, out_m3]

                target_m = [0, 0, 0]

                if sys_state == "STARTING":
                    target_m = [self.config["safe_pos"]] * 3
                    if current_m == target_m:
                        sys_state = "ACTIVE"
                        self.gui_queue.put({"type": "STATE_UPDATE", "state": sys_state})

                elif sys_state == "ACTIVE":
                    target_m = last_active_target

                elif sys_state == "STOPPING":
                    target_m = [0, 0, 0]
                    if current_m == target_m:
                        sys_state = "STOPPED"
                        silence_countdown = int(self.config["hz"] * 2)
                        self.gui_queue.put({"type": "STATE_UPDATE", "state": sys_state})

                elif sys_state == "STOPPED":
                    target_m = [0, 0, 0]

                # --- 4. Apply Split Slew Rate Limit (Max Delta) ---
                if sys_state in ["STARTING", "STOPPING"] or manual:
                    active_delta = self.config["max_delta_manual"]
                else:
                    active_delta = self.config["max_delta_auto"]

                if sys_state != "STOPPED":
                    should_send_motion = True
                    for i in range(3):
                        diff = target_m[i] - current_m[i]
                        if diff > active_delta:
                            diff = active_delta
                        elif diff < -active_delta:
                            diff = -active_delta
                        current_m[i] += diff
                elif silence_countdown > 0:
                    should_send_motion = True
                    silence_countdown -= 1

                if not manual:
                    self.gui_queue.put(
                        {
                            "type": "TARGET_UPDATE",
                            "m1": current_m[0],
                            "m2": current_m[1],
                            "m3": current_m[2],
                        }
                    )

                # --- 5. Send Motion Packets ---
                if should_send_motion:
                    try:
                        pkt = IMAXProtocol.pack_motion_data(
                            current_m[0], current_m[1], current_m[2]
                        )
                        sock_tx.sendto(
                            pkt, (self.config["vega_ip"], self.config["vega_port"])
                        )
                    except Exception:
                        pass

                    if vis_running:
                        try:
                            vis_data = json.dumps(
                                {
                                    "m1": current_m[0],
                                    "m2": current_m[1],
                                    "m3": current_m[2],
                                }
                            ).encode("utf-8")
                            sock_vis.sendto(vis_data, ("127.0.0.1", self.vis_port))
                        except Exception:
                            pass

                # --- 6. Debug Logging ---
                if debug and (time.time() - last_log_time > 0.5):
                    if should_send_motion:
                        log_msg = f"[{sys_state}] Tgt: {target_m} -> Out: {current_m}"
                    else:
                        log_msg = "[STOPPED] Network Idle (Rig at Zero)"
                    self.gui_queue.put({"type": "LOG", "data": log_msg})
                    last_log_time = time.time()

                # --- 7. Dynamic Hz Timing ---
                sleep_time = 1.0 / self.config["hz"]
                elapsed = time.time() - loop_start
                if elapsed < sleep_time:
                    time.sleep(sleep_time - elapsed)
                elif debug:
                    self.gui_queue.put(
                        {
                            "type": "LOG",
                            "data": f"[NET TIMING WARNING] Loop took {elapsed*1000:.1f}ms (Exceeded {sleep_time*1000:.1f}ms budget!)",
                        }
                    )

            except Exception as loop_e:
                self.gui_queue.put(
                    {"type": "LOG", "data": f"[CRITICAL THREAD ERROR] {loop_e}"}
                )
                time.sleep(0.1)
