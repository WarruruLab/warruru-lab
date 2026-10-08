"""문제풀이 (명세 §2.17).

문제는 파일이고 푼 기록은 DB 다. 여기서 붙잡을 것은 셋이다 —
에이전트가 쓴 마크다운을 **헤딩 수 그대로** 문항으로 읽는지,
**맞힌 것은 다시 안 나오고 틀린 것은 다시 나오는지**, 그리고
주소에서 온 값이 경로나 조건을 넘지 않는지.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from warruru_local import paths
from warruru_local.clock import FixedClock
from warruru_local.config import load_settings
from warruru_local.daemon import quizzing
from warruru_local.daemon.app import create_app

START = datetime(2026, 10, 5, 1, 0, 0, tzinfo=timezone.utc)

SET_A = """---
title: 자체 — M4 연습
source: 자체
area: M4
---

## 위험을 범위에서 빼는 대응은?

비용 초과가 우려되는 기능을 이번 범위에서 뺀다.

1) 수용
2) 전가
3) 회피
4) 완화

정답: 3
근거: 에센스 06
해설: 범위에서 **빼면** 회피다. 보험은 전가다.

## 브레인스토밍에서 우선하는 것은?

1) 질
2) 양

정답: 2
해설: 질보다 양.

## BCG 물음표 전략을 서술하라

점유율은 낮고 성장률은 높다.

정답: 물음표다. 스타로 가려면 투자하거나 철수한다.
해설: 채점 키워드: 물음표, 투자, 철수.
"""

SET_B = """---
title: 자체 — M1 연습
source: 기출
area: M1
---

## 코드의 출력은?

```java
// ## 이건 헤딩이 아니다
System.out.println(1);
1) 이것도 보기가 아니다
```

1) 0
2) 1

정답: 2
영역: M3
해설: 펜스 안은 읽지 않는다.

## 정답이 없는 문항은 버린다

1) 가
2) 나

해설: 정답 줄이 없다.
"""


@pytest.fixture
def client(home):
    settings = load_settings(home)
    app = create_app(settings, clock=FixedClock(START), start_background=False)
    with TestClient(app) as made:
        made.headers.update({"X-Warruru-Token": settings.token})
        yield made


def _sets(home, **files):
    root = paths.quiz_dir(home) / "topcit"
    root.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (root / f"{name}.md").write_text(text, encoding="utf-8")
    return root


def test_헤딩_하나가_한_문항이고_보기가_없으면_서술형이다(home):
    root = _sets(home, a=SET_A)
    made = quizzing.parse_set(root / "a.md")
    qs = made["questions"]
    assert [q["kind"] for q in qs] == ["choice", "choice", "free"]
    assert qs[0]["choices"] == ["수용", "전가", "회피", "완화"]
    assert qs[0]["answer"] == "3" and qs[0]["area"] == "M4"
    assert qs[0]["basis"] == "에센스 06"
    assert "보험은 전가다" in qs[0]["explain"]
    assert "비용 초과" in qs[0]["body"]
    assert qs[2]["answer"].startswith("물음표다")


def test_코드펜스_안은_헤딩도_보기도_아니다(home):
    root = _sets(home, b=SET_B)
    qs = quizzing.parse_set(root / "b.md")["questions"]
    # 정답 없는 문항은 빠지고, 펜스 안의 `## ` 는 새 문항을 만들지 않는다.
    assert len(qs) == 1
    assert qs[0]["choices"] == ["0", "1"]
    assert "이것도 보기가 아니다" in qs[0]["body"]
    # 문항별 `영역:` 이 앞머리를 이긴다.
    assert qs[0]["area"] == "M3"


def test_문제가_없어도_화면이_열리고_어디에_두는지_말한다(client):
    page = client.get("/career/cert/topcit/quiz").text
    assert "문제가 아직 없다" in page
    assert "~/.warruru/career/quiz/topcit/" in page


def test_맞힌_것은_다시_안_나오고_틀린_것은_다시_나온다(client, home):
    _sets(home, a=SET_A)
    토큰 = client.app.state.ctx.settings.token
    sets = quizzing.load(home, "topcit")
    첫째, 둘째, 셋째 = quizzing.all_questions(sets)

    res = client.get("/career/cert/topcit/quiz/next?area=M4", follow_redirects=False)
    assert res.headers["location"].startswith(f"/career/cert/topcit/quiz/q/{첫째['hash']}")

    # 첫째는 맞히고, 둘째는 틀린다.
    res = client.post(f"/web/certs/topcit/quiz/{첫째['hash']}",
                      data={"_token": 토큰, "picked": "3", "area": "M4"},
                      follow_redirects=False)
    assert "picked=3" in res.headers["location"]
    page = client.get(res.headers["location"]).text
    assert "맞았다" in page and "보험은 전가다" in page
    # 제목은 "문제 N" 이고 헤딩은 주제 줄로 내려간다.
    assert "문제 <span class=\"num\">1</span>" in page and "객관식" in page

    client.post(f"/web/certs/topcit/quiz/{둘째['hash']}",
                data={"_token": 토큰, "picked": "1"}, follow_redirects=False)
    page = client.get(f"/career/cert/topcit/quiz/q/{둘째['hash']}?picked=1").text
    # 내가 고른 것은 빨강, 정답은 파랑으로 갈린다.
    assert "틀렸다" in page
    assert '<li class="wrong">' in page and '<li class="right">' in page

    # 서술형은 답을 먼저 쓰고, 모범답안을 본 뒤 스스로 고른다.
    page = client.get(f"/career/cert/topcit/quiz/q/{셋째['hash']}").text
    assert "저장하고 모범답안 확인" in page and "물음표다" not in page
    assert "서술형" in page
    res = client.post(f"/web/certs/topcit/quiz/{셋째['hash']}/mine",
                      data={"_token": 토큰, "mine": "물음표\n투자"},
                      follow_redirects=False)
    assert "reveal=1" in res.headers["location"]
    page = client.get(res.headers["location"]).text
    # 답안은 저장돼 다시 열어도 남는다(2026-10-06).
    assert "물음표\n투자" in page and "저장됨" in page
    assert "물음표\n투자" in client.get(f"/career/cert/topcit/quiz/q/{셋째['hash']}").text
    assert "물음표다. 스타로" in page and "채점 키워드" in page
    # 채점 키워드가 칩으로 쪼개진다.
    assert page.count('class="cbt-chip"') == 3
    res = client.post(f"/web/certs/topcit/quiz/{셋째['hash']}",
                      data={"_token": 토큰, "self": "1"}, follow_redirects=False)
    assert "/quiz/next" in res.headers["location"]

    # 이제 남은 것은 틀린 둘째뿐이다.
    res = client.get("/career/cert/topcit/quiz/next", follow_redirects=False)
    assert 둘째["hash"] in res.headers["location"]

    # 둘째를 맞히면 다 끝난다.
    client.post(f"/web/certs/topcit/quiz/{둘째['hash']}",
                data={"_token": 토큰, "picked": "2"}, follow_redirects=False)
    res = client.get("/career/cert/topcit/quiz/next", follow_redirects=False)
    assert res.headers["location"].endswith("/quiz?done=1")

    # 영역별 정답률이 첫 화면에 선다.
    page = client.get("/career/cert/topcit/quiz").text
    assert "M4" in page and ">100</span>%" in page
    # 자격증 화면에서 문제풀이로 가는 길이 있다.
    assert "/career/cert/topcit/quiz" in client.get("/career/cert/topcit").text


def test_많이_틀린_것이_먼저_나오고_방금_푼_것은_바로_안_나온다(home):
    root = _sets(home, a=SET_A)
    qs = quizzing.parse_set(root / "a.md")["questions"]
    sets = [quizzing.parse_set(root / "a.md")]
    state = {
        qs[0]["hash"]: {"last": 0, "tries": 1, "wrongs": 1, "at": "1"},
        qs[1]["hash"]: {"last": 0, "tries": 3, "wrongs": 3, "at": "2"},
        qs[2]["hash"]: {"last": 1, "tries": 1, "wrongs": 0, "at": "3"},
    }
    assert quizzing.pick_next(sets, state)["hash"] == qs[1]["hash"]
    assert quizzing.pick_next(sets, state, after=qs[1]["hash"])["hash"] == qs[0]["hash"]
    # 하나만 남았으면 방금 푼 것이라도 낸다.
    state[qs[0]["hash"]]["last"] = 1
    assert quizzing.pick_next(sets, state, after=qs[1]["hash"])["hash"] == qs[1]["hash"]


def test_기록은_토큰이_있어야_하고_없는_보기는_거절한다(client, home):
    _sets(home, a=SET_A)
    q = quizzing.all_questions(quizzing.load(home, "topcit"))[0]
    client.headers.pop("X-Warruru-Token")
    res = client.post(f"/web/certs/topcit/quiz/{q['hash']}", data={"picked": "1"})
    assert res.status_code in (401, 403)

    토큰 = client.app.state.ctx.settings.token
    res = client.post(f"/web/certs/topcit/quiz/{q['hash']}",
                      data={"_token": 토큰, "picked": "9"})
    assert res.status_code == 400
    assert client.app.state.ctx.records.quiz_state("topcit") == {}


def test_주소에서_온_조건은_아는_꼴만_받는다(client, home):
    _sets(home, a=SET_A)
    assert client.get("/career/cert/topcit/quiz/q/없는해시").status_code == 404
    res = client.get("/career/cert/topcit/quiz/next?set=../../etc&area=X9",
                     follow_redirects=False)
    # 모르는 조건은 버리고 전체에서 고른다.
    assert res.status_code == 303 and "set=" not in res.headers["location"]
    # 경로가 될 수 있는 파일 이름은 세트가 아니다.
    root = paths.quiz_dir(home) / "topcit"
    (root / "a.b.md").write_text(SET_A, encoding="utf-8")
    assert [s["name"] for s in quizzing.load(home, "topcit")] == ["a"]


def test_정답이_번호가_아니면_소물음이지_보기가_아니다(home):
    """서술형 지문의 `1) …` 소물음을 보기로 읽으면 모범답안의 첫 숫자가
    정답 번호가 된다(2026-10-05, 문제를 만든 에이전트가 짚었다)."""
    root = _sets(home, c="""---
area: M3
---

## 서브넷을 계산하라

1) 네트워크 주소를 구하라
2) 호스트 수를 구하라

정답: (1) 192.168.1.0 (2) 30개
해설: /27 이다.
""")
    q = quizzing.parse_set(root / "c.md")["questions"][0]
    assert q["kind"] == "free" and q["choices"] == []
    assert "1) 네트워크 주소를 구하라" in q["body"]
    assert q["answer"].startswith("(1) 192.168.1.0")


def test_영역을_펼쳐_보고_정답은_접어_둔다(client, home):
    """자격증 화면에서 영역을 골라 [풀이 보기] 로 들어가면 그 영역 문제가
    펼쳐지고, 정답·해설은 눌러야 열린다(2026-10-05, 사용자 요청)."""
    _sets(home, a=SET_A, b=SET_B)
    cert = client.get("/career/cert/topcit").text
    assert "/career/cert/topcit/quiz/browse?area=M4" in cert
    assert "/career/cert/topcit/quiz/next?area=M4" in cert

    page = client.get("/career/cert/topcit/quiz/browse?area=M4").text
    assert "위험을 범위에서 빼는 대응은?" in page
    assert "BCG 물음표 전략을 서술하라" in page
    # 다른 영역(M3 로 옮겨 간 코드 문항)은 안 섞인다.
    assert "코드의 출력은?" not in page
    assert page.count("<details") == 3 and "<details open" not in page
    assert "보험은 전가다" in page

    # 틀린 것만 — 아직 안 풀었으니 비어 있다.
    page = client.get("/career/cert/topcit/quiz/browse?area=M4&only=wrong").text
    assert "틀린 문제가 없다" in page


def test_제목은_유형_꼬리표를_떼고_번호판이_선다(client, home):
    """"[서술] …" 처럼 헤딩에 섞인 유형은 배지로 옮기고, 세트 안 번호와
    번호판·이전·다음이 같은 순서를 쓴다(2026-10-05, CBT 화면)."""
    _sets(home, a=SET_A)
    qs = quizzing.all_questions(quizzing.load(home, "topcit"))
    q = dict(qs[0], heading="[서술] 위험 대응을 설명하라")
    assert quizzing.topic_of(q) == "위험 대응을 설명하라"
    assert quizzing.kind_label(dict(q, kind="free")) == "서술형"
    assert quizzing.kind_label(qs[0]) == "객관식"

    page = client.get(f"/career/cert/topcit/quiz/q/{qs[1]['hash']}").text
    assert "/ 3" in page                      # 세트 3문항 중 2번째
    assert f"/quiz/q/{qs[0]['hash']}" in page  # 이전
    assert f"/quiz/q/{qs[2]['hash']}" in page  # 다음
    import re
    assert len(re.findall(r'aria-label="문제 \d', page)) == 3
    assert "①" in page and "②" in page
    # 풀기 전에는 주제 줄(헤딩)이 안 보인다 — 답을 흘릴 수 있다.
    assert "주제 ·" not in page


def test_안_풀고_넘기면_같은_문제가_다시_안_나온다(home):
    """[이어서 풀기] 를 눌렀는데 방금 본 문제가 또 나왔다(2026-10-06)."""
    root = _sets(home, a=SET_A)
    sets = [quizzing.parse_set(root / "a.md")]
    qs = sets[0]["questions"]
    assert quizzing.pick_next(sets, {}, after=qs[0]["hash"])["hash"] == qs[1]["hash"]


def test_한_줄에_붙은_소물음_답을_줄마다_나눈다():
    made = quizzing.split_subanswers("(1) 30, (2) 55, (3) 15")
    assert made.splitlines() == ["(1) 30", "(2) 55", "(3) 15"]
    # 표지가 하나뿐이면 문장이므로 그대로 둔다.
    assert quizzing.split_subanswers("정답은 (1) 하나뿐") == "정답은 (1) 하나뿐"


def test_서술_수행만_골라_돌린다(client, home):
    """시험 전날 배점이 큰 쪽만 돌린다(2026-10-08)."""
    _sets(home, a=SET_A)
    free = [q for q in quizzing.all_questions(quizzing.load(home, "topcit"))
            if q["kind"] == "free"]
    res = client.get("/career/cert/topcit/quiz/next?kind=free", follow_redirects=False)
    assert free[0]["hash"] in res.headers["location"] and "kind=free" in res.headers["location"]
    assert "기출 서술·수행만" in client.get("/career/cert/topcit").text
