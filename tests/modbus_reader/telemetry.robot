*** Settings ***
Resource        ../resources/common.robot
Library         Cumulocity

Suite Setup     Set Child Device1


*** Test Cases ***
ChildDevice TestCase1 should have a Test.Int16 Measurement
    Cumulocity.Device Should Have Measurements    1    fragment=Test    series=Int16

ChildDevice TestCase1 should have a Test.Float32 Measurement
    Cumulocity.Device Should Have Measurements    1    fragment=Test    series=Float32

ChildDevice TestCase1 should have Alarms of type TestAlarm on Coil Value 1
    Log    Test Not implemented
