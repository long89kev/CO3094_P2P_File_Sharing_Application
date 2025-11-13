import streamlit as st
import os
import threading
import time
from datetime import datetime
from client import P2PClient

# Page configuration
st.set_page_config(
    page_title="P2P File Sharing",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        font-weight: 600;
        color: #2c3e50;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
    }
    .file-card {
        background-color: #1d2d3d;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #1f77b4;
        margin-bottom: 0.5rem;
    }
    .client-card {
        background-color: #1d2d3d;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #17a2b8;
        margin-bottom: 0.5rem;
    }
    .success-card {
        background-color: #d4edda;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #28a745;
        margin-bottom: 0.5rem;
    }
    .info-badge {
        background-color: #17a2b8;
        color: white;
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-size: 0.85rem;
        font-weight: bold;
    }
    .warning-badge {
        background-color: #ffc107;
        color: #212529;
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-size: 0.85rem;
        font-weight: bold;
    }
    .stButton>button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'client' not in st.session_state:
    st.session_state.client = None
    st.session_state.connected = False
    st.session_state.logs = []
    st.session_state.file_owners_cache = {}
    st.session_state.selected_client = None
    st.session_state.client_files = []
    st.session_state.search_results = []
    st.session_state.last_refresh = None

# Logger function
def add_log(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.logs.append(f"[{timestamp}] {message}")
    if len(st.session_state.logs) > 100:
        st.session_state.logs.pop(0)

# Connection sidebar
with st.sidebar:
    st.markdown('<div class="main-header">P2P File Sharing</div>', unsafe_allow_html=True)
    st.markdown("---")
    
    st.subheader("Connection Settings")
    
    server_ip = st.text_input("Server IP", value="127.0.0.1", key="server_ip")
    server_port = st.number_input("Server Port", value=8000, min_value=1, max_value=65535, key="server_port")
    
    st.markdown("---")
    
    hostname = st.text_input("Your Hostname", value="client1", key="hostname")
    p2p_port = st.number_input("Your P2P Port", value=9001, min_value=1024, max_value=65535, key="p2p_port")
    
    st.markdown("---")
    
    if not st.session_state.connected:
        if st.button("🔌 Connect to Server", type="primary"):
            shared_folder = os.path.join(os.getcwd(), "shared_files", hostname)
            os.makedirs(shared_folder, exist_ok=True)
            
            st.session_state.client = P2PClient(
                hostname=hostname,
                server_host=server_ip,
                server_port=int(server_port),
                p2p_port=int(p2p_port),
                shared_folder=shared_folder,
                logger=add_log,
            )
            
            with st.spinner("Connecting..."):
                ok = st.session_state.client.connect_and_start()
                if ok:
                    st.session_state.connected = True
                    add_log("Successfully connected to server")
                    st.success("Connected!")
                    st.rerun()
                else:
                    add_log("Failed to connect to server")
                    st.error("Connection failed. Check logs.")
    else:
        st.success(f"Connected as **{st.session_state.client.hostname}**")

        if st.button("🔌 Disconnect", type="secondary"):
            if st.session_state.client:
                st.session_state.client.shutdown()
            st.session_state.client = None
            st.session_state.connected = False
            st.session_state.file_owners_cache = {}
            add_log("Disconnected from server")
            st.rerun()
    
    st.markdown("---")
    st.caption(f"📁 Shared folder: `{st.session_state.client.shared_folder if st.session_state.client else 'Not connected'}`")

# Main content area
if not st.session_state.connected:
    st.markdown('<div class="main-header">Welcome to P2P File Sharing! 🚀</div>', unsafe_allow_html=True)
    st.info("👈 Please connect to the server using the sidebar to get started.")
    
    # st.markdown("### 🌟 Features")
    # col1, col2, col3 = st.columns(3)
    
    # with col1:
    #     st.markdown("""
    #     #### 📤 Share Files
    #     - Upload files easily
    #     - Auto-publish on connect
    #     - Track file availability
    #     """)
    
    # with col2:
    #     st.markdown("""
    #     #### 🔍 Browse Network
    #     - View all clients
    #     - See their files
    #     - Direct downloads
    #     """)
    
    # with col3:
    #     st.markdown("""
    #     #### 📊 Real-time Updates
    #     - Live connection status
    #     - Progress tracking
    #     - Activity logs
    #     """)
else:
    # Create tabs for different sections
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📁 My Files", 
        "👥 Network Clients", 
        "🔍 Search & Download",
        "📤 Upload Files",
        "📋 Activity Log"
    ])
    
    # Tab 1: My Files
    with tab1:
        st.markdown('<div class="sub-header">📁 My Shared Files</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.info(f"Folder: `{st.session_state.client.shared_folder}`")
        with col2:
            if st.button("Refresh Files", key="refresh_files"):
                st.rerun()
        
        st.markdown("---")
        
        # Display shared files
        try:
            files = sorted([f for f in os.listdir(st.session_state.client.shared_folder) 
                          if os.path.isfile(os.path.join(st.session_state.client.shared_folder, f))])
            
            if files:
                # Check availability button
                if st.button("🌐 Check File Availability on Network", key="check_availability"):
                    with st.spinner("Checking file availability..."):
                        for filename in files:
                            peers = st.session_state.client.fetch_peers(filename)
                            if peers:
                                st.session_state.file_owners_cache[filename] = [p['hostname'] for p in peers]
                        add_log(f"Checked availability for {len(files)} files")
                        st.success("✅ File availability updated!")
                        st.rerun()
                
                st.markdown("---")
                
                for filename in files:
                    filepath = os.path.join(st.session_state.client.shared_folder, filename)
                    filesize = os.path.getsize(filepath)
                    size_str = f"{filesize:,} bytes" if filesize < 1024 else f"{filesize/1024:.1f} KB" if filesize < 1024*1024 else f"{filesize/(1024*1024):.1f} MB"
                    
                    # Check if we have availability info
                    availability = ""
                    if filename in st.session_state.file_owners_cache:
                        owners = st.session_state.file_owners_cache[filename]
                        if len(owners) > 1:
                            availability = f'<span class="info-badge">{len(owners)} clients</span>'
                    
                    st.markdown(f"""
                    <div class="file-card">
                        <strong>📄 {filename}</strong> {availability}<br>
                        <small>Size: {size_str}</small>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Show which clients have this file
                    if filename in st.session_state.file_owners_cache:
                        with st.expander(f"View clients with '{filename}'"):
                            owners = st.session_state.file_owners_cache[filename]
                            for owner in owners:
                                if owner != st.session_state.client.hostname:
                                    st.markdown(f"✓ **{owner}**")
                                else:
                                    st.markdown(f"✓ **{owner}** (You)")
            else:
                st.warning("No files in your shared folder yet. Upload files in the '📤 Upload Files' tab!")
        except Exception as e:
            st.error(f"Error listing files: {e}")
    
    # Tab 2: Network Clients
    with tab2:
        st.markdown('<div class="sub-header">👥 Connected Clients</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.info("Browse files from other clients on the network")
        with col2:
            if st.button("🔄 Refresh Clients", key="refresh_clients"):
                with st.spinner("Fetching client list..."):
                    clients = st.session_state.client.get_client_list()
                    add_log(f"Found {len(clients)} clients on network")
                    st.rerun()
        
        st.markdown("---")
        
        # Get client list
        clients = st.session_state.client.get_client_list()
        other_clients = [c for c in clients if c != st.session_state.client.hostname]
        
        if other_clients:
            for client_hostname in other_clients:
                st.markdown(f"""
                <div class="client-card">
                    <strong>👤 {client_hostname}</strong>
                </div>
                """, unsafe_allow_html=True)
                
                # Button to view files
                if st.button(f"📂 View files from {client_hostname}", key=f"view_{client_hostname}"):
                    with st.spinner(f"Loading files from {client_hostname}..."):
                        files = st.session_state.client.get_client_files(client_hostname)
                        st.session_state.selected_client = client_hostname
                        st.session_state.client_files = files if files else []
                        add_log(f"Loaded {len(st.session_state.client_files)} files from {client_hostname}")
                
                # Show files if this client is selected
                if st.session_state.selected_client == client_hostname and st.session_state.client_files:
                    with st.expander(f"📁 Files from {client_hostname} ({len(st.session_state.client_files)} files)", expanded=True):
                        for filename in st.session_state.client_files:
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.markdown(f"📄 **{filename}**")
                            with col2:
                                if st.button("⬇️ Download", key=f"dl_{client_hostname}_{filename}"):
                                    st.session_state.search_file = filename
                                    st.info(f"Go to '🔍 Search & Download' tab to download '{filename}'")
                                    add_log(f"Selected {filename} for download")
        else:
            st.warning("👥 No other clients connected. Try refreshing!")
    
    # Tab 3: Search & Download
    with tab3:
        st.markdown('<div class="sub-header">🔍 Search & Download Files</div>', unsafe_allow_html=True)
        
        # Search box
        col1, col2 = st.columns([3, 1])
        with col1:
            search_file = st.text_input("Enter filename to search:", key="search_file_input", 
                                       value=st.session_state.get('search_file', ''))
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            search_btn = st.button("🔍 Search", type="primary", key="search_btn")
        
        if search_btn and search_file:
            with st.spinner(f"Searching for '{search_file}'..."):
                peers = st.session_state.client.fetch_peers(search_file)
                st.session_state.search_results = peers
                if peers:
                    st.session_state.file_owners_cache[search_file] = [p['hostname'] for p in peers]
                    add_log(f"Found {len(peers)} peer(s) with '{search_file}'")
                else:
                    add_log(f"No peers found with '{search_file}'")
                st.rerun()
        
        st.markdown("---")
        
        # Display search results
        if st.session_state.search_results:
            st.success(f"✅ Found {len(st.session_state.search_results)} peer(s) with '{search_file}'")
            
            for i, peer in enumerate(st.session_state.search_results, 1):
                st.markdown(f"""
                <div class="success-card">
                    <strong>Peer {i}: {peer['hostname']}</strong><br>
                    <small>📍 Address: {peer['ip']}:{peer['port']}</small>
                </div>
                """, unsafe_allow_html=True)
                
                # Download button
                if st.button(f"⬇️ Download from {peer['hostname']}", key=f"download_{i}_{peer['hostname']}"):
                    progress_bar = st.progress(0, text="Starting download...")
                    status_text = st.empty()
                    
                    def progress_callback(done, total):
                        if total > 0:
                            pct = int((done / total) * 100)
                            progress_bar.progress(pct, text=f"Downloading... {pct}%")
                    
                    with st.spinner(f"Downloading '{search_file}' from {peer['hostname']}..."):
                        ok = st.session_state.client.download_from_peer_with_progress(
                            peer['ip'], peer['port'], search_file, progress_callback
                        )
                        
                        if ok:
                            add_log(f"✅ Successfully downloaded '{search_file}' from {peer['hostname']}")
                            status_text.success(f"✅ Downloaded '{search_file}' successfully!")
                            
                            # Try to publish the downloaded file
                            try:
                                filepath = os.path.join(st.session_state.client.shared_folder, search_file)
                                st.session_state.client.publish_file(filepath, search_file)
                                add_log(f"📤 Published '{search_file}' to network")
                            except Exception as e:
                                add_log(f"⚠️ Could not publish downloaded file: {e}")
                            
                            time.sleep(1)
                            st.rerun()
                        else:
                            add_log(f"❌ Failed to download '{search_file}' from {peer['hostname']}")
                            status_text.error(f"❌ Download failed. Check logs.")
                
                st.markdown("<br>", unsafe_allow_html=True)
        elif hasattr(st.session_state, 'search_file') and st.session_state.search_file:
            st.warning(f"❌ No peers found with '{st.session_state.search_file}'. Try a different filename.")
    
    # Tab 4: Upload Files
    with tab4:
        st.markdown('<div class="sub-header">📤 Upload & Publish Files</div>', unsafe_allow_html=True)
        st.info("Upload files to your shared folder and publish them to the network")
        
        uploaded_files = st.file_uploader(
            "Choose files to upload and share",
            accept_multiple_files=True,
            key="file_uploader"
        )
        
        if uploaded_files:
            st.markdown("---")
            st.subheader("📋 Files to upload:")
            
            for uploaded_file in uploaded_files:
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    st.markdown(f"📄 **{uploaded_file.name}**")
                with col2:
                    size = len(uploaded_file.getvalue())
                    size_str = f"{size:,} bytes" if size < 1024 else f"{size/1024:.1f} KB" if size < 1024*1024 else f"{size/(1024*1024):.1f} MB"
                    st.caption(f"Size: {size_str}")
                with col3:
                    st.caption("✓ Ready")
            
            st.markdown("---")
            
            if st.button("📤 Upload & Publish All Files", type="primary", key="upload_publish"):
                progress_bar = st.progress(0, text="Uploading files...")
                
                for i, uploaded_file in enumerate(uploaded_files):
                    # Save file
                    filepath = os.path.join(st.session_state.client.shared_folder, uploaded_file.name)
                    with open(filepath, "wb") as f:
                        f.write(uploaded_file.getvalue())
                    
                    # Publish file
                    ok = st.session_state.client.publish_file(filepath, uploaded_file.name)
                    
                    if ok:
                        add_log(f"✅ Uploaded and published: {uploaded_file.name}")
                    else:
                        add_log(f"⚠️ Uploaded but failed to publish: {uploaded_file.name}")
                    
                    progress_bar.progress((i + 1) / len(uploaded_files), 
                                        text=f"Processing {i+1}/{len(uploaded_files)}...")
                
                st.success(f"✅ Successfully uploaded {len(uploaded_files)} file(s)!")
                add_log(f"Uploaded {len(uploaded_files)} files to shared folder")
                time.sleep(1)
                st.rerun()
    
    # Tab 5: Activity Log
    with tab5:
        st.markdown('<div class="sub-header">📋 Activity Log</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.info(f"Showing last {len(st.session_state.logs)} activities")
        with col2:
            if st.button("🗑️ Clear Log", key="clear_log"):
                st.session_state.logs = []
                st.rerun()
        
        st.markdown("---")
        
        # Display logs in reverse order (newest first)
        if st.session_state.logs:
            log_container = st.container()
            with log_container:
                for log in reversed(st.session_state.logs[-50:]):  # Show last 50 logs
                    # Color code based on content
                    if "✅" in log or "Successfully" in log:
                        st.success(log)
                    elif "❌" in log or "Failed" in log or "Error" in log:
                        st.error(log)
                    elif "⚠️" in log or "Warning" in log:
                        st.warning(log)
                    else:
                        st.info(log)
        else:
            st.caption("No activity yet. Interact with the application to see logs here.")

# Footer
st.markdown("---")
st.caption("🔄 P2P File Sharing Application | Built with Streamlit | 2025")

# Auto-refresh every 30 seconds when connected
if st.session_state.connected:
    time.sleep(0.1)  # Small delay to prevent too frequent updates
