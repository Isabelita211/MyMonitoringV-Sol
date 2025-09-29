import os

# Configuración de base de datos
# Para desarrollo local usa SQLite, para producción PostgreSQL
USE_SQLITE = os.getenv('USE_SQLITE', 'true').lower() == 'true'

if USE_SQLITE:
    DB_CONFIG = {
        'database': 'monitor_vsol.db',  # Archivo SQLite local
        'driver': 'sqlite3'
    }
else:
    DB_CONFIG = {
        'host': os.getenv('DB_HOST', '172.20.5.2'),
        'database': os.getenv('DB_NAME', 'n8n_automations'),
        'user': os.getenv('DB_USER', 'n8n_automations'),
        'password': os.getenv('DB_PASSWORD', 'tu_password'),
        'port': int(os.getenv('DB_PORT', 5432))
    }

# Configuración de red
NETWORK_CONFIG = {
    'scan_ranges': [
        '10.0.0.',
        '172.16.0.', 
        '192.168.0.',
        '192.168.1.',
        '192.168.100.'
    ],
    'ssh_credentials': [
        {'username': 'admin', 'password': 'admin'},
        {'username': 'admin', 'password': 'Admin123!'},
        {'username': 'admin', 'password': 'vsol123'},
    ]
}

# Configuración de la aplicación
APP_CONFIG = {
    'scan_interval': 300,  # 5 minutos
    'update_interval': 30,  # 30 segundos
    'port': 5000
}