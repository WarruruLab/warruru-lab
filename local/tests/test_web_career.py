"""포트폴리오 화면. 파일 하나를 읽어 보여주는 것이 전부다.

DB 도 노션도 보지 않는다. 그래서 여기서 붙잡을 것은 두 가지다 —
빈 상태가 '고장' 이 아니라 '다음에 할 일' 로 읽히는지, 그리고
파일 이름이 URL 이 되는 자리에서 **경로 탈출이 막히는지**.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from warruru_local import paths
from warruru_local.clock import FixedClock, local_date_of
from warruru_local.config import load_settings
from warruru_local.daemon import careerview
from warruru_local.daemon.app import create_app

START = datetime(2026, 7, 22, 8, 0, 0, tzinfo=timezone.utc)
TODAY = local_date_of("2026-07-22T08:00:00.000Z")

NOTE = """# 현대오토에버 — 엔터프라이즈IT

## 4. 빈 곳
- `db-index` 0건
"""


@pytest.fixture
def client(home):
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as made:
        made.headers.update({"X-Warruru-Token": settings.token})
        yield made


@pytest.fixture
def ctx(client):
    return client.app.state.ctx


def _write(home, name: str, text: str = NOTE):
    root = paths.career_dir(home)
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(text, encoding="utf-8")


def test_디렉터리가_없어도_열리고_할_일을_알려준다(client, home):
    """9월 전까지는 이게 기본 상태다. 500 이 나면 안 된다."""
    assert not paths.career_dir(home).exists()
    page = client.get("/career/companies").text
    assert "회사 노트 0곳" in page
    assert "career-prep" in page


def test_회사_노트가_목록에_선다(client, home):
    _write(home, "hyundai-autoever.md")
    page = client.get("/career/companies").text
    assert "현대오토에버 — 엔터프라이즈IT" in page
    assert 'href="/career/c/hyundai-autoever"' in page


def test_상세가_마크다운을_렌더한다(client, home):
    _write(home, "hyundai-autoever.md")
    page = client.get("/career/c/hyundai-autoever").text
    assert "<h2>4. 빈 곳</h2>" in page
    assert "db-index" in page


def test_없는_회사는_404(client):
    assert client.get("/career/c/samsung-sds").status_code == 404


@pytest.mark.parametrize(
    "slug",
    [
        "../secret",
        "../../etc/passwd",
        "..%2f..%2fetc%2fpasswd",
        "/etc/passwd",
        "hyundai autoever",
        "",
        "-leading-dash",
        "UPPER",
        "a" * 65,
    ],
)
def test_경로_탈출과_이상한_이름을_거부한다(ctx, home, slug):
    """파일 이름이 그대로 URL 이 되는 자리다. 느슨하면 홈 밖을 읽는다."""
    _write(home, "hyundai-autoever.md")
    assert careerview.build_company(ctx, slug) is None


def test_심볼릭_링크로_밖을_가리켜도_안_읽는다(ctx, home, tmp_path):
    outside = tmp_path / "밖에있는비밀.md"
    outside.write_text("# 비밀", encoding="utf-8")
    root = paths.career_dir(home)
    root.mkdir(parents=True, exist_ok=True)
    (root / "leak.md").symlink_to(outside)
    assert careerview.build_company(ctx, "leak") is None


def test_규칙_밖_파일은_보이되_링크가_없다(client, home):
    """눌러서 404 가 뜨는 것보다 왜 못 여는지가 보여야 한다."""
    _write(home, "삼성SDS.md")
    page = client.get("/career/companies").text
    assert "파일 이름이 규칙 밖" in page
    assert 'href="/career/c/삼성SDS"' not in page


def test_제목이_없으면_파일_이름이_제목이다(client, home):
    _write(home, "sk-ax.md", "제목 줄이 없는 노트\n")
    assert "sk-ax" in client.get("/career/companies").text


def test_모든_화면의_nav_에_포트폴리오가_있다(client, home):
    for path in ("/career", f"/d/{TODAY}", "/t", f"/c/{TODAY[:7]}"):
        assert 'href="/career"' in client.get(path).text, path


# ── 앞머리와 live 계산 (2026-08-31) ──────────────────────────────────

WITH_META = """---
company: 현대오토에버
role: 엔터프라이즈IT / 백엔드
confidence: A
source: https://example.com/posting.pdf
deadline: 2026-07-10
gates:
  - 영어회화자격(OPIc/토스) | 미확인
  - 2026년 8월 이전 졸업 | 충족
required:
  - Java 21 | jvm-gc, java-concurrency
  - RDBMS | db-index, db-transaction
unmapped: MSA
---
# 메모

설명회에서 들은 것.
"""


def _record(client, slug_topic, **extra):
    body = {
        "record_id": f"rec_{slug_topic}", "client_instance_id": "cli_X",
        "tool": "codex", "kind": "CONCEPT", "topic": slug_topic,
        "title": f"{slug_topic} 이해", "body": "본문",
    }
    body.update(extra)
    return client.post("/v1/records", json=body)


def test_앞머리에서_회사와_신뢰도를_읽는다(client, home):
    _write(home, "hyundai-autoever.md", WITH_META)
    page = client.get("/career/c/hyundai-autoever").text
    assert "현대오토에버" in page
    assert "신뢰도 A" in page
    assert "https://example.com/posting.pdf" in page


def test_준비도를_파일이_아니라_DB_에서_센다(client, home):
    """**이 테스트가 이 화면의 이유다.**

    파일에 숫자를 박아 두면 기록을 하나 남긴 뒤에도 화면이 옛 숫자를 말한다.
    확인하러 여는 화면이 거짓말을 하면 확인용이 아니다.
    """
    _write(home, "hyundai-autoever.md", WITH_META)
    assert "0 / 4 슬러그" in client.get("/career/c/hyundai-autoever").text

    _record(client, "db-index")
    page = client.get("/career/c/hyundai-autoever").text
    assert "1 / 4 슬러그" in page          # 파일은 한 글자도 안 고쳤다


def test_막힌_자격이_맨_위에서_붙잡는다(client, home):
    """어학 하나가 서류 자체를 막는다. 준비도보다 먼저 보여야 한다."""
    _write(home, "hyundai-autoever.md", WITH_META)
    page = client.get("/career/c/hyundai-autoever").text
    assert "아직 1개가 막혀 있다" in page
    # 제목 태그로 비교한다. 본문 문자열로 찾으면 스타일 주석의 같은 낱말이 걸린다.
    assert page.index("<h2>지원 자격</h2>") < page.index("<h2>준비도</h2>")


def test_지난_마감은_다음_기수_대기로_눕는다(client, home):
    _write(home, "hyundai-autoever.md", WITH_META)
    assert "다음 기수 대기" in client.get("/career/c/hyundai-autoever").text


def test_남은_마감은_D_day_로_센다(client, home):
    _write(home, "sk-ax.md", WITH_META.replace("2026-07-10", "2026-07-30"))
    assert "D-8" in client.get("/career/c/sk-ax").text


def test_빈_곳이_주제_화면으로_이어진다(client, home):
    """눌러서 바로 그 주제의 기록을 볼 수 있어야 다음 행동이 이어진다."""
    _write(home, "hyundai-autoever.md", WITH_META)
    page = client.get("/career/c/hyundai-autoever").text
    assert "빈 곳 4개" in page
    assert 'href="/t/jvm-gc"' in page


def test_면접_문장이_모인다(client, home):
    _write(home, "hyundai-autoever.md", WITH_META)
    _record(client, "db-index", interview="인덱스를 왜 이렇게 잡았는지 설명했습니다")
    page = client.get("/career/c/hyundai-autoever").text
    assert "인덱스를 왜 이렇게 잡았는지" in page


def test_로드맵_밖_기술을_지어내지_않고_보여준다(client, home):
    _write(home, "hyundai-autoever.md", WITH_META)
    assert "로드맵 밖" in client.get("/career/c/hyundai-autoever").text
    assert "MSA" in client.get("/career/c/hyundai-autoever").text


def test_앞머리가_없어도_열린다(client, home):
    """앞머리는 나중에 생긴 것이다. 먼저 쓴 노트를 깨면 안 된다."""
    _write(home, "sk-ax.md", "# 제목만 있는 노트\n\n본문.\n")
    page = client.get("/career/c/sk-ax").text
    assert "제목만 있는 노트" in page
    assert "required" in page          # 앞머리를 채우라는 안내


def test_닫히지_않은_앞머리라도_본문을_잃지_않는다(ctx, home):
    _write(home, "sk-ax.md", "---\ncompany: 어딘가\n\n# 본문은 살아야 한다\n")
    view = careerview.build_company(ctx, "sk-ax")
    assert "본문은 살아야 한다" in view["markdown"]
    assert "본문은 살아야 한다" in view["html"]


def test_요구_기술이_없으면_0퍼센트다(ctx, home):
    """0/0 을 100% 로 만들지 않는다. 못 적은 것과 다 갖춘 것은 다른 상태다."""
    _write(home, "sk-ax.md", "---\ncompany: SK AX\n---\n# 메모\n")
    assert careerview.build_company(ctx, "sk-ax")["coverage"]["percent"] == 0


def test_목록에도_막대와_배지가_선다(client, home):
    _write(home, "hyundai-autoever.md", WITH_META)
    page = client.get("/career/companies").text
    assert "자격 1개 막힘" in page
    assert "0 / 4 슬러그" in page


# ── 두 갈래 (2026-08-31) ─────────────────────────────────────────────

def test_허브가_두_갈래를_보여준다(client, home):
    """묻는 것이 다르다 — 무엇을 공부할까 / 어디에 지원할까."""
    _write(home, "hyundai-autoever.md", WITH_META)
    page = client.get("/career").text
    assert 'href="/career/stack"' in page
    assert 'href="/career/companies"' in page
    assert "회사 1곳" in page


def test_기술스택_화면이_로드맵_100개를_다_보여준다(client):
    page = client.get("/career/stack").text
    assert "0 / 100 슬러그" in page
    assert "db-index" in page and "k8s-hpa" in page


def test_요구하는_회사가_있는데_0건이면_먼저_할_것에_선다(client, home):
    _write(home, "hyundai-autoever.md", WITH_META)
    page = client.get("/career/stack").text
    assert "먼저 할 것" in page
    assert "현대오토에버" in page


def test_회사가_많이_요구하는_슬러그가_위로_온다(ctx, home):
    """하나를 채우면 여러 회사의 막대가 같이 오른다. 같은 노력으로 가장 많이 움직인다."""
    _write(home, "hyundai-autoever.md", WITH_META)
    _write(home, "lg-cns.md", WITH_META
           .replace("company: 현대오토에버", "company: LG CNS")
           .replace("  - Java 21 | jvm-gc, java-concurrency\n", ""))
    first = careerview.build_stack(ctx)["first"]
    assert first[0]["slug"] in ("db-index", "db-transaction")
    assert len(first[0]["companies"]) == 2
    assert first[-1]["slug"] in ("java-concurrency", "jvm-gc")


def test_기록한_슬러그는_먼저_할_것에서_빠진다(client, home):
    _write(home, "hyundai-autoever.md", WITH_META)
    _record(client, "db-index")
    page = client.get("/career/stack").text
    # 기록이 생기면 '먼저 할 것' 에서 사라지고 전체 막대가 오른다.
    assert "1 / 100 슬러그" in page


def test_로드맵_밖_주제도_숨기지_않는다(client):
    """도구를 만들며 남긴 기록이다. 면접에서 쓸 수는 있지만 공고와는 안 겹친다."""
    _record(client, "spool-durability")
    page = client.get("/career/stack").text
    assert "로드맵 밖" in page
    assert "spool-durability" in page


def test_회사_상세는_c_아래에_있다(client, home):
    """`/career/{slug}` 로 두면 `stack` 이라는 이름의 회사와 충돌한다."""
    _write(home, "hyundai-autoever.md", WITH_META)
    assert client.get("/career/c/hyundai-autoever").status_code == 200
    assert client.get("/career/hyundai-autoever").status_code == 404
