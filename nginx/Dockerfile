FROM nginx:alpine

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Copy our custom config
COPY nginx/nginx.conf /etc/nginx/nginx.conf

# Copy static frontend files from the API directory
COPY rosetta-api/static /usr/share/nginx/html