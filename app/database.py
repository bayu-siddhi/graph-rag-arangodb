import re
import itertools
import networkx as nx
import nx_arangodb as nxadb

from arango import client
from arango import database
from app import custom_adbnx
from adbnx_adapter import adapter


class Database:

    def __init__(
        self, host: str, db_name: str, graph_name: str, username: str, password: str
    ) -> None:
        self._host = host
        self._db_name = db_name
        self._graph_name = graph_name
        self._username = username
        self._password = password
        self.db_obj = None
    
    @property
    def host(self) -> None:
        raise AttributeError()
    
    @property
    def db_name(self) -> None:
        raise AttributeError()
    
    @property
    def graph_name(self) -> None:
        raise AttributeError()
    
    @property
    def username(self) -> None:
        raise AttributeError()
    
    @property
    def password(self) -> None:
        raise AttributeError()
    
    @host.setter
    def host(self, value) -> None:
        self._host = value
    
    @db_name.setter
    def db_name(self, value) -> None:
        self._db_name = value
    
    @graph_name.setter
    def graph_name(self, value) -> None:
        self._graph_name = value
    
    @username.setter
    def username(self, value) -> None:
        self._username = value
    
    @password.setter
    def password(self, value) -> None:
        self._password = value
    

    def is_empty(
        self, dataset: dict[str, list[dict]]
    ) -> bool:
        # Connect to the ArangoDB database
        self.db_obj = self._connect_to_arangodb()

        # Check if graph exist
        if not self.db_obj.has_graph(self._graph_name):
            return True

        # Check if all collections (vertex and edge) exist in the database
        for key in dataset.keys():
            if key.startswith("node_"):
                label = re.search(r"node_(.*)", key, re.IGNORECASE)[1].lower()
                if self.db_obj.has_collection(label):
                    vertex_coll = self.db_obj.collection(label)
                    if vertex_coll.count() == 0:
                        return True
                else:
                    return True
            
            if key.startswith("edge_"):
                edge_type = re.search(r"([A-Z_]*)$", key)[1]
                edge_type = edge_type[1:].lower()
                if self.db_obj.has_collection(edge_type):
                    edge_coll = self.db_obj.collection(edge_type)
                    if edge_coll.count() == 0:
                        return True
                else:
                    return True
        
        return False
    

    def get_nxadb_graph(
        self
    ) -> nxadb.MultiDiGraph:
        # Re-connect to the same Graph using nxadb (required)
        self.db_obj = self._connect_to_arangodb()

        # Get NetworkX graph representation from ArangoDB
        return nxadb.MultiDiGraph(name=self._graph_name, db=self.db_obj)
    

    def load_dataset_to_arangodb(
        self, dataset: dict[str, list[dict]]
    ) -> None:
        # Connect to the ArangoDB database
        self.db_obj = self._connect_to_arangodb() 

        # Instantiate the custom ADBNX using the DB and custom ADBNX controller
        custom_adbnx_adapter = adapter.ADBNX_Adapter(self.db_obj, custom_adbnx.CustomADBNXController())

        # Create NetworkX graph from dataset
        G = self._create_networkx_graph(dataset=dataset)

        # Load the NetworkX Graph into new ArangoDB graph
        self.db_obj.delete_graph(self._graph_name, drop_collections=True, ignore_missing=True)
        custom_adbnx_adapter.networkx_to_arangodb(
            self._graph_name, G, custom_adbnx.edge_definitions, batch_size=128
        )

        # Get NetworkX graph representation from ArangoDB
        G_adb = self.get_nxadb_graph()
        
        # Modify some attribute in graph
        self._modify_graph(nxadb_graph=G_adb)
    

    def _connect_to_arangodb(self) -> database.StandardDatabase:
        return client.ArangoClient(hosts=self._host).db(
            name=self._db_name,
            username=self._username,
            password=self._password,
            verify=True
        ) 
    

    def _create_networkx_graph(
        self, dataset: dict[str, list[dict]]
    ) -> nx.MultiDiGraph:
        # Crate empty multi directed graph
        G = nx.MultiDiGraph()

        # Load node data into multi directed graph
        for key, data in dataset.items():
            if key.startswith("node_"):
                label = re.search(r"node_(.*)", key, re.IGNORECASE)[1].lower()
                for row in data:
                    node_id = f"{label}/{row['id']}"
                    attributes = dict(itertools.islice(row.items(), 1, None))
                    G.add_node(node_id, label=label, **attributes)
        
        # Load edge data into multi directed graph
        for key, data in dataset.items():
            if key.startswith("edge_"):
                edge_type = re.search(r"([A-Z_]*)$", key)[1]
                edge_type = edge_type[1:].lower()
                for row in data:
                    source_id = f"{row['from_type'].lower()}/{row['from']}"
                    target_id = f"{row['to_type'].lower()}/{row['to']}"
                    attributes = dict(itertools.islice(row.items(), 4, None))
                    G.add_edge(source_id, target_id, label=edge_type, **attributes)
        
        return G
    

    def _modify_graph(
        self, nxadb_graph: nxadb.MultiDiGraph
    ) -> None:
        # Set the "effective" attribute to True for all articles
        nxadb_graph.query("""
            RETURN COUNT (
                FOR node IN article
                    UPDATE node WITH { effective: true } IN article
                    RETURN NEW
            )
        """)

        # Set the "effective" attribute to False for all articles that are "amended_by"
        nxadb_graph.query("""
            RETURN COUNT(
                FOR node IN article
                    FILTER node._id IN (
                        FOR edge IN amended_by
                            RETURN edge._from
                    )
                    UPDATE node WITH { effective: false } IN article
                    RETURN NEW
            )
        """)

        # Set the "effective" attribute to True for all next_article edges
        nxadb_graph.query("""
            RETURN COUNT (
                FOR edge IN next_article
                    UPDATE edge WITH { effective: true } IN next_article
                    RETURN NEW
            )
        """)

        # Set the "effective" attribute to False for all next_article edges
        # that point to an article node with an "effective" attribute set to False
        nxadb_graph.query("""
        RETURN COUNT(
            FOR node IN article
                FILTER node.effective == false

                // Update edges dengan arah MASUK ke article yang effective-nya false
                FOR edge IN next_article
                    FILTER edge._to == node._id
                    UPDATE edge WITH { effective: false } IN next_article
                    RETURN NEW
        )
        """)

        # Set the "effective" attribute to False for all next_article edges
        # that originate from an article node with an "effective" attribute set to False
        nxadb_graph.query("""
        RETURN COUNT(
            FOR node IN article
                FILTER node.effective == false

                // Update edges dengan arah KELUAR dari article yang effective-nya false
                FOR edge IN next_article
                    FILTER edge._from == node._id
                    UPDATE edge WITH { effective: false } IN next_article
                    RETURN NEW
        )
        """)

        # For article nodes that have more than one outgoing next_article edge:
        # - Set effective = True for the next_article edge with the highest amendment_number
        # - Set effective = False for next_article edges with an amendment_number lower than the highest one
        nxadb_graph.query("""
            RETURN COUNT(
                FOR node IN article
                    LET outgoing_edges = (
                        FOR edge IN next_article
                            FILTER edge._from == node._id
                            RETURN { _id: edge._id, amendment_number: edge.amendment_number, edge: edge}
                    )

                    LET max_amendment_number = MAX(outgoing_edges[*].amendment_number)

                    FOR edge_info IN outgoing_edges
                        FILTER edge_info.amendment_number < max_amendment_number
                        UPDATE edge_info.edge WITH { effective: false } IN next_article
                        RETURN NEW
            )
        """)
