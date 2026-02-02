FROM python:3.12-slim

WORKDIR /code

COPY requirements.txt /code/

# Install git before pip requirements, then remove it after installation is complete
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    pip install --no-cache-dir --upgrade -r /code/requirements.txt && \
    apt-get purge -y git && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY . /code/

EXPOSE 8000

CMD ["gunicorn", "--workers", "2", \ 
     "--bind", "0.0.0.0:8000", "-k", "uvicorn.workers.UvicornWorker", \
     "main:app"]