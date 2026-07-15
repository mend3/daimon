import os

import pytest

from daimon_flow.model import Edge, Node, PortKind, Workflow
from daimon_flow.executor import execute
from daimon_flow.spec import Services
from daimon_flow.registry import catalog


def test_catalog_has_core_nodes():
    types = {nt.type for nt in catalog()}
    assert {"trigger.manual", "agent.daimon", "logic.if", "output.return"} <= types
    agent = next(nt for nt in catalog() if nt.type == "agent.daimon")
    assert {s.name for s in agent.resource_slots} == {"model", "knowledge", "tools"}
    # output schema is what downstream nodes offer as variables
    assert {f.key for f in agent.output_fields} == {"text", "citations"}


def test_interpolate_helper():
    from daimon_flow.executor import _interpolate
    cfg = {"value": "{{ input.text }}", "url": "{{ n1.link }}/x", "plain": "no vars"}
    out = _interpolate(cfg, {"text": "hello"}, {"n1": {"link": "http://a"}})
    assert out == {"value": "hello", "url": "http://a/x", "plain": "no vars"}


def test_interpolate_nested_paths():
    from daimon_flow.executor import _interpolate
    out = _interpolate({"to": "{{ tg.from.id }}", "cap": "{{ tg.media.url }}"}, {},
                       {"tg": {"from": {"id": 42}, "media": {"url": "http://m/x.jpg"}}})
    assert out == {"to": "42", "cap": "http://m/x.jpg"}


def test_interpolate_array_index():
    from daimon_flow.executor import _interpolate
    outputs = {"a": {"citations": [{"title": "First"}, {"title": "Second"}], "tags": ["x", "y"]}}
    out = _interpolate({"t": "{{ a.citations[1].title }}", "g": "{{ a.tags[0] }}",
                        "miss": "{{ a.citations[9].title }}"}, {}, outputs)
    assert out == {"t": "Second", "g": "x", "miss": ""}


def test_telegram_trigger_nested_schema():
    tg = next(nt for nt in catalog() if nt.type == "trigger.telegram")
    frm = next(f for f in tg.output_fields if f.key == "from")
    assert frm.type == "object" and {c.key for c in frm.fields} == {"id", "username", "name"}


def test_config_interpolation_in_flow():
    # IF compares the input against a value pulled from the input via {{ }}.
    wf = Workflow(
        id="wfi",
        nodes=[
            Node(id="t", type="trigger.manual"),
            Node(id="iff", type="logic.if", config={"operator": "equals", "value": "{{ input.text }}"}),
            Node(id="yes", type="output.return"),
            Node(id="no", type="output.return"),
        ],
        edges=[
            Edge(id="e1", source="t", source_port="out", target="iff", target_port="in"),
            Edge(id="e2", source="iff", source_port="true", target="yes", target_port="in"),
            Edge(id="e3", source="iff", source_port="false", target="no", target_port="in"),
        ],
    )
    ex = execute(wf, trigger_payload={"text": "match"}, services=Services())
    assert ex.runs["yes"].state.value == "success"   # value resolved to "match" == input


def test_executor_branching_no_llm():
    wf = Workflow(
        id="wf1", name="branch",
        nodes=[
            Node(id="t", type="trigger.manual"),
            Node(id="iff", type="logic.if", config={"operator": "contains", "value": "urgent"}),
            Node(id="yes", type="output.return"),
            Node(id="no", type="output.return"),
        ],
        edges=[
            Edge(id="e1", source="t", source_port="out", target="iff", target_port="in"),
            Edge(id="e2", source="iff", source_port="true", target="yes", target_port="in"),
            Edge(id="e3", source="iff", source_port="false", target="no", target_port="in"),
        ],
    )
    ex = execute(wf, trigger_payload={"text": "this is urgent please act"},
                 services=Services())
    assert ex.status == "success"
    assert ex.runs["yes"].state.value == "success"
    assert ex.runs["no"].state.value == "idle"  # false branch not taken


@pytest.mark.skipif(os.environ.get("DAIMON_KB_IT") != "1", reason="needs live Ollama")
def test_agent_flow_live():
    wf = Workflow(
        id="wf2", name="agent",
        nodes=[
            Node(id="t", type="trigger.manual"),
            Node(id="a", type="agent.daimon", config={"instruction": "Reply with one short sentence."}),
            Node(id="r", type="output.return"),
        ],
        edges=[
            Edge(id="e1", source="t", source_port="out", target="a", target_port="in"),
            Edge(id="e2", source="a", source_port="out", target="r", target_port="in"),
        ],
    )
    ex = execute(wf, trigger_payload={"text": "Say hello in Portuguese."})
    assert ex.status == "success"
    assert ex.runs["a"].output["out"]["text"].strip()
