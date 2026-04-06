FROM nginx:alpine

# Generar certificado TLS self-signed (reemplazar con cert real en produccion)
RUN apk add --no-cache openssl && \
    mkdir -p /etc/nginx/ssl && \
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /etc/nginx/ssl/key.pem \
        -out    /etc/nginx/ssl/cert.pem \
        -subj   "/C=US/ST=Cloud/L=Factory/O=ModFactory/CN=localhost" \
        2>/dev/null

# Configuracion HTTPS
COPY nginx/nginx.conf /etc/nginx/nginx.conf

# Archivos estaticos del frontend
COPY index.html /usr/share/nginx/html/
COPY styles.css /usr/share/nginx/html/
COPY app.js     /usr/share/nginx/html/
COPY lib/       /usr/share/nginx/html/lib/

EXPOSE 80 443
CMD ["nginx", "-g", "daemon off;"]
