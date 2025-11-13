import socket
import threading
import sys
from datetime import datetime

class CentralServer:
    def __init__(self, port):
        self.port = port
        self.clients = {}  # {hostname: {'ip': '...', 'port': ..., 'socket': ..., 'active': True}}
        # Updated structure: {filename: {'owner': 'client1', 'holders': [hostname1, hostname2, ...]}}
        self.files = {}    
        self.lock = threading.Lock()  # Thread-safe access to shared data
        self.server_socket = None
        
    def start(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('', self.port))
            self.server_socket.listen(10)
            
            print(f"[{self.get_timestamp()}] Central Server started on port {self.port}")
            print(f"[{self.get_timestamp()}] Waiting for client connections...")
            print("\nAvailable server commands:")
            print("  - discover <hostname>  : List files shared by a client")
            print("  - ping <hostname>      : Check if a client is active")
            print("  - list                 : List all connected clients")
            print("  - files                : List all available files")
            print("  - quit                 : Shutdown the server\n")
            
            command_thread = threading.Thread(target=self.server_command_interface, daemon=True)
            command_thread.start()
            
            # Accept client connections
            while True:
                try:
                    client_socket, client_address = self.server_socket.accept()
                    print(f"[{self.get_timestamp()}] New connection from {client_address}")
                    
                    # Handle each client in a separate thread
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, client_address),
                        daemon=True
                    )
                    client_thread.start()
                    
                except Exception as e:
                    print(f"[{self.get_timestamp()}] Error accepting connection: {e}")
                    
        except Exception as e:
            print(f"[{self.get_timestamp()}] Server error: {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()
    
    def handle_client(self, client_socket, client_address):
        hostname = None
        try:
            while True:
                data = client_socket.recv(4096).decode('utf-8').strip()
                if not data:
                    break
                
                print(f"[{self.get_timestamp()}] Received: {data}")
                
                parts = data.split()
                command = parts[0]
                
                if command == "REGISTER":
                    hostname = parts[1]
                    p2p_port = int(parts[2])
                    response = self.handle_register(hostname, client_address[0], p2p_port, client_socket)
                    
                elif command == "PUBLISH":
                    filename = parts[1]
                    hostname = parts[2]
                    response = self.handle_publish(filename, hostname)
                    
                elif command == "FETCH":
                    filename = parts[1]
                    response = self.handle_fetch(filename)
                    
                elif command == "LIST_CLIENTS":
                    response = self.handle_list_clients()
                    
                elif command == "DISCOVER_CLIENT":
                    if len(parts) < 2:
                        response = "DISCOVER_CLIENT_NOT_FOUND"
                    else:
                        client_hostname = parts[1]
                        response = self.handle_discover_client(client_hostname)
                    
                else:
                    response = "UNKNOWN_COMMAND"
                
                client_socket.send(response.encode('utf-8'))
                print(f"[{self.get_timestamp()}] Sent: {response}")
                
        except Exception as e:
            print(f"[{self.get_timestamp()}] Error handling client {hostname}: {e}")
        finally:
            if hostname:
                self.handle_disconnect(hostname)
            client_socket.close()
    
    def handle_register(self, hostname, ip, port, client_socket):
        with self.lock:
            if hostname in self.clients:
                return "REGISTER_FAIL Hostname already exists"
            
            self.clients[hostname] = {
                'ip': ip,
                'port': port,
                'socket': client_socket,
                'active': True
            }
            
        print(f"[{self.get_timestamp()}] Client '{hostname}' registered at {ip}:{port}")
        return "REGISTER_SUCCESS"
    
    def handle_publish(self, filename, hostname):
        with self.lock:
            if hostname not in self.clients:
                return "PUBLISH_FAIL Client not registered"
            
            if filename not in self.files:
                # First time this file is published - set owner
                self.files[filename] = {
                    'owner': hostname,
                    'holders': [hostname]
                }
                print(f"[{self.get_timestamp()}] File '{filename}' published by '{hostname}' (ORIGINAL)")
            else:
                # File already exists, add this client as a holder if not already
                if hostname not in self.files[filename]['holders']:
                    self.files[filename]['holders'].append(hostname)
                    print(f"[{self.get_timestamp()}] File '{filename}' published by '{hostname}' (owner: {self.files[filename]['owner']})")
                else:
                    print(f"[{self.get_timestamp()}] File '{filename}' re-published by '{hostname}'")
            
        return "PUBLISH_SUCCESS"
    
    def handle_fetch(self, filename):
        with self.lock:
            if filename not in self.files or len(self.files[filename]['holders']) == 0:
                return "FETCH_NOT_FOUND"
            
            # Build list of peers with the file (include owner info)
            owner = self.files[filename]['owner']
            peers = []
            for hostname in self.files[filename]['holders']:
                if hostname in self.clients and self.clients[hostname]['active']:
                    client = self.clients[hostname]
                    # Format: ip:port:hostname:owner_flag (1 if owner, 0 if not)
                    owner_flag = "1" if hostname == owner else "0"
                    peers.append(f"{client['ip']}:{client['port']}:{hostname}:{owner_flag}")
            
            if not peers:
                return "FETCH_NOT_FOUND"
            
            return "FETCH_OK " + " ".join(peers)
    
    def handle_disconnect(self, hostname):
        with self.lock:
            if hostname in self.clients:
                self.clients[hostname]['active'] = False
                print(f"[{self.get_timestamp()}] Client '{hostname}' disconnected")
    
    def handle_list_clients(self):
        """Return list of all active clients"""
        with self.lock:
            active_clients = []
            for hostname, info in self.clients.items():
                if info['active']:
                    active_clients.append(hostname)
            
            if not active_clients:
                return "LIST_CLIENTS_OK"
            
            return "LIST_CLIENTS_OK " + " ".join(active_clients)
    
    def handle_discover_client(self, client_hostname):
        """Return list of files shared by a specific client (with owner info)"""
        with self.lock:
            if client_hostname not in self.clients:
                return "DISCOVER_CLIENT_NOT_FOUND"
            
            # Format: filename:owner_flag (1 if this client is owner, 0 if not)
            files = []
            for filename, file_info in self.files.items():
                if client_hostname in file_info['holders']:
                    owner_flag = "1" if client_hostname == file_info['owner'] else "0"
                    files.append(f"{filename}:{owner_flag}")
            
            if not files:
                return "DISCOVER_CLIENT_OK"
            
            return "DISCOVER_CLIENT_OK " + " ".join(files)
    
    def server_command_interface(self):
        while True:
            try:
                command = input().strip()
                if not command:
                    continue
                
                parts = command.split()
                cmd = parts[0].lower()
                
                if cmd == "discover":
                    if len(parts) < 2:
                        print("Usage: discover <hostname>")
                        continue
                    hostname = parts[1]
                    self.discover_files(hostname)
                    
                elif cmd == "ping":
                    if len(parts) < 2:
                        print("Usage: ping <hostname>")
                        continue
                    hostname = parts[1]
                    self.ping_client(hostname)
                    
                elif cmd == "list":
                    self.list_clients()
                    
                elif cmd == "files":
                    self.list_files()
                    
                elif cmd == "quit":
                    print(f"[{self.get_timestamp()}] Shutting down server...")
                    sys.exit(0)
                    
                else:
                    print(f"Unknown command: {cmd}")
                    
            except Exception as e:
                print(f"Error processing command: {e}")
    
    def discover_files(self, hostname):
        with self.lock:
            if hostname not in self.clients:
                print(f"Client '{hostname}' not found")
                return
            
            print(f"\nFiles shared by '{hostname}':")
            found = False
            for filename, file_info in self.files.items():
                if hostname in file_info['holders']:
                    owner_mark = " (ORIGINAL)" if hostname == file_info['owner'] else f" (from {file_info['owner']})"
                    print(f"  - {filename}{owner_mark}")
                    found = True
            
            if not found:
                print("  (no files)")
            print()
    
    def ping_client(self, hostname):
        with self.lock:
            if hostname not in self.clients:
                print(f"Client '{hostname}' not found")
                return
            
            status = "ACTIVE" if self.clients[hostname]['active'] else "INACTIVE"
            ip = self.clients[hostname]['ip']
            port = self.clients[hostname]['port']
            print(f"Client '{hostname}' at {ip}:{port} is {status}")
    
    def list_clients(self):
        with self.lock:
            print("\nRegistered Clients:")
            if not self.clients:
                print("  (none)")
            else:
                for hostname, info in self.clients.items():
                    status = "ACTIVE" if info['active'] else "INACTIVE"
                    print(f"  - {hostname} ({info['ip']}:{info['port']}) - {status}")
            print()
    
    def list_files(self):
        with self.lock:
            print("\nAvailable Files:")
            if not self.files:
                print("  (none)")
            else:
                for filename, file_info in self.files.items():
                    active_hosts = [h for h in file_info['holders'] if h in self.clients and self.clients[h]['active']]
                    owner = file_info['owner']
                    print(f"  - {filename} (owner: {owner}, available on: {', '.join(active_hosts) if active_hosts else 'none'})")
            print()
    
    def get_timestamp(self):
        """Get formatted timestamp"""
        return datetime.now().strftime("%H:%M:%S")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python server.py <port>")
        print("Example: python server.py 8000")
        sys.exit(1)
    
    try:
        port = int(sys.argv[1])
        server = CentralServer(port)
        server.start()
    except ValueError:
        print("Error: Port must be a number")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nServer shutdown")
        sys.exit(0)
