"""
Genera un WAR de prueba con patrones JEE reales para testear el extractor.
Ejecutar: .venv\Scripts\python crear_war_prueba.py
"""
import zipfile, io, struct

def make_class(class_name: str, strings: list[str]) -> bytes:
    """Genera un .class mínimo con un constant pool que contiene los strings dados."""
    cp_entries = []
    # Tag 1 = Utf8
    def utf8(s: str) -> bytes:
        b = s.encode("utf-8")
        return bytes([1]) + struct.pack(">H", len(b)) + b

    for s in strings:
        cp_entries.append(utf8(s))
    # Class ref al primer entry (índice 1)
    cp_entries.append(bytes([7]) + struct.pack(">H", 1))   # Class
    cp_entries.append(bytes([7]) + struct.pack(">H", 2))   # Superclass (Object)

    cp_count = len(cp_entries) + 1
    cp_bytes = b"".join(cp_entries)

    magic        = b"\xca\xfe\xba\xbe"
    minor        = struct.pack(">H", 0)
    major        = struct.pack(">H", 52)   # Java 8
    cp_count_b   = struct.pack(">H", cp_count)
    access_flags = struct.pack(">H", 0x0021)  # public
    this_class   = struct.pack(">H", cp_count - 1)
    super_class  = struct.pack(">H", cp_count)
    interfaces   = struct.pack(">H", 0)
    fields       = struct.pack(">H", 0)
    methods      = struct.pack(">H", 0)
    attributes   = struct.pack(">H", 0)

    return (magic + minor + major + cp_count_b + cp_bytes
            + access_flags + this_class + super_class
            + interfaces + fields + methods + attributes)


buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:

    # MANIFEST.MF
    zf.writestr("META-INF/MANIFEST.MF",
        "Manifest-Version: 1.0\n"
        "Implementation-Title: SistemaFacturacion\n"
        "Implementation-Version: 3.2.1\n"
        "Main-Class: com.empresa.facturacion.Main\n"
        "Built-By: jenkins\n"
    )

    # web.xml con Servlet y seguridad
    zf.writestr("WEB-INF/web.xml", """<?xml version="1.0" encoding="UTF-8"?>
<web-app xmlns="http://java.sun.com/xml/ns/javaee" version="3.0">
  <display-name>SistemaFacturacion</display-name>
  <servlet>
    <servlet-name>FacturaServlet</servlet-name>
    <servlet-class>com.empresa.facturacion.FacturaServlet</servlet-class>
  </servlet>
  <servlet>
    <servlet-name>LoginServlet</servlet-name>
    <servlet-class>com.empresa.facturacion.LoginServlet</servlet-class>
  </servlet>
  <servlet-mapping>
    <servlet-name>FacturaServlet</servlet-name>
    <url-pattern>/factura/*</url-pattern>
  </servlet-mapping>
  <filter>
    <filter-name>AuthFilter</filter-name>
    <filter-class>com.empresa.facturacion.AuthFilter</filter-class>
  </filter>
  <listener>
    <listener-class>org.springframework.web.context.ContextLoaderListener</listener-class>
  </listener>
  <context-param>
    <param-name>contextConfigLocation</param-name>
    <param-value>classpath:applicationContext.xml</param-value>
  </context-param>
  <session-config><session-timeout>30</session-timeout></session-config>
  <security-constraint>
    <web-resource-collection>
      <url-pattern>/admin/*</url-pattern>
    </web-resource-collection>
    <auth-constraint><role-name>ADMIN</role-name></auth-constraint>
  </security-constraint>
  <login-config><auth-method>FORM</auth-method></login-config>
</web-app>""")

    # persistence.xml
    zf.writestr("WEB-INF/classes/META-INF/persistence.xml", """<?xml version="1.0"?>
<persistence xmlns="http://java.sun.com/xml/ns/persistence" version="2.0">
  <persistence-unit name="facturaciónPU" transaction-type="JTA">
    <provider>org.hibernate.jpa.HibernatePersistenceProvider</provider>
    <jta-data-source>java:jboss/datasources/FacturacionDS</jta-data-source>
    <class>com.empresa.model.Factura</class>
    <class>com.empresa.model.Cliente</class>
    <class>com.empresa.model.Producto</class>
    <properties>
      <property name="hibernate.dialect" value="org.hibernate.dialect.Oracle12cDialect"/>
      <property name="hibernate.show_sql" value="true"/>
      <property name="hibernate.hbm2ddl.auto" value="validate"/>
    </properties>
  </persistence-unit>
</persistence>""")

    # Spring applicationContext.xml
    zf.writestr("WEB-INF/classes/applicationContext.xml", """<?xml version="1.0"?>
<beans xmlns="http://www.springframework.org/schema/beans">
  <bean id="dataSource" class="org.apache.commons.dbcp.BasicDataSource">
    <property name="driverClassName" value="oracle.jdbc.OracleDriver"/>
    <property name="url" value="jdbc:oracle:thin:@prod-oracle-db:1521:FACTUDB"/>
    <property name="username" value="factura_user"/>
  </bean>
  <bean id="transactionManager" class="org.springframework.orm.jpa.JpaTransactionManager">
    <property name="dataSource" ref="dataSource"/>
  </bean>
  <bean id="emailService" class="com.empresa.service.EmailService"/>
</beans>""")

    # ejb-jar.xml
    zf.writestr("WEB-INF/ejb-jar.xml", """<?xml version="1.0"?>
<ejb-jar xmlns="http://java.sun.com/xml/ns/javaee" version="3.1">
  <enterprise-beans>
    <session>
      <ejb-name>FacturacionEJB</ejb-name>
      <ejb-class>com.empresa.ejb.FacturacionEJBBean</ejb-class>
      <session-type>Stateless</session-type>
    </session>
    <session>
      <ejb-name>ClienteEJB</ejb-name>
      <ejb-class>com.empresa.ejb.ClienteEJBBean</ejb-class>
      <session-type>Stateful</session-type>
    </session>
    <message-driven>
      <ejb-name>NotificacionMDB</ejb-name>
      <ejb-class>com.empresa.mdb.NotificacionMDB</ejb-class>
    </message-driven>
  </enterprise-beans>
</ejb-jar>""")

    # db.properties con JDBC
    zf.writestr("WEB-INF/classes/db.properties",
        "datasource.url=jdbc:oracle:thin:@prod-oracle-db:1521:FACTUDB\n"
        "datasource.driver=oracle.jdbc.OracleDriver\n"
        "datasource.host=prod-oracle-db\n"
        "datasource.port=1521\n"
        "mail.server=smtp.empresa.com\n"
        "mail.port=25\n"
    )

    # JARs en WEB-INF/lib con versiones vulnerables
    libs = [
        ("log4j-core-2.14.1.jar",            1024),
        ("struts2-core-2.5.28.jar",           2048),
        ("spring-core-5.3.15.jar",            3072),
        ("spring-webmvc-5.3.15.jar",          2048),
        ("jackson-databind-2.12.3.jar",       1024),
        ("commons-collections-3.2.1.jar",     512),
        ("commons-text-1.9.jar",              256),
        ("hibernate-core-5.4.32.Final.jar",   4096),
        ("ojdbc8-21.1.0.0.jar",               512),
        ("commons-dbcp-1.4.jar",              256),
        ("spring-security-core-5.5.3.jar",    1024),
        ("xstream-1.4.17.jar",                512),
    ]
    for jar_name, size in libs:
        # JAR mínimo válido con MANIFEST
        jar_buf = io.BytesIO()
        with zipfile.ZipFile(jar_buf, "w") as jf:
            artifact = jar_name.rsplit("-", 1)[0]
            version  = jar_name.rsplit("-", 1)[1].replace(".jar","").replace(".Final","").replace(".RELEASE","")
            jf.writestr("META-INF/MANIFEST.MF",
                f"Manifest-Version: 1.0\nImplementation-Title: {artifact}\nImplementation-Version: {version}\nBundle-Version: {version}\n")
        zf.writestr(f"WEB-INF/lib/{jar_name}", jar_buf.getvalue())

    # Clases Java con patrones JEE reales
    classes = [
        ("WEB-INF/classes/com/empresa/facturacion/FacturaServlet.class", [
            "com/empresa/facturacion/FacturaServlet",
            "javax/servlet/http/HttpServlet",
            "javax/servlet/annotation/WebServlet",
            "javax/naming/InitialContext",
            "java:comp/env/jdbc/FacturacionDS",
            "SELECT f.id, f.numero, f.monto, f.cliente_id FROM facturas f WHERE f.estado = 'PENDIENTE'",
            "HttpSession",
            "java.io.FileInputStream",
            "MD5",
            "http://servicios.empresa.com/validar",
        ]),
        ("WEB-INF/classes/com/empresa/ejb/FacturacionEJBBean.class", [
            "com/empresa/ejb/FacturacionEJBBean",
            "javax/ejb/Stateless",
            "javax/ejb/TransactionAttribute",
            "javax/persistence/EntityManager",
            "javax/annotation/security/RolesAllowed",
            "INSERT INTO facturas (numero, monto, cliente_id, fecha) VALUES (?, ?, ?, SYSDATE)",
            "UPDATE facturas SET estado = ? WHERE id = ?",
            "java:comp/env/ejb/ClienteEJB",
            "UserTransaction",
            "EJBContext",
        ]),
        ("WEB-INF/classes/com/empresa/model/Factura.class", [
            "com/empresa/model/Factura",
            "javax/persistence/Entity",
            "javax/persistence/Table",
            "javax/persistence/Id",
            "javax/persistence/Column",
            "javax/persistence/ManyToOne",
            "javax/persistence/OneToMany",
            "java/io/Serializable",
        ]),
        ("WEB-INF/classes/com/empresa/model/Cliente.class", [
            "com/empresa/model/Cliente",
            "javax/persistence/Entity",
            "javax/persistence/Table",
            "javax/persistence/Id",
            "java/io/Serializable",
        ]),
        ("WEB-INF/classes/com/empresa/service/EmailService.class", [
            "com/empresa/service/EmailService",
            "org/springframework/stereotype/Service",
            "javax/mail/Transport",
            "System.getProperty",
            "new Thread(",
            "Runtime.exec",
            "printStackTrace",
            "smtp.empresa.com",
        ]),
        ("WEB-INF/classes/com/empresa/facturacion/LoginServlet.class", [
            "com/empresa/facturacion/LoginServlet",
            "javax/servlet/http/HttpServlet",
            "HttpURLConnection",
            "HttpSession",
            "MD5",
            "SELECT u.id FROM usuarios u WHERE u.user=? AND u.pass=?",
            "DES",
        ]),
        ("WEB-INF/classes/com/empresa/mdb/NotificacionMDB.class", [
            "com/empresa/mdb/NotificacionMDB",
            "javax/ejb/MessageDriven",
            "javax/jms/MessageListener",
            "javax/jms/Message",
            "java:comp/env/jms/NotificacionQueue",
        ]),
    ]

    for path, strings in classes:
        zf.writestr(path, make_class(path.split("/")[-1].replace(".class",""), strings))

output_path = "prueba-facturacion.war"
with open(output_path, "wb") as f:
    f.write(buf.getvalue())

print(f"WAR creado: {output_path} ({len(buf.getvalue())//1024} KB)")
print(f"\nAhora ejecuta:")
print(f"  .venv\\Scripts\\python test_artifact.py {output_path}")
