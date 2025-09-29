#!/usr/bin/env python3
"""
Script para cargar datos de prueba en la base de datos
Ejecutar después de iniciar la aplicación por primera vez
"""

from monitor_vsol import VSOLMonitorEmpresarial
from config import DB_CONFIG
from datetime import datetime
import random

def crear_datos_prueba():
    """Crea datos de prueba para desarrollo local"""

    # Crear instancia del monitor
    monitor = VSOLMonitorEmpresarial(DB_CONFIG)

    # Datos de ejemplo de OLTs
    olts_prueba = [
        {
            'ip': '192.168.1.100',
            'nombre': 'OLT-Central',
            'modelo': 'VSOL-OLT-1000',
            'temperatura': 45.5,
            'cpu': 25.0,
            'memoria': 60.0,
            'onus': [
                {'serial': 'VSOL001', 'interfaz': 'gpon-olt_1/1', 'slot': '1', 'puerto': '1', 'rx': -15.5, 'tx': 2.1},
                {'serial': 'VSOL002', 'interfaz': 'gpon-olt_1/1', 'slot': '1', 'puerto': '2', 'rx': -18.2, 'tx': 1.8},
                {'serial': 'VSOL003', 'interfaz': 'gpon-olt_1/1', 'slot': '1', 'puerto': '3', 'rx': -12.8, 'tx': 2.5},
            ]
        },
        {
            'ip': '192.168.1.101',
            'nombre': 'OLT-Norte',
            'modelo': 'VSOL-OLT-2000',
            'temperatura': 42.0,
            'cpu': 30.0,
            'memoria': 55.0,
            'onus': [
                {'serial': 'VSOL101', 'interfaz': 'gpon-olt_1/2', 'slot': '1', 'puerto': '1', 'rx': -16.1, 'tx': 1.9},
                {'serial': 'VSOL102', 'interfaz': 'gpon-olt_1/2', 'slot': '1', 'puerto': '2', 'rx': -14.7, 'tx': 2.2},
            ]
        },
        {
            'ip': '192.168.1.102',
            'nombre': 'OLT-Sur',
            'modelo': 'VSOL-OLT-1000',
            'temperatura': 48.0,
            'cpu': 20.0,
            'memoria': 45.0,
            'onus': [
                {'serial': 'VSOL201', 'interfaz': 'gpon-olt_1/3', 'slot': '1', 'puerto': '1', 'rx': -19.3, 'tx': 1.5},
                {'serial': 'VSOL202', 'interfaz': 'gpon-olt_1/3', 'slot': '1', 'puerto': '2', 'rx': -17.8, 'tx': 2.0},
                {'serial': 'VSOL203', 'interfaz': 'gpon-olt_1/3', 'slot': '1', 'puerto': '3', 'rx': -13.2, 'tx': 2.3},
                {'serial': 'VSOL204', 'interfaz': 'gpon-olt_1/3', 'slot': '1', 'puerto': '4', 'rx': -21.1, 'tx': 1.7},
            ]
        }
    ]

    print("🧪 Creando datos de prueba...")

    for olt_data in olts_prueba:
        # Crear OLT
        from monitor_vsol import OLTInfo
        olt = OLTInfo(
            ip=olt_data['ip'],
            nombre=olt_data['nombre'],
            modelo=olt_data['modelo'],
            temperatura=olt_data['temperatura'],
            consumo_cpu=olt_data['cpu'],
            consumo_memoria=olt_data['memoria']
        )

        # Guardar OLT
        monitor.db.guardar_olt(olt)
        monitor.olts_detectadas[olt.ip] = olt

        # Crear ONUs
        for onu_data in olt_data['onus']:
            from monitor_vsol import ONUInfo
            onu = ONUInfo(
                serial=onu_data['serial'],
                interfaz=onu_data['interfaz'],
                slot=onu_data['slot'],
                puerto=onu_data['puerto'],
                rx_power=onu_data['rx'],
                tx_power=onu_data['tx'],
                estado='online',
                ultima_actualizacion=datetime.now()
            )

            # Guardar ONU
            monitor.db.guardar_onu(onu, olt.ip)
            olt.onus_detalladas.append(onu)

            # Simular datos de tráfico
            bytes_rx = random.randint(1000000, 10000000)
            bytes_tx = random.randint(500000, 5000000)
            monitor.db.guardar_trafico(olt.ip, onu.serial, bytes_rx, bytes_tx)

        olt.total_onus = len(olt.onus_detalladas)
        olt.onus_por_puerto = monitor.contar_onus_por_puerto(olt.onus_detalladas)

        print(f"✅ Creada OLT {olt.nombre} con {olt.total_onus} ONUs")

    print("🎉 Datos de prueba creados exitosamente!")
    print(f"📊 Total OLTs: {len(monitor.olts_detectadas)}")
    total_onus = sum(len(olt.onus_detalladas) for olt in monitor.olts_detectadas.values())
    print(f"📊 Total ONUs: {total_onus}")

if __name__ == '__main__':
    crear_datos_prueba()