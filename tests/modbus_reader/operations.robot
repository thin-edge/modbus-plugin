*** Settings ***
Resource        ../resources/common.robot
Library         Cumulocity
Library    DateTime

Suite Setup     Set Child Device1


*** Test Cases ***
Device should set supported operations for writing to registers and coils
    Cumulocity.Should Contain Supported Operations    c8y_SetRegister    c8y_SetCoil

Device should write to a registers
    ${operation}=    Cumulocity.Create Operation    {"c8y_SetRegister": { "input": false, "address": 1, "startBit": 0, "noBits": 16, "ipAddress": "simulator", "value": 23, "register": 3 }}    description=Write to register
    Operation Should Be SUCCESSFUL    ${operation}

Device should write to a coil
    ${operation}=    Cumulocity.Create Operation    {"c8y_SetCoil": { "input": false, "coil": 48, "address": 1, "value": 1, "ipAddress": "simulator" } }    description=Write to coil
    Operation Should Be SUCCESSFUL    ${operation}
