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
