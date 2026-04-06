# Enterprise Security Policies & Tech Radar V5

Todos los análisis deben emitir un hallazgo de "Riesgo Severo" si los siguientes lineamientos se descubren en la infraestructura legada analizada.

## 1. Ciclo de Vida EOL (End of Life)
Nuestra empresa tiene una agresiva política contra tecnologías EOL:
- **Java Runtime**: Java 8 o inferior (incluyendo Java 1.4/6/7) están proscritas. Se exige actualización a **Amazon Corretto 17 o 21 LTS**.
- **Python**: Cualquier versión inferior a Python 3.10 (ej. Python 2.7) amerita una migración por "Riesgo de Parcheo Nulo".
- **PHP**: Versiones 5.x y 7.x son catalogadas con riesgo Crítico por CVEs históricos públicos (Injection / Type Juggling). Sugerir Mover a PHP 8.3 de inmediato.

## 2. Infraestructura de Claves
Cualquier archivo o código (Spring, PHP, Node) que posea tokens duros, variables de `password=` estáticas o secretos en el código fuente debe ser marcado como VULNERABILIDAD CRÍTICA. El Blueprint de salida debe sugerir el uso de **AWS Secrets Manager** para proteger estas variables.

## 3. Protocolos Inseguros
Se prohíbe explícitamente el uso de Telnet o FTP en proyecciones futuras. Migrar todas las ingestas de archivos a Amazon MFT (Managed File Transfer) vía SFTP respaldado por S3.
