FROM node:20-alpine

WORKDIR /app

# Copy package files and install dependencies
COPY package.json package-lock.json* ./
RUN npm install

# Copy source code
COPY . .

# Expose the port (Railway sets PORT dynamically)
EXPOSE ${PORT:-3000}

# Run the Vite dev server bound to all interfaces
CMD ["sh", "-c", "npx vite --host 0.0.0.0 --port ${PORT:-3000}"]
