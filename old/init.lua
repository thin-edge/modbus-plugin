function init()
   port = tonumber(cdb:get(keyPort)) or 502
   pollingRate = tonumber(cdb:get(keyPollingRate)) or 30
   transmitRate = tonumber(cdb:get(keyTransmitRate)) or 3600
   serPort = cdb:get(keySerPort)
   serBaud = tonumber(cdb:get(keySerBaud)) or 19200
   serData = tonumber(cdb:get(keySerData)) or 8
   serPar = cdb:get(keySerPar)
   serPar = serPar == '' and 'E' or serPar
   serStop = tonumber(cdb:get(keySerStop)) or 1
   c8y:addMsgHandler(816, 'addDevice')
   c8y:addMsgHandler(817, 'saveConfigure')
   c8y:addMsgHandler(821, 'addCoil')
   c8y:addMsgHandler(822, 'addCoilAlarm')
   c8y:addMsgHandler(823, 'addCoilMeasurement')
   c8y:addMsgHandler(824, 'addCoilEvent')
   c8y:addMsgHandler(825, 'addRegister')
   c8y:addMsgHandler(826, 'addRegisterAlarm')
   c8y:addMsgHandler(827, 'addRegisterMeasurement')
   c8y:addMsgHandler(828, 'addRegisterEvent')
   c8y:addMsgHandler(829, 'setServerTime')
   c8y:addMsgHandler(830, 'addCoilStatus')
   c8y:addMsgHandler(831, 'addRegisterStatus')
   c8y:addMsgHandler(832, 'addDevice')
   c8y:addMsgHandler(833, 'setCoil')
   c8y:addMsgHandler(834, 'setRegister')
   c8y:addMsgHandler(835, 'clearCoilAlarm')
   c8y:addMsgHandler(836, 'clearRegisterAlarm')
   c8y:addMsgHandler(839, 'setmbtype')
   c8y:addMsgHandler(840, 'setmbtype')
   c8y:addMsgHandler(847, 'addDevice')
   c8y:addMsgHandler(848, 'addDevice')
   c8y:addMsgHandler(849, 'saveSerialConfiguration')
   c8y:addMsgHandler(851, 'clearAvailabilityAlarm')
   c8y:addMsgHandler(874, 'addRegisterEndian')
   timer0 = c8y:addTimer(pollingRate * 1000, 'poll')
   timer1 = c8y:addTimer(transmitRate * 1000, 'transmit')
   c8y:send(table.concat({'321', c8y.ID, pollingRate, transmitRate, 5}, ','))
   c8y:send(table.concat({'335', c8y.ID, serBaud, serData, serPar, serStop}, ','))
   c8y:send('323,' .. c8y.ID)
   timer0:start()
   timer1:start()
   return 0
end