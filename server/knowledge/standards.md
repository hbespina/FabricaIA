# Estándares de Modernización - OTSOrchestrAI

Este documento es el cerebro de los agentes de modernización. Cualquier cambio aquí será aprendido por la IA en el siguiente análisis.

## 🚀 Arquitectura Destino (AWS)
- **Cómputo**: Todo lo que no sea una base de datos debe ir a **AWS ECS con Fargate** (Serverless Containers). No usar EC2 directamente.
- **Base de Datos**: Migrar de Oracle/On-Premise a **AWS Aurora PostgreSQL** (Serverless V2).
- **Red**: Usar una VPC con subredes privadas. Publicar servicios solo mediante un **Application Load Balancer (ALB)**.

## 📦 Contenedores y Docker
- **Base Image**: Siempre usar imágenes ligeras como **Alpine Linux** o **Distroless** (ej. `openjdk:17-alpine`).
- **Secretos**: No poner contraseñas ni llaves SSH en el Dockerfile. Usar **AWS Secrets Manager**.
- **Puertos**: Las aplicaciones deben escuchar en el puerto **8080** por defecto.

## 🛠️ Refactorización de Código (Monolito -> Contenedor)
- **SOAP a REST**: Si detectas archivos `.wsdl` o el framework **Axis**, propón migrar a **REST** usando **OpenAPI 3.0**.
- **JNDI y Config**: Eliminar búsquedas JNDI. Los recursos (DB, Colas) se inyectan por **Variables de Entorno**.
- **Almacenamiento**: No guardar archivos en el sistema de archivos local (`/opt/...`). Usar **Amazon S3** o **AWS EFS**.
- **Sesión**: Las aplicaciones deben ser **Stateless**. No usar `HttpSession` en memoria; usar **Redis** (Amazon ElastiCache) si es necesario.

## 📈 Plan de Migración (Sprints)
- **Sprint 0**: Seguridad y Base de Datos (IaaS + DB Setup).
- **Sprint 1**: Dockerización de la App Base y CI/CD Pipeline.
- **Sprint 2**: Refactorización de servicios críticos y desacoplamiento de DB.
- **Sprint 3**: Pruebas de Carga y Corte Final a Producción.
