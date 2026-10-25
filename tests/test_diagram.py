import pytest

from gerald.tools.diagram import layout_diagram


def _nodes(*texts):
    return [{"id": str(index), "text": text} for index, text in enumerate(texts)]


def _box_map(layout):
    return {node.id: node for node in layout.nodes}


def test_chain_layers_advance_in_flow_and_tree_directions():
    nodes = _nodes("A", "B", "C", "D")
    edges = [{"from": str(i), "to": str(i + 1)} for i in range(3)]

    flow = _box_map(layout_diagram(title=None, layout="flow", nodes=nodes, edges=edges))
    tree = _box_map(layout_diagram(title=None, layout="tree", nodes=nodes, edges=edges))

    assert flow["0"].x < flow["1"].x < flow["2"].x < flow["3"].x
    assert tree["0"].y < tree["1"].y < tree["2"].y < tree["3"].y


def test_branching_children_share_a_layer():
    layout = layout_diagram(
        title=None,
        layout="flow",
        nodes=_nodes("Root", "First child", "Second child"),
        edges=[{"from": "0", "to": "1"}, {"from": "0", "to": "2"}],
    )
    boxes = _box_map(layout)
    assert boxes["1"].x + boxes["1"].w / 2 == boxes["2"].x + boxes["2"].w / 2


def test_tree_root_is_centered_over_three_children_and_edges_elbow():
    layout = layout_diagram(
        title=None,
        layout="tree",
        nodes=_nodes("Root", "First child", "Second child", "Third child"),
        edges=[
            {"from": "0", "to": "1"},
            {"from": "0", "to": "2"},
            {"from": "0", "to": "3"},
        ],
    )
    boxes = _box_map(layout)
    child_centers = [boxes[str(index)].x + boxes[str(index)].w / 2 for index in (1, 2, 3)]
    root_center = boxes["0"].x + boxes["0"].w / 2

    assert abs(root_center - sum(child_centers) / len(child_centers)) <= 1
    assert all(len(edge.points) == 4 for edge in layout.edges)
    for edge in layout.edges:
        assert edge.points[0][0] == edge.points[1][0]
        assert edge.points[1][1] == edge.points[2][1]
        assert edge.points[2][0] == edge.points[3][0]


def test_node_wraps_only_at_spaces_and_keeps_minimum_width():
    layout = layout_diagram(
        title=None,
        layout="flow",
        nodes=[
            {"id": "a", "text": "Membrane transport consumes energy"},
            {"id": "b", "text": "A"},
        ],
    )
    boxes = _box_map(layout)

    assert boxes["a"].lines == ("Membrane transport", "consumes energy")
    assert boxes["a"].w >= 84
    assert boxes["b"].w == 84


def test_directed_cycle_terminates_and_keeps_three_nodes():
    layout = layout_diagram(
        title=None,
        layout="flow",
        nodes=_nodes("A", "B", "C"),
        edges=[{"from": "0", "to": "1"}, {"from": "1", "to": "2"}, {"from": "2", "to": "0"}],
    )
    assert len(layout.nodes) == 3
    assert len(layout.edges) == 2


@pytest.mark.parametrize(
    ("nodes", "edges", "message"),
    [
        ([{"id": "a", "text": "one"}, {"id": "a", "text": "two"}], [], "duplicate"),
        (_nodes("one", "two"), [{"from": "missing", "to": "0"}], "unknown"),
        (_nodes(*["word"] * 13), [], "between 2 and 12"),
        ([{"id": "a", "text": ""}, {"id": "b", "text": "two"}], [], "non-empty"),
    ],
)
def test_layout_validation_rejects_invalid_graphs(nodes, edges, message):
    with pytest.raises(ValueError, match=message):
        layout_diagram(title=None, layout="flow", nodes=nodes, edges=edges)


def test_layout_title_and_edges_are_optional():
    layout = layout_diagram(layout="flow", nodes=_nodes("A", "B"))
    assert layout.title is None
    assert layout.edges == []
    with pytest.raises(ValueError, match="layout must"):
        layout_diagram(layout=[], nodes=_nodes("A", "B"))


def test_cycle_nodes_are_spaced_around_an_ellipse():
    layout = layout_diagram(title="Cycle", layout="cycle", nodes=_nodes("A", "B", "C", "D"), edges=[])
    centers = [(node.x + node.w / 2, node.y + node.h / 2) for node in layout.nodes]
    assert len(set(centers)) == 4
    assert all(0 < x < layout.width and 0 < y < layout.height for x, y in centers)


@pytest.mark.parametrize("kind", ["flow", "tree", "cycle"])
def test_layout_boxes_do_not_overlap(kind):
    nodes = _nodes("Glucose", "Lumière solaire", "Chlorophylle", "Eau et CO2", "Oxygène")
    edges = [{"from": "1", "to": "2"}, {"from": "2", "to": "0"}, {"from": "0", "to": "4"}, {"from": "3", "to": "0"}]
    layout = layout_diagram(title="Photosynthèse", layout=kind, nodes=nodes, edges=edges)
    for index, first in enumerate(layout.nodes):
        for second in layout.nodes[index + 1 :]:
            assert (
                first.x + first.w <= second.x
                or second.x + second.w <= first.x
                or first.y + first.h <= second.y
                or second.y + second.h <= first.y
            )
