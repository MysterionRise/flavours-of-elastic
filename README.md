# Repo with collection of different Elastic flavours and their usage

[![CI](https://github.com/MysterionRise/flavours-of-elastic/actions/workflows/ci.yml/badge.svg)](https://github.com/MysterionRise/flavours-of-elastic/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## What's supported:

- [OpenSearch](https://opensearch.org)
- [ElasticSearch](https://www.elastic.co)

### Versions (.env file)
- OpenSearch: **2.17.1**
- Elastic OSS (legacy): **7.10.2**
- Elastic Stack: **8.15.2**

## Quick Start

Choose the stack you want to explore:

1. **Elastic Stack (Latest)** - Modern Elasticsearch with Kibana
   - Best for: Learning latest features, production use with licensing
   - Port: 9200 (HTTPS), Kibana: 5601

2. **OpenSearch** - Open-source alternative to Elasticsearch
   - Best for: Open-source projects, AWS compatibility
   - Port: 9200 (HTTPS), Dashboards: 5601

3. **Elastic OSS (Legacy)** - Elasticsearch 7.10.2 OSS
   - Best for: Supporting legacy 7.x applications, no authentication
   - Port: 9200 (HTTP)

## Comparison Table

| Feature | Elastic Stack (Latest) | OpenSearch | Elastic OSS (Legacy) |
|---------|------------------------|------------|----------------------|
| **Version** | 8.15.2 | 2.17.1 | 7.10.2 |
| **License** | SSPL / Elastic License | Apache 2.0 | Apache 2.0 |
| **Security** | ✅ Built-in (Basic Auth, TLS) | ✅ Built-in | ❌ Not included |
| **Protocol** | HTTPS | HTTPS | HTTP |
| **UI** | Kibana | OpenSearch Dashboards | Kibana OSS |
| **Use Case** | Latest features, commercial support | Fully open-source, AWS ecosystem | Legacy 7.x support |
| **Authentication** | Required (elastic/elastic) | Required (admin/strong-password) | Not required |
| **Updates** | Active development | Active development | No updates (frozen) |
| **Plugins** | Extensive ecosystem | Growing ecosystem | Limited (7.x only) |
| **Memory Usage** | ~2-3GB | ~4GB | ~1GB |
| **Best For Students** | Learning modern features | Open-source projects | Simple setup, testing |

**When to use each:**
- **Elastic Stack**: You want to learn the latest Elasticsearch features and don't mind the licensing
- **OpenSearch**: You prefer truly open-source software or plan to deploy on AWS
- **Elastic OSS**: You need compatibility with legacy 7.x applications or want the simplest setup without security

## Prerequisites

Before running these examples, ensure you have:

- **Docker**: Version 20.10+ ([Install Docker](https://docs.docker.com/install/))
- **Docker Compose**: Version 1.29+ ([Install Docker Compose](https://docs.docker.com/compose/install/))
- **System RAM**: Minimum 8GB recommended (4GB absolute minimum)
  - Elastic Stack: ~2-3GB
  - OpenSearch: ~4GB
  - Elastic OSS: ~1GB
- **Disk Space**: At least 10GB free
- **Available Ports**: 9200, 5601, 9600

**Note for Linux users**: You may need to increase `vm.max_map_count`:
```sh
sudo sysctl -w vm.max_map_count=262144
```

**Java Heap Sizes Explained:**

The different memory configurations reflect realistic usage patterns:
- **Elastic Stack (1GB per node)**: Balanced for production-like testing with security features
- **OpenSearch (2GB per node)**: Higher baseline due to additional built-in features and plugins
- **Elastic OSS (512MB per node)**: Minimal configuration for legacy support and testing

If you have limited RAM (< 8GB), you can reduce these values in the docker-compose.yml files:
```yaml
- "ES_JAVA_OPTS=-Xms512m -Xmx512m"  # Minimum recommended
```

## How To Run Those Examples

You would need to install [Docker](https://docs.docker.com/install/) and [Docker Compose](https://docs.docker.com/compose/install/)

### Start cluster

```sh
# Elastic Stack
# The .env file is pre-configured with default credentials (elastic/elastic)
# You can modify them if needed before running
docker compose -f docker/elk/docker-compose.yml --env-file .env up
curl --insecure https://localhost:9200 -u elastic:elastic

# OpenSearch
# The .env file is pre-configured with a strong admin password
# Check OPENSEARCH_INITIAL_ADMIN_PASSWORD in .env file
docker compose -f docker/opensearch/docker-compose.yml --env-file .env up
curl --insecure https://localhost:9200 -u admin:YOUR_PASSWORD_FROM_ENV

# Elasticsearch OSS (do not update OSS version)
docker compose -f docker/elk-oss/docker-compose.yml --env-file .env up
curl http://localhost:9200

```

After some time you will have Kibana/OpenSearch Dashboards available at this [URL](http://localhost:5601/)

### Next Steps - Getting Started with Queries

Once your cluster is running, try these basic operations:

#### 1. Create an Index

**Elastic Stack / OpenSearch:**
```sh
curl --insecure -X PUT "https://localhost:9200/my-first-index" -u elastic:elastic
```

**Elastic OSS:**
```sh
curl -X PUT "http://localhost:9200/my-first-index"
```

#### 2. Add a Document

**Elastic Stack / OpenSearch:**
```sh
curl --insecure -X POST "https://localhost:9200/my-first-index/_doc/1" \
  -u elastic:elastic \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "Learning Elasticsearch",
    "description": "This is my first document",
    "timestamp": "2025-01-15"
  }'
```

**Elastic OSS:**
```sh
curl -X POST "http://localhost:9200/my-first-index/_doc/1" \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "Learning Elasticsearch",
    "description": "This is my first document",
    "timestamp": "2025-01-15"
  }'
```

#### 3. Search Documents

**Elastic Stack / OpenSearch:**
```sh
curl --insecure "https://localhost:9200/my-first-index/_search?q=Learning" -u elastic:elastic
```

**Elastic OSS:**
```sh
curl "http://localhost:9200/my-first-index/_search?q=Learning"
```

#### 4. Explore with Kibana/Dashboards

1. Open http://localhost:5601/ in your browser
2. **For Elastic Stack**: Login with `elastic` / `elastic`
3. **For OpenSearch**: Login with `admin` / `<password-from-env>`
4. **For Elastic OSS**: No login required
5. Go to **Dev Tools** (Console) to run queries interactively
6. Try creating visualizations and dashboards

#### 5. Common Operations

```sh
# List all indices
curl --insecure "https://localhost:9200/_cat/indices?v" -u elastic:elastic

# Check cluster health
curl --insecure "https://localhost:9200/_cluster/health?pretty" -u elastic:elastic

# Get document by ID
curl --insecure "https://localhost:9200/my-first-index/_doc/1" -u elastic:elastic

# Delete an index
curl --insecure -X DELETE "https://localhost:9200/my-first-index" -u elastic:elastic
```

## Licence Changes

After recent changes [announced](https://www.elastic.co/blog/licensing-change) for Elastic to move its product to SSPL licence, I would strongly recommend to keep using truly open source version of it.
Not only it has security features available for free, but also it doesn't have any strings attached to it via SSPL licence.

Read more on this [here](https://anonymoushash.vmbrasseur.com/2021/01/14/elasticsearch-and-kibana-are-now-business-risks)

## Benchmarking

Want to compare performance between different stacks? Use these benchmarking tools:

### For Elastic Stack (and Elastic OSS)

Use [ESRally](https://github.com/elastic/rally) - the official Elasticsearch benchmarking tool.

**Install:**
```sh
pip3 install esrally
```

**Run benchmark:**
```sh
# For Elastic Stack (with authentication)
esrally race --track=geonames --target-hosts=localhost:9200 --pipeline=benchmark-only \
  --client-options="use_ssl:true,verify_certs:false,basic_auth_user:'elastic',basic_auth_password:'elastic'"

# For Elastic OSS (no authentication)
esrally race --track=geonames --target-hosts=localhost:9200 --pipeline=benchmark-only
```

### For OpenSearch

Use [OpenSearch Benchmark](https://github.com/opensearch-project/opensearch-benchmark) - compatible with OpenSearch.

**Install:**
```sh
pip install opensearch-benchmark
```

**Run benchmark:**
```sh
opensearch-benchmark execute-test --workload=geonames --target-hosts=localhost:9200 --pipeline=benchmark-only \
  --client-options="use_ssl:true,verify_certs:false,basic_auth_user:'admin',basic_auth_password:'YOUR_PASSWORD_FROM_ENV'"
```

**Available workloads:** geonames, http_logs, nyc_taxis, percolator, and more. See [workload repository](https://github.com/opensearch-project/opensearch-benchmark-workloads) for details.

Compare results between stacks and create your own test experiments!

## Troubleshooting

### Port Already in Use (9200 or 5601)

If you see an error like "port is already allocated":

```sh
# Check what's using the port
sudo lsof -i :9200
sudo lsof -i :5601

# Stop any existing Elasticsearch/Kibana processes
docker compose down

# Or use different ports by modifying docker-compose.yml
```

### Out of Memory Errors

If containers crash with OOM errors:

1. **Reduce Java heap size** in docker-compose.yml:
   ```yaml
   - "ES_JAVA_OPTS=-Xms512m -Xmx512m"  # Reduce from 1G or 2G
   ```

2. **Increase Docker memory limit**:
   - Docker Desktop: Settings → Resources → Memory (set to 6GB+)
   - Linux: Docker uses host memory directly

3. **Run only one stack at a time** to reduce memory usage

### vm.max_map_count Too Low (Linux)

Error: `max virtual memory areas vm.max_map_count [65530] is too low`

**Temporary fix:**
```sh
sudo sysctl -w vm.max_map_count=262144
```

**Permanent fix:**
```sh
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### Connection Refused or Timeout

If `curl` commands fail:

1. **Wait for services to start** - initial startup can take 2-5 minutes
2. **Check container health**:
   ```sh
   docker compose ps
   docker compose logs
   ```
3. **Verify correct protocol**: Elastic Stack and OpenSearch use HTTPS, Elastic OSS uses HTTP

### Elasticsearch Fails to Start in Cluster

For two-node clusters, both nodes must start successfully:

1. **Check logs**:
   ```sh
   docker compose logs es01
   docker compose logs es02
   ```

2. **Clean restart**:
   ```sh
   docker compose down -v  # Warning: deletes all data
   docker compose up
   ```

### Certificate Errors (Elastic Stack)

If you see SSL/TLS errors:

1. Certificates are auto-generated on first run
2. If corrupted, remove and regenerate:
   ```sh
   docker compose down -v
   docker volume rm elk_certs  # if exists
   docker compose up
   ```

### Docker Not Running

Error: `Cannot connect to the Docker daemon`

```sh
# Start Docker
sudo systemctl start docker  # Linux
# or open Docker Desktop (Mac/Windows)

# Verify Docker is running
docker ps
```

### Disk Space Issues

If you run low on disk space:

```sh
# Remove all stopped containers and unused volumes
docker system prune -a --volumes

# Check Docker disk usage
docker system df
```

## Cleanup

To stop services and preserve data:
```sh
docker compose down
```

To stop services and **remove all data**:
```sh
docker compose down -v
```

To remove everything and start fresh:
```sh
docker compose down -v
docker system prune -a
```

## Development & Contributing

### For Contributors

If you want to contribute to this repository:

1. **Fork and clone** the repository
2. **Install pre-commit hooks** for code quality:
   ```sh
   pip install pre-commit
   pre-commit install
   ```

3. **Make your changes** to docker compose files, documentation, or configurations
4. **Test your changes** by running the affected stack(s)
5. **Submit a Pull Request** with a clear description

### Pre-commit Hooks

This repository uses pre-commit hooks to maintain code quality:
- **check-yaml**: Validates YAML syntax
- **end-of-file-fixer**: Ensures files end with newline
- **trailing-whitespace**: Removes trailing spaces
- **black**: Python code formatter
- **isort**: Sorts Python imports
- **flake8**: Python linter

To run manually before committing:
```sh
pre-commit run --all-files
```

### Testing & Validation

This repository includes automated testing to ensure all stacks work correctly.

#### Continuous Integration

GitHub Actions automatically tests all three stacks on every push and pull request:
- ✅ YAML validation
- ✅ Each stack starts successfully
- ✅ Cluster health checks pass
- ✅ Index operations work (create, insert, search)
- ✅ UI (Kibana/Dashboards) is accessible

View CI status: [![CI](https://github.com/MysterionRise/flavours-of-elastic/actions/workflows/ci.yml/badge.svg)](https://github.com/MysterionRise/flavours-of-elastic/actions/workflows/ci.yml)

#### Local Validation

Test all stacks locally using the validation script:

**Install dependencies:**
```sh
pip install -r requirements.txt
```

**Run validation:**
```sh
# Test all stacks
python validate.py --stack all

# Test specific stack
python validate.py --stack elk-oss
python validate.py --stack opensearch
python validate.py --stack elastic
```

The validation script checks:
1. Stack starts successfully
2. Cluster responds and is healthy
3. Can create indices
4. Can index documents
5. Can search documents
6. UI is accessible

**Note:** The script automatically cleans up Docker volumes after testing. Use `--no-cleanup` to preserve volumes.

### Project Structure

```
flavours-of-elastic/
├── .github/
│   └── workflows/
│       └── ci.yml        # GitHub Actions CI pipeline
├── docker/
│   ├── elk/              # Elastic Stack (latest)
│   ├── opensearch/       # OpenSearch
│   └── elk-oss/          # Elastic OSS (7.10.2 legacy)
├── benchmarks/           # Benchmark results
├── .env                  # Environment configuration
├── .env.example          # Template for configuration
├── validate.py           # Validation script for local testing
├── requirements.txt      # Python dependencies
└── ISSUES.md            # Tracked issues and improvements
```

### Updating Versions

When updating Elastic or OpenSearch versions:

1. Update version in `.env` file
2. Update version in `README.md` (Versions section)
3. Test all three stacks to ensure compatibility
4. Update `ISSUES.md` if new issues are discovered
5. Commit with clear message: `feat: update <stack> to <version>`

## Learn More

- [Elasticsearch Official Documentation](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)
- [OpenSearch Documentation](https://opensearch.org/docs/latest/)
- [Kibana Guide](https://www.elastic.co/guide/en/kibana/current/index.html)
- [OpenSearch Dashboards](https://opensearch.org/docs/latest/dashboards/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)

## License

See [LICENSE](LICENSE) file for details.
