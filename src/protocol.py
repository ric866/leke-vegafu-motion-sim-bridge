import struct
import time


class IMAXProtocol:
    @staticmethod
    def pack_motion_data(m1, m2, m3):
        """0x1301 Absolute time multi-axis motion data"""
        t_stamp = int(time.time() * 1000) & 0xFFFFFFFF
        return struct.pack(
            ">HHHHHHIIiiiiiiHI",
            0x55AA,
            0x0000,
            0x1301,
            0x0001,
            0xFFFF,
            0xFFFF,
            t_stamp,
            t_stamp & 0xFFFF,
            int(m1),
            int(m2),
            int(m3),
            0,
            0,
            0,
            0x0000,
            0x5678ABCD,
        )

    @staticmethod
    def pack_read_register(reg_address, is_pa=True):
        """0x1101 Master read slave register operation"""
        obj_channel = 1 if is_pa else 0  # 1: PAxx, 0: DPxx
        return struct.pack(
            ">HHHBBHH",
            0x55AA,  # Confirm Code
            0x1101,  # Function Code
            0x0000,  # Pass Code
            obj_channel,  # Object Channel
            0xFF,  # Accept Code (ff: all)
            0x00,  # Reply Code (0: none/default)
            reg_address,  # RegStart Address
            1,  # Reg Num (read 1 register)
        )

    @staticmethod
    def pack_write_register(reg_address, value, is_pa=True):
        """0x1201 Master write slave register operation"""
        obj_channel = 1 if is_pa else 0
        return struct.pack(
            ">HHHBBHHI",
            0x55AA,  # Confirm Code
            0x1201,  # Function Code
            0x0000,  # Pass Code
            obj_channel,  # Object Channel
            0xFF,  # Accept Code
            0x00,  # Reply Code
            reg_address,  # RegStart Address
            1,  # Reg Num
            int(value),  # Reg Data (32-bit integer)
        )
