*** Settings ***
Resource        ../resources/common.robot
Library         Cumulocity

Suite Setup     Set Main Device


*** Test Cases ***
Device should have the fragment c8y_ModbusConfiguration
    Cumulocity.Device Should Have Fragments    c8y_ModbusConfiguration
    Managed Object Should Have Fragment Values    c8y_ModbusConfiguration.pollingRate=2

ChildDevice TestCase1 should be created
    Cumulocity.Should Be A Child Device Of Device    ${DEVICE_ID}:device:TestCase1

ChildDevice TestCase1 should have the fragment c8y_ModbusDevice
    ${expected_address}    Set Variable    1
    ${expected_protocol}    Set Variable    TCP
    ${expected_ipAddress}    Set Variable    simulator

    Set Child Device1
    ${mo}    Managed Object Should Have Fragments    c8y_ModbusDevice

    ${address}    Set Variable    ${mo}[c8y_ModbusDevice][address]
    ${ipAddress}    Set Variable    ${mo}[c8y_ModbusDevice][ipAddress]
    ${protocol}    Set Variable    ${mo}[c8y_ModbusDevice][protocol]
    Should Be Equal As Numbers    ${address}    ${expected_address}
    Should Be Equal As Strings    ${ipAddress}    ${expected_ipAddress}
    Should Be Equal As Strings    ${protocol}    ${expected_protocol}
    Set Main Device

Service tedge-modbus-plugin should be enabled
    Should Have Services    name=tedge-modbus-plugin    service_type=service    status=up
