# Monitor VSOL - Desarrollo Local

Sistema de monitoreo para OLTs VSOL con interfaz web en tiempo real.

## 🚀 Inicio Rápido para Desarrollo Local

### 1. Instalar Python

Descarga e instala Python 3.8+ desde [python.org](https://python.org) o usa el Microsoft Store en Windows.

### 2. Instalar Dependencias

```bash
# Para desarrollo local (usa SQLite, no requiere PostgreSQL)
pip install -r requirements.txt

# Para producción con PostgreSQL, instala adicionalmente:
# pip install psycopg2-binary==2.9.7
```

### 3. Configurar Base de Datos

Por defecto, usa SQLite para desarrollo local. El archivo `monitor_vsol.db` se creará automáticamente.

Si prefieres PostgreSQL:

- Instala PostgreSQL
- Crea una base de datos
- Configura las variables de entorno o modifica `config.py`

### 4. Ejecutar la Aplicación

Opción 1 - Modo desarrollo simplificado:

```bash
python run_dev.py
```

Opción 2 - Ejecución directa:

```bash
python app.py
```

La aplicación estará disponible en: http://localhost:5000

### 5. Cargar Datos de Prueba (Opcional)

Para probar con datos de ejemplo sin escanear la red:

```bash
python test_data.py
```

Esto creará 3 OLTs de prueba con varias ONUs cada una.

## 📁 Estructura del Proyecto

```
MyMonitoringV-Sol/
├── app.py                 # Aplicación Flask principal
├── monitor_vsol.py        # Lógica de monitoreo y base de datos
├── config.py              # Configuraciones
├── run_dev.py             # Script para desarrollo local
├── test_data.py           # Script para datos de prueba
├── README.md              # Documentación
├── requirements.txt       # Dependencias Python
├── Install.txt            # Instrucciones de instalación
├── templates/             # Plantillas HTML
│   ├── base.html
│   ├── index.html
│   ├── olts.html
│   └── onus.html
├── static/                # Archivos estáticos
│   ├── styles.css
│   └── script.js
└── monitor_vsol.db        # Base de datos SQLite (creada automáticamente)
```

````

## 🔧 Configuración

### Variables de Entorno

```bash
# Para desarrollo local (SQLite - recomendado)
export USE_SQLITE=true

# Para producción (PostgreSQL)
export USE_SQLITE=false
export DB_HOST=172.20.5.2
export DB_NAME=n8n_automations
export DB_USER=n8n_automations
export DB_PASSWORD=tu_password_real
export DB_PORT=5432
````

### Configuración de Red

En `config.py`, puedes modificar los rangos de IP a escanear:

```python
NETWORK_CONFIG = {
    'scan_ranges': [
        '192.168.1.',    # Tu red local
        '10.0.0.',       # Otra red
    ]
}
```

## 🧪 Pruebas

### Interfaz Web

- Dashboard: http://localhost:5000
- Lista de OLTs: http://localhost:5000/olts
- Lista de ONUs: http://localhost:5000/onus

### API Endpoints

- GET `/api/olts` - Lista todas las OLTs
- GET `/api/olts/{ip}` - Detalles de una OLT
- GET `/api/onus/{ip}` - ONUs de una OLT
- GET `/api/stats` - Estadísticas generales
- POST `/api/scan` - Iniciar escaneo de red

## 🔍 Funcionalidades

- ✅ Escaneo automático de red para detectar OLTs VSOL
- ✅ Monitoreo en tiempo real vía WebSockets
- ✅ Dashboard con estadísticas
- ✅ Gestión de OLTs y ONUs
- ✅ Persistencia en base de datos
- ✅ Interfaz web responsive
- ✅ Logging detallado

## 🐛 Solución de Problemas

### Python no encontrado

- Instala Python 3.8+ desde [python.org](https://python.org)
- En Windows: usa el Microsoft Store o descarga el instalador
- Verifica con `python --version`

### Error al instalar dependencias

- Usa `python -m pip install -r requirements.txt`
- Si pip no está disponible, instala Python completo
- En algunos sistemas: `py -m pip install -r requirements.txt`

### Error de conexión a base de datos

- **Para SQLite (desarrollo):** Borra `monitor_vsol.db` y reinicia
- **Para PostgreSQL (producción):** Verifica que esté corriendo y las credenciales
- Asegúrate de que el servidor sea accesible desde tu máquina

### No se detectan OLTs

- Verifica que las IPs en `config.py` sean accesibles desde tu red
- Revisa el firewall/antivirus
- Las OLTs deben tener SSH habilitado con credenciales conocidas
- Para pruebas locales: usa `python test_data.py`

### La interfaz web no carga

- Verifica que el puerto 5000 no esté bloqueado
- Intenta acceder desde http://127.0.0.1:5000
- Revisa la consola del navegador (F12) por errores JavaScript

### Error "Module not found"

- Asegúrate de ejecutar desde el directorio del proyecto
- Verifica que todas las dependencias estén instaladas
- Reinicia la terminal/IDE después de instalar dependencias

## 📝 Notas para Producción

- Cambia `SECRET_KEY` en `app.py`
- Configura credenciales de base de datos seguras
- Implementa autenticación de usuarios
- Configura HTTPS
- Ajusta rangos de IP para tu red empresarial
- Considera usar un servidor WSGI como Gunicorn

## 🤝 Contribuir

1. Fork el proyecto
2. Crea una rama para tu feature
3. Commit tus cambios
4. Push a la rama
5. Abre un Pull Request
