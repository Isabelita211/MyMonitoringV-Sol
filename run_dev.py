#!/usr/bin/env python3
"""
Script para ejecutar la aplicación en modo desarrollo
"""

import os
import sys

# Configurar variables de entorno para desarrollo
os.environ['FLASK_ENV'] = 'development'
os.environ['USE_SQLITE'] = 'true'

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(__file__))

# Importar y ejecutar la aplicación
from app import app, socketio

if __name__ == '__main__':
    print("🚀 Iniciando Monitor VSOL en modo desarrollo...")
    print("📱 Interfaz web: http://localhost:5000")
    print("🛑 Presiona Ctrl+C para detener")

    # Ejecutar con SocketIO
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)