FROM nginx:1.27-alpine

COPY infra/nginx/nginx.conf /etc/nginx/nginx.conf

EXPOSE 80
