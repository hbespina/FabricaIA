# Arquitectura Funcional: Modernization Factory V2.1 (SRE & Financial)

Este documento describe la arquitectura técnica del sistema construido para automatizar el descubrimiento y diseño de modernización cloud.

## Diagrama de Bloques (Flujo de Datos)

```mermaid
graph TD
    subgraph Legacy_Zone ["Zona Legacy: On-Premise"]
        A["Agente Colector: collector.sh"] -- "Ejecución Local" --> B["Inventario Crudo: inventory.txt"]
    end

    subgraph User_Workspace ["Área de Trabajo: Browser"]
        B -- "Copy/Paste" --> C["Dashboard UI: index.html"]
        subgraph Engine_Processing ["Motor de Procesamiento JS V2.0"]
            C -. "Parse/Analysis" .-> D["app.js Engine"]
            D -- "Transformación" --> E["JSON Blueprint V2.0"]
            D -- "Persistencia" --> DB[("LocalStorage")]
        end
        subgraph Assistant_Interaction ["IA Interaction"]
            J["SRE Chat Assistant"] <--> D
        end
    end

    subgraph Visualization_Layer ["Capa de Visualización & Reporte"]
        E -- "Financials" --> F["ROI / TCO Card"]
        E -- "Analytics" --> G["SRE Scores (Risk/Complexity)"]
        E -- "Architecture" --> H["Mermaid Target Diagram"]
        E -- "IaC" --> I["Terraform & NGINX Config"]
        K["Print-to-PDF Engine"] -- "Export" --> L["Reporte Profesional"]
    end

    style A fill:#f9f,stroke:#333,stroke-width:2px
    style C fill:#00d2ff,stroke:#333,stroke-width:2px
    style E fill:#9d50bb,stroke:#f8f8f8,color:#fff
    style DB fill:#00b09b,color:#fff
    style J fill:#ff8c00,color:#fff
```

## Componentes Detallados

### 1. Agente Colector ([collector.sh](file:///c:/Users/hberrioe/Fabrica/collector.sh))
- **Responsabilidad**: Extracción forense de metadatos del OS, procesos activos y puertos escuchando en sistemas antiguos (RHEL 4+).

### 2. Dashboard UI & Export System
- **Estética**: High-Fidelity Glassmorphism.
- **Reporting**: Motor `@media print` optimizado para generar PDFs listos para entrega ejecutiva sin elementos de UI interactivos.

### 3. Motor de Análisis V2.0 ([app.js](file:///c:/Users/hberrioe/Fabrica/app.js))
- **Módulo Financiero**: Cálculo automático de OPEX Cloud, Costos de Migración y ROI (Cálculo de Payback basado en ahorro de mantenimiento).
- **Módulo SRE**: Puntuación de Complejidad Técnica y Readiness.
- **NGINX Logic**: Generación de configuraciones proxy-pass con soporte de sticky sessions.

### 4. SRE AI Assistant & Persistencia
- **Chat Assistant**: Interfaz interactiva para consultas técnicas sobre el análisis legacy.
- **LocalStorage**: Mantiene el estado del último análisis para evitar pérdida de datos en el navegador.

---
> [!NOTE]
> Esta arquitectura está diseñada para ser **Zero-Infrastructure**; todo el procesamiento ocurre localmente en el navegador del arquitecto, garantizando la privacidad de los datos del servidor analizado.
