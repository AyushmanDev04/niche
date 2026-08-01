FROM python:3.10

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir  --upgrade -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:80", "app:create_app()"]