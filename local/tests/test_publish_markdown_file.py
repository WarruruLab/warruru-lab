"""`MarkdownFileTarget` — 초안이 저장소 바깥에 앉는다."""

import pytest

from warruru_local.publish.markdown_file import (
    MarkdownFileTarget,
    RepositoryPathError,
)


def _target(tmp_path, repo_root=None):
    return MarkdownFileTarget(tmp_path / "drafts", repo_root=repo_root)


def test_초안은_저장소_바깥_경로에_쓰인다(tmp_path):
    result = _target(tmp_path).publish(
        title="connection pool", markdown="# 본문\n",
        date="2026-08-24", slug="connection-pool",
    )
    assert result.path.endswith("2026-08-24-connection-pool.md")
    assert "drafts" in result.path


def test_파일이_연월_디렉터리로_나뉜다(tmp_path):
    """한 디렉터리에 파일이 수백 개 쌓이는 것을 막는다."""
    path = _target(tmp_path).path_for("2026-08-24", "connection-pool")
    assert path.parent.name == "08"
    assert path.parent.parent.name == "2026"


def test_저장소_안_경로를_주면_예외를_던진다(tmp_path):
    """경고가 아니라 예외다. 경고는 로그에 묻히고,
    묻히면 다음 `git add -A` 에서 사고가 난다.
    """
    repo = tmp_path / "repo"
    (repo / "blog").mkdir(parents=True)
    with pytest.raises(RepositoryPathError):
        MarkdownFileTarget(repo / "blog" / "drafts", repo_root=repo)


def test_저장소_자체를_주어도_예외다(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(RepositoryPathError):
        MarkdownFileTarget(repo, repo_root=repo)


def test_저장소_밖이면_통과한다(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    target = MarkdownFileTarget(tmp_path / "drafts", repo_root=repo)
    assert target.publish(title="t", markdown="본문",
                          date="2026-08-24", slug="s").path


def test_front_matter_에_topic_과_status_가_들어간다(tmp_path):
    """파일만 열어도 무엇으로 조립됐는지 읽혀야 한다."""
    result = _target(tmp_path).publish(
        title="connection pool", markdown="# 본문\n",
        date="2026-08-24", slug="connection-pool",
        topic="  Connection Pool  ", kinds=["EXPERIMENT", "EXPERIMENT"],
        source_record_ids=["rec_A", "rec_B"], status="DRAFT",
    )
    text = open(result.path, encoding="utf-8").read()
    assert text.startswith("---\n")
    assert "Connection Pool" in text
    assert '["EXPERIMENT"]' in text          # 중복은 접힌다
    assert "rec_A" in text and "rec_B" in text
    assert "status: DRAFT" in text
    assert "# 본문" in text


def test_기본_공개_범위는_비공개다(tmp_path):
    """실수로 공개되는 사고를 막는다. 공개는 명시해야만 된다."""
    import inspect

    from warruru_local.publish.base import PublishTarget

    signature = inspect.signature(PublishTarget.publish)
    assert signature.parameters["visibility"].default == "private"


def test_슬러그에_경로_문자가_있어도_밖으로_못_나간다(tmp_path):
    """지키는 것은 '루트 밖으로 못 나간다' 이다.

    슬러그는 이미 정규화돼 있지만 그 보장은 이 모듈 밖에 있다.
    """
    root = (tmp_path / "drafts").resolve()
    path = _target(tmp_path).path_for("2026-08-24", "../../etc/passwd").resolve()
    assert root in path.parents
    assert ".." not in path.name


def test_한글_슬러그도_파일명이_된다(tmp_path):
    path = _target(tmp_path).path_for("2026-08-24", "커넥션-풀")
    assert "커넥션-풀" in path.name
