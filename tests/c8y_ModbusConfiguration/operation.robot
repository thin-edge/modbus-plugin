*** Settings ***
Resource        ../resources/common.robot
Library         Cumulocity
Library         String

Suite Setup     Run Keywords    Set Main Device    Create c8y_ModbusConfiguration Operation


*** Variables ***
${OPERATION}    ${EMPTY}


*** Test Cases ***
c8y_ModbusConfiguration Operation should be successful
    Cumulocity.Operation Should Be SUCCESSFUL    ${OPERATION}    timeout=60

Poll rate and transmit rate should be updated for the Device
    ${expected_pollrate}    Set Variable    3
    ${expected_transmitrate}    Set Variable    3

    ${mo}    Managed Object Should Have Fragments    c8y_ModbusConfiguration

    ${pollrate}    Set Variable    ${mo}[c8y_ModbusConfiguration][pollingRate]
    ${transmitrate}    Set Variable    ${mo}[c8y_ModbusConfiguration][transmitRate]

    Should Be Equal As Numbers    ${pollrate}    ${expected_pollrate}
    Should Be Equal As Numbers    ${transmitrate}    ${expected_transmitrate}

Poll rate and transmit rate should be updated on the Device
    ${expected_pollrate}    Set Variable    3
    ${expected_transmitrate}    Set Variable    3

    ${shell_operation}    Execute Shell Command    cat /etc/tedge/plugins/modbus/modbus.toml
    ${shell_operation}    Cumulocity.Operation Should Be SUCCESSFUL    ${shell_operation}    timeout=60

    ${result_text}    Set Variable    ${shell_operation}[c8y_Command][result]

    Should Contain    ${result_text}    transmitinterval = 3
    Should Contain    ${result_text}    pollinterval = 3


*** Keywords ***
Create c8y_ModbusConfiguration Operation
    ${OPERATION}    Cumulocity.Create Operation
    ...    fragments={"c8y_ModbusConfiguration": {"transmitRate": 3,"pollingRate": 3}}
    Set Global Variable    ${OPERATION}    ${OPERATION}
