ARG ELK_OSS_VERSION

FROM docker.elastic.co/elasticsearch/elasticsearch-oss:$ELK_OSS_VERSION
ARG ELK_OSS_VERSION

# Adding custom plugin here, remove if you're not needed
# Replace it with the plugins of your choice
RUN /usr/share/elasticsearch/bin/elasticsearch-plugin install --batch https://github.com/spinscale/elasticsearch-ingest-opennlp/releases/download/$ELK_VERSION.1/ingest-opennlp-$ELK_VERSION.1.zip
