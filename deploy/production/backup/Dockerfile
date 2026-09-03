FROM postgres:17-alpine
RUN apk add --no-cache bash restic
COPY backup-loop.sh backup-once.sh restore-drill.sh /usr/local/bin/
RUN chmod 755 /usr/local/bin/backup-loop.sh /usr/local/bin/backup-once.sh /usr/local/bin/restore-drill.sh
ENTRYPOINT ["/usr/local/bin/backup-loop.sh"]
