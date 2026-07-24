import subprocess

import pytest

from warruru_local.gitinfo import GitCollector, GitSnapshot


def _run(cwd, *args):
    subprocess.run(
        ["git", *args], cwd=cwd, check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


@pytest.fixture
def git_repo(tmp_path):
    root = tmp_path / "sample-repo"
    root.mkdir()
    _run(root, "init", "-b", "main")
    _run(root, "config", "user.email", "test@example.com")
    _run(root, "config", "user.name", "Test")
    (root / "a.txt").write_text("hello", encoding="utf-8")
    _run(root, "add", "a.txt")
    _run(root, "commit", "-m", "first")
    return root


def test_저장소가_아니면_빈_스냅샷이다(tmp_path):
    snapshot = GitCollector().collect(str(tmp_path))
    assert snapshot.available is False
    assert snapshot.as_dict() is None


def test_경로가_None_이면_빈_스냅샷이다():
    assert GitCollector().collect(None).available is False


def test_없는_경로면_빈_스냅샷이다(tmp_path):
    assert GitCollector().collect(str(tmp_path / "없음")).available is False


def test_저장소면_브랜치와_커밋을_읽는다(git_repo):
    snapshot = GitCollector().collect(str(git_repo))
    assert snapshot.available is True
    assert snapshot.repo_name == "sample-repo"
    assert snapshot.branch == "main"
    assert len(snapshot.commit_sha) == 40
    assert snapshot.dirty is False
    assert snapshot.dirty_file_count == 0


def test_미커밋_변경이_있으면_dirty_다(git_repo):
    (git_repo / "b.txt").write_text("new", encoding="utf-8")
    snapshot = GitCollector().collect(str(git_repo))
    assert snapshot.dirty is True
    assert snapshot.dirty_file_count == 1


def test_변경_파일_수는_상한까지만_센다(git_repo):
    for index in range(5):
        (git_repo / f"f{index}.txt").write_text("x", encoding="utf-8")
    snapshot = GitCollector(dirty_file_cap=3).collect(str(git_repo))
    assert snapshot.dirty_file_count == 3
    assert snapshot.dirty_count_capped is True


def test_하위_디렉터리에서도_최상위를_찾는다(git_repo):
    nested = git_repo / "src" / "deep"
    nested.mkdir(parents=True)
    snapshot = GitCollector().collect(str(nested))
    assert snapshot.repo_name == "sample-repo"


class _ManualClock:
    """FixedClock.advance() 와 같은 정신으로, 소진되지 않는 monotonic 대역이다."""

    def __init__(self, start: float = 0.0, step: float = 0.01) -> None:
        self._value = start
        self._step = step

    def __call__(self) -> float:
        value = self._value
        self._value += self._step
        return value

    def jump(self, amount: float) -> None:
        self._value += amount


def test_같은_경로는_캐시_동안_다시_읽지_않는다(git_repo):
    clock = _ManualClock()
    collector = GitCollector(cache_ttl_seconds=5.0, monotonic=clock)
    first = collector.collect(str(git_repo))
    (git_repo / "b.txt").write_text("new", encoding="utf-8")
    second = collector.collect(str(git_repo))
    assert second.dirty == first.dirty is False


def test_캐시가_만료되면_다시_읽는다(git_repo):
    clock = _ManualClock()
    collector = GitCollector(cache_ttl_seconds=5.0, monotonic=clock)
    collector.collect(str(git_repo))
    clock.jump(99.0)
    (git_repo / "b.txt").write_text("new", encoding="utf-8")
    assert collector.collect(str(git_repo)).dirty is True


def test_앞선_호출이_예산을_다_쓰면_뒤의_호출은_건너뛴다(git_repo):
    """공유 예산이 실제로 줄어드는지 검증한다.

    monotonic 이 toplevel 호출 이후로 타임아웃을 넘겨버리면, branch·commit·
    status 호출은 각각 새 타임아웃을 받는 대신 건너뛰어야 한다.
    """
    ticks = iter([0.0, 0.0, 2.5, 2.5, 2.5])
    collector = GitCollector(timeout_seconds=2.0, monotonic=lambda: next(ticks))
    snapshot = collector.collect(str(git_repo))
    assert snapshot.available is True
    assert snapshot.branch is None
    assert snapshot.commit_sha is None
    assert snapshot.dirty is None


def test_빈_스냅샷의_as_dict_는_None_이다():
    assert GitSnapshot.EMPTY.as_dict() is None


def test_스냅샷의_as_dict_는_API_필드_이름을_쓴다(git_repo):
    payload = GitCollector().collect(str(git_repo)).as_dict()
    assert set(payload) == {
        "repo_path", "repo_name", "branch", "commit", "dirty", "dirty_file_count",
    }
