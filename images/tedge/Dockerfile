#Build dpkg package
FROM goreleaser/nfpm as build-stage

# Copy required files
WORKDIR /build
COPY tedge_modbus /build/tedge_modbus
COPY operations /build/operations
COPY scripts /build/scripts
COPY nfpm.yaml /build/nfpm.yaml
COPY tedge-modbus-plugin.service /build/tedge-modbus-plugin.service
# Build Package
RUN nfpm pkg --packager deb --target /tmp/modbus-plugin_all.deb

FROM ghcr.io/thin-edge/tedge-demo-main-systemd:latest
# Install Modbus Plugin
COPY --from=build-stage /tmp/modbus-plugin_all.deb /tmp/modbus-plugin_all.deb
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    /tmp/modbus-plugin_all.deb \
    && rm /tmp/modbus-plugin_all.deb

# Add confguration plugin config
COPY images/tedge/config/tedge-configuration-plugin.toml /etc/tedge/plugins/tedge-configuration-plugin.toml
COPY images/tedge/config/tedge-log-plugin.toml /etc/tedge/plugins/tedge-log-plugin.toml
