from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
import threading
import time
import logging
from datetime import datetime
import json
from monitor_vsol import VSOLMonitorEmpresarial

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu_clave_secreta'
socketio = SocketIO(app, cors_allowed_origins="*")

# Instancia global del monitor
monitor = None

@app.route('/')
def index():
    """Página principal del dashboard"""
    return render_template('index.html')

@app.route('/olts')
def olts_page():
    """Página de lista de OLTs"""
    return render_template('olts.html')

@app.route('/onus')
def onus_page():
    """Página de ONUs"""
    return render_template('onus.html')

# API Endpoints
@app.route('/api/olts')
def get_olts():
    """API para obtener OLTs"""
    if monitor:
        return jsonify({
            'olts': list(monitor.olts_detectadas.values()),
            'total': len(monitor.olts_detectadas)
        })
    return jsonify({'olts': [], 'total': 0})

@app.route('/api/olts/<olt_ip>')
def get_olt_detail(olt_ip):
    """API para detalle de OLT específica"""
    if monitor and olt_ip in monitor.olts_detectadas:
        return jsonify(monitor.olts_detectadas[olt_ip])
    return jsonify({'error': 'OLT no encontrada'})

@app.route('/api/onus/<olt_ip>')
def get_onus_by_olt(olt_ip):
    """API para ONUs de una OLT"""
    if monitor and olt_ip in monitor.olts_detectadas:
        olt = monitor.olts_detectadas[olt_ip]
        return jsonify({
            'onus': olt.onus_detalladas,
            'total': olt.total_onus
        })
    return jsonify({'onus': [], 'total': 0})

@app.route('/api/scan', methods=['POST'])
def start_scan():
    """API para iniciar escaneo"""
    def scan_background():
        try:
            socketio.emit('scan_status', {'status': 'started', 'message': 'Iniciando escaneo...'})
            monitor.escanear_red_empresarial()
            socketio.emit('scan_status', {'status': 'completed', 'message': f'Escaneo completado. {len(monitor.olts_detectadas)} OLTs encontradas'})
        except Exception as e:
            socketio.emit('scan_status', {'status': 'error', 'message': f'Error en escaneo: {str(e)}'})
    
    thread = threading.Thread(target=scan_background)
    thread.daemon = True
    thread.start()
    
    return jsonify({'status': 'scan_started'})

@app.route('/api/stats')
def get_stats():
    """API para estadísticas generales"""
    if not monitor:
        return jsonify({})
    
    total_onus = sum(olt.total_onus for olt in monitor.olts_detectadas.values())
    olts_online = len([olt for olt in monitor.olts_detectadas.values()])
    
    return jsonify({
        'total_olts': len(monitor.olts_detectadas),
        'total_onus': total_onus,
        'olts_online': olts_online,
        'last_update': datetime.now().isoformat()
    })

# WebSocket events
@socketio.on('connect')
def handle_connect():
    print('Cliente conectado via WebSocket')
    socketio.emit('status', {'message': 'Conectado al monitor VSOL'})

@socketio.on('request_update')
def handle_update_request():
    """Actualización en tiempo real"""
    if monitor:
        stats = {
            'total_olts': len(monitor.olts_detectadas),
            'total_onus': sum(olt.total_onus for olt in monitor.olts_detectadas.values()),
            'timestamp': datetime.now().isoformat()
        }
        socketio.emit('real_time_update', stats)

def background_monitoring():
    """Monitoreo en segundo plano"""
    while True:
        try:
            if monitor:
                # Actualizar datos cada 30 segundos
                for ip, olt_info in monitor.olts_detectadas.items():
                    try:
                        # Aquí iría la lógica de actualización
                        socketio.emit('olt_update', {
                            'ip': ip,
                            'status': 'online',
                            'timestamp': datetime.now().isoformat()
                        })
                    except Exception as e:
                        logging.error(f"Error actualizando OLT {ip}: {e}")
            
            time.sleep(30)  # Actualizar cada 30 segundos
        except Exception as e:
            logging.error(f"Error en monitoreo background: {e}")
            time.sleep(60)

if __name__ == '__main__':
    # Inicializar monitor
    from config import DB_CONFIG
    monitor = VSOLMonitorEmpresarial(DB_CONFIG)
    
    # Iniciar monitoreo en background
    monitor_thread = threading.Thread(target=background_monitoring)
    monitor_thread.daemon = True
    monitor_thread.start()
    
    # Iniciar servidor web
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)