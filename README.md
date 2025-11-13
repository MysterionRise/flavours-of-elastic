# Repo with collection of different Elastic flavours and their usage

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

## How To Run Those Examples

You would need to install [Docker](https://docs.docker.com/install/) and [Docker Compose](https://docs.docker.com/compose/install/)

### Start cluster

```sh
# Elastic Stack
# The .env file is pre-configured with default credentials (elastic/elastic)
# You can modify them if needed before running
docker-compose -f docker/elk/docker-compose.yml --env-file .env up
curl --insecure https://localhost:9200 -u elastic:elastic

# OpenSearch
# The .env file is pre-configured with a strong admin password
# Check OPENSEARCH_INITIAL_ADMIN_PASSWORD in .env file
docker-compose -f docker/opensearch/docker-compose.yml --env-file .env up
curl --insecure https://localhost:9200 -u admin:YOUR_PASSWORD_FROM_ENV

# Elasticsearch OSS (do not update OSS version)
docker-compose -f docker/elk-oss/docker-compose.yml --env-file .env up
curl http://localhost:9200

```

After some time you will have Kibana/OpenSearch Dashboards available at this [URL](http://localhost:5601/)

## Licence Changes

After recent changes [announced](https://www.elastic.co/blog/licensing-change) for Elastic to move its product to SSPL licence, I would strongly recommend to keep using truly open source version of it.
Not only it has security features available for free, but also it doesn't have any strings attached to it via SSPL licence.

Read more on this [here](https://anonymoushash.vmbrasseur.com/2021/01/14/elasticsearch-and-kibana-are-now-business-risks)

### Benchmarking

One of the possibility to compare those are to use [ESRally](https://github.com/elastic/rally) and run some experiments with it

Install ESRally


#### Elastic Stack

Install ESRally
```
pip3 install esrally
```

and then benchmark

```sh
esrally race --track=geonames --target-hosts=localhost:9200 --pipeline=benchmark-only --client-options="use_ssl:true,verify_certs:false,basic_auth_user:'admin',basic_auth_password:'admin'"
```

#### OpenSearch

Install Opensearch Benchmark
```
pip install opensearch-benchmark
```

and then benchmark

```sh
opensearch-benchmark execute-test --workload=geonames --target-hosts=localhost:9200 --pipeline=benchmark-only --client-options="use_ssl:true,verify_certs:false,basic_auth_user:'admin',basic_auth_password:'admin'"
```

Enjoy the results or create your own test experiments.
