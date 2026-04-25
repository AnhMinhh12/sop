const socket = io();

// Store for chart and data
let violationChart = null;

document.addEventListener('DOMContentLoaded', () => {
    initDashboard();
});

async function initDashboard() {
    console.log("Initializing SOP Monitoring Dashboard...");
    
    // 1. Load Cameras
    try {
        const response = await fetch('/api/cameras');
        const cameras = await response.json();
        renderCameraGrid(cameras);
    } catch (err) {
        console.error("Failed to load cameras:", err);
    }

    // 2. Load Initial Events
    loadRecentEvents();

    // 3. Sys Health Every 5s
    setInterval(updateSystemHealth, 5000);
}

function renderCameraGrid(cameras) {
    const grid = document.getElementById('camera-grid');
    grid.innerHTML = '';

    cameras.forEach(cam => {
        const card = document.createElement('div');
        card.className = 'station-card';
        card.id = `station-${cam.id}`;
        card.innerHTML = `
            <div class="video-wrapper">
                <img class="video-feed" src="/video_feed/${cam.id}" alt="Stream">
                <div class="bimanual-status">
                    <span>LH</span><div id="lh-${cam.id}" class="dot"></div>
                    <span>RH</span><div id="rh-${cam.id}" class="dot"></div>
                </div>
            </div>
            <div class="info-panel">
                <div class="station-meta">
                    <span class="station-name">${cam.name} (${cam.id})</span>
                    <div id="status-${cam.id}" class="status-indicator">INITIALIZING</div>
                </div>
                
                <div class="progress-container">
                    <div style="font-size: 0.75rem; color: #999; text-transform: uppercase; margin-bottom: 5px;">Bước tiếp theo:</div>
                    <div id="step-name-${cam.id}" style="font-weight:700; font-size: 1.1rem; color: #111; margin-bottom: 20px;">Ready</div>
                    
                    <div style="font-size: 0.75rem; color: #999; text-transform: uppercase; margin-bottom: 5px;">AI đang thấy:</div>
                    <div id="detected-step-${cam.id}" style="font-weight:700; font-size: 1.1rem; color: var(--primary); margin-bottom: 20px;">Idle</div>

                    <div class="progress-bar">
                        <div id="progress-${cam.id}" class="progress-fill" style="width: 0%"></div>
                    </div>

                    <!-- DANH SÁCH CÁC BƯỚC SOP -->
                    <div id="step-list-${cam.id}" class="sop-steps-list">
                        <!-- Sẽ được fill bằng JS -->
                    </div>
                </div>
            </div>
        `;
        grid.appendChild(card);
    });
}

// Real-time Updates via SocketIO
socket.on('step_update', (data) => {
    const { camera_id, current_step, detected_step, sop_status, progress_percent, hands_detected, step_index, step_list } = data;
    
    // Update Progress
    const fill = document.getElementById(`progress-${camera_id}`);
    const detectedEle = document.getElementById(`detected-step-${camera_id}`);
    const stepLabel = document.getElementById(`step-name-${camera_id}`);
    const status = document.getElementById(`status-${camera_id}`);
    const card = document.getElementById(`station-${camera_id}`);

    if (fill) fill.style.width = `${progress_percent}%`;
    if (detectedEle) detectedEle.innerText = detected_step || "Idle";
    if (stepLabel) stepLabel.innerText = current_step;
    
    if (status) {
        status.innerText = sop_status.toUpperCase();
        if (sop_status === 'correct' || sop_status === 'completed') {
            status.style.color = 'var(--success)';
            if (sop_status === 'completed') {
                status.innerHTML = "⭐ CYCLE COMPLETED ⭐";
            }
        } else {
            status.style.color = '#888';
        }
    }

    // UPDATE DANH SÁCH BƯỚC (Cập nhật dấu tích)
    const listContainer = document.getElementById(`step-list-${camera_id}`);
    if (listContainer && step_list && step_list.length > 0) {
        // Vẽ danh sách nếu chưa có
        if (listContainer.children.length === 0) {
            listContainer.innerHTML = step_list.map((name, idx) => `
                <div class="sop-step-item" id="step-item-${camera_id}-${idx}">
                    <div class="tick-box">${idx + 1}</div>
                    <span>${name}</span>
                </div>
            `).join('');
        }

        // Cập nhật trạng thái từng bước
        const items = listContainer.querySelectorAll('.sop-step-item');
        items.forEach((item, idx) => {
            item.classList.remove('active', 'completed');
            const tickBox = item.querySelector('.tick-box');
            
            if (idx < step_index) {
                item.classList.add('completed');
                tickBox.innerHTML = '✓';
            } else if (idx === step_index) {
                item.classList.add('active');
                tickBox.innerHTML = idx + 1;
                // Tự động cuộn đến bước đang làm nếu danh sách dài
                if (idx > 3) item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            } else {
                tickBox.innerHTML = idx + 1;
            }
        });
    }

    // Hand Dots (Left/Right)
    if (hands_detected) {
        const lh = document.getElementById(`lh-${camera_id}`);
        const rh = document.getElementById(`rh-${camera_id}`);
        if (lh) lh.classList.toggle('active', hands_detected.left);
        if (rh) rh.classList.toggle('active', hands_detected.right);
    }

    // Clear violation effects if system is back to correct
    if (sop_status === 'correct' && card) {
        card.classList.remove('violation-active');
    }
});

socket.on('violation', (data) => {
    const { camera_id, violation_type, timestamp } = data;
    const card = document.getElementById(`station-${camera_id}`);
    const status = document.getElementById(`status-${camera_id}`);

    if (card) {
        card.classList.add('violation-active');
        // Shake animation could be added here
    }
    
    if (status) {
        status.innerText = `VIOLATION: ${violation_type}`;
        status.style.color = 'var(--danger)';
    }

    // Refresh list
    loadRecentEvents();
});

async function loadRecentEvents() {
    try {
        const response = await fetch('/api/events?limit=10');
        const events = await response.json();
        const list = document.getElementById('event-list');
        list.innerHTML = '';

        events.forEach(ev => {
            const row = document.createElement('tr');
            row.className = 'event-row';
            row.innerHTML = `
                <td class="event-cell">${ev.timestamp.split(' ')[1]}</td>
                <td class="event-cell" style="color:#aaa">${ev.camera_id}</td>
                <td class="event-cell event-type">${ev.violation_type}</td>
                <td class="event-cell">
                    <a href="/clip/${ev.id}" target="_blank" style="color:var(--primary); text-decoration:none; font-size:0.75rem">▶ REPLAY</a>
                </td>
            `;
            list.appendChild(row);
        });
    } catch (err) {
        console.error("Error loading events:", err);
    }
}

async function updateSystemHealth() {
    try {
        const response = await fetch('/api/system/health');
        const data = await response.json();
        
        document.getElementById('cpu-val').innerText = `${data.cpu_usage_percent}%`;
        document.getElementById('ram-val').innerText = `${data.ram_used_mb} MB`;
        document.getElementById('disk-val').innerText = `${data.disk_free_gb} GB Free`;
    } catch (err) {}
}
