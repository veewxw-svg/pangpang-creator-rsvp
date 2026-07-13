FROM node:20-bookworm-slim

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    curl \
    python3 \
    python3-pip \
    fonts-noto-cjk \
  && rm -rf /var/lib/apt/lists/*

COPY package.json requirements.txt ./
RUN npm install --omit=dev
RUN pip3 install --break-system-packages --no-cache-dir -r requirements.txt

COPY . .

ENV NODE_ENV=production
ENV PORT=8787
ENV PYTHON_BIN=python3
ENV DATA_DIR=/var/data
ENV OUTPUT_DIR=/tmp/pangpang-output

EXPOSE 8787

CMD ["node", "server.mjs"]
