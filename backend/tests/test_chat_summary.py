from app.services import chat_summary as cs


class _M:
    def __init__(self, role, content): self.role = role; self.content = content


def _msgs(n):
    return [_M("user" if i % 2 == 0 else "assistant", f"m{i}") for i in range(n)]


def test_select_window_below_max_no_fold():
    msgs = _msgs(10)  # 10 <= max_buffer(14)
    to_fold, recent, new_count = cs.select_window(msgs, summarized_count=0)
    assert to_fold == []
    assert len(recent) == 10
    assert new_count == 0


def test_select_window_overflow_folds_all_but_keep_recent():
    msgs = _msgs(20)  # 20 > 14 → folden
    to_fold, recent, new_count = cs.select_window(msgs, summarized_count=0)
    assert len(recent) == 6                      # keep_recent
    assert new_count == 14                        # len-6
    assert len(to_fold) == 14                      # messages[0:14]
    assert to_fold[0].content == "m0"


def test_select_window_respects_summarized_count():
    msgs = _msgs(20)
    # 12 bereits gefaltet → unsummarized = 8 (<=14) → kein neuer Fold
    to_fold, recent, new_count = cs.select_window(msgs, summarized_count=12)
    assert to_fold == []
    assert len(recent) == 8
    assert new_count == 12


def test_build_turn_input_with_and_without_summary():
    recent = _msgs(2)
    out = cs.build_turn_input("ALT-SUMMARY", recent)
    assert "Zusammenfassung" in out and "ALT-SUMMARY" in out
    assert "Nutzer: m0" in out
    out2 = cs.build_turn_input("", recent)
    assert "Zusammenfassung" not in out2
    assert "Nutzer: m0" in out2
