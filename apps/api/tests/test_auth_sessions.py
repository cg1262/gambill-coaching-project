from auth import issue_token, validate_token, revoke_user_sessions


def test_revoke_user_sessions_clears_tokens():
    t1 = issue_token("alice", "admin")
    t2 = issue_token("alice", "admin")
    t3 = issue_token("bob", "viewer")

    removed = revoke_user_sessions("alice")
    assert removed >= 2
    assert validate_token(t1) is None
    assert validate_token(t2) is None
    assert validate_token(t3) is not None
