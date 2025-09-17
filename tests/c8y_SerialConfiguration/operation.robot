*** Settings ***
Resource        ../resources/common.robot
Library         Cumulocity

Suite Setup     Set Main Device

*** Variables ***

${EXPECTED_BAUD_RATE}    9600
${EXPECTED_STOP_BITS}    2
${EXPECTED_PARITY}    N
${EXPECTED_DATA_BITS}    8


*** Test Cases ***
Set values via c8y_SerialConfiguration Operation
    ${operation}=    Update Serial Configuration Settings
    ...    baud_rate=${EXPECTED_BAUD_RATE}
    ...    stop_bits=${EXPECTED_STOP_BITS}
    ...    parity=${EXPECTED_PARITY}
    ...    data_bits=${EXPECTED_DATA_BITS}
    Cumulocity.Operation Should Be SUCCESSFUL    ${operation}

Serial configuration should be updated for the Device
    ${mo}=    Managed Object Should Have Fragment Values
    ...    c8y_SerialConfiguration.baudRate\=${EXPECTED_BAUD_RATE}
    ...    c8y_SerialConfiguration.stopBits\=${EXPECTED_STOP_BITS}
    ...    c8y_SerialConfiguration.parity\=${EXPECTED_PARITY}
    ...    c8y_SerialConfiguration.dataBits\=${EXPECTED_DATA_BITS}

    ${baudrate}=    Set Variable    ${mo}[c8y_SerialConfiguration][baudRate]
    ${stopbits}=    Set Variable    ${mo}[c8y_SerialConfiguration][stopBits]
    ${parity}=    Set Variable    ${mo}[c8y_SerialConfiguration][parity]
    ${databits}=    Set Variable    ${mo}[c8y_SerialConfiguration][dataBits]

    Should Be Equal As Numbers    ${baudrate}    ${EXPECTED_BAUD_RATE}
    Should Be Equal As Numbers    ${stopbits}    ${EXPECTED_STOP_BITS}
    Should Be Equal As Strings    ${parity}    ${EXPECTED_PARITY}
    Should Be Equal As Numbers    ${databits}    ${EXPECTED_DATA_BITS}

Serial configuration should be updated on the Device
    ${shell_operation}=    Execute Shell Command    cat /etc/tedge/plugins/modbus/modbus.toml
    ${shell_operation}=    Cumulocity.Operation Should Be SUCCESSFUL    ${shell_operation}

    ${result_text}=    Set Variable    ${shell_operation}[c8y_Command][result]

    Should Contain    ${result_text}    baudrate = ${EXPECTED_BAUD_RATE}
    Should Contain    ${result_text}    stopbits = ${EXPECTED_STOP_BITS}
    Should Contain    ${result_text}    parity = "${EXPECTED_PARITY}"
    Should Contain    ${result_text}    databits = ${EXPECTED_DATA_BITS}

*** Keywords ***

Update Serial Configuration Settings
    [Arguments]    ${baud_rate}    ${stop_bits}    ${parity}    ${data_bits}
    ${operation}=    Cumulocity.Create Operation
    ...    fragments={"c8y_SerialConfiguration": {"baudRate":${baud_rate},"stopBits":${stop_bits},"parity":"${parity}","dataBits":${data_bits}}}
    RETURN    ${operation}
