FROM python:3.12-slim

WORKDIR /app

# matplotlib needs these for font rendering on slim images
RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    "pyTelegramBotAPI==4.22.1" \
    "supabase==2.10.0" \
    "python-dotenv==1.0.1" \
    "pandas==2.2.3" \
    "matplotlib==3.9.4"

COPY src/ ./src/

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV MPLBACKEND=Agg

CMD ["python", "-m", "src.main"]
