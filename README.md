# P2P File Sharing System

A centralized-hybrid peer-to-peer (P2P) file sharing application implemented in Python which is a project of **Computer Networking course (CO3094)**. The system uses a central server to track file locations while enabling direct peer-to-peer file transfers.

## System Architecture

### Overview
- **Central Server**: Tracks which files are available on which clients, but does not store the files themselves
- **Clients**: Register with the server, publish files they want to share, and download files directly from other peers
- **P2P Transfers**: File transfers happen directly between clients without going through the server

### Components

1. **server.py** - Central tracking server
2. **client.py** - P2P client application
3. **protocol.py** - Protocol definitions and helper functions

### Server Command Protocol

Commands entered directly on the server:

- **discover <hostname>**: List all files shared by a specific client
- **ping <hostname>**: Check if a specific client is still connected
- **list**: Show all registered clients
- **files**: Show all available files and their locations
- **quit**: Shutdown the server

### Peer-to-Peer Protocol (TCP)

Direct file transfer between clients:

```
Client A → Client B: DOWNLOAD <filename>
Client B → Client A: FILESIZE <bytes>
Client A → Client B: BEGIN_DOWNLOAD
Client B → Client A: <binary file data>
```
## Installation & Requirements

### Requirements
- Python 3.6 or higher
- No external dependencies (uses only standard library)

### Setup
```bash
# Clone or download the project
cd P2P_FileSharing

# Create shared folders for testing (optional)
mkdir -p shared_files/client1
mkdir -p shared_files/client2
mkdir -p shared_files/client3
```
## Usage Guide

### 1. Start the Central Server

```bash
python server.py <port>
```
Example:
```bash
python server.py 8000
```

### 2. Run the GUI Client (Recommended)

```bash
python client_gui.py
```
In the GUI:
- Enter Server IP, Server Port, your Hostname, and your P2P Port
- Click Connect to REGISTER and start your P2P listener
- Use "Publish New File..." to share files
- Type a filename and click Fetch to see peers
- Select a peer and click "Download from Selected Peer" to download

The System Log panel shows all actions and responses.

### 3. Start Client(s) (CLI)

Open new terminal windows for each client:

```bash
python client.py <hostname> <server_host> <server_port> <p2p_port> <shared_folder>
```

Examples:
```bash
# Terminal 1 - Client 1
python client.py client1 localhost 8000 9001 ./shared_files/client1

# Terminal 2 - Client 2
python client.py client2 localhost 8000 9002 ./shared_files/client2

# Terminal 3 - Client 3
python client.py client3 localhost 8000 9003 ./shared_files/client3
```

Parameters:
- `hostname`: Unique identifier for this client
- `server_host`: IP/hostname of the central server
- `server_port`: Port the central server is listening on
- `p2p_port`: Port this client will listen on for peer connections
- `shared_folder`: Directory where shared files are stored

## Project Structure

```
P2P_FileSharing/
├── server.py           # Central tracking server
├── client.py           # P2P client implementation
├── protocol.py         # Protocol definitions
├── client_gui.py       # Full GUI implementation
├── README.md           # This file
└── shared_files/       # Directory for shared files
    ├── client1/        # Client 1's shared folder
    ├── client2/        # Client 2's shared folder
    └── client3/        # Client 3's shared folder
```
### Client Commands Cheat Sheet

| Command | Description | Example |
|---------|-------------|---------|
| `publish <local> <shared>` | Share a file | `publish test.txt test.txt` |
| `fetch <filename>` | Download a file | `fetch test.txt` |
| `list` | List local files | `list` |
| `quit` | Exit client | `quit` |

### Server Commands Cheat Sheet

| Command | Description | Example |
|---------|-------------|---------|
| `discover <hostname>` | Show client's files | `discover client1` |
| `ping <hostname>` | Check client status | `ping client1` |
| `list` | Show all clients | `list` |
| `files` | Show all files | `files` |
| `quit` | Shutdown server | `quit` |
