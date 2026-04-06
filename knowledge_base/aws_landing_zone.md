# AWS Landing Zone & Architecture Guidelines v1.2

Estas directrices mandatorias definen la arquitectura Cloud de la corporación. Todas las migraciones y análisis deben sugerir estos patrones.

## 1. Patrones de Cómputo (Compute Patterns)
- **Monolitos y Aplicaciones Tradicionales (Java, Node, Python)**: Deberán ser containerizadas en Docker y desplegadas en **Amazon ECS usando Fargate**. Nunca sugerir Amazon EC2 directamente.
- **Microservicios Masivos**: Se destinarán a Amazon EKS (Kubernetes) si y sólo si el clúster requiere Service Mesh profundo, de lo contrario usar ECS.
- **Funciones Event-Driven**: Usar AWS Lambda si el componente analizado es un script que corre por Cron o escucha eventos asíncronos puntuales.

## 2. Bases de Datos (Database Patterns)
- **Oracle DB a AWS**: Nuestra empresa NO utiliza el servicio nativo de Oracle RDS. Todas las bases de datos Oracle deben plantearse hacia una refactorización a **Amazon Aurora PostgreSQL Serverless v2**.
- **MySQL / SQL Server**: Mover a Amazon Aurora MySQL u Opciones nativas.
- **Bases Relacionales Pequeñas**: No sugerir DynamoDB a menos que la data sea puramente clave-valor sin uniones complejas.

## 3. Integración y Middleware
- **Oracle Service Bus (OSB) o SOAP**: Migrar forzosamente a un enrutamiento por **Amazon API Gateway v2** con validación OAuth y respaldado por Lambdas.
- **Oracle Data Integrator (ODI)**: Reemplazar el procesamiento de datos por rutinas de PySpark ejecutadas en **AWS Glue**.
- **Servidores de Aplicaciones Pesados (WebSphere, Weblogic)**: Eliminar completamente. Aislar el .war/.ear hacia Apache Tomcat o Spring Boot embebido en Corretto Java.
