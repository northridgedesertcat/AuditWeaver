# Docker Operations

Run commands from the repository root. Copy the environment template and configure it privately before starting services. The [Compose file](../../docker/docker-compose.yml), not a copied documentation table, defines actual containers, ports, and volumes.

## Inspect Before Starting

```shell
docker compose --env-file .env -f docker/docker-compose.yml config --quiet
docker compose --env-file .env -f docker/docker-compose.yml ps
```

The first command validates configuration without starting containers. Avoid publishing the expanded output of `config`, which can contain substituted secrets.

## Manual Container Lifecycle

```shell
docker compose --env-file .env -f docker/docker-compose.yml up -d
docker compose --env-file .env -f docker/docker-compose.yml logs --tail 100
docker compose --env-file .env -f docker/docker-compose.yml stop
```

`up -d` changes the running environment and may create or recreate containers. `stop` stops containers without requesting volume deletion. These commands operate on infrastructure only; they do not replace host-process startup, database migrations, topic creation, or connector initialization. Use the checkout's startup entry point for its coordinated development flow.

The old `docker/upCommand.txt` contained only the `up -d` command above. Its content is consolidated here.

## Configuration Ownership

- Container definitions and health checks: [docker-compose.yml](../../docker/docker-compose.yml).
- Index mappings and initializer: [Elasticsearch configuration](../../docker/config/elasticsearch/).
- Topic declarations and initializer: [Kafka configuration](../../docker/config/kafka/).
- Connector definitions: [Kafka Connect configuration](../../docker/config/kafka-connect/).
- Parsing pipeline: [Logstash configuration](../../docker/config/logstash/).

Do not use volume-removal options as routine shutdown commands. Backup and restore procedures must be verified for the actual deployment; an old diagram or a successful local test does not establish recoverability.
