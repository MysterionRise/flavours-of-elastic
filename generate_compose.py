import yaml


def create_node(node_id, node_type, opensearch_version, opensearch_java_opts):
    node_config = {
        "cluster_manager": "node.roles: [ cluster_manager ]",
        "data": "node.roles: [ data ]",
        "ingest": "node.roles: [ ingest ]",
    }

    return {
        f"opensearch-{node_type}{node_id}": {
            "image": f"opensearchproject/opensearch:{opensearch_version}",
            "container_name": f"opensearch-{node_type}{node_id}",
            "environment": [
                "cluster.name=opensearch-cluster",
                f"node.name=opensearch-{node_type}{node_id}",
                "discovery.seed_hosts="
                + ",".join(
                    f"opensearch-{node_type}{i}" for i in range(1, num_nodes + 1)
                ),
                "cluster.initial_master_nodes="
                + ",".join(
                    f"opensearch-{node_type}{i}" for i in range(1, num_nodes + 1)
                ),
                "bootstrap.memory_lock=true",
                f'"OPENSEARCH_JAVA_OPTS={opensearch_java_opts[node_type]}"',
                node_config[node_type],
            ],
            "ulimits": {
                "memlock": {
                    "soft": -1,
                    "hard": -1,
                },
                "nofile": {
                    "soft": 65536,
                    "hard": 65536,
                },
            },
            "volumes": [
                f"opensearch-data-{node_type}{node_id}:/usr/share/opensearch/data"
            ],
            "ports": [f"{9200 + node_id - 1}:9200", f"{9600 + node_id - 1}:9600"],
            "networks": ["opensearch-net"],
        }
    }


num_nodes = 1  # update this to the desired number of nodes
opensearch_version = "2.7.0"  # update this to the desired version
opensearch_java_opts = {
    "cluster_manager": "-Xms1g -Xmx1g",
    "data": "-Xms2g -Xmx2g",
    "ingest": "-Xms1g -Xmx1g",
}

data = {
    "version": "3.8",
    "services": {},
    "volumes": {},
    "networks": {"opensearch-net": None},
}

node_types = ["cluster_manager", "data", "ingest"]

for node_type in node_types:
    for i in range(1, num_nodes + 1):
        data["services"].update(
            create_node(i, node_type, opensearch_version, opensearch_java_opts)
        )
        # data['volumes'][f'opensearch-data-{node_type}{i}'] = None

# only one instance of opensearch-dashboards
data["services"]["opensearch-dashboards"] = {
    "image": f"opensearchproject/opensearch-dashboards:{opensearch_version}",
    "container_name": "opensearch-dashboards",
    "ports": ["5601:5601"],
    "expose": ["5601"],
    "environment": {
        "OPENSEARCH_HOSTS": str(
            [
                "https://" + f"opensearch-{node_type}{i}:9200"
                for node_type in node_types
                for i in range(1, num_nodes + 1)
            ]
        )
    },
    "networks": ["opensearch-net"],
}

with open("docker-compose.yml", "w") as f:
    yaml.dump(data, f)
