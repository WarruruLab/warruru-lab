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
    """묻는 것이 다르다 — 무엇을 공부할까 / 어디에 지원할까.

    2026-09-08 부터 허브는 **균등 카드 그리드**다. 두 갈래를 큰 칸 둘로
    나누는 대신 카드 여섯으로 흩는다 — 목록 길이가 8배 차이 나는 두 칸을
    나란히 놓으니 오른쪽 아래가 화면 절반 넘게 비었다.
    """
    _write(home, "hyundai-autoever.md", WITH_META)
    page = client.get("/career").text
    assert 'class="board"' in page
    assert 'href="/career/companies"' in page
    assert 'href="/career/stack"' in page


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

def test_허브에서_축을_눌러_들어간다(client):
    """허브는 요약이라 주제 하나하나를 걸지 않는다. 축으로 들어간다."""
    page = client.get("/career").text
    assert "채워지는 정도" in page
    assert 'href="/career/stack"' in page


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

STAGED = """---
status: 필기 합격
issuer: 한국산업인력공단
stages:
  - 필기 | 합격
  - 실기 | 준비중
exams:
  - 2026-07-10 | 필기 발표 | 지난 것 | 해당없음 | 필기
  - 2026-07-30 | 실기 접수 | 사흘뿐이다 | | 실기
  - 2026-08-20 | 실기 시험 | | | 실기
---

# 필기 — 끝났다

# 실기 — 남은 것

## 문제 유형

필답형. 부분 점수가 없다.
"""


def test_허브에_자격증이_상위_셋만_선다(client, home):
    """허브는 요약이다. 여섯 개를 다 펼치면 카드 높이가 무너진다."""
    _cert(home, "jeongcheogi", STAGED)
    page = client.get("/career").text
    카드 = page[page.index("<h2>자격증</h2>"):]
    카드 = 카드[:카드.index("</section>")]
    assert 카드.count('href="/career/cert/') <= 3
    assert "전체 →" in 카드


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

def test_허브에_세_축이_격자로_선다(client):
    """프로젝트 · CS · AI 셋을 한 카드에 격자로 놓는다.
    막대가 아니라 칸이라 **몇 칸이 비었는지**가 먼저 읽힌다."""
    page = client.get("/career").text
    카드 = page[page.index("채워지는 정도"):]
    for 이름 in ("프로젝트 주제", "CS 지식", "AI · 에이전트"):
        assert 이름 in 카드, 이름
    assert 카드.count('class="grid-gauge"') >= 3


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


def test_허브가_마감을_가까운_순으로_보여준다(client, home):
    """허브가 먼저 답해야 하는 것은 '다음에 뭐가 닥치나' 다."""
    _write(home, "sk-ax.md", WITH_META.replace("2026-07-10", "2026-07-28"))
    page = client.get("/career").text
    카드 = page[page.index("<h2>마감</h2>"):]
    assert "D-6" in 카드[:600]


def test_단계마다_칸이_선다(client, home):
    """필기와 실기는 유형도 공부법도 다른 시험이다. 같은 칸에 놓으면 흐려진다."""
    _cert(home, "jeongcheogi", STAGED)
    page = client.get("/career/cert/jeongcheogi").text
    assert "<h2>필기" in page and "<h2>실기" in page
    assert "합격" in page and "준비중" in page


def test_단계마다_자기_다음_일정을_본다(ctx, home):
    _cert(home, "jeongcheogi", STAGED)
    stages = {s["name"]: s for s in careerview.build_cert(ctx, "jeongcheogi")["stages"]}
    assert stages["실기"]["next"]["label"] == "실기 접수"
    assert stages["필기"]["next"] is None      # 지났고 해당없음이다


def test_단계가_없으면_예전처럼_다음에_할_일만(client, home):
    _cert(home, "sqld")                        # stages 없는 노트
    page = client.get("/career/cert/sqld").text
    assert "다음에 할 일" in page


def test_일정_목록에_단계가_붙는다(client, home):
    _cert(home, "jeongcheogi", STAGED)
    page = client.get("/career/cert/jeongcheogi").text
    assert "실기 시험" in page and "필기 발표" in page


def test_문제_유형과_공부법이_보인다(client, home):
    """이 화면의 주인공은 슬러그 목록이 아니라 시험이다."""
    _cert(home, "jeongcheogi", STAGED)
    page = client.get("/career/cert/jeongcheogi").text
    assert "과목 · 유형 · 공부법" in page
    assert "부분 점수가 없다" in page


def test_슬러그_겹침은_아래에_작게_남는다(client, home):
    """기록과 잇는 유일한 끈이라 지우지는 않는다."""
    _cert(home, "jeongcheogi", STAGED)
    page = client.get("/career/cert/jeongcheogi").text
    assert "내 기록과 겹치는 것" in page
    assert page.index("과목 · 유형 · 공부법") < page.index("내 기록과 겹치는 것")


# ── CS 는 면접 문서다 — 묶음 한 장 (2026-09-01 확정) ──────────────────

def _topic_note(home, slug, asks):
    from warruru_local import paths

    root = paths.topic_note_dir(home)
    root.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"  - {ask}" for ask in asks)
    (root / f"{slug}.md").write_text(
        f"---\nlabel: 해시\nasks:\n{body}\nrefs:\n  - Hash | https://example.com/h.md\n---\n\n# 무엇을 기록하나\n\n본문.\n",
        encoding="utf-8",
    )


def test_묶음_화면이_질문을_모아_한_장으로_만든다(client, home):
    """CS 화면을 여는 이유는 '답할 수 있나' 를 점검하는 것이다."""
    _topic_note(home, "ds-hash", ["해시 충돌을 어떻게 해결하나?", "리해싱은 언제 일어나나?"])
    page = client.get("/career/stack/ds").text
    assert "면접에서 묻는 것" in page
    assert "해시 충돌을 어떻게 해결하나?" in page
    assert "리해싱은 언제 일어나나?" in page


def test_질문_수를_센다(ctx, home):
    _topic_note(home, "ds-hash", ["하나?", "둘?"])
    assert careerview.build_group(ctx, "ds")["asks_total"] == 2


def test_기록_숫자는_맨_아래로_내려간다(client, home):
    _topic_note(home, "ds-hash", ["하나?"])
    page = client.get("/career/stack/ds").text
    assert page.index("면접에서 묻는 것") < page.index("내 기록")


def test_묶음_머리말이_있으면_맨_위에_온다(client, home):
    from warruru_local import paths

    root = paths.group_note_dir(home)
    root.mkdir(parents=True, exist_ok=True)
    (root / "ds.md").write_text("이 묶음은 면접에서 가장 먼저 묻는다.\n", encoding="utf-8")
    page = client.get("/career/stack/ds").text
    assert "면접에서 가장 먼저 묻는다" in page
    assert page.index("가장 먼저 묻는다") < page.index("면접에서 묻는 것")


def test_머리말이_없어도_묶음_화면은_열린다(client):
    """있으면 좋은 것이지 관문이 아니다."""
    assert client.get("/career/stack/algo").status_code == 200


# ── 로드맵은 진도다 — 순서를 본다 (2026-09-01 확정) ──────────────────

def test_로드맵_묶음이_로드맵_순서로_선다(ctx):
    """공고에 나오는 말로 묶은 순서로는 다음에 뭘 할지가 안 나온다."""
    labels = [g["label"] for g in careerview.build_stack(ctx)["groups"]]
    assert labels[0] == "네트워크"          # `net-tcp` 가 로드맵 첫 주제다
    assert labels.index("네트워크") < labels.index("Kubernetes")


def test_묶음_안_슬러그도_로드맵_순서다(ctx):
    from warruru_local.topics import roadmap_index

    slugs = [row["slug"] for row in careerview.build_group(ctx, "db")["slugs"]]
    assert slugs == sorted(slugs, key=roadmap_index)


def test_로드맵_묶음은_진도가_맨_위다(client):
    """'어디까지 왔는가' 를 물으러 오는 화면이다."""
    page = client.get("/career/stack/db").text
    assert "어디까지 왔나" in page
    assert page.index("어디까지 왔나") < page.index("면접에서 묻는 것")


def test_CS_묶음은_질문이_맨_위다(client):
    """같은 템플릿이지만 축이 다르면 순서가 다르다."""
    page = client.get("/career/stack/ds").text
    assert "어디까지 왔나" not in page
    assert page.index("면접에서 묻는 것") < page.index("내 기록")


def test_다음에_할_것이_로드맵_순서에서_나온다(ctx, client):
    """'먼저 할 것'(회사가 많이 요구) 과 다른 값이다 — 이쪽은 순서를 본다."""
    ahead = careerview.build_stack(ctx)["ahead"]
    assert ahead[0]["slug"] == "net-tcp"
    _record(client, "net-tcp")
    assert careerview.build_stack(ctx)["ahead"][0]["slug"] == "net-udp"


# ── 공고는 '요구 + 자소서' 다 (2026-09-01 확정) ───────────────────────

ESSAY_NOTE = """---
company: 현대오토에버
required:
  - RDBMS | db-index, db-transaction
essays:
  - 문제를 해결한 경험 | 1000자 | db-index
  - 지원 동기 | 700자
---

# 메모
"""


def test_자소서_문항마다_붙일_기록을_센다(client, home):
    """지원서 쓸 때 기록을 다시 뒤지지 않게, 무엇을 붙일지가 문항 옆에 있어야 한다."""
    _write(home, "hyundai-autoever.md", ESSAY_NOTE)
    _record(client, "db-index", interview="인덱스를 이렇게 잡았습니다")
    page = client.get("/career/c/hyundai-autoever").text
    assert "문제를 해결한 경험" in page
    assert "1000자" in page
    assert "붙일 기록 1건" in page
    assert "인덱스를 이렇게 잡았습니다" in page


def test_붙일_기록이_없으면_없다고_말한다(client, home):
    """비슷한 것으로 채우면 지원서에 그대로 나가고 면접에서 답이 없다."""
    _write(home, "hyundai-autoever.md", ESSAY_NOTE)
    page = client.get("/career/c/hyundai-autoever").text
    assert "붙일 기록 0건" in page
    assert "붙일 기록이 없다" in page


def test_슬러그를_안_적은_문항도_보인다(client, home):
    _write(home, "hyundai-autoever.md", ESSAY_NOTE)
    assert "지원 동기" in client.get("/career/c/hyundai-autoever").text


def test_문항이_없으면_적는_법을_알려준다(client, home):
    _write(home, "hyundai-autoever.md", WITH_META)
    page = client.get("/career/c/hyundai-autoever").text
    assert "아직 문항이 없다" in page
    assert "essays" in page


def test_자소서가_요구_기술_뒤에_온다(client, home):
    """이 화면이 답할 것은 '무엇을 요구하나' 와 '자소서를 어떻게 준비하나' 둘이다."""
    _write(home, "hyundai-autoever.md", ESSAY_NOTE)
    page = client.get("/career/c/hyundai-autoever").text
    assert page.index("<h2>준비도</h2>") < page.index("<h2>자소서</h2>")


def test_카드_이름이_성격을_말한다(client):
    """이름이 '자격증 목록' 이 아니라 '마감' 인 것이 이 화면의 태도다 —
    무엇이 담겼나가 아니라 **무엇에 답하나**로 부른다."""
    page = client.get("/career").text
    for 이름 in ("마감", "쌓인 것", "채워지는 정도"):
        assert f"<h2>{이름}</h2>" in page or f"{이름}</a></h2>" in page, 이름


def _ask_note(home, slug, asks):
    from warruru_local import paths

    root = paths.topic_note_dir(home)
    root.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"  - {a}" for a in asks)
    (root / f"{slug}.md").write_text(
        f"---\nlabel: 해시\nasks:\n{body}\n---\n\n# 무엇을 기록하나\n\n본문.\n",
        encoding="utf-8",
    )


def _hash(text):
    from warruru_local.daemon.topicview import ask_hash

    return ask_hash(text)


def test_질문을_체크하면_켜진다(client, home):
    """3초짜리다. 기록(5분)과 같은 문턱에 두면 아무것도 안 눌린다."""
    _ask_note(home, "ds-hash", ["충돌은 어떻게 해결하나?"])
    token = client.app.state.ctx.settings.token
    posted = client.post(
        "/web/topics/ds-hash/asks",
        data={"_token": token, "ask": _hash("충돌은 어떻게 해결하나?"),
              "text": "충돌은 어떻게 해결하나?", "back": "/career/stack/ds"},
        follow_redirects=False,
    )
    assert posted.status_code == 302
    assert posted.headers["location"] == "/career/stack/ds"
    assert "1 / 1" in client.get("/career/stack/ds").text


def test_다시_누르면_꺼진다(client, home):
    _ask_note(home, "ds-hash", ["충돌은?"])
    token = client.app.state.ctx.settings.token
    data = {"_token": token, "ask": _hash("충돌은?"), "text": "충돌은?"}
    client.post("/web/topics/ds-hash/asks", data=data, follow_redirects=False)
    client.post("/web/topics/ds-hash/asks", data=data, follow_redirects=False)
    assert "0 / 1" in client.get("/career/stack/ds").text


def test_체크는_토큰을_요구한다(client, home):
    """상태를 바꾸는 폼이다."""
    _ask_note(home, "ds-hash", ["충돌은?"])
    assert client.post(
        "/web/topics/ds-hash/asks", data={"ask": _hash("충돌은?")}
    ).status_code == 401


def test_체크와_기록은_다른_값이다(client, home):
    """체크는 '답할 수 있다', 기록은 '내 말로 정리했다' 다."""
    _ask_note(home, "ds-hash", ["충돌은?"])
    token = client.app.state.ctx.settings.token
    client.post("/web/topics/ds-hash/asks",
                data={"_token": token, "ask": _hash("충돌은?"), "text": "충돌은?"},
                follow_redirects=False)
    page = client.get("/career/stack/ds").text
    assert "답 1/1" in page
    assert "기록 0건" in page


def test_질문_문구를_고치면_체크가_풀린다(client, home):
    """고친 것은 다른 질문이다. 색인이 아니라 문구로 잡는 이유이기도 하다."""
    _ask_note(home, "ds-hash", ["충돌은?"])
    token = client.app.state.ctx.settings.token
    client.post("/web/topics/ds-hash/asks",
                data={"_token": token, "ask": _hash("충돌은?"), "text": "충돌은?"},
                follow_redirects=False)
    _ask_note(home, "ds-hash", ["충돌을 어떻게 해결하나?"])
    assert "0 / 1" in client.get("/career/stack/ds").text


def test_주제_화면에서도_체크할_수_있다(client, home):
    _ask_note(home, "ds-hash", ["충돌은?"])
    page = client.get("/t/ds-hash").text
    assert "확인할 것 0 / 1" in page
    assert '/web/topics/ds-hash/asks' in page


def test_바깥으로_되돌리지_않는다(client, home):
    """`back` 은 폼이 주는 값이라 그대로 믿지 않는다."""
    _ask_note(home, "ds-hash", ["충돌은?"])
    token = client.app.state.ctx.settings.token
    posted = client.post(
        "/web/topics/ds-hash/asks",
        data={"_token": token, "ask": _hash("충돌은?"), "text": "충돌은?",
              "back": "https://example.com/훔치기"},
        follow_redirects=False,
    )
    assert posted.headers["location"] == "/career/stack"


# ── 자격증 커리큘럼 (2026-09-01) ─────────────────────────────────────

CURRICULUM = """---
status: 준비중
stages:
  - 실기 | 준비중
curriculum:
  - 실기 | 기출 3개년 | 12
  - 실기 | 서브네팅 연습 | 10
exams:
  - 2026-07-30 | 실기 접수 | | | 실기
---

# 준비
"""


def _cert_hash(text):
    from warruru_local.daemon.topicview import ask_hash

    return ask_hash(text)


def test_항목마다_오늘_분량을_따로_센다(ctx, home):
    """회차와 문항은 단위가 달라 더하면 아무 뜻도 없는 숫자가 나온다."""
    _cert(home, "jeongcheogi", CURRICULUM)
    stage, = careerview.build_cert(ctx, "jeongcheogi")["stages"]
    plans = {row["title"]: row["per_day"] for row in stage["plan"]}
    assert plans["기출 3개년"] == 1.5           # 12 / 8일
    assert plans["서브네팅 연습"] == 1.2        # 10 / 8일 = 1.25 → 반올림


def test_진도를_올리면_오늘_분량이_준다(client, ctx, home):
    _cert(home, "jeongcheogi", CURRICULUM)
    token = client.app.state.ctx.settings.token
    client.post("/web/certs/jeongcheogi/progress",
                data={"_token": token, "item": _cert_hash("기출 3개년"),
                      "text": "기출 3개년", "total": 12, "delta": 1},
                follow_redirects=False)
    row, = [r for r in careerview.build_cert(ctx, "jeongcheogi")["curriculum"]
            if r["title"] == "기출 3개년"]
    assert row["done"] == 1 and row["left"] == 11


def test_전체를_넘거나_0_아래로_안_간다(client, ctx, home):
    """잘못 누른 한 번이 숫자를 영영 틀리게 만들면 그 화면을 안 믿게 된다."""
    _cert(home, "jeongcheogi", CURRICULUM)
    token = client.app.state.ctx.settings.token
    data = {"_token": token, "item": _cert_hash("기출 3개년"),
            "text": "기출 3개년", "total": 12}
    for _ in range(15):
        client.post("/web/certs/jeongcheogi/progress",
                    data=dict(data, delta=1), follow_redirects=False)
    row, = [r for r in careerview.build_cert(ctx, "jeongcheogi")["curriculum"]
            if r["title"] == "기출 3개년"]
    assert row["done"] == 12

    for _ in range(20):
        client.post("/web/certs/jeongcheogi/progress",
                    data=dict(data, delta=-1), follow_redirects=False)
    row, = [r for r in careerview.build_cert(ctx, "jeongcheogi")["curriculum"]
            if r["title"] == "기출 3개년"]
    assert row["done"] == 0


def test_일정을_모르면_오늘_분량을_말하지_않는다(ctx, home):
    """모르는 것을 그럴듯한 숫자로 채우면 그 숫자를 믿게 된다."""
    _cert(home, "aws-saa", CURRICULUM.replace(
        "exams:\n  - 2026-07-30 | 실기 접수 | | | 실기\n", ""))
    stage, = careerview.build_cert(ctx, "aws-saa")["stages"]
    assert all(row["per_day"] == 0 for row in stage["plan"])


def test_진도_변경도_토큰을_요구한다(client, home):
    _cert(home, "jeongcheogi", CURRICULUM)
    assert client.post(
        "/web/certs/jeongcheogi/progress",
        data={"item": _cert_hash("기출 3개년"), "total": 12},
    ).status_code == 401


def test_뷰_키가_dict_메서드를_가리지_않는다(ctx, home):
    """Jinja 에서 `view.items` 는 dict 의 메서드를 먼저 집는다.

    세 번 밟았다 — `group.items` · `stage.items` · `view.values`. 셋 다 화면이
    500 으로 죽었고, 템플릿을 열기 전에는 안 보였다. 그래서 여기서 막는다.
    """
    _write(home, "hyundai-autoever.md", WITH_META)
    _cert(home, "network-2")
    _topic_note(home, "ds-hash", ["하나?"])

    shadowed = set(dir({})) - {"__class__"}

    def walk(value, path="view"):
        if isinstance(value, dict):
            for key, child in value.items():
                assert key not in shadowed, f"{path}.{key} 가 dict 메서드를 가린다"
                walk(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")

    walk(careerview.build_company(ctx, "hyundai-autoever"))
    walk(careerview.build_cert(ctx, "network-2"))
    walk(careerview.build_group(ctx, "ds"))
    walk(careerview.build_stack(ctx))


# ── 책 (2026-09-02) ──────────────────────────────────────────────────

def test_허브에_책이_상위_셋만_선다(client):
    page = client.get("/career").text
    카드 = page[page.index("<h2>책</h2>"):]
    카드 = 카드[:카드.index("</section>")]
    assert 0 < 카드.count('href="/career/book/') <= 3
    assert "전체 →" in 카드


def test_책_화면이_덮는_주제를_보여준다(client):
    page = client.get("/career/book/real-mysql").text
    assert "이 책이 덮는 주제" in page
    assert "인덱스" in page and "실행 계획" in page
    assert "DFS" not in page          # 다른 책의 주제는 안 섞인다


def test_책_화면도_질문과_체크를_쓴다(client, home):
    """'이 책을 읽으면 어느 질문에 답할 수 있게 되는가' 가 같은 질문이라
    묶음 화면과 같은 모양을 쓴다."""
    _topic_note(home, "ds-btree", ["인덱스가 왜 B+트리인가?"])
    page = client.get("/career/book/real-mysql").text
    assert "인덱스가 왜 B+트리인가?" in page
    assert "/web/topics/ds-btree/asks" in page


def test_묶음_열쇠로는_책_화면이_안_열린다(client):
    """`/career/book/db` 가 열리면 어느 쪽인지 알 수 없다."""
    assert client.get("/career/book/db").status_code == 404
    assert client.get("/career/stack/real-mysql").status_code == 404


def test_책은_기록_구획을_따로_두지_않는다(client):
    """맨 위 막대가 이미 그 숫자다. 두 번 세면 어느 쪽이 맞는지 헷갈린다."""
    page = client.get("/career/book/clean-code").text
    assert page.count("이 책이 덮는 주제") == 1
    assert "<h2>내 기록" not in page


# ── AI 는 세 번째 축이다 (2026-09-04 추가) ──────────────────────────

def test_아래_요약이_그리드가_안_여는_곳을_연다(client):
    """A 안의 아래 줄을 가져오되 자격증·공고·책은 이미 카드로 있다.
    같은 것을 두 번 놓는 대신 기록·초안·달력으로 채운다 —
    그 셋은 상단 nav 말고는 들어갈 길이 없었다."""
    page = client.get("/career").text
    줄 = page[page.index('class="entries"'):]
    assert "주제 기록" in 줄 and "초안" in 줄 and "달력" in 줄


def test_AI_묶음_화면이_열린다(client):
    """`/career/stack/{열쇠}` 하나가 세 축을 다 받는다."""
    page = client.get("/career/stack/multi-agent").text
    assert page.count("핸드오프") >= 1
    assert "오케스트레이션" in page


def test_AI_축이_다른_두_축과_따로_세어진다(ctx):
    """한 막대로 합치면 어느 쪽이 비었는지 알 수 없다."""
    view = careerview.build_stack(ctx)
    assert view["ai_coverage"]["total"] == 31
    assert view["ai_coverage"]["total"] != view["cs_coverage"]["total"]


# ── 빌린 책에는 기한이 있다 (2026-09-04 추가) ───────────────────────

def _book_note(home, key: str, text: str):
    root = paths.book_note_dir(home)
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{key}.md").write_text(text, encoding="utf-8")


def test_빌린_책에_반납_D_day_가_붙는다(client, home):
    """기한이 안 보이면 빌린 책은 그냥 반납일에 사라진다."""
    _book_note(home, "real-mysql", "---\nstate: 빌림\ndue: 2026-08-04\n---\n")
    page = client.get("/career").text
    assert "D-13" in page


def test_반납일이_지나도_지우지_않는다(client, home):
    """연장했는지 반납했는지는 사람만 안다. 화면이 임의로 지우면
    그 사실이 조용히 사라진다."""
    _book_note(home, "real-mysql", "---\nstate: 빌림\ndue: 2026-07-20\n---\n")
    page = client.get("/career/book/real-mysql").text
    assert "반납 2일 지남" in page


def test_노트가_없는_책도_그대로_선다(client):
    """대부분의 책은 노트가 없다. 없다고 화면이 깨지면 안 된다."""
    assert client.get("/career/book/effective-java").status_code == 200
    page = client.get("/career").text
    assert 'class="board"' in page


def test_책_화면이_기한과_진도를_보여준다(client, home):
    _book_note(
        home, "real-mysql",
        "---\nstate: 빌림\ndue: 2026-08-04\nat: 8장\n---\n\n인덱스 장부터.\n",
    )
    page = client.get("/career/book/real-mysql").text
    assert "D-13" in page and "2026-08-04까지" in page
    assert "지금 8장" in page
    assert "인덱스 장부터" in page


def test_망가진_반납일은_없는_것으로_친다(client, home):
    """틀린 D-day 는 없는 것보다 나쁘다 — 그걸 믿고 일정을 짠다."""
    _book_note(home, "real-mysql", "---\nstate: 빌림\ndue: 곧\n---\n")
    page = client.get("/career/book/real-mysql").text
    assert "D-" not in page.split("이 책이 덮는 주제")[1][:400]


def test_목표가_있으면_맨_위에_뜬다(client, home):
    """TOPCIT 처럼 점수가 나오는 시험은 목표를 안 정하면 무엇을 버릴지
    못 고른다. 목표는 화면을 열 때마다 먼저 보여야 한다."""
    _cert(home, "topcit", "---\nstatus: 준비중\ngoal: 수준 5 (850점 이상)\n---\n\n# 메모\n")
    page = client.get("/career/cert/topcit").text
    assert "목표 — 수준 5 (850점 이상)" in page


def test_목표가_없으면_그_줄이_아예_없다(client, home):
    """합격/불합격 시험은 목표가 하나뿐이라 적을 것이 없다.
    빈 줄을 남기면 '안 적었다' 로 읽혀서 없는 숙제가 생긴다."""
    _cert(home, "sqld", "---\nstatus: 미시작\n---\n\n# 메모\n")
    assert "목표 —" not in client.get("/career/cert/sqld").text


def test_단계가_다르면_하루_분량이_시험일을_기준으로_잡힌다(client, home):
    """접수 마감과 시험일이 같은 단계에 있으면 커리큘럼이 접수일까지로
    나뉜다. 접수는 하루면 끝나는 일이라 그 분량은 거짓말이 된다."""
    _cert(home, "topcit", (
        "---\nstatus: 준비중\n"
        "stages:\n  - 접수 | 준비중\n  - 정기평가 | 준비중\n"
        "curriculum:\n  - 정기평가 | 손으로 쓰기 | 60\n"
        "exams:\n"
        "  - 2026-07-25 | 접수 마감 | | | 접수\n"
        "  - 2026-08-21 | 정기평가 | | | 정기평가\n"
        "---\n\n# 메모\n"
    ))
    page = client.get("/career/cert/topcit").text
    assert "D-3" in page and "D-30" in page
    assert "오늘 2.0" in page          # 60 / 30일. 접수일(3일)로 나누지 않는다


# ── 옵시디언과 같은 볼트를 쓴다 (2026-09-07) ─────────────────────

def test_옵시디언이_감싼_따옴표를_벗긴다(client, home):
    """프로퍼티 UI 로 한 번만 건드리면 값이 따옴표로 감싸여 저장된다.
    그러면 `deadline` 이 날짜 정규식에 안 맞아 **D-day 가 조용히 사라진다.**
    화면이 아무 말 없이 마감을 잊는 것이 이 파일에서 가장 나쁜 결말이다.
    """
    _write(home, "sk-ax.md",
           '---\ncompany: "SK AX"\ndeadline: "2026-07-30"\n'
           'gates:\n  - "어학 | 미충족"\n---\n# 메모\n')
    page = client.get("/career/c/sk-ax").text
    assert "SK AX" in page and '"SK AX"' not in page
    assert "D-8" in page                    # 따옴표를 안 벗기면 이 줄이 통째로 없다
    assert "자격" in page


def test_한쪽만_있는_따옴표는_값의_일부다(ctx, home):
    """벗기면 없던 값이 만들어진다."""
    _write(home, "sk-ax.md", '---\ncompany: 그는 "말했다\n---\n# 메모\n')
    assert careerview.build_company(ctx, "sk-ax")["company"] == '그는 "말했다'


# ── 계기판 (2026-09-07 재설계) ───────────────────────────────────

def test_마감이_자격증과_공고를_섞어_한_줄로_선다(client, home):
    """아침에 묻는 것은 '자격증이 언제인가' 도 '공고가 언제인가' 도 아니라
    '다음에 뭐가 닥치나' 하나다."""
    _write(home, "sk-ax.md", WITH_META.replace("2026-07-10", "2026-07-28"))
    _cert(home, "jeongcheogi", STAGED)
    줄 = careerview.deadlines(client.app.state.ctx)
    이름 = [row["name"] for row in 줄]
    # 공고 마감(7/28)이 실기 접수(7/30)보다 먼저다
    assert 이름.index("현대오토에버") < 이름.index("정보처리기사")
    assert {row["kind"] for row in 줄} == {"공고", "자격증"}

    카드 = client.get("/career").text
    카드 = 카드[카드.index("<h2>마감</h2>"):]
    assert "현대오토에버" in 카드[:600]


def test_지난_마감은_레인에_안_선다(client, home):
    """못 하는 일을 카운트다운하면 그 숫자가 거짓말이다."""
    _write(home, "sk-ax.md", WITH_META)          # deadline 2026-07-10, 오늘은 7/22
    카드 = client.get("/career").text
    카드 = 카드[카드.index("<h2>마감</h2>"):]
    assert "다가오는 마감이 없다" in 카드[:400]


def test_0_인_칸이_눈에_띄게_선다(client):
    """만들어 두고 안 쓰는 자리를 숫자로 드러낸다. 안 보이면 계속 0 이다."""
    page = client.get("/career").text
    칸 = page[page.index('class="tally"'):]
    칸 = 칸[:칸.index("</section>")]
    assert 칸.count("stat zero") >= 2      # 질문 체크 0 · 발행 0
    assert "답할 수 있다" in 칸 and "발행" in 칸


def test_면접_문장이_적으면_경고로_뜬다(client, home):
    """나머지 필드는 96% 넘게 차는데 이것만 15% 다(2026-09-07 실측).
    면접에 들고 갈 문장이 그것뿐이라 기록의 1/3 을 못 넘으면 경고로 칠한다.
    """
    for n in range(4):
        _record(client, f"db-index-{n}")                     # interview 없이 4건
    page = client.get("/career").text
    칸 = page[page.index('class="tally"'):page.index("면접 문장")]
    assert "stat zero" in 칸

    _record(client, "extra", interview="인덱스를 왜 이렇게 잡았는지 설명했습니다")
    _record(client, "extra2", interview="두 번째 문장")
    page = client.get("/career").text                        # 5건 중 2건 → 1/3 넘음
    칸 = page[page.index('class="tally"'):page.index("면접 문장")]
    assert "stat zero" not in 칸


def test_준비도가_막대가_아니라_칸이다(client, home):
    """막대는 '얼마나 왔나', 칸은 '몇 칸이 비었나' 를 말한다.
    이 도구가 매번 답하려는 질문은 후자다."""
    _write(home, "hyundai-autoever.md", WITH_META)
    page = client.get("/career/c/hyundai-autoever").text
    assert 'class="grid-gauge"' in page
    assert page.count('class="cell ') >= 4      # 슬러그 4개 = 칸 4개
    assert "0 / 4 슬러그" in page               # 글자는 이어져 있어야 한다


def test_색이_둘을_넘지_않는다():
    """상태에 쓰는 색은 **파랑과 빨강 둘뿐**이다.

    2026-09-08 에 사용자가 방향을 정해 '인주 하나' 규칙을 접었다.
    그 규칙은 종이·잉크 위에서 성립했고, 흰 카드 위에서는 파랑이
    '누를 수 있다' 를 맡아야 상태와 조작이 갈린다.

    다만 **둘을 넘기지 않는다.** 셋이 되는 순간 어느 것도 신호가 못 된다 —
    이전 판(청록·주황·붉은색)이 정확히 그렇게 실패했고, 그때는 주황과
    붉은색이 정상 시각에서도 ΔE 10.5 로 구별조차 안 됐다.
    `--key-fill` 은 `--key` 와 같은 색상의 다른 단이라 따로 세지 않는다.
    """
    import re
    from pathlib import Path

    css = (Path(__file__).resolve().parents[1] / "src" / "warruru_local" /
           "daemon" / "templates" / "base.html").read_text(encoding="utf-8")
    css = css[css.index("<style>"):css.index("</style>")]
    tokens = {name for name in re.findall(r"--([a-z][a-z-]*):", css)}
    색상 = {t.split("-")[0] for t in tokens
            if t.split("-")[0] not in
            {"ground", "panel", "ink", "rule", "sans", "mono", "t", "radius",
             "pad", "shadow"}}
    assert 색상 == {"key", "alert"}, 색상


def test_흐린_글자도_읽힌다():
    """`.quiet` 이 감싸는 것은 장식이 아니라 날짜와 건수다.
    안 읽히면 그 자리가 없는 것과 같아서 본문 기준(4.5:1)을 지킨다.

    **카드 위에서 잰다.** 글자가 실제로 앉는 면은 바닥이 아니라 카드다.
    이 검사 때문에 파랑을 두 단으로 나눴다 — 토스의 #3182F6 은 흰 바탕에서
    3.71:1 이라 글자로 쓸 수 없고, 면에만 쓴다.
    """
    import re
    from pathlib import Path

    def 밝기(hex6: str) -> float:
        parts = [int(hex6[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        parts = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
                 for v in parts]
        return 0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2]

    def 대비(a: str, b: str) -> float:
        높, 낮 = sorted((밝기(a), 밝기(b)), reverse=True)
        return (높 + 0.05) / (낮 + 0.05)

    css = (Path(__file__).resolve().parents[1] / "src" / "warruru_local" /
           "daemon" / "templates" / "base.html").read_text(encoding="utf-8")
    밝은 = css[css.index(":root {"):css.index('[data-theme="dark"]')]
    어두운 = css[css.index('[data-theme="dark"]'):css.index("* { box-sizing")]

    # **카드 위**에서 잰다. 글자가 실제로 앉는 면이 바닥이 아니라 카드다.
    for 블록 in (밝은, 어두운):
        땅 = re.search(r"--panel:\s*(#[0-9A-Fa-f]{6})", 블록).group(1)
        for 이름 in ("--ink", "--ink-soft", "--ink-faint", "--key", "--alert"):
            색 = re.search(rf"{이름}:\s*(#[0-9A-Fa-f]{{6}})", 블록).group(1)
            assert 대비(색, 땅) >= 4.5, (이름, 색, 땅, round(대비(색, 땅), 2))
