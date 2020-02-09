# Example of OpenDistro Elastic cluster 

Docker compose example and configurations for fully featured [Amazon Opendistro Elastic](https://opendistro.github.io/for-elasticsearch/) cluster with 2 nodes of Elastic + 1 node of Kibana

Open distro version - **1.3**

Elastic version - **7.3.2**

## How To

You would need to install [Docker](https://docs.docker.com/install/) and [Docker Compose](https://docs.docker.com/compose/install/)

### Build Docker image (to support custom plugins)

```
docker build --tag=odfe-custom-plugin:0.1 .
```

### Update docker-compose.yml

Update `docker-compose.yml` with proper image for Elasticsearch

```
...
image: odfe-custom-plugin:0.1
...
```


### Start cluster 

```
docker-compose up
```

After some time you will have Kibana available at this [URL](http://localhost:5601/app/kibana#/discover)

### Stop cluster

```
docker-compose down
```


## Comparison results of esrally tracks

### Build both images
```
docker build --tag=elk:0.2 --file=ELKDockerfile .
```
and
```
docker build --tag=odfe:0.2 --file=ODFEDockerfile .
```

### Update docker-compose files with relevant image version

### Start clusters

ODFE
```
docker-compose -f odfe-docker-compose.yml up
```

ELK
```
docker-compose -f elk-docker-compose.yml up
```

### Start ESRally track

ODFE
```
esrally --track=geonames --report-format=csv -report-file=~/benchmarks/result.csv --target-hosts=http://localhost:9200,http://localhost:9201 --pipeline=benchmark-only --client-options="use_ssl:false,basic_auth_user:'admin',basic_auth_password:'admin'"
```

ELK
```
esrally --track=geonames --report-format=csv -report-file=~/benchmarks/result.csv --target-hosts=http://localhost:9200,http://localhost:9201 --pipeline=benchmark-only
```
### Enjoy the results
