#Build dpkg package
FROM goreleaser/nfpm as build-stage

# Copy required files
WORKDIR /build
COPY modbus_reader /build/modbus_reader
COPY operations /build/operations
COPY scripts /build/scripts
COPY requirements.txt /build/requirements.txt
COPY nfpm.yaml /build/nfpm.yaml
COPY te-modbus-plugin.service /build/te-modbus-plugin.service
# Build Package
RUN nfpm pkg --packager deb --target /tmp/modbus-plugin_all.deb

FROM ghcr.io/thin-edge/tedge-demo-main-systemd:20231105.1
# Install Modbus Plugin
COPY --from=build-stage /tmp/modbus-plugin_all.deb /tmp/modbus-plugin_all.deb
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    /tmp/modbus-plugin_all.deb \
    && rm /tmp/modbus-plugin_all.deb

#Add modbus and device config
COPY images/tedge/config/devices.toml /etc/tedge/plugins/modbus/devices.toml
COPY images/tedge/config/modbus.toml /etc/tedge/plugins/modbus/modbus.toml
RUN chmod 666 /etc/tedge/plugins/modbus/modbus.toml
RUN chmod 666 /etc/tedge/plugins/modbus/devices.toml

#Add confguration plugin config
COPY images/tedge/config/tedge-configuration-plugin.toml /etc/tedge/plugins/tedge-configuration-plugin.toml
COPY images/tedge/config/tedge-log-plugin.toml /etc/tedge/plugins/tedge-log-plugin.toml

