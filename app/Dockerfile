FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH=/app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# instala dependências Python
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# copia código
COPY . .

# copia e configura o entrypoint (converte CRLF -> LF para compatibilidade Linux)
COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r//' /entrypoint.sh && chmod +x /entrypoint.sh

# expõe porta do streamlit
EXPOSE 8501

ENTRYPOINT ["/entrypoint.sh"]