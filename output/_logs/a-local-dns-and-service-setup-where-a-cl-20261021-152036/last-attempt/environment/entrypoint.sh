#!/bin/sh
# Copy system configuration files that cannot be written during Docker build
# because Docker mounts /etc/hosts and /etc/resolv.conf as read-only during build.

if [ -f /etc/hosts.stage ]; then
    cp /etc/hosts.stage /etc/hosts
fi

if [ -f /etc/resolv.conf.stage ]; then
    cp /etc/resolv.conf.stage /etc/resolv.conf
fi

exec "$@"
