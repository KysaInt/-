import tkinter as tk
from tkinter import messagebox
import socket
import os
import pathlib
import re

def encode_varint(value):
    if value == 0:
        return b'\x00'
    data = b''
    while value:
        data += bytes([(value & 0x7f) | 0x80])
        value >>= 7
    data = data[:-1] + bytes([data[-1] & 0x7f])
    return data

def encode_string(s):
    s_bytes = s.encode('utf-8')
    length = len(s_bytes)
    return encode_varint(length) + s_bytes

def encode_online_request(peers):
    data = b''
    for peer in peers:
        data += b'\x0a'  # field 1, type 2
        data += encode_string(peer)
    return data

def decode_varint(data, pos):
    value = 0
    shift = 0
    while True:
        byte = data[pos]
        pos += 1
        value |= (byte & 0x7f) << shift
        if not (byte & 0x80):
            break
        shift += 7
    return value, pos

def decode_online_response(data):
    pos = 0
    states = b''
    while pos < len(data):
        byte = data[pos]
        pos += 1
        field_num = byte >> 3
        wire_type = byte & 0x7
        if field_num == 1 and wire_type == 2:
            length, pos = decode_varint(data, pos)
            states = data[pos:pos+length]
            pos += length
        else:
            # skip
            if wire_type == 0:
                _, pos = decode_varint(data, pos)
            elif wire_type == 1:
                pos += 8
            elif wire_type == 2:
                length, pos = decode_varint(data, pos)
                pos += length
            elif wire_type == 5:
                pos += 4
    return states

def get_rustdesk_config_path():
    if os.name == 'nt':  # Windows
        appdata = os.environ.get('APPDATA')
        if appdata:
            return pathlib.Path(appdata) / 'RustDesk' / 'config' / 'RustDesk.toml'
    else:  # Linux/macOS
        home = pathlib.Path.home()
        return home / '.config' / 'rustdesk' / 'RustDesk.toml'
    return None

def read_rustdesk_config():
    config_path = get_rustdesk_config_path()
    if not config_path or not config_path.exists():
        return None
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # 查找rendezvous_server
        match = re.search(r'rendezvous_server\s*=\s*"([^"]+)"', content)
        if match:
            return match.group(1)
        return None
    except Exception:
        return None

def get_online_status(server_ip, peers, port=21116):
    data = encode_online_request(peers)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((server_ip, port))
    sock.send(data)
    response_data = sock.recv(1024)
    sock.close()
    states = decode_online_response(response_data)
    return states

def get_help(server_ip, port=21114):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((server_ip, port))
    sock.send(b"h\n")
    response = sock.recv(1024)
    sock.close()
    return response.decode()

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("RustDesk Device Status")
        
        self.server_ip_label = tk.Label(root, text="Server IP:")
        self.server_ip_label.pack()
        self.server_ip_entry = tk.Entry(root)
        self.server_ip_entry.pack()
        
        self.auto_detect_button = tk.Button(root, text="Auto Detect Server", command=self.auto_detect_server)
        self.auto_detect_button.pack()
        
        self.peers_label = tk.Label(root, text="Peers (comma separated):")
        self.peers_label.pack()
        self.peers_entry = tk.Entry(root)
        self.peers_entry.pack()
        
        self.get_status_button = tk.Button(root, text="Get Online Status", command=self.get_status)
        self.get_status_button.pack()
        
        self.get_help_button = tk.Button(root, text="Get Help", command=self.get_help)
        self.get_help_button.pack()
        
        self.result_text = tk.Text(root, height=10, width=50)
        self.result_text.pack()
    
    def auto_detect_server(self):
        server_ip = read_rustdesk_config()
        if server_ip:
            self.server_ip_entry.delete(0, tk.END)
            self.server_ip_entry.insert(0, server_ip)
            messagebox.showinfo("Success", f"Auto-detected server: {server_ip}")
        else:
            messagebox.showerror("Error", "Could not auto-detect server. Please check RustDesk configuration.")
    
    def get_status(self):
        server_ip = self.server_ip_entry.get()
        peers_str = self.peers_entry.get()
        peers = [p.strip() for p in peers_str.split(',') if p.strip()]
        if not server_ip or not peers:
            messagebox.showerror("Error", "Please enter server IP and peers")
            return
        try:
            states = get_online_status(server_ip, peers)
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, f"States: {states}\n")
            for i, peer in enumerate(peers):
                byte_index = i // 8
                bit_index = 7 - (i % 8)
                if byte_index < len(states):
                    bit = (states[byte_index] >> bit_index) & 1
                    status = "Online" if bit else "Offline"
                else:
                    status = "Unknown"
                self.result_text.insert(tk.END, f"{peer}: {status}\n")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def get_help(self):
        server_ip = self.server_ip_entry.get()
        if not server_ip:
            messagebox.showerror("Error", "Please enter server IP")
            return
        try:
            help_text = get_help(server_ip)
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, help_text)
        except Exception as e:
            messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
