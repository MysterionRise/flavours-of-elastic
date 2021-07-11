# Repo with collection of different OpenDistro Elastic usage

## Example of OpenDistro Elastic cluster  

Docker compose example and configurations for fully featured [Amazon Opendistro Elastic](https://opendistro.github.io/for-elasticsearch/) cluster with 2 nodes of Elastic + 1 node of Kibana
Additionally, both Elastic instances are having custom plugin installed


### Versions (.env file)
- Open distro: **1.12.0**
- Elastic: **7.10.0**


## How To

You would need to install [Docker](https://docs.docker.com/install/) and [Docker Compose](https://docs.docker.com/compose/install/)

### Start cluster 

```sh
# ELK
docker-compose -f docker/elk/docker-compose.yml --env-file .env up

# ODFE
docker-compose -f docker/odfe/docker-compose.yml --env-file .env up
```

After some time you will have Kibana available at this [URL](http://localhost:5601/app/kibana#/discover)

## Comparison with Elastic version

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
