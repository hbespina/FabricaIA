# Modernization Factory Portal V1.0

Este portal permite automatizar el descubrimiento y diseño de estrategias de modernización para sistemas legacy (RHEL, Solaris, AIX).

## Cómo Ejecutar la Fábrica (V3.0)

### Opción 1: Docker (Recomendado - Microservicios) 🐳
1. Abre una terminal en la carpeta `Fabrica`.
2. Ejecuta: `docker-compose up --build`.
3. Accede al Dashboard en `http://localhost`. El Backend estará en `http://localhost:8000`.

### Opción 2: Inicio Rápido (Windows - Sin Docker)
1. Abre la carpeta `Fabrica` en el explorador.
2. Haz doble clic en `run_factory.bat`. Este script instalará dependencias, iniciará el backend de Bedrock y abrirá el Dashboard.
3. Asegúrate de configurar tus credenciales en `server/.env`.

### Opción 2: Manual
1. **Backend**: `cd server && pip install -r requirements.txt && python main.py`
2. **Frontend**: Abre `index.html` en cualquier navegador moderno.

## Componentes y Versiones

### V2.0 - SRE & Financial Edition [NUEVO]
- **Módulo Financiero**: Estimación de OPEX Cloud, Costos de Migración y cálculo de Payback (ROI).
- **SRE Analytics**: Puntuación de Complejidad y Readiness para la modernización.
- **Sprint Planner**: Recomendaciones críticas de arquitectura para el primer sprint.
- **Expanded IaC**: Generación automática de configuraciones NGINX para legacy support.

### 1. Agente Colector (`collector.sh`)
Script diseñado para ejecutarse incluso en kernels antiguos (RHEL 4+).
- **Uso**: `chmod +x collector.sh && ./collector.sh > data.txt`
- **Función**: Rescata procesos, red, variables de entorno y estructura de directorios crítica.

### 2. Dashboard de Análisis (`index.html`)
Interfaz premium basada en Glassmorphism para la toma de decisiones.
- **Uso**: Abre `index.html` en un navegador moderno (Chrome/Edge).
- **Flujo**: 
    1. Copia el contenido de `data.txt`.
    2. Pégalo en el área de texto del Dashboard.
    3. Haz clic en "Iniciar Análisis Forense".
    4. Visualiza el Score de Riesgo, Inventario Maestro, Diagramas Mermaid y código de Infraestructura (Terraform).

## Tecnologías Utilizadas
- **Frontend**: Vanilla HTML5, CSS3 (Custom Design System).
- **Visualización**: Mermaid.js para diagramas de arquitectura dinámicos.
- **Tipografía**: Outfit (Google Fonts).
