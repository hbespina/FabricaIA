# Arquitectura: Modernization Factory V4.0 (Microservices & Docker)

Esta arquitectura describe el ecosistema de **Microservicios** orquestado mediante **Docker Compose**.

## Diagrama de Orquestación Docker

```mermaid
graph TD
    subgraph Docker_Host ["Docker Engine (Local Machine)"]
        subgraph Web_Tier ["Frontend Container (NGINX)"]
            FE["Dashboard UI (Port 80)"]
        end
        subgraph App_Tier ["Backend Container (FastAPI)"]
            BE["Proxy API (Port 8000)"]
        end
    end

    subgraph External_Analytics ["Cerebro de Modernización"]
        LLM["Amazon Bedrock: Claude 3.5 Sonnet"]
    end

    A[Colector .sh] -->|Data Dump| B(Discovery Engine V4.8)
    B -->|Firmas de Procesos| C[Detección de Stack]
    B -->|Firmas de Puertos| D[Inferencia de Layer]
    C & D --> E(Generador de Plan Paso-a-Paso)
    E -->|IA / Heurística| F[Reporte Final PDF/Web]
    F -->|Salida| G[Plan SRE Accionable]
```

## Beneficios
*   **Cero Sesgo**: No requiere que el usuario declare las tecnologías.
*   **Predictibilidad**: Planes numerados listos para ser incorporados a JIRA o n8n.
*   **Portabilidad Extrema**: Funciona en laptops aisladas sin dependencias externas.
