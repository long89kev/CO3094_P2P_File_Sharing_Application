import socket
import threading
import sys
import os
from datetime import datetime

class P2PClient:
    BUFFER_SIZE = 4096
    
    def __init__(self, hostname, server_host, server_port, p2p_port, shared_folder, logger=None):
        self.hostname = hostname
        self.server_host = server_host
        self.server_port = server_port
        self.p2p_port = p2p_port
        self.shared_folder = shared_folder
        
        self.server_socket = None
        self.p2p_server_socket = None
        self.registered = False
        self._p2p_thread = None
        self._logger = logger  
        
        # Ensure shared folder exists
        if not os.path.exists(shared_folder):
            os.makedirs(shared_folder)
            self._log(f"Created shared folder: {shared_folder}")
    
    def start(self):
        try:
            if not self.connect_to_server():
                return
            self.start_p2p_listener()
            self.command_interface()
        except KeyboardInterrupt:
            self._log("Client shutting down...")
        finally:
            self.shutdown()

    def connect_and_start(self):
        if not self.connect_to_server():
            return False
        self.start_p2p_listener()
        return True

    def start_p2p_listener(self):
        if self._p2p_thread and self._p2p_thread.is_alive():
            return
        self._p2p_thread = threading.Thread(target=self.p2p_server, daemon=True)
        self._p2p_thread.start()

    def shutdown(self):
        try:
            if self.server_socket:
                self.server_socket.close()
        except Exception:
            pass
        try:
            if self.p2p_server_socket:
                self.p2p_server_socket.close()
        except Exception:
            pass
    
    def connect_to_server(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.connect((self.server_host, self.server_port))
            self._log(f"Connected to server at {self.server_host}:{self.server_port}")
            
            # Send registration message
            message = f"REGISTER {self.hostname} {self.p2p_port}"
            self.server_socket.send(message.encode('utf-8'))
            
            # Receive response
            response = self.server_socket.recv(self.BUFFER_SIZE).decode('utf-8')
            self._log(f"Server response: {response}")
            
            if "REGISTER_SUCCESS" in response:
                self.registered = True
                self._log(f"Successfully registered as '{self.hostname}'")
                # Auto-publish all files in shared folder
                self.auto_publish_files()
                return True
            else:
                self._log("Registration failed")
                return False
                
        except Exception as e:
            self._log(f"Error connecting to server: {e}")
            return False
    
    def p2p_server(self):
        try:
            self.p2p_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.p2p_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.p2p_server_socket.bind(('', self.p2p_port))
            self.p2p_server_socket.listen(5)
            
            self._log(f"P2P server listening on port {self.p2p_port}")
            
            while True:
                peer_socket, peer_address = self.p2p_server_socket.accept()
                self._log(f"Peer connection from {peer_address}")
                
                # Handle each peer in a separate thread
                peer_thread = threading.Thread(
                    target=self.handle_peer_download,
                    args=(peer_socket, peer_address),
                    daemon=True
                )
                peer_thread.start()
                
        except Exception as e:
            self._log(f"P2P server error: {e}")
    
    def handle_peer_download(self, peer_socket, peer_address):
        try:
            # Receive download request
            request = peer_socket.recv(self.BUFFER_SIZE).decode('utf-8').strip()
            self._log(f"Received from peer: {request}")
            
            if not request.startswith("DOWNLOAD"):
                peer_socket.send("ERROR Invalid request".encode('utf-8'))
                return
            
            # Extract filename
            parts = request.split()
            if len(parts) < 2:
                peer_socket.send("ERROR No filename specified".encode('utf-8'))
                return
            
            filename = parts[1]
            filepath = os.path.join(self.shared_folder, filename)
            
            # Check if file exists
            if not os.path.exists(filepath):
                peer_socket.send("ERROR File not found".encode('utf-8'))
                self._log(f"File not found: {filename}")
                return
            
            # Send file size
            filesize = os.path.getsize(filepath)
            peer_socket.send(f"FILESIZE {filesize}".encode('utf-8'))
            self._log(f"Sending file '{filename}' ({filesize} bytes)")
            
            # Wait for acknowledgment
            ack = peer_socket.recv(self.BUFFER_SIZE).decode('utf-8').strip()
            if ack != "BEGIN_DOWNLOAD":
                self._log("Download cancelled by peer")
                return
            
            # Send file data
            with open(filepath, 'rb') as f:
                sent = 0
                while True:
                    data = f.read(self.BUFFER_SIZE)
                    if not data:
                        break
                    peer_socket.send(data)
                    sent += len(data)
            
            self._log(f"File transfer complete: {sent} bytes sent")
            
        except Exception as e:
            self._log(f"Error handling peer download: {e}")
        finally:
            peer_socket.close()
    
    def command_interface(self):
        self._log("=== P2P File Sharing Client ===")
        self._log(f"Hostname: {self.hostname}")
        self._log(f"Shared folder: {self.shared_folder}")
        self._log("Available commands: publish, fetch, list, quit")
        
        while True:
            try:
                command = input(f"{self.hostname}> ").strip()
                if not command:
                    continue
                
                parts = command.split()
                cmd = parts[0].lower()
                
                if cmd == "publish":
                    if len(parts) < 3:
                        print("Usage: publish <local_filename> <shared_filename>")
                        continue
                    local_filename = parts[1]
                    shared_filename = parts[2]
                    self.publish_file(local_filename, shared_filename)
                    
                elif cmd == "fetch":
                    if len(parts) < 2:
                        print("Usage: fetch <filename>")
                        continue
                    filename = parts[1]
                    self.fetch_file(filename)
                    
                elif cmd == "list":
                    self.list_local_files()
                    
                elif cmd == "quit":
                    self._log("Goodbye!")
                    break
                    
                else:
                    print(f"Unknown command: {cmd}")
                    
            except Exception as e:
                self._log(f"Error: {e}")
    
    def publish_file(self, local_filename, shared_filename):
        try:
            # Check if file exists in shared folder or copy it there
            source_path = local_filename
            dest_path = os.path.join(self.shared_folder, shared_filename)
            
            if not os.path.exists(source_path):
                # Maybe it's already in shared folder
                source_path = os.path.join(self.shared_folder, local_filename)
                if not os.path.exists(source_path):
                    print(f"Error: File '{local_filename}' not found")
                    return
            
            # Copy file to shared folder if not already there
            if os.path.abspath(source_path) != os.path.abspath(dest_path):
                import shutil
                shutil.copy2(source_path, dest_path)
                self._log(f"Copied '{local_filename}' to shared folder as '{shared_filename}'")
            
            # Send publish message to server
            message = f"PUBLISH {shared_filename} {self.hostname}"
            self.server_socket.send(message.encode('utf-8'))
            
            # Receive response
            response = self.server_socket.recv(self.BUFFER_SIZE).decode('utf-8')
            self._log(response)
            return response.startswith("PUBLISH_SUCCESS")
            
        except Exception as e:
            self._log(f"Error publishing file: {e}")
            return False
    
    def auto_publish_files(self):
        """Automatically publish all files in the shared folder"""
        try:
            files = os.listdir(self.shared_folder)
            for filename in files:
                filepath = os.path.join(self.shared_folder, filename)
                if os.path.isfile(filepath):
                    message = f"PUBLISH {filename} {self.hostname}"
                    self.server_socket.send(message.encode('utf-8'))
                    response = self.server_socket.recv(self.BUFFER_SIZE).decode('utf-8')
                    if response.startswith("PUBLISH_SUCCESS"):
                        self._log(f"Auto-published: {filename}")
                    else:
                        self._log(f"Failed to auto-publish: {filename}")
        except Exception as e:
            self._log(f"Error auto-publishing files: {e}")
    
    def fetch_file(self, filename):
        try:
            # Send fetch request to server
            message = f"FETCH {filename}"
            self.server_socket.send(message.encode('utf-8'))
            
            # Receive response
            response = self.server_socket.recv(self.BUFFER_SIZE).decode('utf-8').strip()
            self._log(response)
            
            if response.startswith("FETCH_NOT_FOUND"):
                self._log(f"File '{filename}' not available on network")
                return
            
            if not response.startswith("FETCH_OK"):
                self._log("Error fetching file")
                return
            
            # Parse peer list
            parts = response.split()
            if len(parts) < 2:
                self._log("No peers available")
                return
            
            peers = parts[1:]  # List of "ip:port:hostname"
            self._log(f"Found {len(peers)} peer(s) with the file")
            
            # Try to download from first available peer
            for peer_info in peers:
                peer_parts = peer_info.split(':')
                if len(peer_parts) < 3:
                    continue
                
                peer_ip = peer_parts[0]
                peer_port = int(peer_parts[1])
                peer_hostname = peer_parts[2]
                
                self._log(f"Attempting download from {peer_hostname} ({peer_ip}:{peer_port})")
                
                if self.download_from_peer(peer_ip, peer_port, filename):
                    self._log(f"Successfully downloaded '{filename}'")
                    return
                else:
                    self._log(f"Failed to download from {peer_hostname}, trying next peer...")
            
            self._log("Failed to download file from any peer")
            
        except Exception as e:
            self._log(f"Error fetching file: {e}")
    
    def download_from_peer(self, peer_ip, peer_port, filename):
        peer_socket = None
        try:
            # Connect to peer
            peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_socket.connect((peer_ip, peer_port))
            
            # Send download request
            message = f"DOWNLOAD {filename}"
            peer_socket.send(message.encode('utf-8'))
            
            # Receive file size
            response = peer_socket.recv(self.BUFFER_SIZE).decode('utf-8').strip()
            
            if response.startswith("ERROR"):
                self._log(f"Peer error: {response}")
                return False
            
            if not response.startswith("FILESIZE"):
                self._log(f"Unexpected response: {response}")
                return False
            
            filesize = int(response.split()[1])
            self._log(f"File size: {filesize} bytes")
            
            # Send acknowledgment
            peer_socket.send("BEGIN_DOWNLOAD".encode('utf-8'))
            
            # Receive file data
            filepath = os.path.join(self.shared_folder, filename)
            received = 0
            
            with open(filepath, 'wb') as f:
                while received < filesize:
                    data = peer_socket.recv(self.BUFFER_SIZE)
                    if not data:
                        break
                    f.write(data)
                    received += len(data)
            
            if received == filesize:
                self._log(f"Download complete: {received} bytes")
                return True
            else:
                self._log(f"Download incomplete: {received}/{filesize} bytes")
                return False
                
        except Exception as e:
            self._log(f"Error downloading from peer: {e}")
            return False
        finally:
            if peer_socket:
                peer_socket.close()

    def fetch_peers(self, filename):
        try:
            message = f"FETCH {filename}"
            self.server_socket.send(message.encode('utf-8'))
            response = self.server_socket.recv(self.BUFFER_SIZE).decode('utf-8').strip()
            if not response.startswith("FETCH_OK"):
                return []
            parts = response.split()
            peers = []
            for p in parts[1:]:
                s = p.split(":")
                # Format: ip:port:hostname:owner_flag
                if len(s) >= 4:
                    peers.append({
                        "ip": s[0], 
                        "port": int(s[1]), 
                        "hostname": s[2],
                        "is_owner": s[3] == "1"
                    })
                elif len(s) >= 3:
                    # Backward compatibility
                    peers.append({
                        "ip": s[0], 
                        "port": int(s[1]), 
                        "hostname": s[2],
                        "is_owner": False
                    })
            return peers
        except Exception:
            return []
    
    def get_client_list(self):
        """Get list of all active clients from server"""
        try:
            message = "LIST_CLIENTS"
            self.server_socket.send(message.encode('utf-8'))
            response = self.server_socket.recv(self.BUFFER_SIZE).decode('utf-8').strip()
            if not response.startswith("LIST_CLIENTS_OK"):
                return []
            parts = response.split()
            # parts[0] is "LIST_CLIENTS_OK", rest are client hostnames
            return parts[1:] if len(parts) > 1 else []
        except Exception as e:
            self._log(f"Error getting client list: {e}")
            return []
    
    def get_client_files(self, client_hostname):
        """Get list of files shared by a specific client with owner info"""
        try:
            message = f"DISCOVER_CLIENT {client_hostname}"
            self.server_socket.send(message.encode('utf-8'))
            response = self.server_socket.recv(self.BUFFER_SIZE).decode('utf-8').strip()
            if response.startswith("DISCOVER_CLIENT_NOT_FOUND"):
                return None
            if not response.startswith("DISCOVER_CLIENT_OK"):
                return []
            parts = response.split()
            # parts[0] is "DISCOVER_CLIENT_OK", rest are filename:owner_flag pairs
            files = []
            for item in parts[1:] if len(parts) > 1 else []:
                file_parts = item.split(":")
                if len(file_parts) >= 2:
                    files.append({
                        "filename": file_parts[0],
                        "is_owner": file_parts[1] == "1"
                    })
                else:
                    # Backward compatibility
                    files.append({
                        "filename": item,
                        "is_owner": False
                    })
            return files
        except Exception as e:
            self._log(f"Error getting client files: {e}")
            return []

    def download_from_peer_with_progress(self, peer_ip, peer_port, filename, progress_cb=None):
        peer_socket = None
        try:
            peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_socket.connect((peer_ip, peer_port))
            peer_socket.send(f"DOWNLOAD {filename}".encode("utf-8"))
            response = peer_socket.recv(self.BUFFER_SIZE).decode("utf-8").strip()
            if not response.startswith("FILESIZE"):
                return False
            filesize = int(response.split()[1])
            peer_socket.send("BEGIN_DOWNLOAD".encode("utf-8"))
            filepath = os.path.join(self.shared_folder, filename)
            received = 0
            with open(filepath, "wb") as f:
                while received < filesize:
                    chunk = peer_socket.recv(self.BUFFER_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)
                    if progress_cb:
                        try:
                            progress_cb(received, filesize)
                        except Exception:
                            pass
            return received == filesize
        except Exception as e:
            self._log(f"Error downloading from peer: {e}")
            return False
        finally:
            try:
                if peer_socket:
                    peer_socket.close()
            except Exception:
                pass
    
    def list_local_files(self):
        try:
            files = os.listdir(self.shared_folder)
            self._log("Files in shared folder:")
            if not files:
                self._log("  (empty)")
            else:
                for f in files:
                    filepath = os.path.join(self.shared_folder, f)
                    if os.path.isfile(filepath):
                        size = os.path.getsize(filepath)
                        self._log(f"  - {f} ({size} bytes)")
        except Exception as e:
            self._log(f"Error listing files: {e}")
    
    def get_timestamp(self):
        return datetime.now().strftime("%H:%M:%S")

    def _log(self, msg: str):
        if self._logger:
            try:
                self._logger(f"[{self.get_timestamp()}] {msg}")
                return
            except Exception:
                # fallback to print if logger fails
                pass
        print(f"[{self.get_timestamp()}] {msg}")


if __name__ == "__main__":
    if len(sys.argv) != 6:
        print("Usage: python client.py <hostname> <server_host> <server_port> <p2p_port> <shared_folder>")
        print("Example: python client.py client1 localhost 8000 9001 ./shared_files/client1")
        sys.exit(1)
    
    hostname = sys.argv[1]
    server_host = sys.argv[2]
    server_port = int(sys.argv[3])
    p2p_port = int(sys.argv[4])
    shared_folder = sys.argv[5]
    
    try:
        client = P2PClient(hostname, server_host, server_port, p2p_port, shared_folder)
        client.start()
    except KeyboardInterrupt:
        print("\nClient shutdown")
        sys.exit(0)
