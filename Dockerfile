FROM python:3.12-slim

WORKDIR /app


COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt


COPY planet_alert.py /app/planet_alert.py
COPY email.html      /app/email.html

# COPY de421.bsp      /root/.skyfield/de421.bsp


CMD ["/bin/sh","-lc","echo '--- runtime ls /app ---' && ls -la /app && python /app/planet_alert.py"]
