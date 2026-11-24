using System;
using System.Collections.Generic;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using ColossalFramework;

namespace Cs1Harness
{
    public static class RailMetadata
    {
        public static void Register()
        {
            Host.Register("rail_metadata", Needs.City,
                "read-only Train graph, authored tangents and public turn limits; {digest_only:bool}", Read);
        }

        static object PublicField(object value, string name)
        {
            if (value == null) return null;
            var field = value.GetType().GetField(name, BindingFlags.Instance | BindingFlags.Public);
            return field == null ? null : field.GetValue(value);
        }

        static object Vector(UnityEngine.Vector3 value)
        {
            return new object[] { value.x, value.y, value.z };
        }

        static Dictionary<string, object> Read(Dictionary<string, object> query)
        {
            var net = Singleton<NetManager>.instance;
            var rows = new List<object>();
            for (int id = 1; id < net.m_segments.m_buffer.Length; id++)
            {
                var s = net.m_segments.m_buffer[id];
                if ((s.m_flags & (NetSegment.Flags.Created | NetSegment.Flags.Deleted)) != NetSegment.Flags.Created)
                    continue;
                var info = s.Info;
                if (info == null || info.m_lanes == null) continue;
                bool train = false;
                foreach (var l in info.m_lanes)
                    if ((l.m_vehicleType & VehicleInfo.VehicleType.Train) != 0) train = true;
                if (!train) continue;
                var lanes = new List<object>();
                uint lane = s.m_lanes;
                for (int i = 0; i < info.m_lanes.Length; i++)
                {
                    var l = info.m_lanes[i];
                    bool eligible = (l.m_vehicleType & VehicleInfo.VehicleType.Train) != 0
                        && (l.m_laneType & (NetInfo.LaneType.Vehicle | NetInfo.LaneType.TransportVehicle | NetInfo.LaneType.CargoVehicle)) != 0;
                    lanes.Add(Host.Obj("index", i, "id", lane == 0 ? null : (object)lane,
                        "type", l.m_laneType.ToString(), "vehicle", l.m_vehicleType.ToString(),
                        "category", l.vehicleCategory.ToString(), "eligible", eligible,
                        "authored_direction_bits", (int)l.m_direction,
                        "direction_bits", (int)l.m_finalDirection,
                        "flags", lane == 0 ? null : (object)net.m_lanes.m_buffer[lane].m_flags.ToString()));
                    if (lane != 0) lane = net.m_lanes.m_buffer[lane].m_nextLane;
                }
                rows.Add(Host.Obj("id", id, "start", s.m_startNode, "end", s.m_endNode,
                    "a", Vector(net.m_nodes.m_buffer[s.m_startNode].m_position),
                    "b", Vector(net.m_nodes.m_buffer[s.m_endNode].m_position),
                    "start_direction", Vector(s.m_startDirection), "end_direction", Vector(s.m_endDirection),
                    "flags", s.m_flags.ToString(), "flags2", s.m_flags2.ToString(),
                    "start_flags", net.m_nodes.m_buffer[s.m_startNode].m_flags.ToString(),
                    "end_flags", net.m_nodes.m_buffer[s.m_endNode].m_flags.ToString(),
                    "prefab", info.name, "lanes", lanes,
                    "prefab_max_turn_angle_cos", PublicField(info, "m_maxTurnAngleCos"),
                    "prefab_max_turn_angle", PublicField(info, "m_maxTurnAngle"),
                    "override_direction_limit", PublicField(s, "m_overrideDirectionLimit")));
            }
            string hash;
            using (var hasher = SHA256.Create())
                hash = BitConverter.ToString(hasher.ComputeHash(Encoding.UTF8.GetBytes(Json.Write(rows))))
                    .Replace("-", "").ToLowerInvariant();
            return Host.Obj("sha256", hash,
                "segments", Json.Bool(query, "digest_only", false) ? null : (object)rows,
                "count", rows.Count, "frame", Singleton<SimulationManager>.instance.m_currentFrameIndex,
                "provenance", "public runtime fields only; unavailable fields are null");
        }
    }
}
