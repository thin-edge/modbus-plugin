*** Settings ***
Resource        ../resources/common.robot
Library         Cumulocity

Suite Setup     Set Main Device

*** Variables ***

${EXPECTED_TRANSMIT_RATE}    6
${EXPECTED_POLLING_RATE}     3


*** Test Cases ***
Set values via c8y_ModbusConfiguration Operation
    ${operation}=    Update Modbus Settings    transmit_rate=${EXPECTED_TRANSMIT_RATE}    polling_rate=${EXPECTED_POLLING_RATE}
    Cumulocity.Operation Should Be SUCCESSFUL    ${operation}

Poll rate and transmit rate should be updated for the Device
    ${mo}=    Managed Object Should Have Fragment Values    c8y_ModbusConfiguration.pollingRate\=${EXPECTED_POLLING_RATE}    c8y_ModbusConfiguration.transmitRate\=${EXPECTED_TRANSMIT_RATE}

    ${pollrate}=    Set Variable    ${mo}[c8y_ModbusConfiguration][pollingRate]
    ${transmitrate}=    Set Variable    ${mo}[c8y_ModbusConfiguration][transmitRate]

    Should Be Equal As Numbers    ${pollrate}    ${EXPECTED_POLLING_RATE}
    Should Be Equal As Numbers    ${transmitrate}    ${EXPECTED_TRANSMIT_RATE}

Poll rate and transmit rate should be updated on the Device
    ${shell_operation}=    Execute Shell Command    cat /etc/tedge/plugins/modbus/modbus.toml
    ${shell_operation}=    Cumulocity.Operation Should Be SUCCESSFUL    ${shell_operation}

    ${result_text}=    Set Variable    ${shell_operation}[c8y_Command][result]

    Should Contain    ${result_text}    transmitinterval = ${EXPECTED_TRANSMIT_RATE}
    Should Contain    ${result_text}    pollinterval = ${EXPECTED_POLLING_RATE}

*** Keywords ***

Update Modbus Settings
    [Arguments]    ${transmit_rate}    ${polling_rate}
    ${operation}=    Cumulocity.Create Operation
    ...    fragments={"c8y_ModbusConfiguration": {"transmitRate":${transmit_rate},"pollingRate":${polling_rate}}}
    RETURN    ${operation}
