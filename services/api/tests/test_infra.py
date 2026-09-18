"""The SAM template keeps the security and contract rules the code relies on (SECURITY T4, ADR-011)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

TEMPLATE = Path(__file__).resolve().parents[3] / "infra" / "template.yaml"
ROUTES_IN_CODE = Path(__file__).resolve().parents[1] / "src" / "crownx" / "app" / "api.py"


class _CfnLoader(yaml.SafeLoader):
    """Reads CloudFormation short-form tags (!Ref, !Sub, !GetAtt ...) as plain values."""


def _tag(loader: yaml.SafeLoader, _suffix: str, node: yaml.Node) -> object:
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    return loader.construct_mapping(node, deep=True)


_CfnLoader.add_multi_constructor("!", _tag)


@pytest.fixture(scope="module")
def template() -> dict:
    return yaml.load(TEMPLATE.read_text(encoding="utf-8"), Loader=_CfnLoader)


def _allow_statements(template: dict):
    for name, resource in template["Resources"].items():
        properties = resource.get("Properties", {})
        documents = [p["PolicyDocument"] for p in properties.get("Policies", [])]
        if "AccessPolicies" in properties:
            documents.append(properties["AccessPolicies"])
        for document in documents:
            for statement in document["Statement"]:
                for branch in _branches(statement):
                    if branch["Effect"] == "Allow":
                        yield name, branch


def _branches(statement: object) -> list[dict]:
    """A plain statement, or both branches of `!If [condition, then, else]` minus AWS::NoValue."""
    if isinstance(statement, list):  # the loader reads `!If` as [condition, then, else]
        _, *choices = statement
        return [c for c in choices if isinstance(c, dict)]
    return [statement]  # type: ignore[list-item]


def test_the_answer_model_permission_exists_only_when_a_model_is_configured(template):
    assert "AnswerModelId" in str(template["Conditions"]["HasAnswerModel"])
    [policy] = template["Resources"]["ApiRole"]["Properties"]["Policies"]
    conditional = [s for s in policy["PolicyDocument"]["Statement"] if isinstance(s, list)]
    assert [c[0] for c in conditional] == ["HasAnswerModel"]
    statements = {
        (name, statement.get("Sid")): statement for name, statement in _allow_statements(template)
    }
    answer = statements[("ApiRole", "AnswerQuestions")]
    assert answer["Action"] == "bedrock:InvokeModel"
    assert answer["Resource"].endswith("foundation-model/${AnswerModelId}")
    assert ("IngestRole", "AnswerQuestions") not in statements


def _as_list(value: object) -> list:
    return value if isinstance(value, list) else [value]


def test_no_wildcard_actions_or_bare_wildcard_resources_in_allow_statements(template):
    statements = list(_allow_statements(template))
    assert len(statements) >= 10
    for name, statement in statements:
        for action in _as_list(statement["Action"]):
            assert "*" not in action, f"{name}: wildcard action {action}"
        for resource in _as_list(statement.get("Resource", [])):
            assert resource != "*", f"{name}: bare * resource"


def test_lambda_roles_carry_no_managed_policies(template):
    for name in ("ApiRole", "IngestRole"):
        assert "ManagedPolicyArns" not in template["Resources"][name]["Properties"]


def test_only_the_ingest_role_can_write_the_index(template):
    statements = {
        (name, statement.get("Sid")): statement for name, statement in _allow_statements(template)
    }
    api_index = statements[("ApiRole", "ReadIndex")]
    ingest_index = statements[("IngestRole", "WriteIndex")]
    assert "es:ESHttpPut" not in api_index["Action"]
    assert "es:ESHttpPut" in ingest_index["Action"]


def test_bucket_blocks_public_access_and_expires_objects(template):
    bucket = template["Resources"]["DocumentsBucket"]["Properties"]
    assert all(bucket["PublicAccessBlockConfiguration"].values())
    assert bucket["LifecycleConfiguration"]["Rules"][0]["ExpirationInDays"] == 30


def test_search_domain_is_the_adr_011_shape(template):
    domain = template["Resources"]["SearchDomain"]["Properties"]
    assert domain["ClusterConfig"]["InstanceCount"] == 1
    assert domain["EBSOptions"] == {"EBSEnabled": True, "VolumeType": "gp3", "VolumeSize": 10}
    assert domain["EncryptionAtRestOptions"]["Enabled"] is True
    assert domain["DomainEndpointOptions"]["EnforceHTTPS"] is True
    assert template["Parameters"]["SearchInstanceType"]["Default"] == "m7g.medium.search"


def test_log_groups_keep_fourteen_days(template):
    groups = [r for r in template["Resources"].values() if r["Type"] == "AWS::Logs::LogGroup"]
    assert len(groups) == 3
    assert {g["Properties"]["RetentionInDays"] for g in groups} == {14}


def test_every_api_route_in_code_is_wired_in_the_template(template):
    in_code = {
        (method.upper(), re.sub(r"<(\w+)>", r"{\1}", path))
        for method, path in re.findall(r'@app\.(get|post)\("([^"]+)"\)', ROUTES_IN_CODE.read_text())
    }
    events = template["Resources"]["ApiFunction"]["Properties"]["Events"].values()
    in_template = {(e["Properties"]["Method"], e["Properties"]["Path"]) for e in events}
    assert in_code == in_template
