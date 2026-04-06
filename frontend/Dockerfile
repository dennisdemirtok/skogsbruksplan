FROM node:20-alpine

WORKDIR /app

# Copy package files and install dependencies
COPY package.json package-lock.json* ./
RUN npm install

# Copy source code
COPY . .

# Expose the Vite dev server port
EXPOSE 5173

# Run the Vite dev server bound to all interfaces
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
