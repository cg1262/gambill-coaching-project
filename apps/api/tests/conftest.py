import pytest

import main
from rate_limits import RATE_LIMIT_POLICIES_DEFAULT, RATE_LIMIT_STORE


@pytest.fixture(autouse=True)
def reset_rate_limits_between_tests():
    payload = {
        "policies": {
            name: {
                "rules": [
                    {
                        "limit": rule.limit,
                        "window_seconds": rule.window_seconds,
                        "burst": rule.burst,
                    }
                    for rule in policy.rules
                ]
            }
            for name, policy in RATE_LIMIT_POLICIES_DEFAULT.items()
        }
    }
    main.rate_limit_policy_update(payload)
    RATE_LIMIT_STORE.reset()
    yield
