// Sử dụng biến toàn cục an toàn để tránh xung đột SyntaxError khi project vệ tinh cũng khai báo socket
if (typeof window.socket === 'undefined') {
    window.socket = typeof io !== 'undefined' ? io() : null;
}
const socket = window.socket;

// Store for chart and data
let violationChart = null;
let healthInterval = null;
let pieChart = null;
let lineChart = null;

document.addEventListener('DOMContentLoaded', () => {
    if (typeof initSpaNavigation === 'function') initSpaNavigation();
    updateSidebarActiveState(window.location.pathname);
    initDashboard(); // Khởi tạo trang đầu tiên
});

/**
 * Hàm khởi tạo chính cho mọi trang
 * Được gọi mỗi khi load trang lần đầu hoặc chuyển tab qua SPA
 */
async function initDashboard() {
    console.log("Detecting page context...");
    
    // Dọn dẹp các interval cũ để tránh rác bộ nhớ
    if (healthInterval) {
        clearInterval(healthInterval);
        healthInterval = null;
    }

    const grid = document.getElementById('camera-grid');
    const stationContainer = document.getElementById('station-container');
    const historyList = document.getElementById('history-list');
    const statsContainer = document.getElementById('violationPieChart');

    // 1. Nếu là trang Dashboard (Overview)
    if (grid) {
        try {
            const response = await fetch('/api/cameras');
            const cameras = await response.json();
            renderOverviewGrid(cameras);
        } catch (err) { console.error("Failed to load cameras:", err); }
    } 
    
    // 2. Nếu là trang Chi tiết trạm
    else if (stationContainer) {
        try {
            const response = await fetch('/api/cameras');
            const cameras = await response.json();
            const cameraId = stationContainer.getAttribute('data-camera-id');
            const camera = cameras.find(c => c.id === cameraId);
            if (camera) renderStationDetail(camera);
            loadRecentEvents(cameraId); // Nạp 10 event gần nhất của trạm này
        } catch (err) { console.error("Failed to load station:", err); }
    }

    // 3. Nếu là trang Lịch sử
    if (historyList) {
        const urlParams = new URLSearchParams(window.location.search);
        const cameraId = urlParams.get('camera_id') || "";
        initHistoryPage(cameraId);
    }

    // 4. Nếu là trang Thống kê
    if (statsContainer) {
        const urlParams = new URLSearchParams(window.location.search);
        const cameraId = urlParams.get('camera_id') || "";
        initStatsPage(cameraId);
    }

    // 5. Cập nhật System Health (CPU/RAM/Disk) - Luôn chạy nếu có các thẻ hiển thị
    if (document.getElementById('cpu-val')) {
        updateSystemHealth();
        healthInterval = setInterval(updateSystemHealth, 15000);
    }
}

/* --- LOGIC TRANG LỊCH SỬ --- */
async function initHistoryPage(selectedId = "") {
    const stationSelect = document.getElementById('filter-station');
    const dateInput = document.getElementById('filter-date');
    
    if (stationSelect && stationSelect.options.length <= 1) {
        const response = await fetch('/api/cameras');
        const cameras = await response.json();
        cameras.forEach(cam => {
            const opt = document.createElement('option');
            opt.value = cam.station_id;
            opt.textContent = cam.name;
            if (cam.station_id === selectedId) opt.selected = true;
            stationSelect.appendChild(opt);
        });
    }

    loadHistory(selectedId, dateInput ? dateInput.value : "");
    
    // Gán sự kiện cho nút tìm kiếm nếu chưa có
    const searchBtn = document.querySelector('.btn-primary');
    if (searchBtn) {
        searchBtn.onclick = () => {
            loadHistory(stationSelect.value, dateInput.value);
        };
    }
}

async function loadHistory(stationId = '', date = '') {
    const list = document.getElementById('history-list');
    if (!list) return;
    list.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 40px; color: #888;">Đang tải dữ liệu...</td></tr>';
    
    let url = `/api/events?limit=100`;
    if (stationId) url += `&camera_id=${stationId}`;
    if (date) url += `&date=${date}`;
    
    try {
        const response = await fetch(url);
        const events = await response.json();
        list.innerHTML = '';
        
        if (events.length === 0) {
            list.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 40px; color: #888;">Không tìm thấy bản ghi nào</td></tr>';
            return;
        }

        events.forEach(ev => {
            const typeMap = { 'skip_step': 'Bỏ bước', 'timeout': 'Quá giờ', 'wrong_step': 'Sai bước', 'premature_restart': 'Reset sớm' };
            const vTypeVN = typeMap[ev.violation_type] || ev.violation_type;
            const isViolation = ev.sop_status === 'violation';
            const row = document.createElement('tr');
            row.className = 'event-row';
            row.innerHTML = `
                <td>${ev.timestamp}</td>
                <td><span class="badge-station">${ev.station_id || 'Trạm ' + ev.camera_id}</span></td>
                <td><span class="event-type ${isViolation ? 'text-danger' : 'text-secondary'}">${vTypeVN}</span></td>
                <td>${ev.expected_step || '-'}</td>
                <td>${ev.step_detected || '-'}</td>
                <td>${(ev.confidence * 100).toFixed(1)}%</td>
                <td>
                    ${isViolation && ev.clip_path ? `<button class="btn-action" onclick="openVideo('${ev.id}', '${ev.station_id || ev.camera_id}', '${vTypeVN}')">▶ XEM LẠI</button>` : '-'}
                </td>
            `;
            list.appendChild(row);
        });
    } catch (err) { console.error(err); list.innerHTML = 'Lỗi nạp dữ liệu'; }
}

/* --- LOGIC TRANG THỐNG KÊ --- */
async function initStatsPage(selectedId = "") {
    const stationSelect = document.getElementById('filter-station');
    const dateInput = document.getElementById('target-date');
    if (!dateInput) return;

    const today = new Date().toISOString().split('T')[0];
    dateInput.value = today;

    // Load filter options if empty
    if (stationSelect && stationSelect.options.length <= 1) {
        const response = await fetch('/api/cameras');
        const cameras = await response.json();
        cameras.forEach(cam => {
            const opt = document.createElement('option');
            opt.value = cam.station_id;
            opt.textContent = cam.name;
            if (cam.station_id === selectedId) opt.selected = true;
            stationSelect.appendChild(opt);
        });
    }

    loadStats(today, selectedId);

    dateInput.onchange = () => loadStats(dateInput.value, stationSelect.value);
    stationSelect.onchange = () => loadStats(dateInput.value, stationSelect.value);
}

async function loadStats(date, cameraId = "") {
    try {
        let filter = `date=${date}`;
        if (cameraId && cameraId !== "null") filter += `&camera_id=${cameraId}`;

        // 1. Summary
        const summaryRes = await fetch(`/api/stats/summary?${filter}`);
        const summary = await summaryRes.json();
        document.getElementById('total-violations').innerText = summary.total_violations;
        document.getElementById('total-completions').innerText = summary.total_completions;
        document.getElementById('compliance-rate').innerText = `${summary.compliance_rate}%`;

        // 2. Pie Chart
        const distRes = await fetch(`/api/stats/distribution?${filter}`);
        const distData = await distRes.json();
        renderPieChart(distData);

        // 3. Line Chart
        const trendRes = await fetch(`/api/stats/trend?${filter}`);
        const trendData = await trendRes.json();
        renderLineChart(trendData);
    } catch (err) { console.error(err); }
}

function renderPieChart(data) {
    const ctx = document.getElementById('violationPieChart').getContext('2d');
    if (pieChart) pieChart.destroy();
    const labels = Object.keys(data);
    const values = Object.values(data);
    const typeMap = { 'skip_step': 'Bỏ bước', 'timeout': 'Quá giờ', 'wrong_step': 'Sai bước', 'premature_restart': 'Reset sớm' };
    const typeColors = { 'skip_step': '#ef4444', 'timeout': '#f59e0b', 'wrong_step': '#6366f1', 'premature_restart': '#10b981' };

    pieChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels.map(l => typeMap[l] || l),
            datasets: [{ data: values, backgroundColor: labels.map(l => typeColors[l] || '#94a3b8'), borderWidth: 0 }]
        },
        options: { responsive: true, plugins: { legend: { position: 'bottom' } }, cutout: '70%' }
    });
}

function renderLineChart(data) {
    const ctx = document.getElementById('violationLineChart').getContext('2d');
    if (lineChart) lineChart.destroy();
    lineChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => d.day),
            datasets: [{ label: 'Số lỗi', data: data.map(d => d.count), borderColor: '#2d5cf7', backgroundColor: 'rgba(45, 92, 247, 0.1)', fill: true, tension: 0.4 }]
        },
        options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } } }
    });
}

/* --- LOGIC DASHBOARD & CAMERA --- */
function renderOverviewGrid(cameras) {
    const grid = document.getElementById('camera-grid');
    if (!grid) return;
    grid.innerHTML = '';
    cameras.forEach(cam => {
        const illustrationHtml = cam.illustration 
            ? `<img src="${cam.illustration}" class="station-illustration" alt="${cam.name}">`
            : `<div class="station-icon">📸</div>`;
        const card = document.createElement('a');
        card.className = 'overview-card';
        card.href = `/station/${cam.id}`;
        card.id = `overview-${cam.id}`;
        card.innerHTML = `
            <div class="overview-header-icon">${illustrationHtml}<div class="status-badge" id="status-badge-${cam.id}">INIT</div></div>
            <div class="overview-info">
                <div class="overview-header"><span class="overview-name">${cam.name}</span><span id="cycle-count-${cam.id}" class="cycle-badge">0</span></div>
                <div id="step-name-${cam.id}" class="overview-step">Ready</div>
                <div class="progress-bar-container"><div class="progress-bar"><div id="progress-${cam.id}" class="progress-fill" style="width: 0%"></div></div></div>
            </div>
        `;
        grid.appendChild(card);
    });
}

function renderStationDetail(cam) {
    const container = document.getElementById('station-container');
    if (!container) return;
    container.innerHTML = `
        <div class="station-card" id="station-${cam.id}">
            <div class="video-wrapper">
                <img class="video-feed" src="/video_feed/${cam.id}" alt="Stream">
                <div class="bimanual-status">LH<div id="lh-${cam.id}" class="dot"></div> RH<div id="rh-${cam.id}" class="dot"></div></div>
            </div>
            <div class="info-panel">
                <div class="station-name">${cam.name}</div>
                <div id="status-${cam.id}" class="status-indicator">INIT</div>
                <div id="step-name-${cam.id}" class="overview-step">Ready</div>
                <div class="progress-bar"><div id="progress-${cam.id}" class="progress-fill" style="width: 0%"></div></div>
                <div id="status-msg-${cam.id}" class="status-msg">Sẵn sàng</div>
                <div id="step-list-${cam.id}" class="sop-steps-list"></div>
            </div>
        </div>
    `;
}

// Socket IO logic giữ nguyên
socket.on('step_update', (data) => {
    const { camera_id, cycle_count, current_step, status_msg, progress_percent } = data;
    const fill = document.getElementById(`progress-${camera_id}`);
    const label = document.getElementById(`step-name-${camera_id}`);
    const cycle = document.getElementById(`cycle-count-${camera_id}`);
    if (fill) fill.style.width = `${progress_percent}%`;
    if (label) label.innerText = current_step;
    if (cycle) cycle.innerText = cycle_count;
});

/* --- SPA NAVIGATION LOGIC --- */
function initSpaNavigation() {
    document.querySelectorAll('aside a, .nav-link').forEach(link => {
        // Sử dụng addEventListener để không ghi đè thuộc tính onclick="..." có sẵn trong HTML
        link.addEventListener('click', async (e) => {
            // Nếu sự kiện đã bị ngăn chặn (ví dụ bởi showTab() trả về false), thì dừng lại
            if (e.defaultPrevented) return;

            const href = link.getAttribute('href');
            if (href && href.startsWith('/') && !href.includes('/station/')) {
                e.preventDefault();
                await loadPage(href);
            }
        });
    });
}

async function loadPage(path, push = true) {
    const mainArea = document.getElementById('main-content-area');
    if (!mainArea) return;
    
    mainArea.style.opacity = '0.5'; // Làm mờ nhẹ khi đang tải
    
    try {
        const response = await fetch(path);
        const text = await response.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(text, 'text/html');
        const newContent = doc.getElementById('main-content-area');
        
        if (newContent) {
            if (push) history.pushState({ path }, '', path);
            mainArea.innerHTML = newContent.innerHTML;
            
            // Cập nhật trạng thái Active trên Sidebar
            updateSidebarActiveState(path);
            
            await initDashboard(); // Nạp lại dữ liệu cho trang mới
            initSpaNavigation();
            mainArea.style.opacity = '1';
        }
    } catch (err) { 
        console.error("SPA Load failed, falling back to normal navigation:", err);
        window.location.href = path; 
    }
}

/**
 * Cập nhật CSS class active cho các link sidebar dựa trên path hiện tại
 */
function updateSidebarActiveState(path) {
    document.querySelectorAll('aside a').forEach(link => {
        if (!link) return;
        const href = link.getAttribute('href');
        // Logic nhận diện path linh hoạt (hỗ trợ cả tab-id hoặc url path)
        const isActive = (href === path) || 
                         (path === '/' && href === '/sop') ||
                         (path.includes(href) && href !== '/');
                         
        if (isActive) {
            link.classList.add('bg-primary/10', 'text-primary');
            link.classList.remove('text-slate-600', 'hover:bg-slate-50');
        } else if (href && href !== '#') {
            link.classList.remove('bg-primary/10', 'text-primary');
            link.classList.add('text-slate-600', 'hover:bg-slate-50');
        }
    });
}

async function updateSystemHealth() {
    try {
        const response = await fetch('/api/system/health');
        const data = await response.json();
        if (document.getElementById('cpu-val')) document.getElementById('cpu-val').innerText = `${data.cpu_usage_percent}%`;
        if (document.getElementById('ram-val')) document.getElementById('ram-val').innerText = `${data.ram_used_mb} MB`;
        if (document.getElementById('disk-val')) document.getElementById('disk-val').innerText = `${data.disk_free_gb} GB Free`;
    } catch (err) {}
}
