*** Settings ***
Resource        ../resources/common.robot
Library         Cumulocity

Suite Setup     Run Keywords    Set Main Device    Create c8y_ModbusConfiguration Operation


*** Variables ***
${OPERATION}    ${EMPTY}


*** Test Cases ***
c8y_ModbusConfiguration Operation should be successful
    Cumulocity.Operation Should Be SUCCESSFUL    ${OPERATION}    timeout=60

Child Device from operation should have been created
    Cumulocity.Operation Should Be SUCCESSFUL    ${OPERATION}    timeout=60
    Cumulocity.Should Be A Child Device Of Device    TestCase1

ChildDevice TestCase1 should have a Test.Int16 Measurement
    Cumulocity.Operation Should Be SUCCESSFUL    ${OPERATION}    timeout=60
    Cumulocity.Set Device    TestCase1
    Cumulocity.Device Should Have Measurements    1    fragment=Test    series=Int16

ChildDevice TestCase1 should have a Test.Float32 Measurement
    Cumulocity.Operation Should Be SUCCESSFUL    ${OPERATION}    timeout=60
    Cumulocity.Set Device    TestCase1
    Cumulocity.Device Should Have Measurements    1    fragment=Test    series=Float32


*** Keywords ***
Create c8y_ModbusConfiguration Operation
    ${OPERATION}=    Cumulocity.Create Operation
    ...    fragments={"c8y_ModbusDevice": {"protocol": "TCP","address": 2,"name": "Test Device 2","ipAddress": "127.0.0.1","type": "/inventory/managedObjects/28891327"},"description": "Test ModbusConfiguration"}
    Set Global Variable    ${OPERATION}    ${OPERATION}
