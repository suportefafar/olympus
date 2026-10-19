# Keep the same Debian/glibc family as Olympus postgres:17 data volumes.
FROM postgres:17-trixie
RUN apt-get update -qq && apt-get install --no-install-recommends -y postgresql-17-pgvector && rm -rf /var/lib/apt/lists/*
