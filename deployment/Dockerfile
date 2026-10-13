FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/Proyecto_Web
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app/Proyecto_Web
RUN useradd --create-home labmanager && mkdir -p private_media staticfiles && chown -R labmanager:labmanager /app
USER labmanager
CMD ["sh", "deployment/start.sh"]
