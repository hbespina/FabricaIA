FROM nginx:alpine

# Copiar archivos estáticos al directorio de NGINX
COPY index.html /usr/share/nginx/html/
COPY styles.css /usr/share/nginx/html/
COPY app.js /usr/share/nginx/html/

# Exponer puerto 80
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
