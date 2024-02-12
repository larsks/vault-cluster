FROM python:3.12

WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY vaultomatic.py ./

CMD ["python", "vaultomatic.py"]
