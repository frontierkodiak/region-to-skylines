"""Adapter operations mapped to the registered harness protocol; no invented RPCs."""

import copy

from wire import Deadline, Unknown

MODES = {"road": "car", "ship": "ship", "air": "plane"}


class Transport:
    def __init__(self, session, native, store, api):
        self.session, self.native, self.store, self.api = session, native, store, api
        self.client = session.client
        self.pending = None
        self.completed = []
        self.rows = []
        self.records = []

    def context(self):
        stats = self.client.call("stats")
        value = self.api.collect_v2.entry_context(stats, self.session.receipt)
        self.api.consumer.entry(value)
        return value

    def graph(self):
        networks = self.client.call("networks")
        self.api.spec.put_json(self.store, networks)
        value = self.api.collect_v2.graph_value(networks)
        return self.api.spec.put_json(self.store, value)

    def inventory(self):
        return self.session.inventory(self.api, self.native)

    def retain(self):
        inv = self.inventory()
        return self.api.adapter.retain_inventory(
            self.native, inv, self.session.read_file, self.store
        )

    def opening(self, control, deadline):
        self.client.deadline = deadline
        installed = self.session.install(control)
        maps = self.client.call("maps")
        entries = [row for row in maps["maps"] if row.get("path") == str(installed)]
        if len(entries) != 1:
            raise Unknown("installed map has no unique maps entry")
        self.client.call("new_game", path=entries[0]["path"])

        def loaded(row):
            if (
                type(row.get("in_game")) is not bool
                or type(row.get("loading")) is not bool
            ):
                raise Unknown("invalid loading status")
            return row["in_game"] and not row["loading"]

        self.client.wait(
            loaded, deadline.remaining(), "New Game", alive=self.session.alive
        )
        context = self.context()
        self.client.call("run", paused=True)
        graph = self.graph()
        if graph != control["exact_graph_sha256"]:
            raise Unknown("opening graph drift")
        return context, graph

    def query(self, plan, expected_graph, deadline):
        if self.pending is not None:
            raise Unknown("unresolved prior path handle")
        self.client.deadline = deadline
        row = dict(plan=copy.deepcopy(plan), error=None)
        self.rows.append(row)
        try:
            row["pre_context"] = self.context()
            row["pre_graph"] = self.graph()
            if row["pre_graph"] != expected_graph:
                raise Unknown("pre-query graph drift")
            # This is the last wire operation before path_start, not the returned oracle.
            before = self.client.call("study_build_index")
            row["pre_build_index"] = self.api.consumer.integer(
                before["build_index"], 0, 2**32 - 1
            )
            # Once send begins a missing reply leaves an UNKNOWN handle, not absence.
            self.pending = dict(
                state="submission-unacknowledged", query_id=plan["query_id"]
            )
            effective = self.client.call(
                "path_start",
                **{
                    "from": plan["request"]["from"],
                    "to": plan["request"]["to"],
                    "mode": MODES[plan["mode"]],
                    "max_length": plan["max_length"],
                },
            )
            row["effective"] = effective
            handle = self.api.consumer.integer(effective.get("id"), 1, 2**32 - 1)
            self.pending = dict(state="pending", id=handle, query_id=plan["query_id"])
            request = self.api.consumer.Request(
                plan["mode"],
                self.api.consumer.position(plan["request"]["from"]),
                self.api.consumer.position(plan["request"]["to"]),
                plan["max_length"],
                row["pre_build_index"],
            )
            self.api.protocol.effective(effective, request)
            while True:
                deadline.remaining()
                self.session.alive()
                result = self.client.call("path_result", id=handle)
                row["result"] = result
                native = self.api.protocol.native_result(result, handle)
                if native.complete:
                    if not native.released:
                        raise Unknown("release not acknowledged")
                    self.pending = None
                    self.completed.append(dict(id=handle, released=True))
                    break
                deadline.pause(0.01)
            decision = self.api.consumer.decide(effective, result, request)
            wanted = {"positive": "success", "invalid-vehicle": "no_path"}.get(
                plan["kind"]
            )
            if wanted is None or decision.literal_label.value != wanted:
                raise Unknown(
                    "literal result Unknown/control failure: " + decision.reason
                )
            row["post_context"] = self.context()
            row["post_graph"] = self.graph()
            if row["post_graph"] != expected_graph:
                raise Unknown("post-query graph drift")
            if row["post_context"]["frame"] < row["pre_context"]["frame"]:
                raise Unknown("reversed frame")
            deadline.remaining()
            return row
        except Exception as error:
            row["error"] = f"{type(error).__name__}: {error}"
            raise


def collect(transport, births, limits):
    """Fresh literal controls; constructed admission never opens a holdout."""
    api, native = transport.api, transport.native
    total = transport.session.total
    for index, control in enumerate(native.value["controls"]):
        opening = (
            transport.session.first_opening
            if index == 0
            else Deadline.after(limits["opening_seconds"], total)
        )
        load = Deadline.after(
            limits["load_seconds"],
            opening,
            *([transport.session.initial_load] if index == 0 else []),
        )
        transport.client.deadline = load
        observed = {
            k: copy.deepcopy(control[k])
            for k in api.consumer.v1.HASHES | {"consumed_fields"}
        }
        observed.update(
            completed=False,
            error=None,
            session_id=transport.session.session_id(control),
            native_context=None,
            opening_graph=None,
            post_graph=None,
            runtime={},
            paths=[],
            cleanup={},
            owned_processes={},
        )
        record = dict(
            case_id=control["case_id"],
            kind="CONSTRUCTED",
            binding=native.bindings(),
            observed=observed,
        )
        transport.records.append(record)
        runtime = observed["runtime"]

        def capture(phase):
            captured = transport.retain()
            runtime[phase] = dict(
                {k: v for k, v in captured.items() if k != "process_roles"},
                **births["game"],
                unresolved=[],
            )

        try:
            capture("launch")
            context, graph = transport.opening(control, load)
            observed.update(native_context=context, opening_graph=graph)
            transport.client.deadline = opening
            capture("pre")
            transport.client.call("run", paused=False, speed=1)
            for plan in control["requests"]:
                transport.rows = observed["paths"]
                transport.query(
                    plan, graph, Deadline.after(limits["query_seconds"], opening)
                )
            transport.client.deadline = opening
            transport.client.call("run", paused=True)
            observed["post_graph"] = transport.graph()
            capture("post")
            if observed["post_graph"] != graph:
                raise Unknown("opening post graph drift")
            opening.remaining()
            observed["completed"] = True
        except Exception as error:
            observed["error"] = f"{type(error).__name__}: {error}"
            raise
    total.remaining()
    return transport.records
