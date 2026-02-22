# Multi-stage build for Rust
FROM rust:1.75-slim as builder

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y pkg-config libssl-dev && rm -rf /var/lib/apt/lists/*

# Copy manifest files first for better caching
COPY Cargo.toml Cargo.lock ./

# Copy source code
COPY src ./src

# Build release binary
RUN cargo build --release

# Runtime stage
FROM debian:bookworm-slim

WORKDIR /app

# Install SSL certificates for HTTPS requests
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*

# Copy binary from builder
COPY --from=builder /app/target/release/weather-trader /app/weather-trader

# Set environment variables
ENV RUST_LOG=info
ENV DASHBOARD=true

# Expose dashboard port
EXPOSE 8080

# Run the bot
CMD ["/app/weather-trader"]
