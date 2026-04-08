import tkinter as tk
from datetime import datetime

from src.gui.masaustu_uygulama import LojistikYonetimGUI


def make_msg(ts_readable):
    return {'timestamp_readable': ts_readable}


def test_filter_messages_in_last_minutes():
    root = tk.Tk()
    root.withdraw()
    app = LojistikYonetimGUI(root)

    now = datetime(2026, 1, 13, 12, 0, 0)
    msgs = [
        make_msg('2026-01-13 11:59:00'),  # 1 minute ago
        make_msg('2026-01-13 11:41:00'),  # 19 minutes ago
        make_msg('2026-01-13 11:20:00'),  # 40 minutes ago
        make_msg('2026-01-13 11:00:00'),  # 60 minutes ago
        make_msg('2026-01-13 10:00:00'),  # 120 minutes ago
        make_msg('invalid format')       # ignored
    ]

    res_20 = app.filter_messages_in_last_minutes(msgs, 20, now_dt=now)
    # Should include 11:59 and 11:41 (19 min ago). 11:20 is 40 min ago, excluded
    assert len(res_20) == 2
    assert res_20[0]['timestamp_readable'].startswith('2026-01-13 11:59')
    assert any(m['timestamp_readable'].startswith('2026-01-13 11:41') for m in res_20)

    res_60 = app.filter_messages_in_last_minutes(msgs, 60, now_dt=now)
    # Should include 11:59,11:41,11:20,11:00 (>= 11:00)
    assert len(res_60) == 4

    root.destroy()
