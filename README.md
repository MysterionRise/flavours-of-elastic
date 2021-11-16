# Repo with collection of different Elastic flavours and their usage

## What's supported:

- [OpenSearch](https://opensearch.org)
- [OpenDistro for Elasticsearch](https://opendistro.github.io/for-elasticsearch/)
- [ElasticSearch](https://www.elastic.co)

### Versions (.env file)
- OpenSearch: **1.1.0**
- OpenDistro: **1.13.2**
- Elastic: **7.10.2**


## How To Run Those Examples

You would need to install [Docker](https://docs.docker.com/install/) and [Docker Compose](https://docs.docker.com/compose/install/)

### Start cluster 

```sh
# ELK
docker-compose -f docker/elk/docker-compose.yml --env-file .env up

# ODFE
docker-compose -f docker/odfe/docker-compose.yml --env-file .env up

# OPENSEARCH
docker-compose -f docker/opensearch/docker-compose.yml --env-file .env up
```

After some time you will have Kibana/OpenSearch Dashboards available at this [URL](http://localhost:5601/)

## Licence Changes

After recent changes [announced](https://www.elastic.co/blog/licensing-change) for Elastic to move its product to SSPL licence, I would strongly recommend to keep using truly open source version of it.
Not only it has security features available for free, but also it doesn't have any strings attached to it via SSPL licence.

Read more on this [here](https://anonymoushash.vmbrasseur.com/2021/01/14/elasticsearch-and-kibana-are-now-business-risks)

### ESRally testing mechanism

One of the possibility to compare those are to use [ESRally](https://github.com/elastic/rally) and run some experiments with it

ODFE
```sh
esrally --track=geonames --report-format=csv -report-file=~/benchmarks/result.csv --target-hosts=http://localhost:9200,http://localhost:9201 --pipeline=benchmark-only --client-options="use_ssl:false,basic_auth_user:'admin',basic_auth_password:'admin'"
```

ELK
```sh
esrally --track=geonames --report-format=csv -report-file=~/benchmarks/result.csv --target-hosts=http://localhost:9200,http://localhost:9201 --pipeline=benchmark-only
```

Enjoy the results or create your own test experiments.
