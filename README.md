# Repo with collection of different OpenDistro Elastic usage

## Example of OpenDistro Elastic cluster  

Docker compose example and configurations for fully featured [Amazon Opendistro Elastic](https://opendistro.github.io/for-elasticsearch/) cluster with 2 nodes of Elastic + 1 node of Kibana

Open distro version - **1.4.0**

Elastic version - **7.4.2**

## How To

You would need to install [Docker](https://docs.docker.com/install/) and [Docker Compose](https://docs.docker.com/compose/install/)

### Build Docker image

```
docker build --tag=odfe:0.2 --file=ODFEDockerfile .
```

or use the tag and version of your choice

### Update docker-compose.yml

Update `docker-compose.yml` with proper image for Elasticsearch (tag and version accordingly)

```
...
image: odfe:0.2
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

## Comparison with Elastic version

### Build both images

```
docker build --tag=elk:0.2 --file=ELKDockerfile .
```
and
```
docker build --tag=odfe:0.2 --file=ODFEDockerfile .
```

Don't forget to select your image name and version. 
Don't forget to update docker-compose with relevant names and versions


### ESRally testing mechanism

One of the possibility to compare those is to use [ESRally](https://github.com/elastic/rally) and run some experiments with it

ODFE
```
esrally --track=geonames --report-format=csv -report-file=~/benchmarks/result.csv --target-hosts=http://localhost:9200,http://localhost:9201 --pipeline=benchmark-only --client-options="use_ssl:false,basic_auth_user:'admin',basic_auth_password:'admin'"
```

ELK
```
esrally --track=geonames --report-format=csv -report-file=~/benchmarks/result.csv --target-hosts=http://localhost:9200,http://localhost:9201 --pipeline=benchmark-only
```

Enjoy the results or create your own test experiments
