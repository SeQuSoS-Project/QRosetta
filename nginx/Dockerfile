FROM nginx:alpine

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Copy our custom config
COPY nginx/nginx.conf /etc/nginx/nginx.conf

# Copy static frontend files from the API directory
COPY rosetta-api/static /usr/share/nginx/html

# Dynamically set the DNS resolver at runtime based on /etc/resolv.conf
# This ensures it works in both Docker (127.0.0.11) and Rahti (Internal Cluster DNS)
CMD ["/bin/sh", "-c", "export DNS_RESOLVER=$(grep nameserver /etc/resolv.conf | awk '{print $2}' | head -n1); echo \"Using DNS Resolver: $DNS_RESOLVER\"; sed -i \"s/127.0.0.11/$DNS_RESOLVER/g\" /etc/nginx/nginx.conf; nginx -g 'daemon off;'"]