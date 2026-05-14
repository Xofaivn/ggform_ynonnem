# FROM python:3.11-slim

# # Install Chrome
# RUN apt-get update && apt-get install -y wget gnupg ca-certificates \
#     && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub \
#        | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
#     && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
#        > /etc/apt/sources.list.d/google-chrome.list \
#     && apt-get update \
#     && apt-get install -y google-chrome-stable \
#     && rm -rf /var/lib/apt/lists/*

# WORKDIR /app
# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt

# COPY . .

# RUN mkdir -p profiles data

# EXPOSE 8000
# CMD ["python", "web_main.py"]
FROM python:3.11-slim

# Install Chrome + dependencies
RUN apt-get update && apt-get install -y \
    wget gnupg ca-certificates curl unzip \
    # Chrome system dependencies
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    xdg-utils \
    --no-install-recommends \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub \
       | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
       > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p profiles data

EXPOSE 8000
CMD ["python", "web_main.py"]