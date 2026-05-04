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
                <div class="station-meta" style="display:flex; justify-content:space-between; align-items:flex-start;">
                    <div>
                        <span class="station-name">${cam.name}</span>
                        <div id="status-${cam.id}" class="status-indicator">INITIALIZING</div>
                    </div>
                    <div id="cycle-count-${cam.id}" class="cycle-badge">Cycle: 0</div>
                </div>
                
                <div class="progress-container">
                    <div style="font-size: 0.75rem; color: #999; text-transform: uppercase; margin-bottom: 5px;">Bước tiếp theo:</div>
                    <div id="step-name-${cam.id}" style="font-weight:700; font-size: 1.1rem; color: #111; margin-bottom: 20px;">Ready</div>
                    
                    <div style="font-size: 0.75rem; color: #999; text-transform: uppercase; margin-bottom: 5px;">AI đang thấy:</div>
                    <div id="detected-step-${cam.id}" style="font-weight:700; font-size: 1.1rem; color: var(--primary); margin-bottom: 20px;">Idle</div>

                    <div class="progress-bar">
                        <div id="progress-${cam.id}" class="progress-fill" style="width: 0%"></div>
                    </div>

                    <div id="status-msg-${cam.id}" style="margin-top: 15px; padding: 10px; background: #f0f7ff; color: #0056b3; border-radius: 6px; font-weight: 600; text-align: center; border: 1px solid #cce5ff;">
                        Sẵn sàng
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
    const { camera_id, cycle_count, current_step, detected_step, status_msg, hit_count, sop_status, progress_percent, hands_detected, step_index, step_list } = data;
    
    // Update Progress
    const fill = document.getElementById(`progress-${camera_id}`);
    const detectedEle = document.getElementById(`detected-step-${camera_id}`);
    const stepLabel = document.getElementById(`step-name-${camera_id}`);
    const status = document.getElementById(`status-${camera_id}`);
    const card = document.getElementById(`station-${camera_id}`);

    if (fill) fill.style.width = `${progress_percent}%`;
    if (detectedEle) detectedEle.innerText = detected_step || "Idle";
    if (stepLabel) stepLabel.innerText = current_step;
    
    const cycleEle = document.getElementById(`cycle-count-${camera_id}`);
    if (cycleEle) cycleEle.innerText = `Cycle: ${cycle_count}`;
    
    const msgEle = document.getElementById(`status-msg-${camera_id}`);
    if (msgEle) {
        msgEle.innerText = status_msg || (sop_status === 'violation' ? "CÓ LỖI - VỀ BƯỚC 1" : "Đang xử lý...");
        if (sop_status === 'violation') msgEle.style.background = '#fff0f0', msgEle.style.color = '#d32f2f', msgEle.style.borderColor = '#ffcdd2';
        else msgEle.style.background = '#f0f7ff', msgEle.style.color = '#0056b3', msgEle.style.borderColor = '#cce5ff';
    }
    
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
                // Tự động cuộn đến bước đang làm
                const scrollContainer = listContainer;
                const itemOffset = item.offsetTop - scrollContainer.offsetTop;
                
                if (idx === 0) {
                    // Nếu là Bước 1 -> Kéo hẳn lên đầu
                    scrollContainer.scrollTo({ top: 0, behavior: 'smooth' });
                } else {
                    // Các bước khác -> Cuộn để bước đó nằm ở vị trí dễ nhìn (khoảng giữa khung)
                    scrollContainer.scrollTo({ top: itemOffset - 60, behavior: 'smooth' });
                }
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
    const { camera_id, violation_type, expected_step, detected_step, timestamp } = data;
    const card = document.getElementById(`station-${camera_id}`);
    const status = document.getElementById(`status-${camera_id}`);

    const typeMap = {
        'skip_step': 'BỎ BƯỚC',
        'timeout': 'QUÁ THỜI GIAN',
        'wrong_step': 'SAI THỨ TỰ',
        'premature_restart': 'LÀM LẠI SỚM'
    };

    const vTypeVN = typeMap[violation_type] || violation_type || 'LỖI CHƯA XÁC ĐỊNH';

    if (card) {
        card.classList.add('violation-active');
        setTimeout(() => card.classList.remove('violation-active'), 1000);
    }
    
    if (status) {
        status.innerText = `LỖI: ${vTypeVN}`;
        status.style.color = 'var(--danger)';
    }

    // Hiển thị thông báo nổi (Toast)
    showToast({
        title: `CẢNH BÁO VI PHẠM - ${camera_id.toUpperCase()}`,
        body: `Phát hiện lỗi: ${vTypeVN}`,
        details: `Cần thực hiện: "${expected_step || 'N/A'}"<br>Nhưng thấy: "${detected_step || 'Không xác định'}"`,
        time: timestamp || new Date().toLocaleTimeString()
    });

    // Refresh list
    loadRecentEvents();
});

function showToast({ title, body, details, time }) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = `
        <div class="toast-header">
            <div class="toast-title">⚠️ ${title}</div>
            <div class="toast-time">${time}</div>
        </div>
        <div class="toast-body">${body}</div>
        <div class="toast-details">${details}</div>
    `;
    
    container.appendChild(toast);
    
    // Tự động xóa sau 8 giây
    setTimeout(() => {
        toast.classList.add('removing');
        setTimeout(() => toast.remove(), 500);
    }, 8000);
}

async function loadRecentEvents() {
    try {
        const response = await fetch('/api/events?limit=10');
        const events = await response.json();
        const list = document.getElementById('event-list');
        list.innerHTML = '';

        events.forEach(ev => {
            const typeMap = {
                'skip_step': 'Bỏ bước',
                'timeout': 'Quá giờ',
                'wrong_step': 'Sai bước',
                'premature_restart': 'Reset sớm'
            };
            const vTypeVN = typeMap[ev.violation_type] || ev.violation_type;

            const row = document.createElement('tr');
            row.className = 'event-row';
            row.innerHTML = `
                <td class="event-cell">${ev.timestamp.split(' ')[1]}</td>
                <td class="event-cell" style="color:#aaa">${ev.camera_id}</td>
                <td class="event-cell event-type">${vTypeVN}</td>
                <td class="event-cell">
                    <button onclick="openVideo(${ev.id}, '${ev.camera_id}', '${vTypeVN}')" 
                            style="background:none; border:none; color:var(--primary); cursor:pointer; font-weight:700; font-size:0.75rem">
                        ▶ XEM LẠI
                    </button>
                </td>
            `;
            list.appendChild(row);
        });
    } catch (err) {
        console.error("Error loading events:", err);
    }
}

function openVideo(eventId, camId, type) {
    const modal = document.getElementById('video-modal');
    const video = document.getElementById('replay-video');
    const title = document.getElementById('modal-title');
    
    title.innerText = `REPLAY: ${camId.toUpperCase()} - ${type}`;
    video.src = `/clip/${eventId}`;
    modal.style.display = 'flex';
    video.play();
}

function closeModal() {
    const modal = document.getElementById('video-modal');
    const video = document.getElementById('replay-video');
    video.pause();
    video.src = "";
    modal.style.display = 'none';
}

// Close modal when clicking outside
window.onclick = (event) => {
    const modal = document.getElementById('video-modal');
    if (event.target == modal) closeModal();
};

async function updateSystemHealth() {
    try {
        const response = await fetch('/api/system/health');
        const data = await response.json();
        
        document.getElementById('cpu-val').innerText = `${data.cpu_usage_percent}%`;
        document.getElementById('ram-val').innerText = `${data.ram_used_mb} MB`;
        document.getElementById('disk-val').innerText = `${data.disk_free_gb} GB Free`;
    } catch (err) {}
}
