from typing import Dict
from typing import List
from adbnx_adapter import typings
from adbnx_adapter import controller


# Specify list of ArangoDB edge definitions
edge_definitions = [
    {
        "edge_collection": "amended_by",
        "from_vertex_collections": ["regulation", "article"],
        "to_vertex_collections": ["regulation", "article"],
    },
    {
        "edge_collection": "has_consideration",
        "from_vertex_collections": ["regulation"],
        "to_vertex_collections": ["consideration"],
    },
    {
        "edge_collection": "has_observation",
        "from_vertex_collections": ["regulation"],
        "to_vertex_collections": ["observation"],
    },
    {
        "edge_collection": "has_definition",
        "from_vertex_collections": ["regulation"],
        "to_vertex_collections": ["definition"],
    },
    {
        "edge_collection": "has_article",
        "from_vertex_collections": ["regulation"],
        "to_vertex_collections": ["article"],
    },
    {
        "edge_collection": "next_article",
        "from_vertex_collections": ["article"],
        "to_vertex_collections": ["article"],
    },
    {
        "edge_collection": "refer_to",
        "from_vertex_collections": ["article"],
        "to_vertex_collections": ["article"],
    }
]


# Create custom ADBNX Controller to handle node and edge transition from NetworkX to ArangoDB
# Reference: https://github.com/arangoml/networkx-adapter/blob/master/examples/outputs/ArangoDB_NetworkX_Adapter_output.ipynb
class CustomADBNXController(controller.ADBNX_Controller):
    """ArangoDB-NetworkX controller.

    Responsible for controlling how nodes & edges are handled when
    transitioning from ArangoDB to NetworkX, and vice-versa.
    """

    def _identify_networkx_node(
        self, nx_node_id: typings.NxId, nx_node: typings.NxData, adb_v_cols: List[str]
    ) -> str:
        """Given a NetworkX node, and a list of ArangoDB vertex collections defined,
        identify which ArangoDB vertex collection **nx_node** should belong to.

        NOTE: You must override this function if len(**adb_v_cols**) > 1.

        :param nx_node_id: The NetworkX ID of the node.
        :type nx_node_id: adbnx_adapter.typings.NxId
        :param nx_node: The NetworkX node object.
        :type nx_node: adbnx_adapter.typings.NxData
        :param adb_v_cols: All ArangoDB vertex collections specified
            by the **edge_definitions** parameter of networkx_to_arangodb()
        :type adb_v_cols: List[str]
        :return: The ArangoDB collection name
        :rtype: str
        """
        return str(nx_node_id).split("/")[0]  # Identify node based on '/' split


    def _identify_networkx_edge(
        self,
        nx_edge: typings.NxData,
        from_node_id: typings.NxId,
        to_node_id: typings.NxId,
        nx_map: Dict[typings.NxId, str],
        adb_e_cols: List[str],
    ) -> str:
        """Given a NetworkX edge, its pair of nodes, and a list of ArangoDB
        edge collections defined, identify which ArangoDB edge collection **nx_edge**
        should belong to.

        NOTE #1: You must override this function if len(**adb_e_cols**) > 1.

        :param nx_edge: The NetworkX edge object.
        :type nx_edge: adbnx_adapter.typings.NxData
        :param from_node_id: The NetworkX ID of the node representing the edge source.
        :type from_node_id: adbnx_adapter.typings.NxId
        :param to_node_id: The NetworkX ID of the node representing the edge destination.
        :type to_node_id: adbnx_adapter.typings.NxId
        :param nx_map: A mapping of NetworkX node ids to ArangoDB vertex ids. You
            can use this to derive the ArangoDB _from and _to values of the edge.
            i.e, `nx_map[from_node_id]` will give you the ArangoDB _from value,
            and `nx_map[to_node_id]` will give you the ArangoDB _to value.
        :type nx_map: Dict[NxId, str]
        :param adb_e_cols: All ArangoDB edge collections specified
            by the **edge_definitions** parameter of
            ADBNX_Adapter.networkx_to_arangodb()
        :type adb_e_cols: List[str]
        :return: The ArangoDB collection name
        :rtype: str
        """
        return nx_edge["label"]  # Identify edge based on "type" attribute
    

    def _keyify_networkx_node(
        self, i: int, nx_node_id: typings.NxId, nx_node: typings.NxData, col: str
    ) -> str:
        """Given a NetworkX node, derive its ArangoDB key.

        NOTE #1: You must override this function if you want to create custom ArangoDB
        _key values for your NetworkX nodes.

        NOTE #2: You are free to use `_string_to_arangodb_key_helper()` and
        `_tuple_to_arangodb_key_helper()` to derive a valid ArangoDB _key value.

        :param i: The index of the NetworkX node in the list of nodes.
        :type i: int
        :param nx_node_id: The NetworkX node id.
        :type nx_node_id: adbnx_adapter.typings.NxId
        :param nx_node: The NetworkX node object.
        :type nx_node: adbnx_adapter.typings.NxData
        :param col: The ArangoDB collection that **nx_node** belongs to.
        :type col: str
        :return: A valid ArangoDB _key value.
        :rtype: str
        """
        return str(nx_node_id).split("/")[1] # Keyify node based on '/' split