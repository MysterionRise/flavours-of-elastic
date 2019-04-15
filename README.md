# Example of OpenDistro Elastic cluster 

Docker compose example and configurations for fully featured [Amazon Opendistro Elastic](https://opendistro.github.io/for-elasticsearch/) cluster with 2 nodes of Elastic + 1 node of Kibana

## How To

You would need to install [Docker](https://docs.docker.com/install/) and [Docker Compose](https://docs.docker.com/compose/install/)

### Start cluster 

```
docker-compose up
```

After some time you will have Kibana available at this [URL](http://localhost:5601/app/kibana#/discover)

### Stop cluster

```
docker-compose down
```
