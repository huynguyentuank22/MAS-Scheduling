"""Tests for the Blackboard artifact store."""

from olm_mas.blackboard import Blackboard
from olm_mas.schemas import ArtifactStatus


def test_write_and_read():
    bb = Blackboard()
    art = bb.write(
        workflow_id="wf-1",
        artifact_type="evidence",
        content={"finding": "A"},
        created_by="researcher",
    )
    assert art.artifact_id
    assert art.version == 1
    assert bb.read(art.artifact_id) is art


def test_version_increment():
    bb = Blackboard()
    art1 = bb.write(
        workflow_id="wf-1",
        artifact_type="draft",
        content="v1",
        created_by="writer",
        artifact_id="fixed-id",
    )
    assert art1.version == 1

    art2 = bb.write(
        workflow_id="wf-1",
        artifact_type="draft",
        content="v2",
        created_by="writer",
        artifact_id="fixed-id",
    )
    assert art2.version == 2


def test_list_artifacts():
    bb = Blackboard()
    bb.write("wf-1", "evidence", "e1", "researcher")
    bb.write("wf-1", "draft", "d1", "writer")
    bb.write("wf-2", "evidence", "e2", "researcher")

    assert len(bb.list_artifacts(workflow_id="wf-1")) == 2
    assert len(bb.list_artifacts(artifact_type="evidence")) == 2
    assert len(bb.list_artifacts(workflow_id="wf-2", artifact_type="draft")) == 0


def test_finalize():
    bb = Blackboard()
    art = bb.write("wf-1", "draft", "content", "writer")
    assert art.status == ArtifactStatus.DRAFT
    finalized = bb.finalize(art.artifact_id)
    assert finalized is not None
    assert finalized.status == ArtifactStatus.FINAL


def test_read_nonexistent():
    bb = Blackboard()
    assert bb.read("nonexistent") is None


def test_clear():
    bb = Blackboard()
    bb.write("wf-1", "evidence", "e", "r")
    bb.clear()
    assert len(bb.list_artifacts()) == 0
