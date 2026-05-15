import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_top_level_imports_work():
    from optionchain_stream import OptionChainPoller, OptionChainRow, CycleHealth
    assert OptionChainPoller is not None
    assert OptionChainRow is not None
    assert CycleHealth is not None


def test_all_list_is_defined():
    import optionchain_stream
    assert hasattr(optionchain_stream, "__all__")
    assert "OptionChainPoller" in optionchain_stream.__all__
    assert "OptionChainRow" in optionchain_stream.__all__
    assert "CycleHealth" in optionchain_stream.__all__
