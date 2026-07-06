# === vybr_web.py ===
# VYBR - TikTok Live Tool - Render.com Optimized

import sys
import os
import json
import asyncio
import threading
import time
import re
import subprocess
from pathlib import Path

# === CHANGE DIRECTORY TO SCRIPT LOCATION ===
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# === AUTO INSTALL ===
def auto_install():
    pkgs = ['flask', 'flask-socketio', 'eventlet', 'requests', 'TikTokLive']
    for p in pkgs:
        try:
            if p == 'flask-socketio':
                __import__('flask_socketio')
            else:
                __import__(p)
        except ImportError:
            print(f"[*] Installing {p}...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', p, '--quiet'])

auto_install()

# === IMPORTS ===
from flask import Flask, render_template_string, request, jsonify
from flask_socketio import SocketIO, emit
import eventlet

# === GLOBALS ===
app = Flask(__name__)
app.config['SECRET_KEY'] = 'vybr-secret-key-2024'
app.config['SESSION_TYPE'] = 'filesystem'

# === SOCKETIO WITH RENDER.COM COMPATIBLE SETTINGS ===
socketio = SocketIO(
    app,
    cors_allowed_origins='*',
    async_mode='eventlet',
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1e6
)

connected = False
client_thread = None
comment_history = []
gift_history = []
follow_history = []
users = set()
blocked_words = []
active_username = None

# === HTML TEMPLATE ===
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>VYBR - TikTok Live Tool</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://cdn.socket.io/4.5.0/socket.io.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        :root {
            --bg: #080808;
            --bg-light: #0f0f0f;
            --card: #141414;
            --border: #1e1e1e;
            --text: #e8e8e8;
            --text-muted: #666;
            --primary: #6c5ce7;
            --secondary: #00cec9;
            --accent: #fd79a8;
            --comment-color: #74b9ff;
            --gift-color: #fdcb6e;
            --follow-color: #55efc4;
            --success: #00b894;
            --danger: #ff6b6b;
            --warning: #fdcb6e;
            --gradient1: linear-gradient(135deg, #6c5ce7, #00cec9);
            --gradient2: linear-gradient(135deg, #6c5ce7, #fd79a8);
        }
        body {
            font-family: 'Segoe UI', sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            overflow: hidden;
        }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: var(--primary); border-radius: 2px; }
        .app { display: flex; height: 100vh; padding: 12px; gap: 12px; }
        .sidebar {
            width: 440px;
            min-width: 440px;
            background: var(--card);
            border-radius: 16px;
            border: 1px solid var(--border);
            padding: 20px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 14px;
        }
        .logo {
            text-align: center;
            padding: 8px 0 12px 0;
            border-bottom: 1px solid var(--border);
        }
        .logo h1 {
            font-size: 34px;
            font-weight: 900;
            background: var(--gradient1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            letter-spacing: 6px;
        }
        .logo span {
            font-size: 10px;
            color: var(--text-muted);
            letter-spacing: 5px;
            text-transform: uppercase;
            font-weight: 300;
            display: block;
            margin-top: 2px;
            -webkit-text-fill-color: var(--text-muted);
        }
        .card {
            background: var(--bg-light);
            border-radius: 10px;
            border: 1px solid var(--border);
            padding: 16px;
        }
        .card-header {
            font-size: 11px;
            font-weight: 700;
            color: var(--primary);
            letter-spacing: 2px;
            text-transform: uppercase;
            margin-bottom: 10px;
        }
        .connection-input {
            width: 100%;
            padding: 12px 16px;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 10px;
            color: var(--text);
            font-size: 14px;
            outline: none;
        }
        .connection-input:focus { border-color: var(--primary); }
        .connection-input::placeholder { color: var(--text-muted); }
        .btn-primary {
            width: 100%;
            padding: 14px;
            background: var(--gradient1);
            border: none;
            border-radius: 10px;
            color: #fff;
            font-weight: 700;
            font-size: 14px;
            letter-spacing: 1px;
            cursor: pointer;
            transition: opacity 0.3s;
        }
        .btn-primary:hover { opacity: 0.9; }
        .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-secondary {
            background: var(--bg-light);
            color: var(--text);
            border: 1px solid var(--border);
        }
        .btn-secondary:hover { background: var(--border); }
        .status {
            padding: 10px;
            border-radius: 10px;
            text-align: center;
            font-weight: 600;
            font-size: 13px;
            background: var(--bg-light);
            border: 1px solid var(--border);
            margin-top: 8px;
        }
        .status.connected { color: var(--success); border-color: rgba(0,184,148,0.2); }
        .status.disconnected { color: var(--danger); border-color: rgba(255,107,107,0.2); }
        .status.connecting { color: var(--warning); border-color: rgba(253,203,110,0.2); }
        .stats-grid {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr 1fr;
            gap: 6px;
        }
        .stat-item {
            background: var(--card);
            border-radius: 10px;
            border: 1px solid var(--border);
            padding: 10px 6px;
            text-align: center;
        }
        .stat-item .number { font-size: 24px; font-weight: 800; }
        .stat-item .number.comments { color: var(--comment-color); }
        .stat-item .number.gifts { color: var(--gift-color); }
        .stat-item .number.follows { color: var(--follow-color); }
        .stat-item .number.online { color: var(--text-muted); }
        .stat-item .label {
            font-size: 9px;
            font-weight: 600;
            letter-spacing: 1px;
            text-transform: uppercase;
            color: var(--text-muted);
            margin-top: 2px;
        }
        .toggle-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 4px 0;
        }
        .toggle-row label { color: var(--text); font-size: 13px; cursor: pointer; }
        .toggle {
            position: relative;
            width: 40px;
            height: 22px;
            flex-shrink: 0;
        }
        .toggle input { opacity: 0; width: 0; height: 0; }
        .toggle .slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: var(--border);
            transition: 0.3s;
            border-radius: 22px;
        }
        .toggle .slider::before {
            content: "";
            position: absolute;
            height: 16px;
            width: 16px;
            left: 3px;
            bottom: 3px;
            background: #fff;
            transition: 0.3s;
            border-radius: 50%;
        }
        .toggle input:checked + .slider { background: var(--primary); }
        .toggle input:checked + .slider::before { transform: translateX(18px); }
        .action-btn {
            width: 100%;
            padding: 10px;
            background: var(--bg-light);
            border: 1px solid var(--border);
            border-radius: 10px;
            color: var(--text);
            font-size: 13px;
            cursor: pointer;
            transition: background 0.3s;
            text-align: left;
        }
        .action-btn:hover { background: var(--border); }
        .action-btn .icon { margin-right: 8px; }
        .feed {
            flex: 1;
            background: var(--card);
            border-radius: 16px;
            border: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            padding: 20px;
        }
        .feed-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            background: var(--bg-light);
            border-radius: 10px;
            border: 1px solid var(--border);
            margin-bottom: 12px;
        }
        .feed-header h2 {
            font-size: 18px;
            font-weight: 800;
            background: var(--gradient1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            letter-spacing: 2px;
        }
        .feed-header .count { color: var(--text-muted); font-size: 13px; }
        .feed-messages {
            flex: 1;
            overflow-y: auto;
            background: var(--bg-light);
            border-radius: 10px;
            border: 1px solid var(--border);
            padding: 8px;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }
        .feed-item {
            display: flex;
            align-items: flex-start;
            gap: 10px;
            padding: 10px 14px;
            background: var(--card);
            border-radius: 10px;
            border: 1px solid var(--border);
            animation: slideIn 0.3s ease;
        }
        @keyframes slideIn {
            from { opacity: 0; transform: translateX(-10px); }
            to { opacity: 1; transform: translateX(0); }
        }
        .feed-item .avatar {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 13px;
            color: #fff;
            flex-shrink: 0;
        }
        .feed-item .content { flex: 1; min-width: 0; }
        .feed-item .content .user { font-weight: 700; font-size: 13px; }
        .feed-item .content .msg { color: var(--text-muted); font-size: 13px; word-wrap: break-word; }
        .feed-item .content .msg.gift { color: var(--gift-color); }
        .feed-item .content .msg.follow { color: var(--follow-color); }
        .feed-item .time {
            font-size: 10px;
            color: var(--text-muted);
            flex-shrink: 0;
            margin-left: 8px;
        }
        .manual-input {
            display: flex;
            gap: 8px;
            padding: 8px;
            background: var(--bg-light);
            border-radius: 10px;
            border: 1px solid var(--border);
            margin-top: 12px;
        }
        .manual-input input {
            padding: 10px 14px;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 10px;
            color: var(--text);
            font-size: 13px;
            outline: none;
        }
        .manual-input input:focus { border-color: var(--primary); }
        .manual-input input::placeholder { color: var(--text-muted); }
        .manual-input .username-input { width: 100px; flex-shrink: 0; }
        .manual-input .message-input { flex: 1; }
        .manual-input .send-btn {
            padding: 10px 20px;
            background: var(--gradient2);
            border: none;
            border-radius: 10px;
            color: #fff;
            font-weight: 700;
            font-size: 13px;
            cursor: pointer;
            transition: opacity 0.3s;
            flex-shrink: 0;
        }
        .manual-input .send-btn:hover { opacity: 0.9; }
        .toast {
            position: fixed;
            bottom: 24px;
            right: 24px;
            padding: 14px 24px;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 10px;
            color: var(--text);
            font-size: 14px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            z-index: 1000;
            opacity: 0;
            transform: translateY(20px);
            transition: opacity 0.3s, transform 0.3s;
            pointer-events: none;
        }
        .toast.show { opacity: 1; transform: translateY(0); pointer-events: auto; }
        .toast.success { border-color: var(--success); }
        .toast.error { border-color: var(--danger); }
        .toast.info { border-color: var(--primary); }
        @media (max-width: 1024px) {
            .sidebar { width: 340px; min-width: 340px; padding: 16px; }
            .stats-grid { grid-template-columns: 1fr 1fr; }
        }
        @media (max-width: 768px) {
            .app { flex-direction: column; padding: 8px; gap: 8px; height: auto; min-height: 100vh; overflow-y: auto; }
            .sidebar { width: 100%; min-width: 0; max-height: 50vh; }
            .feed { min-height: 50vh; }
            .stats-grid { grid-template-columns: 1fr 1fr 1fr 1fr; }
            .manual-input { flex-wrap: wrap; }
            .manual-input .username-input { width: 100%; }
            .manual-input .send-btn { width: 100%; }
        }
        @media (max-width: 480px) {
            .stats-grid { grid-template-columns: 1fr 1fr; }
            .feed-header h2 { font-size: 15px; }
            .sidebar { padding: 12px; }
            .feed { padding: 12px; }
        }
    </style>
</head>
<body>
    <div class="app">
        <div class="sidebar">
            <div class="logo">
                <h1>VYBR</h1>
                <span>TikTok Live Tool</span>
            </div>
            <div class="card">
                <div class="card-header"><i class="fas fa-plug" style="margin-right:6px;"></i> Connection</div>
                <input class="connection-input" id="usernameInput" placeholder="Enter TikTok username" value="khaby.lame" />
                <button class="btn-primary" id="connectBtn" onclick="toggleConnection()">CONNECT LIVE</button>
                <div class="status disconnected" id="statusLabel">● Disconnected</div>
            </div>
            <div class="card">
                <div class="card-header"><i class="fas fa-chart-simple" style="margin-right:6px;"></i> Statistics</div>
                <div class="stats-grid">
                    <div class="stat-item"><div class="number comments" id="statComments">0</div><div class="label">Comments</div></div>
                    <div class="stat-item"><div class="number gifts" id="statGifts">0</div><div class="label">Gifts</div></div>
                    <div class="stat-item"><div class="number follows" id="statFollows">0</div><div class="label">Follows</div></div>
                    <div class="stat-item"><div class="number online" id="statOnline">0h 0m</div><div class="label">Online</div></div>
                </div>
            </div>
            <div class="card">
                <div class="card-header"><i class="fas fa-volume-up" style="margin-right:6px;"></i> Text-to-Speech</div>
                <div class="toggle-row">
                    <label for="ttsToggle">Enable TTS</label>
                    <label class="toggle">
                        <input type="checkbox" id="ttsToggle" checked />
                        <span class="slider"></span>
                    </label>
                </div>
                <div style="margin-top:6px;">
                    <label style="color:var(--text-muted);font-size:12px;">Voice:</label>
                    <select id="voiceSelect" style="width:100%;padding:8px 12px;background:var(--card);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:13px;">
                        <option value="en-US-JennyNeural">Jenny (US - Female)</option>
                        <option value="en-US-GuyNeural">Guy (US - Male)</option>
                        <option value="en-US-AriaNeural">Aria (US - Female)</option>
                        <option value="en-US-DavisNeural">Davis (US - Male)</option>
                        <option value="en-GB-RyanNeural">Ryan (UK - Male)</option>
                        <option value="en-GB-SoniaNeural">Sonia (UK - Female)</option>
                        <option value="en-AU-NatashaNeural">Natasha (AU - Female)</option>
                        <option value="en-AU-WilliamNeural">William (AU - Male)</option>
                        <option value="en-CA-ClaraNeural">Clara (CA - Female)</option>
                        <option value="en-IN-PrabhatNeural">Prabhat (IN - Male)</option>
                        <option value="en-NZ-MollyNeural">Molly (NZ - Female)</option>
                        <option value="en-ZA-LeahNeural">Leah (ZA - Female)</option>
                    </select>
                </div>
                <div style="margin-top:6px;">
                    <label style="color:var(--text-muted);font-size:12px;">Speed: <span id="speedLabel">100%</span></label>
                    <input type="range" id="speedSlider" min="50" max="200" value="100" style="width:100%;-webkit-appearance:none;height:4px;background:var(--border);border-radius:2px;" oninput="document.getElementById('speedLabel').textContent=this.value+'%'" />
                </div>
            </div>
            <div class="card">
                <div class="card-header"><i class="fas fa-gift" style="margin-right:6px;"></i> Gifts</div>
                <div class="toggle-row">
                    <label for="giftSoundToggle">Gift Sounds</label>
                    <label class="toggle">
                        <input type="checkbox" id="giftSoundToggle" checked />
                        <span class="slider"></span>
                    </label>
                </div>
                <div class="toggle-row">
                    <label for="giftTTSToggle">Gift TTS</label>
                    <label class="toggle">
                        <input type="checkbox" id="giftTTSToggle" checked />
                        <span class="slider"></span>
                    </label>
                </div>
            </div>
            <div class="card">
                <div class="card-header"><i class="fas fa-shield-halved" style="margin-right:6px;"></i> Filters</div>
                <div class="toggle-row">
                    <label for="autoClearToggle">Auto Clear Messages</label>
                    <label class="toggle">
                        <input type="checkbox" id="autoClearToggle" checked />
                        <span class="slider"></span>
                    </label>
                </div>
                <div class="toggle-row">
                    <label for="profanityToggle">Profanity Filter</label>
                    <label class="toggle">
                        <input type="checkbox" id="profanityToggle" />
                        <span class="slider"></span>
                    </label>
                </div>
                <div class="toggle-row">
                    <label for="spamToggle">Spam Filter</label>
                    <label class="toggle">
                        <input type="checkbox" id="spamToggle" checked />
                        <span class="slider"></span>
                    </label>
                </div>
            </div>
            <div class="card">
                <div class="card-header"><i class="fas fa-bolt" style="margin-right:6px;"></i> Actions</div>
                <button class="action-btn" onclick="clearFeed()"><i class="fas fa-trash icon"></i> Clear Feed</button>
                <button class="action-btn" style="margin-top:4px;" onclick="exportLogs()"><i class="fas fa-download icon"></i> Export Logs</button>
            </div>
        </div>
        <div class="feed">
            <div class="feed-header">
                <h2><i class="fas fa-bolt" style="color:var(--primary);font-size:16px;margin-right:8px;"></i> LIVE FEED</h2>
                <span class="count" id="feedCount">0 messages</span>
            </div>
            <div class="feed-messages" id="feedMessages"></div>
            <div class="manual-input">
                <input class="username-input" id="manualUser" placeholder="Username" value="Viewer" />
                <input class="message-input" id="manualMsg" placeholder="Type a message..." onkeypress="if(event.key==='Enter') sendManual()" />
                <button class="send-btn" onclick="sendManual()">Send</button>
            </div>
        </div>
    </div>
    <div class="toast" id="toast"></div>
    <script>
        // ============================================================
        // CONNECT TO SOCKET - WITH RENDER.COM COMPATIBLE SETTINGS
        // ============================================================
        const socket = io({
            transports: ['websocket', 'polling'],
            upgrade: true,
            rememberUpgrade: true,
            reconnection: true,
            reconnectionAttempts: 10,
            reconnectionDelay: 1000,
            timeout: 20000
        });

        // ============================================================
        // STATE
        // ============================================================
        let connected = false;
        let commentCount = 0;
        let giftCount = 0;
        let followCount = 0;
        let seen = new Set();
        let connectionStart = null;
        let connectionTimer = null;

        // ============================================================
        // DOM REFS
        // ============================================================
        const $ = id => document.getElementById(id);
        const feedMessages = $('feedMessages');
        const feedCount = $('feedCount');
        const statusLabel = $('statusLabel');
        const connectBtn = $('connectBtn');
        const usernameInput = $('usernameInput');
        const statComments = $('statComments');
        const statGifts = $('statGifts');
        const statFollows = $('statFollows');
        const statOnline = $('statOnline');
        const ttsToggle = $('ttsToggle');
        const voiceSelect = $('voiceSelect');
        const speedSlider = $('speedSlider');

        // ============================================================
        // SOCKET EVENTS
        // ============================================================
        socket.on('connect', () => {
            console.log('[Socket] Connected to server');
            showToast('Connected to server', 'success');
        });

        socket.on('disconnect', () => {
            console.log('[Socket] Disconnected from server');
            showToast('Disconnected from server', 'error');
        });

        socket.on('new_comment', (data) => {
            console.log('[Socket] Comment:', data.user, data.comment);
            addFeedItem(data, 'comment');
            commentCount++;
            statComments.textContent = commentCount;
            if (ttsToggle.checked) speak(`${data.user} says: ${data.comment}`);
        });

        socket.on('new_gift', (data) => {
            console.log('[Socket] Gift:', data.user, data.gift);
            addFeedItem(data, 'gift');
            giftCount++;
            statGifts.textContent = giftCount;
            if ($('giftTTSToggle').checked) speak(`${data.user} sent a ${data.gift}`);
        });

        socket.on('new_follow', (data) => {
            console.log('[Socket] Follow:', data.user);
            addFeedItem(data, 'follow');
            followCount++;
            statFollows.textContent = followCount;
            speak(`${data.user} just followed!`);
        });

        socket.on('connect_error', (error) => {
            console.error('[Socket] Connection error:', error);
            showToast('Socket connection error', 'error');
        });

        // ============================================================
        // CONNECTION FUNCTIONS
        // ============================================================
        function toggleConnection() {
            console.log('[UI] Toggle connection, current state:', connected);
            if (connected) {
                disconnect();
            } else {
                connect();
            }
        }

        function connect() {
            const username = usernameInput.value.trim();
            if (!username) {
                showToast('Enter a username', 'error');
                return;
            }

            console.log('[UI] Connecting to:', username);

            connectBtn.disabled = true;
            connectBtn.textContent = 'CONNECTING...';
            statusLabel.textContent = '● Connecting...';
            statusLabel.className = 'status connecting';

            fetch('/api/connect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: username })
            })
            .then(res => res.json())
            .then(data => {
                console.log('[API] Connect response:', data);
                connectBtn.disabled = false;
                if (data.success) {
                    connected = true;
                    connectBtn.textContent = 'DISCONNECT';
                    connectBtn.className = 'btn-primary btn-secondary';
                    statusLabel.textContent = '● Connected';
                    statusLabel.className = 'status connected';
                    showToast('Connected to ' + username, 'success');
                    connectionStart = Date.now();
                    if (connectionTimer) clearInterval(connectionTimer);
                    connectionTimer = setInterval(updateOnlineTime, 1000);
                } else {
                    connectBtn.textContent = 'CONNECT LIVE';
                    connectBtn.className = 'btn-primary';
                    statusLabel.textContent = '● Disconnected';
                    statusLabel.className = 'status disconnected';
                    showToast('Failed: ' + (data.error || 'Unknown'), 'error');
                }
            })
            .catch((err) => {
                console.error('[API] Connect error:', err);
                connectBtn.disabled = false;
                connectBtn.textContent = 'CONNECT LIVE';
                connectBtn.className = 'btn-primary';
                statusLabel.textContent = '● Disconnected';
                statusLabel.className = 'status disconnected';
                showToast('Connection failed: ' + err.message, 'error');
            });
        }

        function disconnect() {
            console.log('[UI] Disconnecting...');
            fetch('/api/disconnect', { method: 'POST' })
            .then(() => {
                connected = false;
                connectBtn.textContent = 'CONNECT LIVE';
                connectBtn.className = 'btn-primary';
                statusLabel.textContent = '● Disconnected';
                statusLabel.className = 'status disconnected';
                showToast('Disconnected', 'error');
                if (connectionTimer) {
                    clearInterval(connectionTimer);
                    connectionTimer = null;
                }
                statOnline.textContent = '0h 0m';
            });
        }

        function updateOnlineTime() {
            if (connectionStart) {
                const elapsed = Math.floor((Date.now() - connectionStart) / 1000);
                const hours = Math.floor(elapsed / 3600);
                const minutes = Math.floor((elapsed % 3600) / 60);
                statOnline.textContent = `${String(hours).padStart(2, '0')}h ${String(minutes).padStart(2, '0')}m`;
            }
        }

        // ============================================================
        // FEED FUNCTIONS
        // ============================================================
        function getColor(username) {
            const colors = ['#6c5ce7', '#74b9ff', '#fdcb6e', '#55efc4', '#fd79a8', '#a29bfe', '#00b894', '#e17055', '#00cec9', '#e84393'];
            let hash = 0;
            for (let i = 0; i < username.length; i++) {
                hash = username.charCodeAt(i) + ((hash << 5) - hash);
            }
            return colors[Math.abs(hash) % colors.length];
        }

        function addFeedItem(data, type) {
            console.log('[Feed] Adding item:', type, data);
            const { user, comment, gift, count, timestamp } = data;
            const time = new Date(timestamp * 1000).toLocaleTimeString();
            const color = getColor(user);
            const avatar = user.charAt(0).toUpperCase();

            let msg = comment || '';
            if (type === 'comment') {
                if ($('profanityToggle').checked) {
                    const profanity = ['fuck', 'shit', 'damn', 'ass', 'bitch', 'cunt'];
                    profanity.forEach(w => {
                        const regex = new RegExp(w, 'gi');
                        msg = msg.replace(regex, '****');
                    });
                }
                if ($('spamToggle').checked) {
                    const key = user + ':' + msg.substring(0, 20);
                    if (seen.has(key)) return;
                    seen.add(key);
                    if (seen.size > 1000) seen.clear();
                }
            }

            let msgHTML = '';
            if (type === 'gift') {
                msgHTML = `<span class="msg gift">🎁 sent ${count}x ${gift}</span>`;
            } else if (type === 'follow') {
                msgHTML = `<span class="msg follow">just followed!</span>`;
            } else {
                msgHTML = `<span class="msg">${msg}</span>`;
            }

            const item = document.createElement('div');
            item.className = 'feed-item';
            item.innerHTML = `
                <div class="avatar" style="background:${color}">${avatar}</div>
                <div class="content">
                    <span class="user" style="color:${color}">@${user}</span>
                    ${msgHTML}
                </div>
                <span class="time">${time}</span>
            `;
            feedMessages.prepend(item);

            const total = feedMessages.children.length;
            feedCount.textContent = total + ' messages';

            if ($('autoClearToggle').checked && total > 500) {
                const last = feedMessages.lastChild;
                if (last) last.remove();
            }
        }

        function clearFeed() {
            console.log('[UI] Clearing feed');
            feedMessages.innerHTML = '';
            feedCount.textContent = '0 messages';
            commentCount = 0;
            giftCount = 0;
            followCount = 0;
            statComments.textContent = '0';
            statGifts.textContent = '0';
            statFollows.textContent = '0';
            seen.clear();
            showToast('Feed cleared', 'success');
        }

        // ============================================================
        // EXPORT LOGS
        // ============================================================
        function exportLogs() {
            console.log('[UI] Exporting logs');
            const items = feedMessages.querySelectorAll('.feed-item');
            let text = 'VYBR Logs\n' + new Date().toLocaleString() + '\n\n';
            items.forEach(item => {
                text += item.textContent.trim() + '\n';
            });
            const blob = new Blob([text], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'vybr_logs_' + new Date().toISOString().slice(0,10) + '.txt';
            a.click();
            URL.revokeObjectURL(url);
            showToast('Logs exported', 'success');
        }

        // ============================================================
        // MANUAL MESSAGE
        // ============================================================
        function sendManual() {
            const user = $('manualUser').value.trim() || 'Manual';
            const msg = $('manualMsg').value.trim();
            if (!msg) {
                showToast('Enter a message', 'error');
                return;
            }

            console.log('[UI] Sending manual message:', user, msg);

            fetch('/api/manual', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user: user, message: msg })
            })
            .then(res => res.json())
            .then(() => {
                $('manualMsg').value = '';
                showToast('Message sent', 'success');
            })
            .catch(err => {
                console.error('[API] Manual message error:', err);
                showToast('Failed to send message', 'error');
            });
        }

        // ============================================================
        // TTS (Speech Synthesis)
        // ============================================================
        function speak(text) {
            try {
                if (!window.speechSynthesis) return;
                const utterance = new SpeechSynthesisUtterance(text);
                const voices = window.speechSynthesis.getVoices();
                const selected = voices.find(v => v.name.includes(voiceSelect.value));
                if (selected) utterance.voice = selected;
                utterance.rate = parseInt(speedSlider.value) / 100;
                window.speechSynthesis.speak(utterance);
            } catch (e) {
                console.log('[TTS] Error:', e);
            }
        }

        // Load voices when they change
        if (window.speechSynthesis) {
            window.speechSynthesis.onvoiceschanged = () => {
                const voices = window.speechSynthesis.getVoices();
                const select = voiceSelect;
                const options = select.querySelectorAll('option');
                options.forEach(opt => {
                    const match = voices.find(v => v.name.includes(opt.text.split('(')[0].trim()));
                    if (match) opt.value = match.name;
                });
            };
        }

        // ============================================================
        // TOAST
        // ============================================================
        function showToast(message, type = 'info') {
            console.log('[UI] Toast:', message, type);
            const toast = $('toast');
            toast.textContent = message;
            toast.className = 'toast ' + type;
            toast.classList.add('show');
            clearTimeout(toast._timeout);
            toast._timeout = setTimeout(() => {
                toast.classList.remove('show');
            }, 3000);
        }

        // ============================================================
        // KEYBOARD SHORTCUTS
        // ============================================================
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter') {
                e.preventDefault();
                sendManual();
            }
            if (e.ctrlKey && e.key === 'c' && !e.target.closest('input')) {
                clearFeed();
            }
        });

        // ============================================================
        // LOGGING
        // ============================================================
        console.log('VYBR - TikTok Live Tool');
        console.log('Ready for connection');

        // Log all button clicks for debugging
        document.querySelectorAll('button').forEach(btn => {
            btn.addEventListener('click', function(e) {
                console.log('[UI] Button clicked:', this.textContent.trim());
            });
        });
    </script>
</body>
</html>
'''

# === FLASK ROUTES ===
def run_tiktok_client(username):
    global connected, comment_history, gift_history, follow_history, users, active_username
    
    try:
        from TikTokLive import TikTokLiveClient
        from TikTokLive.events import CommentEvent, GiftEvent, ConnectEvent, DisconnectEvent, FollowEvent
        
        active_username = username
        
        # Create client with proper settings
        client = TikTokLiveClient(unique_id=username if username.startswith('@') else '@' + username)
        
        @client.on(ConnectEvent)
        async def on_connect(_):
            global connected
            connected = True
            socketio.emit('connected', {'status': True})
            socketio.emit('tts_status', {'message': f'Connected to {username}'})
            print(f"[✓] Connected to {username}")
        
        @client.on(DisconnectEvent)
        async def on_disconnect(_):
            global connected
            connected = False
            socketio.emit('connected', {'status': False})
            socketio.emit('tts_status', {'message': 'Disconnected'})
            print("[!] Disconnected")
        
        @client.on(CommentEvent)
        async def on_comment(event):
            try:
                # Safely get user info
                user_obj = getattr(event, 'user', None)
                if user_obj:
                    nickname = getattr(user_obj, 'nickname', 'Unknown')
                else:
                    nickname = 'Unknown'
                
                comment = getattr(event, 'comment', '')
                
                if not comment:
                    return
                
                # Check blocked words
                for word in blocked_words:
                    if word.lower() in comment.lower():
                        return
                
                entry = {
                    'user': nickname,
                    'comment': comment,
                    'timestamp': time.time(),
                    'source': 'tiktok'
                }
                comment_history.append(entry)
                users.add(nickname)
                socketio.emit('new_comment', entry)
                print(f"[Comment] {nickname}: {comment}")
                
            except Exception as e:
                print(f"[!] Comment error: {e}")
        
        @client.on(GiftEvent)
        async def on_gift(event):
            try:
                user_obj = getattr(event, 'user', None)
                if user_obj:
                    nickname = getattr(user_obj, 'nickname', 'Unknown')
                else:
                    nickname = 'Unknown'
                
                gift_obj = getattr(event, 'gift', None)
                if gift_obj:
                    gift_name = getattr(gift_obj, 'name', 'Gift')
                    count = getattr(gift_obj, 'count', 1)
                else:
                    gift_name = 'Gift'
                    count = 1
                
                entry = {
                    'user': nickname,
                    'gift': gift_name,
                    'count': count,
                    'timestamp': time.time(),
                    'source': 'tiktok'
                }
                gift_history.append(entry)
                users.add(nickname)
                socketio.emit('new_gift', entry)
                print(f"[Gift] {nickname} sent {count}x {gift_name}")
                
            except Exception as e:
                print(f"[!] Gift error: {e}")
        
        @client.on(FollowEvent)
        async def on_follow(event):
            try:
                user_obj = getattr(event, 'user', None)
                if user_obj:
                    nickname = getattr(user_obj, 'nickname', 'Unknown')
                else:
                    nickname = 'Unknown'
                
                entry = {
                    'user': nickname,
                    'timestamp': time.time(),
                    'source': 'tiktok'
                }
                follow_history.append(entry)
                users.add(nickname)
                socketio.emit('new_follow', entry)
                print(f"[Follow] {nickname} followed!")
                
            except Exception as e:
                print(f"[!] Follow error: {e}")
        
        print(f"[*] Starting TikTok client for {username}...")
        await client.run()
        
    except Exception as e:
        connected = False
        socketio.emit('error', {'message': str(e)})
        socketio.emit('tts_status', {'message': f'Error: {str(e)}'})
        print(f"[!] Client error: {e}")

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/connect', methods=['POST'])
def api_connect():
    global connected, client_thread, active_username
    
    if connected:
        return jsonify({'success': False, 'error': 'Already connected'})
    
    data = request.get_json()
    username = data.get('username', '').strip()
    
    if not username:
        return jsonify({'success': False, 'error': 'No username provided'})
    
    # Remove @ if present
    if username.startswith('@'):
        username = username[1:]
    
    active_username = username
    
    # Start client in background thread
    client_thread = threading.Thread(target=run_tiktok_client, args=(username,), daemon=True)
    client_thread.start()
    
    # Wait a moment for connection
    time.sleep(2)
    
    return jsonify({'success': True, 'message': f'Connecting to {username}...'})

@app.route('/api/disconnect', methods=['POST'])
def api_disconnect():
    global connected, client_thread, active_username
    
    connected = False
    client_thread = None
    active_username = None
    
    return jsonify({'success': True})

@app.route('/api/manual', methods=['POST'])
def api_manual():
    data = request.get_json()
    user = data.get('user', 'Manual')
    message = data.get('message', '')
    
    if message:
        entry = {
            'user': user,
            'comment': message,
            'timestamp': time.time(),
            'source': 'manual'
        }
        comment_history.append(entry)
        socketio.emit('new_comment', entry)
    
    return jsonify({'success': True})

@app.route('/api/stats')
def api_stats():
    return jsonify({
        'comments': len(comment_history),
        'gifts': len(gift_history),
        'follows': len(follow_history),
        'users': len(users)
    })

# === MAIN ===
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("=" * 60)
    print(" VYBR - TikTok Live Tool ".center(60))
    print("=" * 60)
    print(f"\n Server running on port {port}")
    print("=" * 60)
    
    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=False,
        allow_unsafe_werkzeug=True,
        log_output=True
    )
