*** Settings ***
Resource        ../resources/common.robot
Library         Cumulocity
Library    DateTime

Suite Setup     Set Child Device1


*** Test Cases ***
Device should set supported operations for writing to registers and coils
    Cumulocity.Should Contain Supported Operations    c8y_SetRegister    c8y_SetCoil

Device should write to a register using explicit address format
    [Documentation]    Test writing to register using explicit address format with explicit parameters
    ${operation}=    Cumulocity.Create Operation    {"c8y_SetRegister": { "input": false, "address": 1, "startBit": 0, "noBits": 16, "ipAddress": "simulator", "value": 23, "register": 3 }}    description=Write to register (reference by name)
    Operation Should Be SUCCESSFUL    ${operation}

Device should write to a register referenced by name
    [Documentation]    Test writing to register using format with metrics and register name. 
    ${operation}=    Cumulocity.Create Operation    {"c8y_SetRegister": { "metrics": [{"name": "Test_Int16", "value": 42}] }}    description=Write to register (reference by name)
    Operation Should Be SUCCESSFUL    ${operation}

Device should write float value to register referenced by name
    [Documentation]    Test writing float value to register using new format with Test_Float32 register name 
    ${operation}=    Cumulocity.Create Operation    {"c8y_SetRegister": { "metrics": [{"name": "Test_Float32", "value": 3.14}] }}    description=Write float to register (reference by name)
    Operation Should Be SUCCESSFUL    ${operation}

Device should write to a coil
    ${operation}=    Cumulocity.Create Operation    {"c8y_SetCoil": { "input": false, "coil": 48, "address": 1, "value": 1, "ipAddress": "simulator" } }    description=Write to coil
    Operation Should Be SUCCESSFUL    ${operation}
