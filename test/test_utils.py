from cogfaithup.mycog import is_valid_member


class DummyCtx:
    def __init__(self, author):
        self.author = author


class DummyMember:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return isinstance(other, DummyMember) and self.name == other.name


def test_is_valid_member_self():
    ctx = DummyCtx(DummyMember("user1"))
    member = DummyMember("user1")
    valid, error = is_valid_member(ctx, member)
    assert not valid
    assert error == "You can't play against yourself!"


def test_is_valid_member_other():
    ctx = DummyCtx(DummyMember("user1"))
    member = DummyMember("user2")
    valid, error = is_valid_member(ctx, member)
    assert valid
    assert error is None
