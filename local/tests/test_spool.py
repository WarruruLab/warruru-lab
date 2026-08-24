from warruru_local import paths, spool

CLIENT = "cli_01K0X4KZ7Y6M2B9DQPXAJ3HTF4"
NOW = "2026-07-22T09:00:00.000Z"


def test_봉투를_한_줄로_덧붙인다(home):
    paths.ensure_layout(home)
    spool.append(home, CLIENT, "record_checkpoint", {"a": 1}, NOW, "evt_A")
    spool.append(home, CLIENT, "record_checkpoint", {"a": 2}, NOW, "evt_B")
    envelopes = spool.read_envelopes(spool.spool_path(home, CLIENT))
    assert [item["payload"]["a"] for item in envelopes] == [1, 2]


def test_봉투에_필요한_필드가_들어간다(home):
    paths.ensure_layout(home)
    spool.append(home, CLIENT, "start_work", {"work_id": "wrk_A"}, NOW, "evt_A")
    envelope = spool.read_envelopes(spool.spool_path(home, CLIENT))[0]
    assert envelope["envelope_version"] == spool.ENVELOPE_VERSION
    assert envelope["event_id"] == "evt_A"
    assert envelope["kind"] == "start_work"
    assert envelope["enqueued_at"] == NOW


def test_대화마다_파일이_나뉜다(home):
    paths.ensure_layout(home)
    spool.append(home, CLIENT, "start_work", {}, NOW, "evt_A")
    spool.append(home, "cli_다른대화", "start_work", {}, NOW, "evt_B")
    assert spool.spool_path(home, CLIENT) != spool.spool_path(home, "cli_다른대화")


def test_깨진_줄은_건너뛴다(home):
    paths.ensure_layout(home)
    target = spool.spool_path(home, CLIENT)
    spool.append(home, CLIENT, "start_work", {"a": 1}, NOW, "evt_A")
    with target.open("a", encoding="utf-8") as handle:
        handle.write("이건 JSON 이 아니다\n")
    spool.append(home, CLIENT, "start_work", {"a": 2}, NOW, "evt_B")
    assert len(spool.read_envelopes(target)) == 2


def test_빈_파일은_빈_목록이다(home):
    paths.ensure_layout(home)
    target = spool.spool_path(home, CLIENT)
    target.write_text("", encoding="utf-8")
    assert spool.read_envelopes(target) == []


def test_한글_본문이_깨지지_않는다(home):
    paths.ensure_layout(home)
    spool.append(home, CLIENT, "record_checkpoint", {"body": "한글 본문"}, NOW, "evt_A")
    envelope = spool.read_envelopes(spool.spool_path(home, CLIENT))[0]
    assert envelope["payload"]["body"] == "한글 본문"


def test_학습기록_봉투는_버전_2_로_쓰인다(home):
    """구버전 데몬이 이 파일을 통째로 건너뛰게 만드는 장치다.

    구버전 데몬은 `learning_record` 핸들러가 없어서 봉투를 조용히 버린다.
    버전을 올려 두면 `_has_unknown_version` 이 먼저 걸러 파일을 손대지 않는다.
    """
    paths.ensure_layout(home)
    spool.append(home, CLIENT, "learning_record", {"a": 1}, NOW, "evt_A")
    envelope = spool.read_envelopes(spool.spool_path(home, CLIENT))[0]
    assert envelope["envelope_version"] == 2


def test_기존_봉투는_버전_1_그대로다(home):
    paths.ensure_layout(home)
    for kind in ("start_work", "record_checkpoint", "finish_work", "client_closed"):
        spool.append(home, CLIENT, kind, {}, NOW, f"evt_{kind}")
    versions = {
        item["envelope_version"]
        for item in spool.read_envelopes(spool.spool_path(home, CLIENT))
    }
    assert versions == {1}


def test_버전_2_는_핸들러와_함께_열렸다():
    """버전을 올리는 것과 핸들러를 더하는 것은 같은 커밋이어야 한다.

    K2 수정 때는 핸들러가 없어 `{1}` 로 묶어 뒀고, `learning_record` 핸들러가
    들어온 커밋에서 `2` 를 함께 열었다. 이 두 값이 어긋난 채 갈라지는 것은
    아래 두 테스트(`쓸_수_있는_봉투는…` · `KINDS_와_HANDLERS…`)가 막는다.
    """
    assert spool.SUPPORTED_ENVELOPE_VERSIONS == {1, 2}
    assert "learning_record" in spool.KINDS


def test_쓸_수_있는_봉투는_전부_읽을_수_있어야_한다():
    """어댑터가 쓰는 버전과 데몬이 읽는 버전이 갈라지면 그 파일은 영원히 밀린다.

    실패 경로와 달리 상한이 없다 — MAX_ATTEMPTS 가 적용되지 않고 파일만 커진다.
    KINDS 에 종류를 더하는 순간 이 테스트가 버전 집합도 같이 보라고 알려 준다.
    """
    for kind in spool.KINDS:
        assert spool.envelope_version_for(kind) in spool.SUPPORTED_ENVELOPE_VERSIONS


def test_읽을_수_없는_버전의_봉투는_아직_쓸_수_없어야_한다():
    """버전만 올려 두고 종류를 먼저 열면 그 대화의 파일이 통째로 멈춘다.

    `_has_unknown_version` 은 파일 단위로 판정하므로, 못 읽는 봉투 한 줄이
    같은 파일의 start_work·record_checkpoint 까지 전부 붙잡아 둔다.
    게다가 SingleInstanceLock 때문에 그 파일을 읽을 수 있는 새 데몬을
    띄우지도 못한다. 그래서 '쓸 수 있다(KINDS)' 와 '읽을 수 있다' 를 묶어 둔다.
    """
    for kind, version in spool.ENVELOPE_VERSION_BY_KIND.items():
        if version not in spool.SUPPORTED_ENVELOPE_VERSIONS:
            assert kind not in spool.KINDS, (
                f"{kind} 는 버전 {version} 로 쓰이는데 데몬이 읽지 못한다. "
                "KINDS 에 넣으려면 SUPPORTED_ENVELOPE_VERSIONS 도 함께 올려라."
            )
