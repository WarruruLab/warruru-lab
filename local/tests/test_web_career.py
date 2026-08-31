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


# ── 허브 두 칸 (2026-08-31) ──────────────────────────────────────────

def test_허브의_왼쪽_칸에서_주제를_눌러_들어간다(client, home):
    """기술스택 칸의 항목은 묶음이다 — Spring · DB · Redis · 네트워크 …"""
    _write(home, "hyundai-autoever.md", WITH_META)
    page = client.get("/career").text
    assert 'href="/career/stack/spring"' in page
    assert 'href="/career/stack/db"' in page
    assert "Spring / Spring Boot" in page


def test_허브의_오른쪽_칸에서_회사를_눌러_들어간다(client, home):
    _write(home, "hyundai-autoever.md", WITH_META)
    page = client.get("/career").text
    assert 'href="/career/c/hyundai-autoever"' in page
    assert "현대오토에버" in page


def test_묶음_화면이_그_묶음의_슬러그만_보여준다(client, home):
    _write(home, "hyundai-autoever.md", WITH_META)
    page = client.get("/career/stack/db").text
    assert "db-index" in page
    assert "jvm-gc" not in page          # 다른 묶음은 안 섞인다
    assert "현대오토에버" in page          # 요구하는 회사가 배지로 붙는다


def test_없는_묶음은_404(client):
    assert client.get("/career/stack/없는것").status_code == 404


def test_묶음_화면의_건수도_그_자리에서_센다(client, home):
    _write(home, "hyundai-autoever.md", WITH_META)
    assert "0건" in client.get("/career/stack/db").text
    _record(client, "db-index")
    assert "1건" in client.get("/career/stack/db").text


# ── 자격증 (2026-08-31) ──────────────────────────────────────────────

def test_허브_왼쪽_칸에_자격증이_선다(client):
    page = client.get("/career").text
    assert 'href="/career/cert/sqld"' in page
    assert "네트워크관리사 2급" in page
    assert "AWS SAA" in page


def test_자격증_화면이_겹치는_주제만_보여준다(client):
    page = client.get("/career/cert/sqld").text
    assert "db-index" in page
    assert "aws-vpc" not in page


def test_자격증_준비도가_시험_합격이_아니라고_말한다(client):
    """이 화면이 다 차도 합격을 뜻하지 않는다. 그 오해가 가장 비싸다."""
    assert "시험 범위가 아니다" in client.get("/career/cert/linux-2").text


def test_자격증_건수도_그_자리에서_센다(client):
    assert "0 / 10 슬러그" in client.get("/career/cert/sqld").text
    _record(client, "db-index")
    assert "1 / 10 슬러그" in client.get("/career/cert/sqld").text


def test_없는_자격증은_404(client):
    assert client.get("/career/cert/없는것").status_code == 404


# ── 자격증 일정 (2026-08-31) ─────────────────────────────────────────

CERT_NOTE = """---
issuer: 한국정보통신자격협회
site: https://www.icqa.or.kr
checked: 2026-07-22
links:
  - 종목 안내 | https://www.icqa.or.kr/cn/page/network
  - 나쁜 링크 | javascript:alert(1)
exams:
  - 2026-07-10 | 3회 필기 | 지난 회차
  - 2026-07-25 | 3회 실기 | 필기 합격자만 | 해당없음
  - 2026-07-30 | 4회 접수 시작 | 4일뿐이다
---

# 준비

서브네팅 계산 연습.
"""


def _cert(home, key, text=CERT_NOTE):
    root = paths.cert_dir(home)
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{key}.md").write_text(text, encoding="utf-8")


def test_노트가_없어도_자격증_화면이_열린다(client):
    """일정은 사람이 확인해 적는 값이다. 없는 것이 기본 상태다."""
    page = client.get("/career/cert/sqld").text
    assert "0 / 10" in page
    assert "다음에 할 일" not in page


def test_다음에_할_일이_D_day_로_뜬다(client, home):
    _cert(home, "network-2")
    page = client.get("/career/cert/network-2").text
    assert "다음에 할 일" in page
    assert "4회 접수 시작" in page
    assert "D-8" in page                    # 2026-07-22 → 07-30


def test_해당없음은_D_day_후보에서_빠진다(client, home):
    """앞 단계에 합격해야 보는 실기다. 못 하는 일을 카운트다운하면 거짓말이다."""
    _cert(home, "network-2")
    page = client.get("/career/cert/network-2").text
    assert "해당없음" in page               # 목록에는 남는다
    assert "D-3" not in page                # 07-25 로는 세지 않는다


def test_지난_일정도_지우지_않는다(client, home):
    """지워 버리면 '이번에 놓쳤다' 는 사실까지 사라진다."""
    _cert(home, "network-2")
    page = client.get("/career/cert/network-2").text
    assert "3회 필기" in page and "지남" in page


def test_자격증_노트의_산문도_보인다(client, home):
    _cert(home, "network-2")
    assert "서브네팅 계산 연습" in client.get("/career/cert/network-2").text


def test_허브의_자격증에도_D_day_가_붙는다(client, home):
    _cert(home, "network-2")
    assert "D-8" in client.get("/career").text


def test_공식_사이트_링크가_붙는다(client, home):
    """일정은 바뀐다. 접수 전에 볼 곳이 화면에 있어야 한다."""
    _cert(home, "network-2")
    page = client.get("/career/cert/network-2").text
    assert 'href="https://www.icqa.or.kr/cn/page/network"' in page
    assert "종목 안내" in page


def test_수상한_링크는_걸지_않는다(client, home):
    """노트를 쓰는 쪽이 에이전트라 섞일 이유가 없어야 하는데,
    '없어야 한다' 를 검사 없이 믿지 않는다."""
    _cert(home, "network-2")
    page = client.get("/career/cert/network-2").text
    assert "javascript:alert" not in page
    assert "나쁜 링크" not in page


# ── CS 지식 (2026-08-31) ─────────────────────────────────────────────

def test_허브에_CS_묶음이_선다(client):
    page = client.get("/career").text
    assert 'href="/career/stack/ds"' in page
    assert "자료구조" in page and "디자인패턴" in page


def test_CS_묶음_화면이_열린다(client):
    page = client.get("/career/stack/algo").text
    assert "algo-dfs-bfs" in page
    assert "db-index" not in page


def test_두_축을_한_막대로_합치지_않는다(ctx):
    """로드맵은 만들어 보는 것, CS 는 묻는 것이다. 합치면 어느 쪽이 비었는지 모른다."""
    view = careerview.build_stack(ctx)
    assert view["coverage"]["total"] == 100
    assert view["cs_coverage"]["total"] == 49


def test_CS_기록도_그_자리에서_센다(client):
    assert "0 / 49 슬러그" in client.get("/career/stack").text
    _record(client, "ds-hash")
    assert "1 / 49 슬러그" in client.get("/career/stack").text


def test_CS_슬러그는_로드맵_밖_구획에_안_간다(client):
    """어느 목록에도 없는 것만 '로드맵 밖' 이다."""
    _record(client, "ds-hash")
    page = client.get("/career/stack").text
    assert "로드맵 밖" not in page


def test_화면이_슬러그_대신_한글을_보여준다(client, home):
    """기록·URL·집계는 슬러그로 간다. 읽는 자리에서만 한글로 바꾼다."""
    page = client.get("/career/stack/db").text
    assert "인덱스" in page
    assert 'href="/t/db-index"' in page          # 링크는 슬러그 그대로


def test_슬러그도_같이_보인다(client):
    """`record_learning` 에 적어야 하는 값이라 화면에서 사라지면 안 된다."""
    page = client.get("/career/stack/ds").text
    assert "해시" in page and "ds-hash" in page


def test_빈_곳_배지도_한글이다(client, home):
    _write(home, "hyundai-autoever.md", WITH_META)
    page = client.get("/career/c/hyundai-autoever").text
    assert "JVM GC" in page
    assert 'title="jvm-gc"' in page


# ── 자격증은 '마감이 있는 일정' 이다 (2026-08-31 확정) ────────────────

def test_접수가_가까운_자격증이_위에_온다(ctx, home):
    """이 화면이 먼저 답할 것은 '언제 접수하나' 다. 사흘·나흘짜리 접수를
    놓치면 몇 달이 밀린다."""
    _cert(home, "sqld", CERT_NOTE.replace("2026-07-30", "2026-09-30"))
    _cert(home, "network-2")                       # 07-30 → 더 가깝다
    order = [cert["key"] for cert in careerview.build_certs(ctx)]
    assert order.index("network-2") < order.index("sqld")


def test_일정을_모르는_자격증은_뒤로_간다(ctx, home):
    _cert(home, "network-2")
    certs = careerview.build_certs(ctx)
    assert certs[0]["key"] == "network-2"
    assert certs[-1]["next"] is None


def test_합격한_자격증은_맨_뒤에서_조용해진다(ctx, home):
    _cert(home, "network-2", "---\nstatus: 합격\n---\n# 끝\n")
    certs = careerview.build_certs(ctx)
    assert certs[-1]["key"] == "network-2"
    assert certs[-1]["done"] is True


def test_상태를_안_적으면_미시작이다(ctx):
    assert all(cert["status"] == "미시작" for cert in careerview.build_certs(ctx))


def test_허브가_다음에_할_일을_이름으로_보여준다(client, home):
    """D-8 만 있으면 무엇이 8일 남았는지 모른다."""
    _cert(home, "network-2")
    page = client.get("/career").text
    assert "D-8" in page and "4회 접수 시작" in page
