# Development image — runs the Vite dev server with HMR.
# For production, build with `npm run build` and serve the static bundle
# (e.g. behind Caddy/Nginx) instead.
FROM node:24-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]
