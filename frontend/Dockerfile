FROM node:22-slim

WORKDIR /app

COPY package.json bun.lock ./
RUN npm install -g bun && bun install

COPY . .

ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npx next build

EXPOSE 3000

CMD ["npx", "next", "start"]
