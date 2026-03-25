# Modernization Factory Portal V1.0

Este portal permite automatizar el descubrimiento y diseño de estrategias de modernización para sistemas legacy (RHEL, Solaris, AIX).

## Componentes

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
