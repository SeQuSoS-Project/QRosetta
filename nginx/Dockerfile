FROM nginxinc/nginx-unprivileged:1.31.7-alpine3.24@sha256:b5047b9b76845eac124358373c6852377c52e4b05834a47647e955dd91cb8f1e

ARG QROSETTA_GIT_SHA=unknown
ENV QROSETTA_IMAGE_GIT_SHA=${QROSETTA_GIT_SHA}

# The base image's entrypoint sources the resolver script, then renders the resolver template into
# conf.d, substituting QROSETTA_* only; nginx runs as uid 101 and listens on 8080.
ENV NGINX_ENVSUBST_FILTER=^QROSETTA_
# nginx loads no dynamic module and nothing here calls curl: removing the optional modules and
# curl takes curl, libgd, freetype and brotli out of the image.
USER 0
RUN apk del --no-cache curl nginx-module-geoip nginx-module-image-filter nginx-module-njs nginx-module-xslt && \
    rm /etc/nginx/conf.d/default.conf
COPY --chmod=0755 nginx/14-qrosetta-resolver.envsh /docker-entrypoint.d/14-qrosetta-resolver.envsh
COPY nginx/resolver.conf.template /etc/nginx/templates/resolver.conf.template
COPY nginx/nginx.conf /etc/nginx/nginx.conf

COPY rosetta-api/static /usr/share/nginx/html

EXPOSE 8080

USER 101
