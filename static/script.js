// Conexión WebSocket
const socket = io();

// Elementos DOM
const totalOltsElement = document.getElementById('total-olts');
const totalOnusElement = document.getElementById('total-onus');
const oltsOnlineElement = document.getElementById('olts-online');
const lastUpdateElement = document.getElementById('last-update');
const scanBtn = document.getElementById('scan-btn');
const scanStatus = document.getElementById('scan-status');
const oltsList = document.getElementById('olts-list');

// Actualizar estadísticas
function updateStats(stats) {
    totalOltsElement.textContent = stats.total_olts;
    totalOnusElement.textContent = stats.total_onus;
    oltsOnlineElement.textContent = stats.olts_online;
    lastUpdateElement.textContent = new Date(stats.timestamp).toLocaleTimeString();
}

// Cargar OLTs
async function loadOlts() {
    try {
        const response = await fetch('/api/olts');
        const data = await response.json();
        renderOltsList(data.olts);
    } catch (error) {
        console.error('Error cargando OLTs:', error);
    }
}

// Renderizar lista de OLTs
function renderOltsList(olts) {
    if (olts.length === 0) {
        oltsList.innerHTML = '<p class="text-muted">No hay OLTs detectadas</p>';
        return;
    }

    let html = `
        <table class="table table-striped">
            <thead>
                <tr>
                    <th>Nombre</th>
                    <th>IP</th>
                    <th>Modelo</th>
                    <th>ONUs</th>
                    <th>Estado</th>
                </tr>
            </thead>
            <tbody>
    `;

    olts.forEach(olt => {
        html += `
            <tr>
                <td>${olt.nombre}</td>
                <td>${olt.ip}</td>
                <td>${olt.modelo}</td>
                <td>${olt.total_onus}</td>
                <td><span class="badge bg-success">Online</span></td>
            </tr>
        `;
    });

    html += '</tbody></table>';
    oltsList.innerHTML = html;
}

// Iniciar escaneo
scanBtn.addEventListener('click', async () => {
    scanBtn.disabled = true;
    scanBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Escaneando...';
    
    try {
        const response = await fetch('/api/scan', { method: 'POST' });
        const data = await response.json();
        
        if (data.status === 'scan_started') {
            scanStatus.innerHTML = '<div class="alert alert-info">Escaneo iniciado...</div>';
        }
    } catch (error) {
        console.error('Error iniciando escaneo:', error);
        scanStatus.innerHTML = '<div class="alert alert-danger">Error iniciando escaneo</div>';
    }
});

// Eventos WebSocket
socket.on('connect', () => {
    console.log('Conectado al servidor');
});

socket.on('real_time_update', (data) => {
    updateStats(data);
});

socket.on('scan_status', (data) => {
    scanStatus.innerHTML = `<div class="alert alert-${data.status === 'completed' ? 'success' : data.status === 'error' ? 'danger' : 'info'}">${data.message}</div>`;
    
    if (data.status === 'completed' || data.status === 'error') {
        scanBtn.disabled = false;
        scanBtn.innerHTML = '<i class="fas fa-search"></i> Iniciar Escaneo';
        loadOlts(); // Recargar lista después del escaneo
    }
});

socket.on('olt_update', (data) => {
    console.log('Actualización OLT:', data);
    // Actualizar interfaz en tiempo real
});

// Cargar datos iniciales
document.addEventListener('DOMContentLoaded', () => {
    loadOlts();
    
    // Cargar estadísticas iniciales
    fetch('/api/stats')
        .then(response => response.json())
        .then(updateStats);
});