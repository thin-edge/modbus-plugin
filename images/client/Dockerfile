FROM composer:latest

EXPOSE 8080

WORKDIR /app
RUN git clone https://github.com/aldas/modbus-tcp-client.git
WORKDIR /app/modbus-tcp-client
RUN composer install
RUN touch /app/modbus-tcp-client/examples/.allow-change
CMD php -S 0.0.0.0:8080 -t examples/