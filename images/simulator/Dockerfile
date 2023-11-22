### 1. Get Linux
FROM python:3.11

### 2. Install pymodbus and aiohttp
COPY images/simulator/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

### 3. Copy modbus server configuration
COPY images/simulator/modbus.json /modbus.json

### 3. Start server
EXPOSE 502
EXPOSE 8080    
ADD images/simulator/simulator.py /
CMD ["python3", "simulator.py"]