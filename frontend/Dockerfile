# Build stage
FROM node:20-alpine AS builder

WORKDIR /app/frontend

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build
RUN npm run build

# Production stage
FROM node:20-alpine

WORKDIR /app

# Install serve to run the app
RUN npm install -g serve

# Copy built app from builder
COPY --from=builder /app/frontend/dist ./dist

# Expose port
EXPOSE 5173

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:5173/ || exit 1

# Run application
CMD ["serve", "-s", "dist", "-l", "5173"]