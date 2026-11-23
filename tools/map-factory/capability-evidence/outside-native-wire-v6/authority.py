"""Parent authority comes from authenticated external records, not caller claims.

The fixed owner and parent identify the assigning study owner. This does not add
credentials or scopes. Native callers must supply two distinct parent comments:
review acceptance and a later explicit opening-budget authorization.
"""

from dataclasses import asdict, dataclass
import subprocess
from uuid import UUID

from wire import decode, encoded, Unknown

PARENT = "01a1fadf-2188-7dfc-988a-b4c2c6ca988a"
OWNER = "43675dd8-225d-4c88-b3f4-d78315bec853"
TARGET = "PL-1142-native-v2"
FIELDS = {"schema", "action", "request", "target", "source_revision", "build_sha256"}


def descriptor(request):
    value = asdict(request)
    value["binding"] = decode(value["binding"])
    value["limits"] = decode(value["limits"])
    return value


def validate_records(acceptance, budget, request, frozen):
    """Same parser for authenticated native records and marked constructed tests."""
    for record, action in (
        (acceptance, "accept-study"),
        (budget, "authorize-openings"),
    ):
        if (
            type(record) is not dict
            or record.get("author_id") != OWNER
            or record.get("author_type") != "agent"
        ):
            raise Unknown("authorization is not from the assigning parent owner")
        body = decode(record.get("content", ""))
        if type(body) is not dict or set(body) != FIELDS:
            raise Unknown("parent authorization shape differs")
        expected = dict(
            schema=6,
            action=action,
            request=descriptor(request),
            target=TARGET,
            source_revision=frozen["source_revision"],
            build_sha256=frozen["v5"]["fresh_build"]["dll"],
        )
        if encoded(body) != encoded(expected):
            raise Unknown(
                "parent authorization source/build/freeze/session/budget differs"
            )
        if (
            type(record.get("id")) is not str
            or not record["id"]
            or type(record.get("revision")) is not int
            or record["revision"] < 1
        ):
            raise Unknown("authorization record identity/revision missing")
        if type(record.get("created_at")) is not str:
            raise Unknown("authorization time missing")
    if (
        acceptance["id"] == budget["id"]
        or budget["created_at"] <= acceptance["created_at"]
    ):
        raise Unknown(
            "opening authorization must be separate and later than acceptance"
        )
    return True


def native_record(comment_id, frozen):
    """Only the authenticated CLI supplies provider actor and record identity."""
    if type(comment_id) is not str or len(comment_id) != 36:
        raise Unknown("explicit parent comment id required")
    try:
        if str(UUID(comment_id)) != comment_id:
            raise ValueError("noncanonical")
    except ValueError as error:
        raise Unknown("canonical parent comment UUID required") from error
    result = subprocess.run(
        [
            frozen["native"]["tools"]["multica"]["path"],
            "issue",
            "comment",
            "list",
            PARENT,
            "--thread",
            comment_id,
            "--tail",
            "1",
            "--compact",
            "--output",
            "json",
        ],
        capture_output=True,
        timeout=15,
        check=True,
    )
    records = decode(result.stdout)
    if type(records) is not list:
        raise Unknown("external parent records unavailable")
    matches = [r for r in records if type(r) is dict and r.get("id") == comment_id]
    if len(matches) != 1:
        raise Unknown("external parent authorization missing/ambiguous")
    return matches[0]


@dataclass(frozen=True)
class ParentAuthority:
    acceptance_comment: str
    budget_comment: str
    purpose = "NATIVE"

    def authorize(self, request, frozen):
        if request.purpose != "NATIVE":
            raise Unknown("native authority cannot be used for constructed facts")
        return validate_records(
            native_record(self.acceptance_comment, frozen),
            native_record(self.budget_comment, frozen),
            request,
            frozen,
        )


@dataclass(frozen=True)
class ConstructedAuthority:
    expected: object
    purpose = "CONSTRUCTED"

    def authorize(self, request, frozen):
        return request.purpose == self.purpose and request == self.expected
