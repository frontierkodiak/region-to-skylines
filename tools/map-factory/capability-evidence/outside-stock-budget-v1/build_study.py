"""Compile a study-local NetworkOps budget parameter, without shared build writes."""

from pathlib import Path
import shutil

import study
from cs1_harness import build
from cs1_harness.config import Config


def main():
    study.configure()
    cfg = Config.for_host()
    stage = cfg.build_dir / "outside-stock-budget-sources"
    stage.mkdir(parents=True, exist_ok=False)
    for path in sorted((study.HARNESS / "mod").glob("*.cs")):
        shutil.copyfile(path, stage / path.name)
    path = stage / "NetworkOps.cs"
    text = path.read_text()
    replacements = {
        "            uint id;\n            bool created": """            float maxLength = q.ContainsKey("max_length") ? Convert.ToSingle(q["max_length"]) : 100000f;
            if (maxLength != 100000f && maxLength != 200000f && maxLength != 1000000f)
                throw new Exception("study budget is not predeclared");
            uint buildIndex = Singleton<SimulationManager>.instance.m_currentBuildIndex;
            uint id;
            bool created""",
        "Singleton<SimulationManager>.instance.m_currentBuildIndex, from, to,": "buildIndex, from, to,",
        "VehicleInfo.VehicleCategory.PassengerCar, 100000f);": "VehicleInfo.VehicleCategory.PassengerCar, maxLength);",
        'return Host.Obj("id", id, "mode", mode);': """return Host.Obj("id", id, "mode", mode, "max_length", maxLength,
                "build_index", buildIndex, "seed", 857, "from", q["from"], "to", q["to"],
                "vehicle", vehicle.ToString(),
                "category", (transport ? VehicleInfo.VehicleCategory.All : VehicleInfo.VehicleCategory.PassengerCar).ToString(),
                "lane_types", (transport ? NetInfo.LaneType.Vehicle | NetInfo.LaneType.TransportVehicle | NetInfo.LaneType.CargoVehicle : NetInfo.LaneType.Vehicle).ToString());""",
    }
    for old, new in replacements.items():
        if text.count(old) != 1:
            raise ValueError("exact NetworkOps source anchor changed")
        text = text.replace(old, new)
    path.write_text(text)
    build.MOD_SOURCES = stage
    receipt = build.build(cfg)
    study.freeze(
        study.HERE / "build.json",
        {
            "frozen_at": study.now(),
            "generator_sha256": study.sha(Path(__file__)),
            "original_sources": {
                p.name: study.sha(p)
                for p in sorted((study.HARNESS / "mod").glob("*.cs"))
            },
            "build_receipt": receipt,
            "staged_NetworkOps": text,
            "scope": "one explicit float maxLength passed unchanged to the public CreatePath overload; source binding, not memory attestation",
        },
    )
    print(receipt["dll_sha256"])


if __name__ == "__main__":
    main()
