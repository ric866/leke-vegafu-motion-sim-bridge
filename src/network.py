import socket
import threading
import time
import select
import struct
import json
from protocol import IMAXProtocol


class NetworkBackend:
    def __init__(self, gui_queue, cmd_queue):
        self.gui_queue = gui_queue
        self.cmd_queue = cmd_queue
        self.running = True
        self.scale_factor = 240000 / 65535.0
        self.vis_port = 9001

        self.config = {
            "bind_ip": "127.0.0.1",
            "rx_port": 10000,
            "tx_port": 8410,
            "vega_ip": "192.168.15.201",
            "vega_port": 7408,
            "safe_pos": 120000,
        }

        self.thread = threading.Thread(target=self._network_worker, daemon=True)

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
        active = manual = debug = vis_running = False
        silence_countdown = 40
        last_log_time = 0

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

                    elif cmd["type"] == "STATE":
                        active, manual, debug = (
                            cmd["active"],
                            cmd["manual"],
                            cmd.get("debug", False),
                        )
                        vis_running = cmd.get("vis_running", False)
                        if active or manual:
                            silence_countdown = 40
                        if debug:
                            self.gui_queue.put(
                                {
                                    "type": "LOG",
                                    "data": f"[NET STATE] Active:{active}, Manual:{manual}, Debug:{debug}, Vis:{vis_running}",
                                }
                            )

                    elif cmd["type"] == "MANUAL_POS":
                        out_m1, out_m2, out_m3 = cmd["m1"], cmd["m2"], cmd["m3"]
                        if debug:
                            self.gui_queue.put(
                                {
                                    "type": "LOG",
                                    "data": f"[NET MANUAL IN] Targets -> M1:{out_m1} M2:{out_m2} M3:{out_m3}",
                                }
                            )

                    elif cmd["type"] == "READ_PARAM":
                        pkt = IMAXProtocol.pack_read_register(cmd["address"])
                        try:
                            sock_tx.sendto(
                                pkt, (self.config["vega_ip"], self.config["vega_port"])
                            )
                            if debug:
                                self.gui_queue.put(
                                    {
                                        "type": "LOG",
                                        "data": f"[NET TX FLASH READ] -> {self.config['vega_ip']}:{self.config['vega_port']} | Payload: {pkt.hex()}",
                                    }
                                )
                        except Exception as e:
                            if debug:
                                self.gui_queue.put(
                                    {
                                        "type": "LOG",
                                        "data": f"[NET TX ERROR] Read Param Send Failed: {e}",
                                    }
                                )

                    elif cmd["type"] == "WRITE_PARAM":
                        pkt = IMAXProtocol.pack_write_register(
                            cmd["address"], cmd["value"]
                        )
                        try:
                            sock_tx.sendto(
                                pkt, (self.config["vega_ip"], self.config["vega_port"])
                            )
                            if debug:
                                self.gui_queue.put(
                                    {
                                        "type": "LOG",
                                        "data": f"[NET TX FLASH WRITE] -> {self.config['vega_ip']}:{self.config['vega_port']} | Payload: {pkt.hex()}",
                                    }
                                )
                        except Exception as e:
                            if debug:
                                self.gui_queue.put(
                                    {
                                        "type": "LOG",
                                        "data": f"[NET TX ERROR] Write Param Send Failed: {e}",
                                    }
                                )

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
                                if debug:
                                    self.gui_queue.put(
                                        {
                                            "type": "LOG",
                                            "data": f"[NET RX FLYPT] <- {addr} | Bytes: {len(data)} | Payload: {data.hex()}",
                                        }
                                    )

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
                                if debug:
                                    self.gui_queue.put(
                                        {
                                            "type": "LOG",
                                            "data": f"[NET RX VEGA RIG] <- {addr} | Bytes: {len(data)} | Payload: {data.hex()}",
                                        }
                                    )

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
                                        if debug:
                                            action = (
                                                "READ"
                                                if func_code == 0x1102
                                                else "WRITE"
                                            )
                                            self.gui_queue.put(
                                                {
                                                    "type": "LOG",
                                                    "data": f"[NET PARSED FLASH] {action} OK -> PA{reg_addr:02X} = {reg_val}",
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
                            if debug:
                                self.gui_queue.put(
                                    {
                                        "type": "LOG",
                                        "data": f"[NET PARSED FEEDBACK] Actuators -> M1:{vals[1]} M2:{vals[2]} M3:{vals[3]}",
                                    }
                                )

                # --- 3. Determine Output ---
                if active or manual:
                    should_send_motion = True
                    silence_countdown = 40
                    if not manual and flypt_data:
                        out_m1 = int(raw_in[0] * self.scale_factor)
                        out_m2 = int(raw_in[1] * self.scale_factor)
                        out_m3 = int(raw_in[2] * self.scale_factor)
                        self.gui_queue.put(
                            {
                                "type": "TARGET_UPDATE",
                                "m1": out_m1,
                                "m2": out_m2,
                                "m3": out_m3,
                            }
                        )
                        if debug:
                            self.gui_queue.put(
                                {
                                    "type": "LOG",
                                    "data": f"[NET AUTO CALC] Scaled FlyPT -> M1:{out_m1} M2:{out_m2} M3:{out_m3}",
                                }
                            )
                else:
                    out_m1 = out_m2 = out_m3 = self.config["safe_pos"]
                    if silence_countdown > 0:
                        should_send_motion = True
                        silence_countdown -= 1

                # --- 4. Send Motion Packets ---
                if should_send_motion:
                    # To Rig
                    try:
                        pkt = IMAXProtocol.pack_motion_data(out_m1, out_m2, out_m3)
                        sock_tx.sendto(
                            pkt, (self.config["vega_ip"], self.config["vega_port"])
                        )
                        if debug:
                            self.gui_queue.put(
                                {
                                    "type": "LOG",
                                    "data": f"[NET TX MOTION] -> {self.config['vega_ip']}:{self.config['vega_port']} | Payload: {pkt.hex()}",
                                }
                            )
                    except Exception as e:
                        if debug:
                            self.gui_queue.put(
                                {
                                    "type": "LOG",
                                    "data": f"[NET TX ERROR] Motion send failed: {e}",
                                }
                            )

                    # To Visualizer (ONLY if the GUI says it's running)
                    if vis_running:
                        try:
                            vis_data = json.dumps(
                                {"m1": out_m1, "m2": out_m2, "m3": out_m3}
                            ).encode("utf-8")
                            sock_vis.sendto(vis_data, ("127.0.0.1", self.vis_port))
                            if debug:
                                self.gui_queue.put(
                                    {
                                        "type": "LOG",
                                        "data": f"[NET TX VISUALIZER] -> 127.0.0.1:{self.vis_port} | Payload: {vis_data}",
                                    }
                                )
                        except Exception as e:
                            if debug:
                                self.gui_queue.put(
                                    {
                                        "type": "LOG",
                                        "data": f"[NET TX ERROR] Visualizer send failed: {e}",
                                    }
                                )

                # --- 5. Debug Logging (Rate Limited) ---
                if debug and (time.time() - last_log_time > 0.5):
                    if should_send_motion:
                        if active and not manual:
                            log_msg = f"[AUTO] In: {raw_in} -> Out: [{out_m1}, {out_m2}, {out_m3}]"
                        elif manual:
                            log_msg = f"[MANUAL] Out: [{out_m1}, {out_m2}, {out_m3}]"
                        else:
                            log_msg = f"[PARKING] Out: [{out_m1}, {out_m2}, {out_m3}]"
                    else:
                        log_msg = "[SILENT] Network Idle"

                    self.gui_queue.put({"type": "LOG", "data": log_msg})
                    last_log_time = time.time()

                # --- 6. 20Hz Timing ---
                elapsed = time.time() - loop_start
                if elapsed < 0.050:
                    time.sleep(0.050 - elapsed)
                elif debug:
                    self.gui_queue.put(
                        {
                            "type": "LOG",
                            "data": f"[NET TIMING WARNING] Loop took {elapsed*1000:.1f}ms (Exceeded 50ms budget!)",
                        }
                    )

            except Exception as loop_e:
                self.gui_queue.put(
                    {"type": "LOG", "data": f"[CRITICAL THREAD ERROR] {loop_e}"}
                )
                time.sleep(0.1)
