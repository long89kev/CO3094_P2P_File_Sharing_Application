import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox

from client import P2PClient

class TextLogger:
    def __init__(self, text_widget: tk.Text):
        self.text = text_widget
        self.text.configure(state=tk.DISABLED)

    def __call__(self, line: str):
        self.text.after(0, self._append, line)

    def _append(self, line: str):
        self.text.configure(state=tk.NORMAL)
        self.text.insert(tk.END, line + "\n")
        self.text.see(tk.END)
        self.text.configure(state=tk.DISABLED)

class ClientGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("P2P File Sharing Client")
        self.geometry("1400x650")

        self.client: P2PClient | None = None

        self._build_connection_panel()
        self._build_main_area()
        self._build_log_panel()
        self.status_var.set("Disconnected")
        self._set_connected(False)

    def _build_connection_panel(self):
        frame = ttk.Frame(self)
        frame.pack(fill=tk.X, padx=8, pady=6)

        ttk.Label(frame, text="Server IP:").grid(row=0, column=0, sticky=tk.W, padx=4)
        self.server_ip_var = tk.StringVar(value="127.0.0.1")
        ttk.Entry(frame, width=16, textvariable=self.server_ip_var).grid(row=0, column=1, padx=4)

        ttk.Label(frame, text="Port:").grid(row=0, column=2, sticky=tk.W, padx=4)
        self.server_port_var = tk.StringVar(value="8000")
        ttk.Entry(frame, width=8, textvariable=self.server_port_var).grid(row=0, column=3, padx=4)

        ttk.Label(frame, text="My Hostname:").grid(row=0, column=4, sticky=tk.W, padx=4)
        self.hostname_var = tk.StringVar(value="client1")
        ttk.Entry(frame, width=16, textvariable=self.hostname_var).grid(row=0, column=5, padx=4)

        ttk.Label(frame, text="My P2P Port:").grid(row=0, column=6, sticky=tk.W, padx=4)
        self.p2p_port_var = tk.StringVar(value="9001")
        ttk.Entry(frame, width=8, textvariable=self.p2p_port_var).grid(row=0, column=7, padx=4)

        self.connect_btn = ttk.Button(frame, text="Connect", command=self._on_connect)
        self.connect_btn.grid(row=0, column=8, padx=6)

        ttk.Label(frame, text="Status:").grid(row=1, column=0, sticky=tk.W, padx=4, pady=(6,0))
        self.status_var = tk.StringVar(value="Disconnected")
        self.status_lbl = ttk.Label(frame, textvariable=self.status_var)
        self.status_lbl.grid(row=1, column=1, columnspan=7, sticky=tk.W, pady=(6,0))

    def _build_main_area(self):
        main = ttk.Frame(self)
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        left = ttk.Frame(main)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Label(left, text="My Shared Files:").pack(anchor=tk.W)
        self.shared_list = tk.Listbox(left, height=20)
        self.shared_list.pack(fill=tk.BOTH, expand=True)
        ttk.Button(left, text="Publish New File...", command=self._on_publish).pack(anchor=tk.W, pady=6)

        # Middle panel for client list
        middle = ttk.Frame(main)
        middle.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8)
        
        client_header = ttk.Frame(middle)
        client_header.pack(fill=tk.X)
        ttk.Label(client_header, text="Connected Clients:").pack(side=tk.LEFT)
        ttk.Button(client_header, text="Refresh", command=self._on_get_clients).pack(side=tk.RIGHT, padx=4)
        
        self.client_list = tk.Listbox(middle, height=10)
        self.client_list.pack(fill=tk.BOTH, expand=True, pady=4)
        self.client_list.bind('<<ListboxSelect>>', self._on_client_selected)
        
        ttk.Label(middle, text="Client's Files:").pack(anchor=tk.W, pady=(8,0))
        self.client_files_list = tk.Listbox(middle, height=10)
        self.client_files_list.pack(fill=tk.BOTH, expand=True)
        self.client_files_list.bind('<Double-Button-1>', self._on_client_file_double_click)

        right = ttk.Frame(main)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        top_row = ttk.Frame(right)
        top_row.pack(fill=tk.X)
        ttk.Label(top_row, text="File to Fetch:").pack(side=tk.LEFT)
        self.fetch_name_var = tk.StringVar()
        ttk.Entry(top_row, width=40, textvariable=self.fetch_name_var).pack(side=tk.LEFT, padx=6)
        ttk.Button(top_row, text="Fetch", command=self._on_fetch).pack(side=tk.LEFT)

        ttk.Label(right, text="Search Results:").pack(anchor=tk.W, pady=(8,0))
        self.results_list = tk.Listbox(right, height=14)
        self.results_list.pack(fill=tk.BOTH, expand=True)

        ttk.Button(right, text="Download from Selected Peer", command=self._on_download).pack(anchor=tk.W, pady=6)

        prog_row = ttk.Frame(right)
        prog_row.pack(fill=tk.X)
        ttk.Label(prog_row, text="Download Progress:").pack(side=tk.LEFT)
        self.progress = ttk.Progressbar(prog_row, mode="determinate")
        self.progress.pack(fill=tk.X, padx=6, expand=True)

    def _build_log_panel(self):
        ttk.Label(self, text="System Log:").pack(anchor=tk.W, padx=8)
        self.log_text = tk.Text(self, height=10)
        self.log_text.pack(fill=tk.BOTH, expand=False, padx=8, pady=(0,8))
        self.logger = TextLogger(self.log_text)
        self.logger("Welcome! Please connect to the server.")

    def _on_connect(self):
        server_ip = self.server_ip_var.get().strip()
        hostname = self.hostname_var.get().strip()
        try:
            server_port = int(self.server_port_var.get().strip())
            p2p_port = int(self.p2p_port_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid Input", "Ports must be integers")
            return

        shared_folder = os.path.join(os.getcwd(), "shared_files", hostname)
        os.makedirs(shared_folder, exist_ok=True)

        self.client = P2PClient(
            hostname=hostname,
            server_host=server_ip,
            server_port=server_port,
            p2p_port=p2p_port,
            shared_folder=shared_folder,
            logger=self.logger,
        )

        def _connect_job():
            ok = self.client.connect_and_start()
            self.log_text.after(0, lambda: self._set_connected(ok))
        threading.Thread(target=_connect_job, daemon=True).start()

    def _on_publish(self):
        if not self.client or not self.client.registered:
            messagebox.showwarning("Not Connected", "Please connect to the server first")
            return

        lname = filedialog.askopenfilename(title="Select file to publish")
        if not lname:
            return
        fname = simpledialog.askstring("Publish As", "Shared filename (fname):", initialvalue=os.path.basename(lname))
        if not fname:
            return

        def _pub_job():
            ok = self.client.publish_file(lname, fname)
            if ok:
                self._refresh_shared_list()
        threading.Thread(target=_pub_job, daemon=True).start()

    def _on_fetch(self):
        if not self.client or not self.client.registered:
            messagebox.showwarning("Not Connected", "Please connect to the server first")
            return
        fname = self.fetch_name_var.get().strip()
        if not fname:
            messagebox.showinfo("Input Needed", "Enter a filename to fetch")
            return

        def _fetch_job():
            peers = self.client.fetch_peers(fname)
            self.results_list.after(0, self._fill_results, peers)
        threading.Thread(target=_fetch_job, daemon=True).start()

    def _on_download(self):
        if not self.client or not self.client.registered:
            messagebox.showwarning("Not Connected", "Please connect to the server first")
            return
        fname = self.fetch_name_var.get().strip()
        if not fname:
            messagebox.showinfo("Input Needed", "Enter a filename to fetch")
            return
        sel = self.results_list.curselection()
        if not sel:
            messagebox.showinfo("Select Peer", "Choose a peer in search results")
            return
        idx = sel[0]
        line = self.results_list.get(idx)
        try:
            host_part = line.split(" (")[0].strip()
            addr_part = line.split("(")[-1].rstrip(")").strip()
            ip, port_s = addr_part.split(":")
            port = int(port_s)
        except Exception:
            messagebox.showerror("Parse Error", "Could not parse selected peer address")
            return

        self.progress.configure(value=0, maximum=100)

        def progress_cb(done, total):
            pct = 0 if total <= 0 else (done / total) * 100.0
            self.progress.after(0, lambda: self.progress.configure(value=pct))

        def _dl_job():
            ok = self.client.download_from_peer_with_progress(ip, port, fname, progress_cb)
            if ok:
                self.logger(f"Downloaded '{fname}' to {self.client.shared_folder}")
                try:
                    self.client.publish_file(os.path.join(self.client.shared_folder, fname), fname)
                except Exception:
                    pass
                self._refresh_shared_list()
            else:
                self.logger(f"Failed to download '{fname}' from {host_part}")
        threading.Thread(target=_dl_job, daemon=True).start()
    
    def _on_get_clients(self):
        """Get list of all connected clients from server"""
        if not self.client or not self.client.registered:
            messagebox.showwarning("Not Connected", "Please connect to the server first")
            return
        
        def _get_clients_job():
            clients = self.client.get_client_list()
            self.client_list.after(0, self._fill_client_list, clients)
        threading.Thread(target=_get_clients_job, daemon=True).start()
    
    def _on_client_selected(self, event):
        """Handle client selection from the list"""
        if not self.client or not self.client.registered:
            return
        
        sel = self.client_list.curselection()
        if not sel:
            return
        
        idx = sel[0]
        client_hostname = self.client_list.get(idx)
        
        def _get_files_job():
            files = self.client.get_client_files(client_hostname)
            self.client_files_list.after(0, self._fill_client_files, files, client_hostname)
        threading.Thread(target=_get_files_job, daemon=True).start()
    
    def _on_client_file_double_click(self, event):
        """Handle double-click on a file in client's file list"""
        if not self.client or not self.client.registered:
            return
        
        sel = self.client_files_list.curselection()
        if not sel:
            return
        
        idx = sel[0]
        filename = self.client_files_list.get(idx)
        
        # Auto-fill the fetch field and trigger fetch
        self.fetch_name_var.set(filename)
        self._on_fetch()

    def _set_connected(self, ok: bool):
        if ok:
            self.status_var.set("Connected")
            self.connect_btn.configure(state=tk.DISABLED)
            self._refresh_shared_list()
        else:
            self.status_var.set("Error: see log")

    def _refresh_shared_list(self):
        if not self.client:
            return
        self.shared_list.delete(0, tk.END)
        try:
            for item in sorted(os.listdir(self.client.shared_folder)):
                p = os.path.join(self.client.shared_folder, item)
                if os.path.isfile(p):
                    self.shared_list.insert(tk.END, item)
        except Exception:
            pass

    def _fill_results(self, peers):
        self.results_list.delete(0, tk.END)
        if not peers:
            self.results_list.insert(tk.END, "(no peers found)")
            return
        for p in peers:
            self.results_list.insert(tk.END, f"{p['hostname']} ({p['ip']}:{p['port']})")
    
    def _fill_client_list(self, clients):
        """Fill the client list with active clients"""
        self.client_list.delete(0, tk.END)
        self.client_files_list.delete(0, tk.END)
        if not clients:
            self.client_list.insert(tk.END, "(no clients found)")
            return
        for client_hostname in clients:
            # Don't show our own hostname
            if self.client and client_hostname != self.client.hostname:
                self.client_list.insert(tk.END, client_hostname)
    
    def _fill_client_files(self, files, client_hostname):
        """Fill the client files list with files from selected client"""
        self.client_files_list.delete(0, tk.END)
        if files is None:
            self.client_files_list.insert(tk.END, f"(client '{client_hostname}' not found)")
            return
        if not files:
            self.client_files_list.insert(tk.END, "(no files shared)")
            return
        for filename in files:
            self.client_files_list.insert(tk.END, filename)


if __name__ == "__main__":
    app = ClientGUI()
    app.mainloop()
