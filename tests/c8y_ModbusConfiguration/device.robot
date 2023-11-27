*** Settings ***
Resource        ../resources/common.robot
Library         Cumulocity

Suite Setup     Set Main Device


*** Test Cases ***


Device should support the operation c8y_ModbusConfiguration
    Cumulocity.Should Contain Supported Operations    c8y_ModbusConfiguration


