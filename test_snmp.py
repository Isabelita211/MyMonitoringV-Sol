#!/usr/bin/env python3
"""
Script de prueba para verificar funcionamiento SNMP
Ejecutar antes de usar el sistema completo
"""

import sys
import os

# Agregar directorio actual al path
sys.path.insert(0, os.path.dirname(__file__))

try:
    # Probar imports SNMP
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
    print("✅ Import SNMP exitoso")

    # Probar import del monitor
    from monitor_vsol import VSOLMonitorEmpresarial
    print("✅ Import del monitor exitoso")

    # Probar configuración
    from config import SNMP_CONFIG
    print(f"✅ Configuración SNMP cargada: {len(SNMP_CONFIG['communities'])} communities")

    # Crear instancia del monitor
    monitor = VSOLMonitorEmpresarial()
    print("✅ Monitor creado exitosamente")

    print("\n🎉 Todos los tests pasaron correctamente!")
    print("📡 SNMP está listo para usar")

except ImportError as e:
    print(f"❌ Error de importación: {e}")
    print("💡 Solución: pip install pysnmp==5.0.27")

except Exception as e:
    print(f"❌ Error general: {e}")
    print("💡 Revisa la configuración y dependencias")