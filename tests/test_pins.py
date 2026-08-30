"""上流の版が動いていないことを確かめる。

件数ゲート(G-01)が落ちたとき、原因が上流の改訂か我々の回帰かを切り分けるための対照。
このテストだけが落ちた場合、期待値の更新が正しい対応であって、コードの修正ではない。
"""
import pytest

from pipeline.pins import upstream_drift

pytestmark = pytest.mark.validation


def test_upstream_unchanged():
    drift = upstream_drift()
    assert drift == [], (
        "上流(PerseusDL)が改訂された。実測し直して pins.py と gates.py の期待値を "
        "chore: repin upstream で更新する:\n" + "\n".join(drift)
    )
