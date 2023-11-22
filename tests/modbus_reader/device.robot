*** Settings ***
Resource        ../resources/common.robot
Library         Cumulocity

Suite Setup     Set Main Device


*** Test Cases ***
ChildDevice TestCase1 should be created
    Cumulocity.Should Be A Child Device Of Device    ${DEVICE_ID}:device:TestCase1

Service tedge-modbus-plugin should be enabled
    Should Have Services    name=tedge-modbus-plugin    service_type=service    status=up

Device should have the fragment c8y_ModbusConfiguration
    Cumulocity.Device Should Have Fragments    c8y_ModbusConfiguration
    Managed Object Should Have Fragment Values    c8y_ModbusConfiguration.pollingRate=2
