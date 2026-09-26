# Helper container for fault injection on kind platform
FROM alpine:3.19

# Install required packages
RUN apk add --no-cache postgresql-client procps

# Copy helper scripts
COPY stop.sh cont.sh kill.sh verify_stopped.sh /helper/
RUN chmod +x /helper/*.sh

# Set working directory
WORKDIR /helper

# Default command (overridden by k8s)
CMD ["/bin/sh", "-c", "sleep infinity"]
