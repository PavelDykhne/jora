FROM node:22-slim
WORKDIR /app
COPY package*.json ./
RUN npm ci --production
COPY src/ ./src/
COPY config/ ./config/
USER node
CMD ["node", "src/index.js"]
