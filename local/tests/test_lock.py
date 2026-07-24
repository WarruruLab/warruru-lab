from warruru_local.daemon.lock import SingleInstanceLock


def test_처음_잠그면_성공한다(tmp_path):
    lock = SingleInstanceLock(tmp_path / "daemon.lock")
    assert lock.acquire() is True
    lock.release()


def test_이미_잠겨_있으면_실패한다(tmp_path):
    path = tmp_path / "daemon.lock"
    first = SingleInstanceLock(path)
    assert first.acquire() is True
    second = SingleInstanceLock(path)
    assert second.acquire() is False
    first.release()


def test_풀고_나면_다시_잠글_수_있다(tmp_path):
    path = tmp_path / "daemon.lock"
    first = SingleInstanceLock(path)
    first.acquire()
    first.release()
    assert SingleInstanceLock(path).acquire() is True


def test_풀기를_두_번_불러도_터지지_않는다(tmp_path):
    lock = SingleInstanceLock(tmp_path / "daemon.lock")
    lock.acquire()
    lock.release()
    lock.release()
