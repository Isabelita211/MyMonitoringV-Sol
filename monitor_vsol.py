# monitor_vsol.py
import paramiko
import threading
import time
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import psycopg2
from psycopg2.extras import RealDictCursor
import sqlite3
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
import random
import socket
import os
import json

# Import SNMP
from pysnmp.hlapi import (
    getCmd,
    nextCmd,
    SnmpEngine,
    CommunityData,
    UdpTransportTarget,
    ContextData,
    ObjectType,
    ObjectIdentity
)

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitor_vsol.log'),
        logging.StreamHandler()
    ]
)

@dataclass
class ONUInfo:
    serial: str
    interfaz: str
    slot: str
    puerto: str
    rx_power: float
    tx_power: float
    estado: str
    consumo_bytes: int = 0
    ultima_actualizacion: datetime = None

    def to_dict(self):
        return asdict(self)

@dataclass
class OLTInfo:
    ip: str
    nombre: str
    modelo: str
    temperatura: Optional[float] = None
    consumo_cpu: Optional[float] = None
    consumo_memoria: Optional[float] = None
    total_onus: int = 0
    onus_por_puerto: Dict[str, int] = None
    onus_detalladas: List[ONUInfo] = None

    def __post_init__(self):
        if self.onus_por_puerto is None:
            self.onus_por_puerto = {}
        if self.onus_detalladas is None:
            self.onus_detalladas = []

    def to_dict(self):
        result = asdict(self)
        # Convertir ONUInfo a dict
        result['onus_detalladas'] = [onu.to_dict() for onu in self.onus_detalladas]
        return result

class DatabaseManager:
    def __init__(self, db_config=None):
        self.db_config = db_config
        self.is_sqlite = 'driver' in db_config and db_config['driver'] == 'sqlite3'
        self.conn = None
        self.conectar()
        self.crear_tablas()

    def conectar(self):
        """Conecta a la base de datos (PostgreSQL o SQLite)"""
        try:
            if self.is_sqlite:
                self.conn = sqlite3.connect(self.db_config['database'])
                logging.info("✅ Conectado a SQLite")
            else:
                self.conn = psycopg2.connect(**self.db_config)
                logging.info("✅ Conectado a PostgreSQL")
        except Exception as e:
            logging.error(f"❌ Error conectando a la base de datos: {e}")
            raise

    def crear_tablas(self):
        """Crea las tablas necesarias (PostgreSQL o SQLite)"""
        try:
            cursor = self.conn.cursor()

            if self.is_sqlite:
                # Tabla de OLTs - SQLite
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS olts (
                        ip TEXT PRIMARY KEY,
                        nombre TEXT,
                        modelo TEXT,
                        ultima_actualizacion TIMESTAMP,
                        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Tabla de ONUs - SQLite
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS onus (
                        serial TEXT PRIMARY KEY,
                        olt_ip TEXT,
                        interfaz TEXT,
                        slot TEXT,
                        puerto TEXT,
                        rx_power REAL,
                        tx_power REAL,
                        estado TEXT,
                        consumo_bytes INTEGER DEFAULT 0,
                        ultima_actualizacion TIMESTAMP,
                        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (olt_ip) REFERENCES olts (ip) ON DELETE CASCADE
                    )
                ''')

                # Tabla de métricas - SQLite
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS metricas (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        olt_ip TEXT,
                        tipo_metrica TEXT,
                        valor REAL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (olt_ip) REFERENCES olts (ip) ON DELETE CASCADE
                    )
                ''')

                # Tabla de tráfico - SQLite
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS trafico (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        olt_ip TEXT,
                        onu_serial TEXT,
                        bytes_rx INTEGER,
                        bytes_tx INTEGER,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (olt_ip) REFERENCES olts (ip) ON DELETE CASCADE,
                        FOREIGN KEY (onu_serial) REFERENCES onus (serial) ON DELETE CASCADE
                    )
                ''')
            else:
                # Tabla de OLTs - PostgreSQL
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS olts (
                        ip VARCHAR(15) PRIMARY KEY,
                        nombre VARCHAR(100),
                        modelo VARCHAR(100),
                        ultima_actualizacion TIMESTAMP,
                        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Tabla de ONUs - PostgreSQL
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS onus (
                        serial VARCHAR(50) PRIMARY KEY,
                        olt_ip VARCHAR(15),
                        interfaz VARCHAR(20),
                        slot VARCHAR(10),
                        puerto VARCHAR(10),
                        rx_power DECIMAL(8,2),
                        tx_power DECIMAL(8,2),
                        estado VARCHAR(20),
                        consumo_bytes BIGINT DEFAULT 0,
                        ultima_actualizacion TIMESTAMP,
                        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (olt_ip) REFERENCES olts (ip) ON DELETE CASCADE
                    )
                ''')

                # Tabla de métricas - PostgreSQL
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS metricas (
                        id SERIAL PRIMARY KEY,
                        olt_ip VARCHAR(15),
                        tipo_metrica VARCHAR(50),
                        valor DECIMAL(8,2),
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (olt_ip) REFERENCES olts (ip) ON DELETE CASCADE
                    )
                ''')

                # Tabla de tráfico - PostgreSQL
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS trafico (
                        id SERIAL PRIMARY KEY,
                        olt_ip VARCHAR(15),
                        onu_serial VARCHAR(50),
                        bytes_rx BIGINT,
                        bytes_tx BIGINT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (olt_ip) REFERENCES olts (ip) ON DELETE CASCADE,
                        FOREIGN KEY (onu_serial) REFERENCES onus (serial) ON DELETE CASCADE
                    )
                ''')

            self.conn.commit()
            db_type = "SQLite" if self.is_sqlite else "PostgreSQL"
            logging.info(f"✅ Tablas creadas/existen en {db_type}")

        except Exception as e:
            logging.error(f"❌ Error creando tablas: {e}")
            if not self.is_sqlite:
                self.conn.rollback()

    def guardar_olt(self, olt_info):
        """Guarda o actualiza una OLT en la base de datos"""
        try:
            cursor = self.conn.cursor()
            if self.is_sqlite:
                cursor.execute('''
                    INSERT OR REPLACE INTO olts (ip, nombre, modelo, ultima_actualizacion)
                    VALUES (?, ?, ?, ?)
                ''', (olt_info.ip, olt_info.nombre, olt_info.modelo, datetime.now()))
            else:
                cursor.execute('''
                    INSERT INTO olts (ip, nombre, modelo, ultima_actualizacion)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (ip)
                    DO UPDATE SET
                        nombre = EXCLUDED.nombre,
                        modelo = EXCLUDED.modelo,
                        ultima_actualizacion = EXCLUDED.ultima_actualizacion
                ''', (olt_info.ip, olt_info.nombre, olt_info.modelo, datetime.now()))
            self.conn.commit()
        except Exception as e:
            logging.error(f"Error guardando OLT {olt_info.ip}: {e}")
            if not self.is_sqlite:
                self.conn.rollback()

    def guardar_onu(self, onu_info, olt_ip):
        """Guarda o actualiza una ONU en la base de datos"""
        try:
            cursor = self.conn.cursor()
            if self.is_sqlite:
                cursor.execute('''
                    INSERT OR REPLACE INTO onus
                    (serial, olt_ip, interfaz, slot, puerto, rx_power, tx_power, estado, consumo_bytes, ultima_actualizacion)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (onu_info.serial, olt_ip, onu_info.interfaz, onu_info.slot, onu_info.puerto,
                    onu_info.rx_power, onu_info.tx_power, onu_info.estado, onu_info.consumo_bytes,
                    onu_info.ultima_actualizacion))
            else:
                cursor.execute('''
                    INSERT INTO onus
                    (serial, olt_ip, interfaz, slot, puerto, rx_power, tx_power, estado, consumo_bytes, ultima_actualizacion)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (serial)
                    DO UPDATE SET
                        olt_ip = EXCLUDED.olt_ip,
                        interfaz = EXCLUDED.interfaz,
                        slot = EXCLUDED.slot,
                        puerto = EXCLUDED.puerto,
                        rx_power = EXCLUDED.rx_power,
                        tx_power = EXCLUDED.tx_power,
                        estado = EXCLUDED.estado,
                        consumo_bytes = EXCLUDED.consumo_bytes,
                        ultima_actualizacion = EXCLUDED.ultima_actualizacion
                ''', (onu_info.serial, olt_ip, onu_info.interfaz, onu_info.slot, onu_info.puerto,
                    onu_info.rx_power, onu_info.tx_power, onu_info.estado, onu_info.consumo_bytes,
                    onu_info.ultima_actualizacion))
            self.conn.commit()
        except Exception as e:
            logging.error(f"Error guardando ONU {onu_info.serial}: {e}")
            if not self.is_sqlite:
                self.conn.rollback()

    def guardar_metrica(self, olt_ip, tipo_metrica, valor):
        """Guarda una métrica en la base de datos"""
        try:
            cursor = self.conn.cursor()
            if self.is_sqlite:
                cursor.execute('''
                    INSERT INTO metricas (olt_ip, tipo_metrica, valor, timestamp)
                    VALUES (?, ?, ?, ?)
                ''', (olt_ip, tipo_metrica, valor, datetime.now()))
            else:
                cursor.execute('''
                    INSERT INTO metricas (olt_ip, tipo_metrica, valor, timestamp)
                    VALUES (%s, %s, %s, %s)
                ''', (olt_ip, tipo_metrica, valor, datetime.now()))
            self.conn.commit()
        except Exception as e:
            logging.error(f"Error guardando métrica {tipo_metrica} para {olt_ip}: {e}")
            if not self.is_sqlite:
                self.conn.rollback()

    def guardar_trafico(self, olt_ip, onu_serial, bytes_rx, bytes_tx):
        """Guarda datos de tráfico para gráficos"""
        try:
            cursor = self.conn.cursor()
            if self.is_sqlite:
                cursor.execute('''
                    INSERT INTO trafico (olt_ip, onu_serial, bytes_rx, bytes_tx)
                    VALUES (?, ?, ?, ?)
                ''', (olt_ip, onu_serial, bytes_rx, bytes_tx))
            else:
                cursor.execute('''
                    INSERT INTO trafico (olt_ip, onu_serial, bytes_rx, bytes_tx)
                    VALUES (%s, %s, %s, %s)
                ''', (olt_ip, onu_serial, bytes_rx, bytes_tx))
            self.conn.commit()
        except Exception as e:
            logging.error(f"Error guardando tráfico para {onu_serial}: {e}")
            if not self.is_sqlite:
                self.conn.rollback()

    def obtener_olts(self):
        """Obtiene todas las OLTs de la base de datos"""
        try:
            if self.is_sqlite:
                cursor = self.conn.cursor()
                cursor.execute('SELECT * FROM olts ORDER BY creado_en DESC')
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows]
            else:
                cursor = self.conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute('SELECT * FROM olts ORDER BY creado_en DESC')
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error obteniendo OLTs: {e}")
            return []

    def obtener_onus_por_olt(self, olt_ip):
        """Obtiene todas las ONUs de una OLT específica"""
        try:
            if self.is_sqlite:
                cursor = self.conn.cursor()
                cursor.execute('''
                    SELECT * FROM onus
                    WHERE olt_ip = ?
                    ORDER BY interfaz, puerto
                ''', (olt_ip,))
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows]
            else:
                cursor = self.conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute('''
                    SELECT * FROM onus
                    WHERE olt_ip = %s
                    ORDER BY interfaz, puerto
                ''', (olt_ip,))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error obteniendo ONUs para {olt_ip}: {e}")
            return []

    def obtener_metricas_recientes(self, olt_ip, tipo_metrica, limite=10):
        """Obtiene métricas recientes para gráficos"""
        try:
            if self.is_sqlite:
                cursor = self.conn.cursor()
                cursor.execute('''
                    SELECT valor, timestamp
                    FROM metricas
                    WHERE olt_ip = ? AND tipo_metrica = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (olt_ip, tipo_metrica, limite))
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows]
            else:
                cursor = self.conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute('''
                    SELECT valor, timestamp
                    FROM metricas
                    WHERE olt_ip = %s AND tipo_metrica = %s
                    ORDER BY timestamp DESC
                    LIMIT %s
                ''', (olt_ip, tipo_metrica, limite))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error obteniendo métricas para {olt_ip}: {e}")
            return []

    def obtener_trafico_reciente(self, olt_ip, limite=20):
        """Obtiene datos de tráfico recientes"""
        try:
            if self.is_sqlite:
                cursor = self.conn.cursor()
                cursor.execute('''
                    SELECT t.*, o.serial, o.interfaz
                    FROM trafico t
                    JOIN onus o ON t.onu_serial = o.serial
                    WHERE t.olt_ip = ?
                    ORDER BY t.timestamp DESC
                    LIMIT ?
                ''', (olt_ip, limite))
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows]
            else:
                cursor = self.conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute('''
                    SELECT t.*, o.serial, o.interfaz
                    FROM trafico t
                    JOIN onus o ON t.onu_serial = o.serial
                    WHERE t.olt_ip = %s
                    ORDER BY t.timestamp DESC
                    LIMIT %s
                ''', (olt_ip, limite))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error obteniendo tráfico para {olt_ip}: {e}")
            return []

class VSOLMonitorEmpresarial:
    def __init__(self, db_config=None):
        # Configuración de escaneo para entorno empresarial
        self.rangos_ip = [
            '10.0.0.',      # Red empresarial común
            '172.16.0.',    # Red privada empresa
            '192.168.0.',   # Red LAN
            '192.168.1.',   # Red administrativa
            '192.168.100.', # Red de gestión OLT
        ]

        self.credenciales = [
            {'username': 'admin', 'password': 'admin'},
            {'username': 'admin', 'password': 'Admin123!'},
            {'username': 'admin', 'password': 'vsol123'},
            {'username': 'support', 'password': 'support'},
            {'username': 'root', 'password': 'root'},
        ]

        # Configuración SNMP
        from config import SNMP_CONFIG
        self.snmp_config = SNMP_CONFIG
        self.communities = SNMP_CONFIG['communities']

        self.olts_detectadas: Dict[str, OLTInfo] = {}

        # Inicializar base de datos
        self.db = DatabaseManager(db_config)

        # Cargar OLTs existentes de la base de datos
        self.cargar_olts_existentes()

    def cargar_olts_existentes(self):
        """Carga OLTs existentes desde la base de datos"""
        try:
            olts_db = self.db.obtener_olts()
            for olt_db in olts_db:
                olt_info = OLTInfo(
                    ip=olt_db['ip'],
                    nombre=olt_db['nombre'],
                    modelo=olt_db['modelo']
                )
                self.olts_detectadas[olt_db['ip']] = olt_info
            logging.info(f"✅ Cargadas {len(olts_db)} OLTs existentes desde BD")
        except Exception as e:
            logging.error(f"Error cargando OLTs existentes: {e}")

    def puerto_abierto(self, ip, puerto, timeout=2):
        """Verifica si un puerto está abierto"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                resultado = sock.connect_ex((ip, puerto))
                return resultado == 0
        except:
            return False

    def snmp_get(self, ip, oid, community='public'):
        """Realiza una consulta SNMP GET"""
        try:
            iterator = getCmd(
                SnmpEngine(),
                CommunityData(community, mpModel=0),
                UdpTransportTarget((ip, self.snmp_config['port']),
                                 timeout=self.snmp_config['timeout'],
                                 retries=self.snmp_config['retries']),
                ContextData(),
                ObjectType(ObjectIdentity(oid))
            )

            errorIndication, errorStatus, errorIndex, varBinds = next(iterator)

            if errorIndication:
                logging.warning(f"SNMP Error en {ip}: {errorIndication}")
                return None
            elif errorStatus:
                logging.warning(f"SNMP Error status en {ip}: {errorStatus}")
                return None
            else:
                for varBind in varBinds:
                    return str(varBind[1])
        except Exception as e:
            logging.debug(f"Error SNMP GET {ip}/{oid}: {e}")
            return None

    def snmp_walk(self, ip, oid, community='public'):
        """Realiza una consulta SNMP WALK"""
        try:
            results = []
            for (errorIndication, errorStatus, errorIndex, varBinds) in nextCmd(
                SnmpEngine(),
                CommunityData(community, mpModel=0),
                UdpTransportTarget((ip, self.snmp_config['port']),
                                 timeout=self.snmp_config['timeout'],
                                 retries=self.snmp_config['retries']),
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
                lexicographicMode=False
            ):
                if errorIndication:
                    logging.warning(f"SNMP WALK Error en {ip}: {errorIndication}")
                    break
                elif errorStatus:
                    logging.warning(f"SNMP WALK Error status en {ip}: {errorStatus}")
                    break
                else:
                    for varBind in varBinds:
                        results.append((str(varBind[0]), str(varBind[1])))
            return results
        except Exception as e:
            logging.debug(f"Error SNMP WALK {ip}/{oid}: {e}")
            return []

    def probar_snmp_olt(self, ip):
        """Prueba si una OLT responde a SNMP y obtiene información básica"""
        for community in self.communities:
            try:
                # Probar con OID de sysDescr (1.3.6.1.2.1.1.1.0)
                sysdescr = self.snmp_get(ip, '1.3.6.1.2.1.1.1.0', community)
                if sysdescr and ('VSOL' in sysdescr.upper() or 'OLT' in sysdescr.upper() or 'GPON' in sysdescr.upper()):
                    # Obtener más información
                    sysname = self.snmp_get(ip, '1.3.6.1.2.1.1.5.0', community) or f"OLT-{ip.split('.')[-1]}"

                    logging.info(f"✅ OLT SNMP detectada: {ip} - {sysname} (Community: {community})")
                    return {
                        'ip': ip,
                        'nombre': sysname,
                        'modelo': sysdescr[:50] if sysdescr else 'VSOL-OLT-SNMP',
                        'community': community,
                        'snmp_available': True
                    }
            except Exception as e:
                continue

        return None

    def obtener_info_snmp_olt(self, ip, community):
        """Obtiene información detallada de OLT vía SNMP"""
        try:
            info = {}

            # Información básica del sistema
            info['sysDescr'] = self.snmp_get(ip, '1.3.6.1.2.1.1.1.0', community)
            info['sysName'] = self.snmp_get(ip, '1.3.6.1.2.1.1.5.0', community)
            info['sysLocation'] = self.snmp_get(ip, '1.3.6.1.2.1.1.6.0', community)

            # Interfaces (OID: 1.3.6.1.2.1.2.2.1)
            interfaces = self.snmp_walk(ip, '1.3.6.1.2.1.2.2.1.2', community)  # ifDescr
            info['interfaces'] = [{'index': oid.split('.')[-1], 'name': value}
                                for oid, value in interfaces if value]

            # Información de ONUs (OIDs específicos de GPON pueden variar)
            # Esto es un ejemplo genérico, necesitarías OIDs específicos del fabricante
            onu_info = self.snmp_walk(ip, '1.3.6.1.4.1', community)  # Private MIBs
            info['onu_count'] = len([x for x in onu_info if 'onu' in str(x[1]).lower()])

            return info

        except Exception as e:
            logging.error(f"Error obteniendo info SNMP de {ip}: {e}")
            return {}

    def actualizar_olt_snmp(self, olt_info):
        """Actualiza información de OLT usando SNMP"""
        try:
            if not hasattr(olt_info, 'snmp_community'):
                return False

            community = olt_info.snmp_community
            info = self.obtener_info_snmp_olt(olt_info.ip, community)

            if info:
                # Actualizar métricas si están disponibles
                # Nota: Los OIDs específicos dependerán del fabricante de la OLT

                # Ejemplo de métricas que podrían obtenerse:
                # - Temperatura
                # - CPU/Memoria
                # - Estado de interfaces
                # - Conteo de ONUs

                logging.info(f"✅ Actualizada OLT {olt_info.ip} vía SNMP")
                return True

        except Exception as e:
            logging.error(f"Error actualizando OLT {olt_info.ip} vía SNMP: {e}")

        return False

    def ejecutar_comando(self, ssh_client, comando):
        """Ejecuta comando SSH y retorna resultado"""
        try:
            stdin, stdout, stderr = ssh_client.exec_command(comando)
            salida = stdout.read().decode('utf-8', errors='ignore').strip()
            error = stderr.read().decode('utf-8', errors='ignore').strip()

            if error and 'invalid' not in error.lower():
                logging.warning(f"Comando '{comando}' generó error: {error}")

            return salida
        except Exception as e:
            logging.error(f"Error ejecutando comando '{comando}': {e}")
            return ""

    def es_olt_vsol(self, version_info):
        """Determina si es OLT VSOL"""
        if not version_info:
            return False
        indicadores = ['VSOL', 'V-SOL', 'GPON', 'OLT']
        return any(indicator in version_info.upper() for indicator in indicadores)

    def extraer_nombre_sistema(self, system_info):
        """Extrae nombre del sistema"""
        lineas = system_info.split('\n')
        for linea in lineas:
            if 'hostname' in linea.lower() or 'nombre' in linea.lower():
                partes = linea.split()
                if len(partes) > 1:
                    return partes[-1]
        return f"OLT-{datetime.now().strftime('%H%M')}"

    def extraer_modelo(self, version_info):
        """Extrae modelo"""
        lineas = version_info.split('\n')
        for linea in lineas:
            if 'model' in linea.lower() or 'hardware' in linea.lower():
                return linea.strip()[:50]  # Limitar longitud
        return "VSOL-OLT"

    def extraer_temperatura(self, output):
        """Extrae temperatura"""
        lineas = output.split('\n')
        for linea in lineas:
            if 'temperature' in linea.lower():
                partes = linea.split()
                for parte in partes:
                    if parte.replace('.', '').replace('-', '').isdigit():
                        return float(parte)
        return None

    def extraer_porcentaje(self, output):
        """Extrae porcentajes"""
        lineas = output.split('\n')
        for linea in lineas:
            if '%' in linea:
                partes = linea.split()
                for parte in partes:
                    if '%' in parte:
                        try:
                            return float(parte.replace('%', ''))
                        except:
                            continue
        return None

    def extraer_serial(self, output):
        """Extrae serial de ONU"""
        lineas = output.split('\n')
        for linea in lineas:
            if 'serial' in linea.lower() or 'sn' in linea.lower():
                partes = linea.split()
                if len(partes) > 1:
                    return partes[-1].strip()
        return None

    def extraer_rx_power(self, output):
        """Extrae potencia RX"""
        lineas = output.split('\n')
        for linea in lineas:
            if 'rx' in linea.lower() and 'power' in linea.lower():
                partes = linea.split()
                for parte in partes:
                    if parte.replace('.', '').replace('-', '').isdigit():
                        return float(parte)
        return -999

    def extraer_tx_power(self, output):
        """Extrae potencia TX"""
        lineas = output.split('\n')
        for linea in lineas:
            if 'tx' in linea.lower() and 'power' in linea.lower():
                partes = linea.split()
                for parte in partes:
                    if parte.replace('.', '').replace('-', '').isdigit():
                        return float(parte)
        return -999

    def obtener_detalles_onu(self, ssh, interfaz, onu_id):
        """Obtiene detalles específicos de ONU"""
        try:
            # Comandos alternativos para VSOL
            comandos = [
                f'show gpon onu detail {interfaz} {onu_id}',
                f'show onu opm-diag {interfaz} {onu_id}',
                f'show gpon onu optical-info {interfaz} {onu_id}'
            ]

            for cmd in comandos:
                output = self.ejecutar_comando(ssh, cmd)
                if output and 'invalid' not in output.lower():
                    serial = self.extraer_serial(output)
                    rx_power = self.extraer_rx_power(output)
                    tx_power = self.extraer_tx_power(output)
                    return serial, rx_power, tx_power

            return None, -999, -999

        except Exception as e:
            logging.error(f"Error en detalles ONU {interfaz}/{onu_id}: {e}")
            return None, -999, -999

    def contar_onus_por_puerto(self, onus_info):
        """Cuenta ONUs por puerto"""
        conteo = {}
        for onu in onus_info:
            puerto = onu.interfaz
            conteo[puerto] = conteo.get(puerto, 0) + 1
        return conteo

    def escanear_red_empresarial(self):
        """Escaneo optimizado para entorno empresarial"""
        logging.info("🚀 INICIANDO ESCANEO EMPRESARIAL")

        def escanear_rango(rango_ip):
            logging.info(f"🔍 Escaneando rango empresarial: {rango_ip}")

            def verificar_ip(ip):
                # Primero intentar SNMP
                snmp_info = self.probar_snmp_olt(ip)
                if snmp_info:
                    # Crear OLT desde SNMP
                    olt_info = OLTInfo(
                        ip=snmp_info['ip'],
                        nombre=snmp_info['nombre'],
                        modelo=snmp_info['modelo']
                    )
                    # Agregar atributo SNMP
                    olt_info.snmp_community = snmp_info['community']
                    self.olts_detectadas[ip] = olt_info
                    self.db.guardar_olt(olt_info)
                    logging.info(f"✅ OLT detectada vía SNMP: {ip}")
                    return

                # Si no SNMP, intentar SSH
                if self.puerto_abierto(ip, 22):
                    olt_info = self.identificar_olt_vsol(ip)
                    if olt_info:
                        self.olts_detectadas[ip] = olt_info
                        self.db.guardar_olt(olt_info)

            with ThreadPoolExecutor(max_workers=20) as executor:
                for i in range(1, 254):
                    ip = f"{rango_ip}{i}"
                    executor.submit(verificar_ip, ip)

        # Escanear rangos en paralelo
        threads = []
        for rango in self.rangos_ip:
            thread = threading.Thread(target=escanear_rango, args=(rango,))
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        logging.info(f"✅ Escaneo completado. OLTs detectadas: {len(self.olts_detectadas)}")
        return len(self.olts_detectadas)

    def identificar_olt_vsol(self, ip):
        """Identificación mejorada para OLTs VSOL"""
        for cred in self.credenciales:
            try:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(ip, username=cred['username'], password=cred['password'], timeout=10)

                # Obtener información completa
                version_info = self.ejecutar_comando(ssh, 'show version')
                system_info = self.ejecutar_comando(ssh, 'show system')

                if self.es_olt_vsol(version_info):
                    nombre = self.extraer_nombre_sistema(system_info)
                    modelo = self.extraer_modelo(version_info)

                    olt_info = OLTInfo(
                        ip=ip,
                        nombre=nombre,
                        modelo=modelo,
                        onus_por_puerto={}
                    )

                    # Obtener información inicial
                    self.actualizar_informacion_olt(ssh, olt_info)

                    ssh.close()
                    return olt_info

                ssh.close()

            except Exception as e:
                continue

        return None

    def actualizar_informacion_olt(self, ssh, olt_info):
        """Actualiza toda la información de la OLT"""
        try:
            # 1. Temperatura de la OLT
            temp_info = self.ejecutar_comando(ssh, 'show system temperature')
            olt_info.temperatura = self.extraer_temperatura(temp_info)
            if olt_info.temperatura:
                self.db.guardar_metrica(olt_info.ip, 'temperatura', olt_info.temperatura)

            # 2. Consumo de CPU/Memoria
            cpu_info = self.ejecutar_comando(ssh, 'show cpu usage')
            mem_info = self.ejecutar_comando(ssh, 'show memory usage')
            olt_info.consumo_cpu = self.extraer_porcentaje(cpu_info)
            olt_info.consumo_memoria = self.extraer_porcentaje(mem_info)

            if olt_info.consumo_cpu:
                self.db.guardar_metrica(olt_info.ip, 'cpu', olt_info.consumo_cpu)
            if olt_info.consumo_memoria:
                self.db.guardar_metrica(olt_info.ip, 'memoria', olt_info.consumo_memoria)

            # 3. Información detallada de ONUs
            onus_info = self.obtener_informacion_onus(ssh, olt_info.ip)
            olt_info.onus_detalladas = onus_info
            olt_info.total_onus = len(onus_info)

            # 4. Contar ONUs por puerto
            olt_info.onus_por_puerto = self.contar_onus_por_puerto(onus_info)

        except Exception as e:
            logging.error(f"Error actualizando OLT {olt_info.ip}: {e}")

    def obtener_informacion_onus(self, ssh, olt_ip):
        """Obtiene información detallada de todas las ONUs"""
        onus = []

        try:
            # Comando para lista de ONUs
            output_onus = self.ejecutar_comando(ssh, 'show gpon onu state')
            lineas = output_onus.split('\n')

            for linea in lineas:
                if 'gpon' in linea.lower() and 'onu' in linea.lower():
                    partes = linea.split()
                    if len(partes) >= 4:
                        interfaz = partes[0]
                        slot = partes[0].split('/')[1] if '/' in partes[0] else '0'
                        puerto = partes[0].split('/')[2] if '/' in partes[0] else '0'
                        onu_id = partes[1]
                        estado = partes[2] if len(partes) > 2 else 'unknown'

                        # Obtener serial y señales
                        serial, rx_power, tx_power = self.obtener_detalles_onu(ssh, interfaz, onu_id)

                        onu_info = ONUInfo(
                            serial=serial or f"UNKNOWN-{interfaz}-{onu_id}",
                            interfaz=interfaz,
                            slot=slot,
                            puerto=puerto,
                            rx_power=rx_power,
                            tx_power=tx_power,
                            estado=estado,
                            ultima_actualizacion=datetime.now()
                        )

                        onus.append(onu_info)
                        self.db.guardar_onu(onu_info, olt_ip)

                        # Simular datos de tráfico para gráficos (en producción obtener de la OLT)
                        bytes_rx = random.randint(1000, 1000000)
                        bytes_tx = random.randint(1000, 500000)
                        self.db.guardar_trafico(olt_ip, onu_info.serial, bytes_rx, bytes_tx)

        except Exception as e:
            logging.error(f"Error obteniendo información de ONUs: {e}")

        return onus

    def actualizar_todas_olts(self):
        """Actualiza información de todas las OLTs detectadas"""
        logging.info("🔄 Actualizando información de todas las OLTs...")
        actualizadas = 0

        for ip, olt_info in self.olts_detectadas.items():
            try:
                # Intentar primero SNMP si está disponible
                if hasattr(olt_info, 'snmp_community') and self.actualizar_olt_snmp(olt_info):
                    actualizadas += 1
                    continue

                # Si no SNMP, usar SSH
                cred = self.credenciales[0]
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(ip, username=cred['username'], password=cred['password'], timeout=10)

                self.actualizar_informacion_olt(ssh, olt_info)
                ssh.close()
                actualizadas += 1

            except Exception as e:
                logging.error(f"Error actualizando OLT {ip}: {e}")

        logging.info(f"✅ Actualizadas {actualizadas} OLTs de {len(self.olts_detectadas)}")
        return actualizadas

    def obtener_estadisticas(self):
        """Obtiene estadísticas generales del sistema"""
        total_onus = sum(olt.total_onus for olt in self.olts_detectadas.values())
        olts_online = len(self.olts_detectadas)

        # Calcular señales problemáticas
        onus_con_señal_baja = 0
        for olt in self.olts_detectadas.values():
            for onu in olt.onus_detalladas:
                if onu.rx_power < -27:  # Señal considerada baja
                    onus_con_señal_baja += 1

        return {
            'total_olts': len(self.olts_detectadas),
            'total_onus': total_onus,
            'olts_online': olts_online,
            'onus_señal_baja': onus_con_señal_baja,
            'ultima_actualizacion': datetime.now().isoformat()
        }

    def obtener_olt_para_web(self, olt_ip):
        """Prepara datos de OLT para la interfaz web"""
        if olt_ip not in self.olts_detectadas:
            return None

        olt = self.olts_detectadas[olt_ip]
        datos_web = olt.to_dict()

        # Agregar métricas recientes
        datos_web['metricas_temperatura'] = self.db.obtener_metricas_recientes(olt_ip, 'temperatura')
        datos_web['metricas_cpu'] = self.db.obtener_metricas_recientes(olt_ip, 'cpu')
        datos_web['trafico_reciente'] = self.db.obtener_trafico_reciente(olt_ip)

        return datos_web

    def obtener_todas_olts_para_web(self):
        """Prepara datos de todas las OLTs para la interfaz web"""
        return [olt.to_dict() for olt in self.olts_detectadas.values()]

# Instancia global para uso en la aplicación web
monitor_global = None

def inicializar_monitor(db_config=None):
    """Inicializa el monitor globalmente"""
    global monitor_global
    if monitor_global is None:
        monitor_global = VSOLMonitorEmpresarial(db_config)
    return monitor_global