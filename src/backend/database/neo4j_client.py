from neo4j import GraphDatabase

class Neo4jClient:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def run_query(self, query, parameters=None):
        with self.driver.session() as session:
            result = session.run(query, parameters or {})
            return [record for record in result]

    def create_node(self, label, properties):
        query = f"CREATE (n:{label} $properties) RETURN n"
        return self.run_query(query, {"properties": properties})

    def find_node(self, label, properties):
        query = f"MATCH (n:{label} $properties) RETURN n"
        return self.run_query(query, {"properties": properties})

    def delete_node(self, label, properties):
        query = f"MATCH (n:{label} $properties) DELETE n"
        return self.run_query(query, {"properties": properties})