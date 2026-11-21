using System;
using System.Collections.Generic;
using ColossalFramework;
using ColossalFramework.Math;

namespace Cs1Harness
{
    public static class NetworkOps
    {
        static readonly HashSet<uint> Paths = new HashSet<uint>();

        public static void Register()
        {
            Host.Register("networks", Needs.City, "native segments, node positions and vehicle lanes", q => Networks());
            Host.Register("path_start", Needs.City, "native path: {from:[segment,lane,offset], to:[segment,lane,offset], mode:car|train|ship|plane}; rail is the legacy train selector", Start);
            Host.Register("path_result", Needs.City, "poll a harness-owned native path; completed paths are released: {id}", Result);
        }

        static Dictionary<string, object> Networks()
        {
            var net = Singleton<NetManager>.instance;
            var segments = new List<object>();
            for (int id = 1; id < net.m_segments.m_buffer.Length; id++)
            {
                var s = net.m_segments.m_buffer[id];
                if ((s.m_flags & (NetSegment.Flags.Created | NetSegment.Flags.Deleted)) != NetSegment.Flags.Created)
                    continue;
                var lanes = new List<object>();
                var info = s.Info;
                uint lane = s.m_lanes;
                for (int i = 0; info != null && i < info.m_lanes.Length && lane != 0; i++)
                {
                    var l = info.m_lanes[i];
                    lanes.Add(Host.Obj("index", i, "id", lane, "type", l.m_laneType.ToString(),
                        "vehicle", l.m_vehicleType.ToString(), "category", l.vehicleCategory.ToString(),
                        "direction", l.m_finalDirection.ToString(), "direction_bits", (int)l.m_finalDirection,
                        "authored_direction", l.m_direction.ToString(),
                        "forward", (l.m_finalDirection & (NetInfo.Direction.Forward | NetInfo.Direction.AvoidForward)) != 0,
                        "backward", (l.m_finalDirection & (NetInfo.Direction.Backward | NetInfo.Direction.AvoidBackward)) != 0,
                        "flags", net.m_lanes.m_buffer[lane].m_flags.ToString()));
                    lane = net.m_lanes.m_buffer[lane].m_nextLane;
                }
                var a = net.m_nodes.m_buffer[s.m_startNode].m_position;
                var b = net.m_nodes.m_buffer[s.m_endNode].m_position;
                var renderParts = new List<object>();
                if (info != null && info.m_segments != null)
                    foreach (var part in info.m_segments)
                    {
                        bool turnAround;
                        if (part.CheckFlags(s.m_flags, s.m_flags2, out turnAround))
                            renderParts.Add(Host.Obj("mesh", part.m_segmentMesh == null ? null : part.m_segmentMesh.name,
                                "lod", part.m_combinedLod != null, "lod_distance", part.m_lodRenderDistance));
                    }
                var bounds = s.m_bounds;
                segments.Add(Host.Obj("id", id, "start", s.m_startNode, "end", s.m_endNode,
                    "a", new object[] { a.x, a.y, a.z }, "b", new object[] { b.x, b.y, b.z },
                    "flags", s.m_flags.ToString(), "flags2", s.m_flags2.ToString(),
                    "start_flags", net.m_nodes.m_buffer[s.m_startNode].m_flags.ToString(),
                    "end_flags", net.m_nodes.m_buffer[s.m_endNode].m_flags.ToString(),
                    "bounds_center", new object[] { bounds.center.x, bounds.center.y, bounds.center.z },
                    "bounds_size", new object[] { bounds.size.x, bounds.size.y, bounds.size.z },
                    "render_parts", renderParts, "prefab", info == null ? null : info.name, "lanes", lanes));
            }
            return Host.Obj("segments", segments, "direction_enum_values", Host.Obj(
                "Forward", (int)NetInfo.Direction.Forward, "Backward", (int)NetInfo.Direction.Backward,
                "AvoidForward", (int)NetInfo.Direction.AvoidForward, "AvoidBackward", (int)NetInfo.Direction.AvoidBackward));
        }

        static PathUnit.Position Position(object input)
        {
            var values = input as List<object>;
            if (values == null || values.Count != 3)
                throw new Exception("path position is [segment,lane,offset]");
            int segment = Convert.ToInt32(values[0]);
            int lane = Convert.ToInt32(values[1]);
            int offset = Convert.ToInt32(values[2]);
            var net = Singleton<NetManager>.instance;
            if (segment <= 0 || segment >= net.m_segments.m_buffer.Length || lane < 0 || offset < 0 || offset > 255)
                throw new Exception("path position is out of range");
            var s = net.m_segments.m_buffer[segment];
            if ((s.m_flags & (NetSegment.Flags.Created | NetSegment.Flags.Deleted)) != NetSegment.Flags.Created
                || s.Info == null || lane >= s.Info.m_lanes.Length)
                throw new Exception("path position does not name an existing lane");
            return new PathUnit.Position { m_segment = (ushort)segment, m_lane = (byte)lane, m_offset = (byte)offset };
        }

        static Dictionary<string, object> Start(Dictionary<string, object> q)
        {
            if (Paths.Count >= 32)
                throw new Exception("poll pending harness paths before creating more");
            var from = Position(q["from"]);
            var to = Position(q["to"]);
            string mode = q.ContainsKey("mode") ? Convert.ToString(q["mode"]) : Json.Bool(q, "rail", false) ? "train" : "car";
            VehicleInfo.VehicleType vehicle;
            switch (mode)
            {
                case "car": vehicle = VehicleInfo.VehicleType.Car; break;
                case "train": vehicle = VehicleInfo.VehicleType.Train; break;
                case "ship": vehicle = VehicleInfo.VehicleType.Ship; break;
                case "plane": vehicle = VehicleInfo.VehicleType.Plane; break;
                default: throw new Exception("mode must be car, train, ship or plane");
            }
            bool transport = mode != "car";
            var random = new Randomizer(857u);
            uint id;
            bool created = Singleton<PathManager>.instance.CreatePath(out id, ref random,
                Singleton<SimulationManager>.instance.m_currentBuildIndex, from, to,
                transport ? NetInfo.LaneType.Vehicle | NetInfo.LaneType.TransportVehicle | NetInfo.LaneType.CargoVehicle : NetInfo.LaneType.Vehicle,
                vehicle,
                transport ? VehicleInfo.VehicleCategory.All : VehicleInfo.VehicleCategory.PassengerCar, 100000f);
            if (!created)
                throw new Exception("native CreatePath refused the request");
            Paths.Add(id);
            return Host.Obj("id", id, "mode", mode);
        }

        static Dictionary<string, object> Result(Dictionary<string, object> q)
        {
            uint id = Convert.ToUInt32(q["id"]);
            if (!Paths.Contains(id))
                throw new Exception("path id is not owned by this harness");
            var pm = Singleton<PathManager>.instance;
            var positions = new List<object>();
            byte flags;
            float length;
            lock (pm.m_bufferLock)
            {
                var first = pm.m_pathUnits.m_buffer[id];
                flags = first.m_pathFindFlags;
                length = first.m_length;
                if ((flags & 4) != 0)
                {
                    uint part = id;
                    var seen = new HashSet<uint>();
                    while (part != 0)
                    {
                        if (!seen.Add(part))
                            throw new Exception("native path chain is cyclic");
                        var unit = pm.m_pathUnits.m_buffer[part];
                        for (int i = 0; i < unit.m_positionCount; i++)
                        {
                            PathUnit.Position p;
                            if (!unit.GetPosition(i, out p))
                                throw new Exception("native path names a missing segment");
                            positions.Add(new object[] { p.m_segment, p.m_lane, p.m_offset });
                        }
                        part = unit.m_nextPathUnit;
                    }
                }
            }
            bool complete = (flags & 12) != 0;
            if (complete)
            {
                pm.ReleasePath(id);
                Paths.Remove(id);
            }
            return Host.Obj("id", id, "flags", flags, "complete", complete,
                "success", (flags & 4) != 0, "length", length, "positions", positions, "released", complete);
        }
    }
}
