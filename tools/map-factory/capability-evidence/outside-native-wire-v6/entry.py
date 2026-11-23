"""External authority precedes all session/queue/install/socket effects.

Integrity is NOT authority. The owning parent supplies an authority implementation
through this Python API after independently accepting source/build/freeze/budget.
No CLI flag, receipt, hash, dictionary, or OFFLINE_CONSTRUCTED_ONLY grant creates
that implementation. Tests inject explicitly constructed authority and sessions.
"""

from dataclasses import dataclass

import accepted_api as api
import candidate
from authority import ParentAuthority, ConstructedAuthority
from wire import Deadline, Unknown


@dataclass(frozen=True)
class Request:
    freeze_sha256: str
    binding: bytes
    session: str
    limits: bytes
    purpose: str


def preflight(frozen, store, request, authority=None, factory=None):
    native, inputs = candidate.validate(frozen, store)
    api.pipeline.validate_policy(
        native,
        api.pipeline.runtime_policy(native, native.descriptor["inventory"]),
        store,
    )
    if (
        type(request) is not Request
        or type(request.session) is not str
        or type(request.binding) is not bytes
        or type(request.limits) is not bytes
        or type(request.purpose) is not str
        or not request.session
        or request.session in native.value["prior_sessions"]
    ):
        raise Unknown("missing/reused session request")
    if (
        request.freeze_sha256 != api.spec.digest(frozen)
        or request.binding != api.spec.canonical(native.bindings())
        or request.limits != api.spec.canonical(frozen["limits"])
    ):
        raise Unknown("requested source/build/freeze/budget differs")
    if request.purpose not in {"CONSTRUCTED", "NATIVE"}:
        raise Unknown("invalid requested purpose")
    if authority is None or factory is None or isinstance(authority, dict):
        raise Unknown("external parent authority and session owner required")
    if request.purpose == "NATIVE":
        from native_session import NativeSession

        valid_factories = (NativeSession,)
    else:
        from exercise import Factory, ConnectedFixture

        valid_factories = (Factory, ConnectedFixture)
    if type(factory) not in valid_factories:
        raise Unknown("unbound session factory")
    expected_authority = (
        ParentAuthority if request.purpose == "NATIVE" else ConstructedAuthority
    )
    if type(authority) is not expected_authority:
        raise Unknown(
            "caller-authored authorizer is not an external authority boundary"
        )
    if request.purpose != authority.purpose or factory.purpose != request.purpose:
        raise Unknown("constructed authorization cannot authorize native effects")
    # This call is the EXTERNAL trust boundary. It is not evidence about a human.
    # Acceptance is supplied by the parent, never synthesized by this entry.
    if authority.authorize(request, frozen) is not True:
        raise Unknown("external parent did not authorize exact request")
    return native, inputs


def enter(frozen, store, request, authority=None, factory=None):
    native, inputs = preflight(frozen, store, request, authority, factory)
    # The only effect-bearing call, deliberately after every check above.
    return factory.open(
        native,
        inputs,
        request,
        store,
        Deadline.after(frozen["limits"]["total_seconds"]),
    )
