---
name: exam-schedule
description: Keep the exam notes under ~/.warruru/career/certs/ correct so the local screens can compute D-day and today's study amount. Use when the user asks 시험 언제야, 접수 언제까지, 오늘 얼마나 해야 해, 커리큘럼 짜줘, 자격증 일정 정리, or when a schedule/registration date needs to be checked or updated.
---

# 자격증 일정

**화면이 계산하고 사람은 확인만 한다.** D-day 도 하루 분량도
`/career/cert/{열쇠}` 가 이미 계산해서 보여 준다. 이 스킬이 하는 일은
그 계산의 **재료를 정확하게 유지하는 것** 하나다.

## 노트가 사는 곳

```
~/.warruru/career/certs/{열쇠}.md
```

지금 있는 열쇠 — `jeongcheogi`(정보처리기사) · `sqld` · `network-2`(네트워크관리사 2급)
· `linux-2`(리눅스마스터 2급) · `aws-saa` · `topcit`

## 앞머리 문법

```yaml
---
status: 준비중                    # 또는 미시작 · 필기 합격 · 합격
goal: 수준 5 (850점 이상)          # 점수제 시험만. 합격/불합격이면 비운다
issuer: 한국산업인력공단 (큐넷)
site: https://www.q-net.or.kr
checked: 2026-09-05               # 일정을 확인한 날. 지어내지 마라
stages:
  - 필기 | 합격
  - 실기 | 준비중
curriculum:
  - 실기 | 기출 3개년 필답형 풀기 | 12      # 단계 | 항목 | 개수
exams:
  - 2026-10-24 | 3회 실기 시험 | 비고 | | 실기   # 날짜|라벨|비고|해당없음?|단계
---
```

## 틀리면 조용히 아픈 것 넷

1. **날짜를 지어내지 마라.** 확인한 곳을 `links:` 에 남기고 확인한 날을
   `checked:` 에 적는다. 틀린 D-day 는 없는 것보다 나쁘다 — 그걸 믿고 일정을 짠다.
2. **접수 마감과 시험일을 같은 단계에 넣지 마라.** 하루 분량이 접수일까지로
   나뉘어 "오늘 20문항" 같은 거짓 분량이 나온다. 단계를 갈라라(`접수` · `정기평가`).
3. **내가 못 하는 일정에는 넷째 칸에 `해당없음` 을 적는다.** 합격 발표처럼
   앞 단계에 붙는 것들이다. 목록에는 남지만 D-day 로는 안 쓰인다 —
   못 하는 일을 카운트다운하면 그 숫자가 거짓말이다.
4. **커리큘럼의 개수는 단위가 같은 것끼리만.** 회차와 문항과 회독을 한 줄에
   섞으면 "오늘 2.2만큼" 이 된다. 항목을 나눠라.

## 준비도 막대가 뜻하는 것

`topics.CERTIFICATIONS` 의 슬러그는 **시험 범위가 아니라 로드맵과 겹치는 부분**이다.
막대가 꽉 차도 합격을 뜻하지 않는다. 시험에는 나오지만 로드맵에 없는 것이 있고,
그 몫은 이 화면이 답하지 못한다. **그 한계를 노트 본문에 적어 두어라.**

## 하지 않는 것

- 코드 상수(`topics.py`)에 날짜를 넣지 않는다. 해마다 바뀐다.
- 회사 공고 마감은 `career-prep` 이 회사 노트에서 다룬다.
- 무엇을 공부할지 고르는 것은 `study-session` 이다.
