### 1. Get Linux
FROM python:3.9-slim

### 2. Install pymodbus
RUN pip install pymodbus
RUN pip install serial
RUN pip install pyserial-asyncio

### 3. Start server
EXPOSE 502    
ADD simulator.py /
CMD ["python3", "simulator.py"]