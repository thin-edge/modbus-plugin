set dotenv-load := true

# Start the demo
up *args="":
    docker compose up --build {{args}}

# Stop the demo
down *args="":
    docker compose down {{args}}

# Stop the demo and destroy the data
down-all:
    docker compose down -v

# Install python virtual environment
venv:
  [ -d .venv ] || python3 -m venv .venv
  ./.venv/bin/pip3 install -r tests/requirements.txt

# Build deb package
setup:
    @mkdir -p ./tests/data
    docker run --rm -v $PWD:/tmp -w /tmp goreleaser/nfpm package \
    --config /tmp/nfpm.yaml \
    --target /tmp/tests/data/tedge-modbus-plugin.deb \
    --packager deb


# Run tests
test *args='':
  ./.venv/bin/python3 -m robot.run --outputdir output {{args}} tests

# Configure and register the device to the cloud
bootstrap *args="":
    docker compose exec --env "DEVICE_ID=${DEVICE_ID:-}" --env "C8Y_BASEURL=${C8Y_BASEURL:-}" --env "C8Y_USER=${C8Y_USER:-}" --env "C8Y_PASSWORD=${C8Y_PASSWORD:-}" tedge bootstrap.sh {{args}}

# Start a shell
shell *args='bash':
    docker compose exec tedge {{args}}



# Clean up
cleanup DEVICE_ID $CI="true":
    echo "Removing device and child devices (including certificates)"
    c8y devicemanagement certificates list -n --tenant "$(c8y currenttenant get --select name --output csv)" --filter "name eq ${DEVICE_ID}" --pageSize 2000 | c8y devicemanagement certificates delete --tenant "$(c8y currenttenant get --select name --output csv)"
    c8y inventory find -n --owner "device_${DEVICE_ID}" -p 100 | c8y inventory delete
    c8y users delete -n --id "device_${DEVICE_ID}$" --tenant "$(c8y currenttenant get --select name --output csv)" --silentStatusCodes 404 --silentExit