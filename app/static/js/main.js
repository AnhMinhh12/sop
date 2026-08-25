// Sử dụng biến toàn cục an toàn để tránh xung đột SyntaxError khi project vệ tinh cũng khai báo socket
if (typeof window.socket === 'undefined') {
    window.socket = typeof io !== 'undefined' ? io() : null;
}
const socket = window.socket;

// Store for chart and data
let violationChart = null;
let healthInterval = null;
let statsInterval = null;
let pieChart = null;
let lineChart = null;
let hourlyChart = null;

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
    if (statsInterval) {
        clearInterval(statsInterval);
        statsInterval = null;
    }

    // Reset chart instances khi chuyển trang hoặc re-init
    if (pieChart) { try { pieChart.destroy(); } catch(e) {} pieChart = null; }
    if (lineChart) { try { lineChart.destroy(); } catch(e) {} lineChart = null; }
    if (hourlyChart) { try { hourlyChart.destroy(); } catch(e) {} hourlyChart = null; }

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
/* --- LOGIC TRANG LỊCH SỬ --- */
async function loadProducts(stationId = '', selectElementId = 'filter-product') {
    console.log("[DEBUG_UI] loadProducts called with stationId:", stationId, "select:", selectElementId);
    const select = document.getElementById(selectElementId);
    if (!select) return;
    select.innerHTML = '<option value="">Tất cả mã</option>';
    
    const target = stationId || 'all';
    const url = `/api/station/${target}/products`;
    console.log("[DEBUG_UI] Fetching products from URL:", url);
    try {
        const response = await fetch(url);
        console.log("[DEBUG_UI] Response status:", response.status);
        const products = await response.json();
        console.log("[DEBUG_UI] Products received:", products);
        products.forEach(prod => {
            const opt = document.createElement('option');
            const cleanName = prod.name.replace(' (Auto)', '');
            opt.value = prod.id || cleanName;
            opt.textContent = cleanName;
            select.appendChild(opt);
        });
    } catch (err) {
        console.error("[DEBUG_UI] Error loading products:", err);
    }
}

let currentHistoryPage = 1;
const historyItemsPerPage = 50;

async function initHistoryPage(selectedId = "") {
    const stationSelect = document.getElementById('filter-station');
    const productSelect = document.getElementById('filter-product');
    const hourSelect = document.getElementById('filter-hour');
    const dateInput = document.getElementById('filter-date');

    if (stationSelect && stationSelect.options.length <= 1) {
        const response = await fetch('/api/cameras');
        const cameras = await response.json();
        cameras.forEach(cam => {
            const opt = document.createElement('option');
            const camId = cam.id || cam.station_id;
            opt.value = camId;
            opt.textContent = cam.name;
            if (camId === selectedId) opt.selected = true;
            stationSelect.appendChild(opt);
        });
    }

    // Load products dropdown on init
    await loadProducts(selectedId, 'filter-product');

    loadHistory(selectedId, productSelect ? productSelect.value : "", dateInput ? dateInput.value : "", hourSelect ? hourSelect.value : "", 1);

    if (stationSelect) {
        stationSelect.onchange = async () => {
            await loadProducts(stationSelect.value, 'filter-product');
            loadHistory(stationSelect.value, productSelect ? productSelect.value : "", dateInput ? dateInput.value : "", hourSelect ? hourSelect.value : "", 1);
        };
    }

    if (productSelect) {
        productSelect.onchange = () => {
            loadHistory(stationSelect ? stationSelect.value : "", productSelect.value, dateInput ? dateInput.value : "", hourSelect ? hourSelect.value : "", 1);
        };
    }

    if (hourSelect) {
        hourSelect.onchange = () => {
            loadHistory(stationSelect ? stationSelect.value : "", productSelect ? productSelect.value : "", dateInput ? dateInput.value : "", hourSelect.value, 1);
        };
    }

    // Gán sự kiện cho nút tìm kiếm nếu chưa có
    const searchBtn = document.querySelector('.btn-primary');
    if (searchBtn) {
        searchBtn.onclick = () => {
            loadHistory(stationSelect ? stationSelect.value : "", productSelect ? productSelect.value : "", dateInput ? dateInput.value : "", hourSelect ? hourSelect.value : "", 1);
        };
    }
}

function applyFilters() {
    const stationSelect = document.getElementById('filter-station');
    const productSelect = document.getElementById('filter-product');
    const hourSelect = document.getElementById('filter-hour');
    const dateInput = document.getElementById('filter-date');
    if (stationSelect && productSelect && dateInput) {
        loadHistory(stationSelect.value, productSelect.value, dateInput.value, hourSelect ? hourSelect.value : "", 1);
    }
}

async function loadHistory(stationId = '', productId = '', date = '', hour = '', page = 1) {
    currentHistoryPage = page;
    const list = document.getElementById('history-list');
    const paginationContainer = document.getElementById('pagination');
    if (!list) return;
    list.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 40px; color: #888;">Đang tải dữ liệu...</td></tr>';

    let url = `/api/events?page=${page}&limit=${historyItemsPerPage}&days=15`;
    if (stationId) url += `&camera_id=${stationId}`;
    if (productId) url += `&product_id=${productId}`;
    if (date) url += `&date=${date}`;
    if (hour !== "" && hour !== null && hour !== undefined) url += `&hour=${hour}`;

    try {
        const response = await fetch(url);
        const data = await response.json();
        const events = Array.isArray(data) ? data : (data.events || []);
        const total = data.total !== undefined ? data.total : events.length;
        const totalPages = data.total_pages !== undefined ? data.total_pages : 1;

        list.innerHTML = '';

        if (events.length === 0) {
            list.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 40px; color: #888;">Không tìm thấy bản ghi nào (15 ngày qua)</td></tr>';
            if (paginationContainer) paginationContainer.innerHTML = '';
            return;
        }

        events.forEach(ev => {
            let vTypeVN = "";
            if (ev.violation_type === 'success' || ev.sop_status === 'completed') {
                vTypeVN = 'Hoàn thành';
            } else if (ev.violation_type === 'timeout' || ev.violation_type === 'idle_timeout') {
                vTypeVN = 'Quá giờ';
            } else {
                vTypeVN = 'Sai thao tác';
            }

            // Tính thời gian vi phạm (s)
            let durationStr = '-';
            if (ev.duration !== null && ev.duration !== undefined && ev.duration !== '') {
                const durNum = parseFloat(ev.duration);
                durationStr = isNaN(durNum) ? ev.duration + 's' : (Number.isInteger(durNum) ? durNum + 's' : durNum.toFixed(1) + 's');
            } else if (ev.clip_duration !== null && ev.clip_duration !== undefined && ev.clip_duration !== '') {
                durationStr = ev.clip_duration + 's';
            }

            const isViolation = ev.sop_status === 'violation';
            const row = document.createElement('tr');
            row.className = 'event-row';
            if (!isViolation) row.style.opacity = '0.8';
            row.innerHTML = `
                <td>${ev.timestamp}</td>
                <td><span class="badge-station">${ev.station_id || 'Trạm ' + ev.camera_id}</span></td>
                <td><span class="event-type ${isViolation ? 'text-danger' : 'text-secondary'}">${vTypeVN}</span></td>
                <td>${ev.expected_step || '-'}</td>
                <td><span class="font-mono text-slate-700 font-semibold">${durationStr}</span></td>
                <td>
                    ${isViolation && ev.clip_path ? `<button class="btn-action" onclick="openVideo('${ev.id}', '${ev.station_id || ev.camera_id}', '${vTypeVN}')">▶ XEM LẠI</button>` : '<span class="text-xs text-slate-400">Không có video</span>'}
                </td>
            `;
            list.appendChild(row);
        });

        // Vẽ bộ chuyển trang
        renderPagination(paginationContainer, page, totalPages, total);

    } catch (err) { 
        console.error(err); 
        list.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 40px; color: #888;">Lỗi nạp dữ liệu</td></tr>'; 
    }
}

function renderPagination(container, currentPage, totalPages, totalCount) {
    if (!container) return;
    if (totalPages <= 1 && totalCount <= historyItemsPerPage) {
        container.innerHTML = `
            <div class="pagination-container">
                <div class="pagination-info">Hiển thị <strong>${totalCount}</strong> bản ghi (15 ngày qua)</div>
                <div></div>
            </div>
        `;
        return;
    }

    const startItem = (currentPage - 1) * historyItemsPerPage + 1;
    const endItem = Math.min(currentPage * historyItemsPerPage, totalCount);

    let pageButtonsHtml = '';

    // Nút Trang trước
    pageButtonsHtml += `<button class="page-btn" ${currentPage === 1 ? 'disabled' : ''} onclick="changeHistoryPage(${currentPage - 1})">❮ Trang trước</button>`;

    // Hiển thị các số trang
    const maxVisiblePages = 5;
    let startPage = Math.max(1, currentPage - 2);
    let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);

    if (endPage - startPage < maxVisiblePages - 1) {
        startPage = Math.max(1, endPage - maxVisiblePages + 1);
    }

    if (startPage > 1) {
        pageButtonsHtml += `<button class="page-btn" onclick="changeHistoryPage(1)">1</button>`;
        if (startPage > 2) pageButtonsHtml += `<span style="padding: 0 6px; color: #94a3b8; font-weight: bold;">...</span>`;
    }

    for (let p = startPage; p <= endPage; p++) {
        pageButtonsHtml += `<button class="page-btn ${p === currentPage ? 'active' : ''}" onclick="changeHistoryPage(${p})">${p}</button>`;
    }

    if (endPage < totalPages) {
        if (endPage < totalPages - 1) pageButtonsHtml += `<span style="padding: 0 6px; color: #94a3b8; font-weight: bold;">...</span>`;
        pageButtonsHtml += `<button class="page-btn" onclick="changeHistoryPage(${totalPages})">${totalPages}</button>`;
    }

    // Nút Trang sau
    pageButtonsHtml += `<button class="page-btn" ${currentPage === totalPages ? 'disabled' : ''} onclick="changeHistoryPage(${currentPage + 1})">Trang sau ❯</button>`;

    container.innerHTML = `
        <div class="pagination-container">
            <div class="pagination-info">Hiển thị <strong>${startItem}-${endItem}</strong> trong tổng số <strong>${totalCount}</strong> bản ghi (15 ngày qua)</div>
            <div class="pagination-controls">${pageButtonsHtml}</div>
        </div>
    `;
}

function changeHistoryPage(newPage) {
    const stationSelect = document.getElementById('filter-station');
    const productSelect = document.getElementById('filter-product');
    const hourSelect = document.getElementById('filter-hour');
    const dateInput = document.getElementById('filter-date');

    const stationId = stationSelect ? stationSelect.value : "";
    const productId = productSelect ? productSelect.value : "";
    const date = dateInput ? dateInput.value : "";
    const hour = hourSelect ? hourSelect.value : "";

    loadHistory(stationId, productId, date, hour, newPage);
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* --- LOGIC TRANG THỐNG KÊ --- */
async function initStatsPage(selectedId = "") {
    const stationSelect = document.getElementById('filter-station');
    const productSelect = document.getElementById('filter-product');
    const dateInput = document.getElementById('target-date');
    const startHourSelect = document.getElementById('filter-start-hour');
    const endHourSelect = document.getElementById('filter-end-hour');
    if (!dateInput) return;

    const d = new Date();
    const today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    dateInput.value = today;

    // Load filter options if empty
    if (stationSelect && stationSelect.options.length <= 1) {
        const response = await fetch('/api/cameras');
        const cameras = await response.json();
        cameras.forEach(cam => {
            const opt = document.createElement('option');
            const camId = cam.id || cam.station_id;
            opt.value = camId;
            opt.textContent = cam.name;
            if (camId === selectedId) opt.selected = true;
            stationSelect.appendChild(opt);
        });
    }

    // Load products dropdown on init
    await loadProducts(selectedId, 'filter-product');

    const triggerRefresh = () => {
        const dateVal = dateInput.value;
        const stationVal = stationSelect ? stationSelect.value : "";
        const productVal = productSelect ? productSelect.value : "";
        const startH = startHourSelect ? startHourSelect.value : "";
        const endH = endHourSelect ? endHourSelect.value : "";
        loadStats(dateVal, stationVal, productVal, startH, endH);
    };

    triggerRefresh();

    // 5 phút cập nhật biểu đồ 1 lần (300,000 ms) để tránh giật/nháy màn hình
    if (statsInterval) clearInterval(statsInterval);
    statsInterval = setInterval(triggerRefresh, 300000);

    dateInput.onchange = triggerRefresh;
    if (stationSelect) {
        stationSelect.onchange = async () => {
            await loadProducts(stationSelect.value, 'filter-product');
            triggerRefresh();
        };
    }
    if (productSelect) productSelect.onchange = triggerRefresh;
    if (startHourSelect) startHourSelect.onchange = triggerRefresh;
    if (endHourSelect) endHourSelect.onchange = triggerRefresh;
}

async function loadStats(date, cameraId = "", productId = "", startHour = "", endHour = "") {
    try {
        // Clean up inputs
        if (cameraId === "undefined" || cameraId === "null") cameraId = "";
        if (productId === "undefined" || productId === "null") productId = "";
        
        let filter = `date=${date}`;
        if (cameraId) filter += `&camera_id=${cameraId}`;
        if (productId) filter += `&product_id=${productId}`;
        if (startHour !== "" && startHour !== null && startHour !== undefined) filter += `&start_hour=${startHour}`;
        if (endHour !== "" && endHour !== null && endHour !== undefined) filter += `&end_hour=${endHour}`;

        // 1. Summary
        const summaryRes = await fetch(`/api/stats/summary?${filter}`);
        const summary = await summaryRes.json();
        document.getElementById('total-violations').innerText = summary.total_violations;
        document.getElementById('total-completions').innerText = `${summary.total_completions * 2}/4540`;
        document.getElementById('compliance-rate').innerText = `${summary.compliance_rate}%`;

        // 2. Pie Chart (Biểu đồ tròn chi tiết loại lỗi)
        const distRes = await fetch(`/api/stats/distribution?${filter}`);
        const distData = await distRes.json();
        renderPieChart(distData);

        // 3. Line/Area Chart (Biểu đồ miền xu hướng tuần)
        const trendRes = await fetch(`/api/stats/trend?${filter}`);
        const trendData = await trendRes.json();
        renderLineChart(trendData);

        // 4. Hourly Area Chart (Biểu đồ miền diễn biến theo thời gian)
        const hourlyRes = await fetch(`/api/stats/hourly?${filter}`);
        const hourlyData = await hourlyRes.json();
        renderHourlyChart(hourlyData);
    } catch (err) { console.error(err); }
}

function renderPieChart(data) {
    const canvas = document.getElementById('violationPieChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    
    if (pieChart) { try { pieChart.destroy(); } catch(e) {} pieChart = null; }
    
    const catMap = {
        'timeout': { name: 'Lỗi quá giờ', color: '#f59e0b' },
        'idle_timeout': { name: 'Lỗi quá giờ chờ', color: '#fbbf24' },
        'skip_step': { name: 'Lỗi bỏ bước', color: '#ef4444' },
        'wrong_sequence': { name: 'Lỗi sai thứ tự', color: '#dc2626' },
        'wrong_hand': { name: 'Lỗi sai tay thao tác', color: '#8b5cf6' },
        'wrong_position': { name: 'Lỗi vị trí linh kiện', color: '#ec4899' },
    };

    const labels = [];
    const values = [];
    const colors = [];
    let otherCount = 0;
    
    Object.keys(data).forEach(key => {
        const val = data[key];
        if (key === 'success' || val <= 0) return;
        
        if (catMap[key]) {
            labels.push(catMap[key].name);
            values.push(val);
            colors.push(catMap[key].color);
        } else {
            otherCount += val;
        }
    });

    if (otherCount > 0) {
        labels.push('Sai thao tác khác');
        values.push(otherCount);
        colors.push('#3b82f6');
    }

    if (labels.length === 0) {
        labels.push('Không có lỗi');
        values.push(1);
        colors.push('#e2e8f0');
    }

    pieChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{ 
                data: values, 
                backgroundColor: colors, 
                borderWidth: 2,
                borderColor: '#ffffff'
            }]
        },
        options: { 
            responsive: true, 
            maintainAspectRatio: false,
            animation: false,
            plugins: { 
                legend: { 
                    position: 'bottom',
                    labels: { boxWidth: 12, padding: 15, font: { size: 12, weight: '600' } }
                } 
            }, 
            cutout: '68%' 
        }
    });
}

function renderLineChart(data) {
    const canvas = document.getElementById('violationLineChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    
    if (lineChart) { try { lineChart.destroy(); } catch(e) {} lineChart = null; }
    
    const labels = data.map(d => d.day);
    const values = data.map(d => d.count);

    // Dynamic gradient fill for Area Chart (Biểu đồ miền)
    const gradient = ctx.createLinearGradient(0, 0, 0, 300);
    gradient.addColorStop(0, 'rgba(45, 92, 247, 0.35)');
    gradient.addColorStop(1, 'rgba(45, 92, 247, 0.01)');

    lineChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{ 
                label: 'Số lỗi vi phạm', 
                data: values, 
                borderColor: '#2d5cf7', 
                borderWidth: 3,
                backgroundColor: gradient, 
                fill: 'start', 
                tension: 0.4,
                pointRadius: 5,
                pointHoverRadius: 7,
                pointBackgroundColor: '#2d5cf7',
                pointBorderColor: '#ffffff',
                pointBorderWidth: 2
            }]
        },
        options: { 
            responsive: true, 
            maintainAspectRatio: false,
            animation: false,
            plugins: { 
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#1e293b',
                    padding: 10,
                    cornerRadius: 8
                }
            }, 
            scales: { 
                y: { 
                    beginAtZero: true, 
                    ticks: { 
                        stepSize: 200,
                        precision: 0 
                    } 
                },
                x: { grid: { display: false } }
            } 
        }
    });
    if (data && data.length > 0) {
        const trendTitle = document.getElementById('trend-title');
        if (trendTitle) {
            trendTitle.innerText = `Xu hướng vi phạm (Biểu đồ miền: ${data[0].date} đến ${data[data.length - 1].date})`;
        }
    }
}

function renderHourlyChart(data) {
    const canvas = document.getElementById('hourlyStatsChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    if (hourlyChart) { try { hourlyChart.destroy(); } catch(e) {} hourlyChart = null; }

    const labels = data.map(d => d.hour);
    const completions = data.map(d => d.completions * 2);
    const violations = data.map(d => d.violations);

    // Area chart gradient fills for completion & violation
    const compGradient = ctx.createLinearGradient(0, 0, 0, 300);
    compGradient.addColorStop(0, 'rgba(16, 185, 129, 0.35)');
    compGradient.addColorStop(1, 'rgba(16, 185, 129, 0.01)');

    const violGradient = ctx.createLinearGradient(0, 0, 0, 300);
    violGradient.addColorStop(0, 'rgba(239, 68, 68, 0.35)');
    violGradient.addColorStop(1, 'rgba(239, 68, 68, 0.01)');

    hourlyChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Sản phẩm hoàn thành',
                    data: completions,
                    borderColor: '#10b981',
                    borderWidth: 2.5,
                    backgroundColor: compGradient,
                    fill: 'start',
                    tension: 0.4,
                    pointRadius: 4,
                    pointBackgroundColor: '#10b981',
                    pointBorderColor: '#ffffff',
                    pointBorderWidth: 2
                },
                {
                    label: 'Lỗi vi phạm',
                    data: violations,
                    borderColor: '#ef4444',
                    borderWidth: 2.5,
                    backgroundColor: violGradient,
                    fill: 'start',
                    tension: 0.4,
                    pointRadius: 4,
                    pointBackgroundColor: '#ef4444',
                    pointBorderColor: '#ffffff',
                    pointBorderWidth: 2
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        boxWidth: 14,
                        padding: 15,
                        font: { size: 12, weight: '600' }
                    }
                },
                tooltip: {
                    backgroundColor: '#1e293b',
                    padding: 10,
                    cornerRadius: 8
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 200,
                        precision: 0
                    }
                },
                x: {
                    grid: { display: false }
                }
            }
        }
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
        card.href = cam.redirect_url || `/station/${cam.id}`;
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
        <div class="station-card" id="station-${cam.id}" style="height: calc(100vh - 140px); min-height: 500px;">
            <div class="video-section">
                <div class="video-wrapper">
                    <img class="video-feed" src="/video_feed/${cam.id}" alt="Stream">
                    <div class="bimanual-status">LH<div id="lh-${cam.id}" class="dot"></div> RH<div id="rh-${cam.id}" class="dot"></div></div>
                </div>
            </div>
            <div class="info-panel">
                <div class="station-header">
                    <div class="station-name">${cam.name}</div>
                    <div id="status-${cam.id}" class="status-indicator">READY</div>
                </div>

                <div class="product-selector-box mb-4">
                    <label class="panel-title">Mã sản phẩm</label>
                    <select id="product-select-${cam.id}" class="modern-select" onchange="switchProduct('${cam.id}', this.value)">
                        <option value="">Đang tải mã hàng...</option>
                    </select>
                </div>

                <!-- Countdown Banner replacing status-banner -->
                <div class="countdown-banner state-normal" id="countdown-banner-${cam.id}">
                    <div class="countdown-timer-icon" id="countdown-icon-${cam.id}">⏱️</div>
                    <div class="countdown-progress-container">
                        <div class="countdown-text-row">
                            <span class="countdown-label">
                                <span id="countdown-label-${cam.id}">Chu kỳ:</span> 
                                <span id="status-msg-${cam.id}" class="status-text font-bold ml-2">Hệ thống sẵn sàng</span>
                            </span>
                            <span id="countdown-val-${cam.id}" class="countdown-value">38.0s</span>
                        </div>
                        <div class="countdown-bar-bg">
                            <div id="countdown-bar-fill-${cam.id}" class="countdown-bar-fill" style="width: 100%"></div>
                        </div>
                    </div>
                </div>

                <div class="progress-section">
                    <div id="step-name-${cam.id}" class="current-step-title">Đang chờ bắt đầu...</div>
                    <div class="progress-bar"><div id="progress-${cam.id}" class="progress-fill" style="width: 0%"></div></div>
                </div>

                <div class="sop-section" style="flex: 1; overflow: hidden; display: flex; flex-direction: column;">
                    <div class="panel-title">Quy trình thực hiện (SOP)</div>
                    <div id="sop-list-${cam.id}" class="sop-steps-checklist" style="flex: 1;"></div>
                </div>
            </div>
        </div>
    `;
    
    // Khởi tạo các thành phần
    initProductSelector(cam.id, cam.engine_id);
    renderSopChecklist(cam.id);
}

/**
 * Vẽ danh sách các bước SOP (Checklist)
 */
async function renderSopChecklist(cameraId) {
    const list = document.getElementById('sop-list-' + cameraId);
    if (!list) return;

    try {
        const response = await fetch(`/api/station/${cameraId}/sop`);
        const steps = await response.json();

        if (steps && Array.isArray(steps)) {
            list.innerHTML = '';
            steps.forEach((step, index) => {
                const item = document.createElement('div');
                item.className = 'sop-step-item';
                item.id = `step-item-${cameraId}-${index}`;
                item.innerHTML = `
                    <div class="step-number">${index + 1}</div>
                    <div class="step-info">
                        <div class="step-name">${step.step_name || step.name}</div>
                        <div class="step-desc">${step.logic || 'Yêu cầu thao tác tay'}</div>
                    </div>
                    <div class="step-status" id="step-status-${cameraId}-${index}">○</div>
                `;
                list.appendChild(item);
            });
        }
    } catch (err) { console.error("Failed to render SOP checklist:", err); }
}

/**
 * Khởi tạo bộ chọn mã sản phẩm
 */
async function initProductSelector(cameraId, currentProductId) {
    const select = document.getElementById(`product-select-${cameraId}`);
    if (!select) return;

    try {
        const response = await fetch(`/api/station/${cameraId}/products`);
        const products = await response.json();
        
        select.innerHTML = '';
        products.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = p.name;
            if (p.id === currentProductId) opt.selected = true;
            select.appendChild(opt);
        });
    } catch (err) { console.error("Failed to load products:", err); }
}

/**
 * Chuyển đổi mã sản phẩm
 */
async function switchProduct(cameraId, productId) {
    if (!productId) return;
    
    const statusMsg = document.getElementById(`status-msg-${cameraId}`);
    if (statusMsg) statusMsg.innerText = "Đang chuyển đổi mã hàng...";

    try {
        const response = await fetch(`/api/station/${cameraId}/switch_product`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ product_id: productId })
        });
        const result = await response.json();
        
        if (result.success) {
            if (statusMsg) statusMsg.innerText = `Đã chuyển sang ${productId}`;
            // Nạp lại checklist mới
            renderSopChecklist(cameraId);
            // Hiển thị toast thông báo
            if (typeof showToast === 'function') showToast("Thành công", `Đã chuyển đổi sang mã hàng: ${productId}`, "success");
        } else {
            alert("Lỗi: " + result.error);
        }
    } catch (err) {
        console.error("Switch product failed:", err);
    }
}

/**
 * Nạp danh sách 10 sự kiện gần nhất của một trạm cụ thể
 */
async function loadRecentEvents(cameraId) {
    const list = document.getElementById('recent-list-' + cameraId);
    if (!list) return;

    try {
        const response = await fetch(`/api/events?camera_id=${cameraId}&limit=10&format=list`);
        const data = await response.json();
        const events = Array.isArray(data) ? data : (data.events || []);

        list.innerHTML = '';
        if (events.length === 0) {
            list.innerHTML = '<div class="text-muted p-2 text-center text-sm">Chưa có dữ liệu</div>';
            return;
        }

        events.forEach(ev => {
            const isViolation = ev.sop_status === 'violation';
            const item = document.createElement('div');
            item.className = `recent-event-item ${isViolation ? 'border-l-red-500' : 'border-l-green-500'}`;
            item.innerHTML = `
                <div class="flex justify-between text-xs">
                    <span class="font-bold ${isViolation ? 'text-red-600' : 'text-green-600'}">
                        ${isViolation ? 'VI PHẠM' : 'HOÀN THÀNH'}
                    </span>
                    <span class="text-slate-400">${ev.timestamp.split(' ')[1]}</span>
                </div>
                <div class="text-sm text-slate-700">${ev.step_detected || 'Chu kỳ SOP'}</div>
            `;
            list.appendChild(item);
        });
    } catch (err) {
        console.error("Failed to load recent events:", err);
    }
}

/**
 * Hiển thị thông báo Toast
 */
function showToast(title, message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const now = new Date();
    const timeStr = now.getHours().toString().padStart(2, '0') + ':' + 
                    now.getMinutes().toString().padStart(2, '0') + ':' + 
                    now.getSeconds().toString().padStart(2, '0');

    toast.innerHTML = `
        <div class="toast-header">
            <span class="toast-title">${title}</span>
            <div style="display: flex; align-items: center; gap: 8px;">
                <span class="toast-time">${timeStr}</span>
                <button class="toast-close" type="button">&times;</button>
            </div>
        </div>
        <div class="toast-body">${message}</div>
    `;

    container.appendChild(toast);

    // Xử lý nút đóng nhanh
    const closeBtn = toast.querySelector('.toast-close');
    let autoRemoveTimeout = null;

    const dismissToast = () => {
        if (autoRemoveTimeout) clearTimeout(autoRemoveTimeout);
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    };

    if (closeBtn) {
        closeBtn.onclick = dismissToast;
    }

    // Tự động xóa sau 5 giây
    autoRemoveTimeout = setTimeout(dismissToast, 5000);
}

// Socket IO logic giữ nguyên
socket.on('step_update', (data) => {
    const { camera_id, cycle_count, current_step, status_msg, progress_percent, step_index, cycle_time_left } = data;
    
    // --- CẬP NHẬT TRANG THỐNG KÊ REALTIME ---
    if (data.sop_status === 'completed' || data.sop_status === 'violation') {
        const statsDateInput = document.getElementById('target-date');
        if (statsDateInput) {
            const statsStationSelect = document.getElementById('filter-station');
            const statsProductSelect = document.getElementById('filter-product');
            loadStats(statsDateInput.value, statsStationSelect ? statsStationSelect.value : "", statsProductSelect ? statsProductSelect.value : "");
        }
    }

    // Cập nhật Progress Bar & Tiêu đề
    const fill = document.getElementById(`progress-${camera_id}`);
    const label = document.getElementById(`step-name-${camera_id}`);
    const cycle = document.getElementById(`cycle-count-${camera_id}`);
    const statusFooter = document.getElementById(`status-msg-${camera_id}`);
    const statusIndicator = document.getElementById(`status-${camera_id}`);

    if (fill) fill.style.width = `${progress_percent}%`;
    if (label) label.innerText = current_step;
    if (cycle) cycle.innerText = cycle_count;
    if (statusFooter) statusFooter.innerText = status_msg;
    
    // Đổi màu indicator nếu đang chạy
    if (statusIndicator) {
        statusIndicator.innerText = "STREAMING";
        statusIndicator.style.background = "#dcfce7";
        statusIndicator.style.color = "#15803d";
    }

    // Cập nhật Countdown Timer
    const countdownVal = document.getElementById(`countdown-val-${camera_id}`);
    const countdownFill = document.getElementById(`countdown-bar-fill-${camera_id}`);
    const countdownBanner = document.getElementById(`countdown-banner-${camera_id}`);
    const countdownLabel = document.getElementById(`countdown-label-${camera_id}`);
    const countdownIcon = document.getElementById(`countdown-icon-${camera_id}`);

    if (cycle_time_left !== undefined) {
        if (countdownVal) countdownVal.innerText = `${cycle_time_left.toFixed(1)}s`;
        if (countdownFill) {
            const maxCycleTime = data.max_cycle_time || 38.0;
            const percentage = (cycle_time_left / maxCycleTime) * 100;
            countdownFill.style.width = `${percentage}%`;
            
            // Remove previous classes
            countdownFill.classList.remove('warning', 'danger');
            if (countdownBanner) {
                countdownBanner.classList.remove('state-normal', 'state-warning', 'state-danger');
            }

            if (data.sop_status === 'violation') {
                countdownFill.classList.add('danger');
                if (countdownBanner) countdownBanner.classList.add('state-danger');
                if (countdownVal) countdownVal.innerText = `TIMEOUT`;
                if (countdownLabel) countdownLabel.innerText = `Lỗi quá giờ: `;
                if (countdownIcon) countdownIcon.innerText = `🚨`;
            } else if (cycle_time_left <= 5.0) {
                countdownFill.classList.add('danger');
                if (countdownBanner) countdownBanner.classList.add('state-danger');
                if (countdownLabel) countdownLabel.innerText = `Thời gian còn lại: `;
                if (countdownIcon) countdownIcon.innerText = `⚠️`;
            } else if (cycle_time_left <= 15.0) {
                countdownFill.classList.add('warning');
                if (countdownBanner) countdownBanner.classList.add('state-warning');
                if (countdownLabel) countdownLabel.innerText = `Thời gian còn lại: `;
                if (countdownIcon) countdownIcon.innerText = `⏱️`;
            } else {
                if (countdownBanner) countdownBanner.classList.add('state-normal');
                if (countdownLabel) {
                    if (data.sop_status === 'idle') {
                        countdownLabel.innerText = `Chu kỳ tiếp theo: `;
                        if (countdownIcon) countdownIcon.innerText = `⏱️`;
                    } else if (data.sop_status === 'completed') {
                        countdownLabel.innerText = `Hoàn thành chu kỳ! `;
                        if (countdownIcon) countdownIcon.innerText = `✅`;
                    } else {
                        countdownLabel.innerText = `Chu kỳ: `;
                        if (countdownIcon) countdownIcon.innerText = `⏱️`;
                    }
                }
            }
        }
    }

    // --- LOGIC TÍCH CHỌN CHECKLIST ---
    if (step_index !== undefined) {
        // Lấy tất cả các item trong checklist của trạm này
        const steps = document.querySelectorAll(`[id^="step-item-${camera_id}-"]`);
        
        steps.forEach((el, idx) => {
            const statusIcon = document.getElementById(`step-status-${camera_id}-${idx}`);
            
            // Xóa hết trạng thái cũ
            el.classList.remove('active', 'completed');
            
            const isCompleted = (data.step_states && Array.isArray(data.step_states)) 
                ? !!data.step_states[idx] 
                : (idx < step_index);

            if (isCompleted) {
                // Các bước đã hoàn thành
                el.classList.add('completed');
                if (statusIcon) {
                    statusIcon.innerHTML = '✓';
                    statusIcon.style.color = '#10b981'; // Màu xanh lá
                }
            } else if (idx === step_index) {
                // Bước đang thực hiện
                el.classList.add('active');
                if (statusIcon) {
                    statusIcon.innerHTML = '▶';
                    statusIcon.style.color = '#3b82f6'; // Màu xanh dương
                }
                
                // TỰ ĐỘNG CUỘN ĐẾN BƯỚC NÀY
                el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            } else {
                // Các bước chưa tới
                if (statusIcon) {
                    statusIcon.innerHTML = '○';
                    statusIcon.style.color = '#cbd5e1';
                }
            }
        });
    }
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
    } catch (err) { }
}

// --- LẮNG NGHE THÔNG BÁO VI PHẠM (DẠNG TOAST) ---
socket.on('violation', (data) => {
    const { camera_id, violation_type, expected_step, detected_step, timestamp, clip_path } = data;
    
    // 1. Hiện thông báo Toast đỏ cực rõ
    if (typeof showToast === 'function') {
        showToast(
            "PHÁT HIỆN VI PHẠM!", 
            `Trạm ${camera_id}: ${violation_type}. Yêu cầu bước: ${expected_step}`, 
            "danger"
        );
    }
    
    // 2. Hiệu ứng rung đỏ khung hình video
    const card = document.getElementById(`station-${camera_id}`);
    if (card) {
        card.classList.add('violation-active');
        setTimeout(() => card.classList.remove('violation-active'), 3000);
    }
});
