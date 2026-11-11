using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using ColossalFramework;
using ColossalFramework.IO;
using ColossalFramework.Packaging;
using ColossalFramework.PlatformServices;
using ColossalFramework.UI;
using UnityEngine;

namespace Cs1Harness
{
    // Explicit disposable MapEditor authoring. Never patch a package or allocate IDs.
    public static class TemplateOps
    {
        static string source, sourceHash, state = "idle", error, checkedPlan, exportPath;
        static volatile bool busy;
        static Dictionary<int, string> originalNodes, originalSegments;
        static Dictionary<string, object> originalCounts, lastPlacement;

        public static void Register()
        {
            Host.Register("template_open", Needs.MainMenu, "load an explicit local map in MapEditor, not New Game: {path}", Open);
            Host.Register("template_status", Needs.Level, "MapEditor-only native graph/prefabs/outside buildings and authoring state", Status);
            Host.Register("template_air", Needs.Level, "native straight air path: {prefab,endpoints:[[x,z],[x,z]],apply:false}; test first, then identical apply:true", Air);
            Host.Register("template_export", Needs.Level, "save a new unpublished map through native SaveMapPanel: {name:air-template-...,map_name}", Export);
        }

        static bool Plane(NetInfo info)
        {
            var ai = info == null ? null : info.m_netAI as FlightPathAI;
            return ai != null && ai.m_transportInfo != null
                && ai.m_transportInfo.m_vehicleType == VehicleInfo.VehicleType.Plane
                && info.m_class.m_subService == ItemClass.SubService.PublicTransportPlane;
        }

        static void Editor()
        {
            if (source == null || !Host.LevelLoaded()
                || Singleton<ToolManager>.instance.m_properties.m_mode != ItemClass.Availability.MapEditor
                || Singleton<SimulationManager>.instance.m_metaData.m_updateMode != SimulationManager.UpdateMode.LoadMap
                || Singleton<SimulationManager>.instance.m_metaData.m_SystemMap)
                throw new Exception("requires this helper's disposable, non-system LoadMap editor session");
        }

        static string Hash(byte[] bytes)
        {
            using (var sha = SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
        }
        static object[] XYZ(Vector3 p) { return new object[] { p.x, p.y, p.z }; }
        static bool Live(NetNode n) { return (n.m_flags & (NetNode.Flags.Created | NetNode.Flags.Deleted)) == NetNode.Flags.Created; }
        static bool Live(NetSegment s) { return (s.m_flags & (NetSegment.Flags.Created | NetSegment.Flags.Deleted)) == NetSegment.Flags.Created; }

        static Dictionary<string, object> Counts()
        {
            var result = new Dictionary<string, object>();
            foreach (var pair in new[] {
                new KeyValuePair<string, ItemClass.SubService>("rail", ItemClass.SubService.PublicTransportTrain),
                new KeyValuePair<string, ItemClass.SubService>("air", ItemClass.SubService.PublicTransportPlane),
                new KeyValuePair<string, ItemClass.SubService>("ship", ItemClass.SubService.PublicTransportShip),
                new KeyValuePair<string, ItemClass.SubService>("road", ItemClass.SubService.None) })
            {
                int incoming, outgoing;
                Singleton<BuildingManager>.instance.CalculateOutsideConnectionCount(
                    pair.Key == "road" ? ItemClass.Service.Road : ItemClass.Service.PublicTransport,
                    pair.Value, out incoming, out outgoing);
                result[pair.Key] = Host.Obj("incoming", incoming, "outgoing", outgoing);
            }
            return result;
        }

        static Dictionary<int, string> Fingerprint(bool nodes)
        {
            var result = new Dictionary<int, string>();
            var net = Singleton<NetManager>.instance;
            int count = nodes ? net.m_nodes.m_buffer.Length : net.m_segments.m_buffer.Length;
            for (int id = 1; id < count; id++)
            {
                if (nodes ? !Live(net.m_nodes.m_buffer[id]) : !Live(net.m_segments.m_buffer[id])) continue;
                using (var bytes = new MemoryStream())
                using (var w = new BinaryWriter(bytes))
                {
                    if (nodes)
                    {
                        var n = net.m_nodes.m_buffer[id];
                        w.Write((ulong)n.m_flags); w.Write(n.Info.name); w.Write(n.m_building);
                        w.Write(n.m_position.x); w.Write(n.m_position.y); w.Write(n.m_position.z);
                        for (int j = 0; j < 8; j++) w.Write(n.GetSegment(j));
                    }
                    else
                    {
                        var s = net.m_segments.m_buffer[id];
                        w.Write((uint)s.m_flags); w.Write((uint)s.m_flags2); w.Write(s.Info.name);
                        w.Write(s.m_startNode); w.Write(s.m_endNode); w.Write(s.m_lanes);
                        w.Write(s.m_startDirection.x); w.Write(s.m_startDirection.y); w.Write(s.m_startDirection.z);
                        w.Write(s.m_endDirection.x); w.Write(s.m_endDirection.y); w.Write(s.m_endDirection.z);
                    }
                    w.Flush(); result.Add(id, Hash(bytes.ToArray()));
                }
            }
            return result;
        }

        static void Preserved()
        {
            var nodes = Fingerprint(true); var segments = Fingerprint(false);
            foreach (var p in originalNodes)
                if (!nodes.ContainsKey(p.Key) || nodes[p.Key] != p.Value) throw new Exception("original node changed: " + p.Key);
            foreach (var p in originalSegments)
                if (!segments.ContainsKey(p.Key) || segments[p.Key] != p.Value) throw new Exception("original segment changed: " + p.Key);
            var net = Singleton<NetManager>.instance;
            foreach (int id in nodes.Keys)
                if (!originalNodes.ContainsKey(id) && !Plane(net.m_nodes.m_buffer[id].Info)) throw new Exception("new non-plane node: " + id);
            foreach (int id in segments.Keys)
                if (!originalSegments.ContainsKey(id) && !Plane(net.m_segments.m_buffer[id].Info)) throw new Exception("new non-plane segment: " + id);
            var counts = Counts();
            foreach (string kind in new[] { "road", "rail", "ship" })
                if (Json.Write(counts[kind]) != Json.Write(originalCounts[kind]))
                    throw new Exception("original outside count changed: " + kind);
        }

        static Dictionary<string, object> Info(NetInfo info)
        {
            var lanes = new List<object>();
            foreach (var lane in info.m_lanes)
                lanes.Add(Host.Obj("lane_type", lane.m_laneType.ToString(), "vehicle_types", lane.m_vehicleType.ToString(), "direction", lane.m_direction.ToString()));
            var ai = info.m_netAI as FlightPathAI;
            return Host.Obj("prefab", info.name, "ai", info.m_netAI.GetType().FullName,
                "service", info.m_class.m_service.ToString(), "subservice", info.m_class.m_subService.ToString(),
                "native_plane", Plane(info), "lanes", lanes, "use_fixed_height", info.m_useFixedHeight,
                "connected_prefab", ai == null || ai.m_connectedInfo == null ? null : ai.m_connectedInfo.name,
                "outside_building_prefab", ai == null || ai.m_outsideConnection == null ? null : ai.m_outsideConnection.name);
        }

        static Dictionary<string, object> Graph()
        {
            var net = Singleton<NetManager>.instance;
            var nodes = new List<object>(); var segments = new List<object>();
            for (int i = 1; i < net.m_nodes.m_buffer.Length; i++)
            {
                var n = net.m_nodes.m_buffer[i]; if (!Live(n)) continue;
                var links = new List<object>();
                for (int j = 0; j < 8; j++) if (n.GetSegment(j) != 0) links.Add(n.GetSegment(j));
                var building = Singleton<BuildingManager>.instance.m_buildings.m_buffer[n.m_building];
                nodes.Add(Host.Obj("id", i, "position", XYZ(n.m_position), "flags", n.m_flags.ToString(),
                    "outside", (n.m_flags & NetNode.Flags.Outside) != 0, "prefab", Info(n.Info), "segments", links,
                    "outside_building_id", n.m_building, "building_flags", building.m_flags.ToString(),
                    "building_prefab", building.Info == null ? null : building.Info.name));
            }
            for (int i = 1; i < net.m_segments.m_buffer.Length; i++)
            {
                var s = net.m_segments.m_buffer[i]; if (!Live(s)) continue;
                var lanes = new List<object>(); uint lane = s.m_lanes;
                var seen = new HashSet<uint>();
                while (lane != 0)
                {
                    if (!seen.Add(lane)) throw new Exception("cyclic native lane chain");
                    lanes.Add(lane); lane = net.m_lanes.m_buffer[lane].m_nextLane;
                }
                segments.Add(Host.Obj("id", i, "from", s.m_startNode, "to", s.m_endNode,
                    "flags", s.m_flags.ToString(), "prefab", Info(s.Info), "lane_ids", lanes,
                    "start_direction", XYZ(s.m_startDirection), "end_direction", XYZ(s.m_endDirection)));
            }
            return Host.Obj("nodes", nodes, "segments", segments, "outside_counts", Counts());
        }

        static Dictionary<string, object> Open(Dictionary<string, object> q)
        {
            string path = Path.GetFullPath(Json.Str(q, "path", ""));
            Package.Asset selected = null;
            foreach (var a in PackageManager.FilterAssets(UserAssetType.MapMetaData))
                if (a != null && a.package.packagePath != null && Path.GetFullPath(a.package.packagePath) == path)
                { if (selected != null) throw new Exception("ambiguous map file"); selected = a; }
            if (selected == null) throw new Exception("map must be installed and listed before editor load");
            var meta = selected.Instantiate<MapMetaData>();
            source = path; sourceHash = Hash(File.ReadAllBytes(path)); state = "loading";
            originalNodes = originalSegments = null; originalCounts = lastPlacement = null;
            error = checkedPlan = exportPath = null; busy = false;
            var sim = new SimulationMetaData { m_updateMode = SimulationManager.UpdateMode.LoadMap,
                m_WorkshopPublishedFileId = PublishedFileId.invalid, m_mapEditorMapPackage = selected.fullName };
            if (meta.mapThemeRef != null)
            {
                var theme = PackageManager.FindAssetByName(meta.mapThemeRef, UserAssetType.MapThemeMetaData);
                if (theme != null) { sim.m_MapThemeMetaData = theme.Instantiate<MapThemeMetaData>(); sim.m_MapThemeMetaData.SetSelfRef(theme); }
            }
            if (Singleton<LoadingManager>.instance.LoadLevel(meta.assetRef, "MapEditor", "InMapEditor", sim) == null)
                throw new Exception("native editor load refused");
            return Host.Obj("loading", path, "source_sha256", sourceHash, "update_mode", 1);
        }

        static Dictionary<string, object> Status(Dictionary<string, object> q)
        {
            Editor();
            if (busy) return Host.Obj("state", state, "busy", true);
            if (originalNodes == null)
            {
                originalNodes = Fingerprint(true); originalSegments = Fingerprint(false); originalCounts = Counts();
                if (originalSegments.Count > 2000) throw new Exception("use a small disposable native template");
                foreach (int id in originalSegments.Keys)
                    if (Plane(Singleton<NetManager>.instance.m_segments.m_buffer[id].Info)) throw new Exception("source already has air paths; refusing duplicate authoring");
                var air = (Dictionary<string, object>)originalCounts["air"];
                if (Convert.ToInt32(air["incoming"]) != 0 || Convert.ToInt32(air["outgoing"]) != 0)
                    throw new Exception("source already advertises plane outside buildings");
                state = "ready";
            }
            var prefabs = new List<object>();
            for (uint i = 0; i < PrefabCollection<NetInfo>.LoadedCount(); i++)
            { var info = PrefabCollection<NetInfo>.GetLoaded(i); if (Plane(info)) prefabs.Add(Info(info)); }
            return Host.Obj("state", state, "busy", false, "error", error, "mode", "MapEditor", "update_mode", 1,
                "source_sha256", sourceHash, "graph", Graph(), "plane_prefabs", prefabs,
                "original_node_fingerprints", originalNodes, "original_segment_fingerprints", originalSegments,
                "placement", lastPlacement, "saving", SaveMapPanel.isSaving,
                "export_path", exportPath, "export_sha256", exportPath != null && !SaveMapPanel.isSaving && File.Exists(exportPath) ? Hash(File.ReadAllBytes(exportPath)) : null);
        }

        static NetTool.ControlPoint Point(NetInfo info, List<object> xy)
        {
            if (xy.Count != 2) throw new Exception("endpoint is [x,z]");
            float x = Convert.ToSingle(xy[0]), z = Convert.ToSingle(xy[1]);
            if (float.IsNaN(x) || float.IsInfinity(x) || float.IsNaN(z) || float.IsInfinity(z)
                || Mathf.Max(Mathf.Abs(x), Mathf.Abs(z)) > 8640 || Mathf.Max(Mathf.Abs(x), Mathf.Abs(z)) < 8600)
                throw new Exception("endpoints must be finite and at a native map edge, within +/-8640");
            NetTool.ControlPoint p;
            if (!NetTool.MakeControlPoint(new Ray(new Vector3(x, 2000, z), Vector3.down), 3000,
                info, false, NetNode.Flags.Untouchable, NetSegment.Flags.Untouchable, Building.Flags.All, 0, false, out p)
                || !p.m_outside || p.m_node != 0 || p.m_segment != 0)
                throw new Exception("native endpoint ray/snap did not produce a new outside control point");
            return p;
        }

        static Dictionary<string, object> Air(Dictionary<string, object> q)
        {
            Editor();
            if (busy || originalNodes == null || (state != "ready" && state != "checked")) throw new Exception("inspect source first; only one authoring attempt per disposable editor");
            string prefab = Json.Str(q, "prefab", "");
            var endpoints = (List<object>)q["endpoints"];
            if (endpoints.Count != 2) throw new Exception("two explicit endpoints required");
            string plan = prefab + "|" + Json.Write(endpoints);
            bool apply = Json.Bool(q, "apply", false);
            if (apply && plan != checkedPlan) throw new Exception("identical successful dry run required before apply");
            busy = true; state = "working";
            Singleton<SimulationManager>.instance.AddAction(delegate
            {
                try
                {
                    Editor(); Preserved();
                    if (!Singleton<SimulationManager>.instance.SimulationPaused) throw new Exception("pause editor simulation first");
                    var info = PrefabCollection<NetInfo>.FindLoaded(prefab);
                    var ai = info == null ? null : info.m_netAI as FlightPathAI;
                    if (!Plane(info) || !Plane(ai.m_connectedInfo)
                        || ((FlightPathAI)ai.m_connectedInfo.m_netAI).m_outsideConnection == null)
                        throw new Exception("explicit prefab must have native Plane FlightPathAI, connected prefab and outside building");
                    var a = Point(info, (List<object>)endpoints[0]); var b = Point(info, (List<object>)endpoints[1]);
                    var direction = b.m_position - a.m_position; direction.y = 0;
                    if (direction.magnitude < 16000) throw new Exception("use a single map-spanning route between opposite edges");
                    direction.Normalize(); a.m_direction = b.m_direction = direction;
                    var mid = new NetTool.ControlPoint { m_position = (a.m_position + b.m_position) * 0.5f,
                        m_direction = direction, m_elevation = (a.m_elevation + b.m_elevation) * 0.5f };
                    ushort first, last, segment; int cost, production;
                    var errors = NetTool.CreateNode(info, a, mid, b, new FastList<NetTool.NodePosition>(), 1000,
                        !apply, true, false, true, false, false, false, 0, out first, out last, out segment, out cost, out production);
                    if (errors != ToolBase.ToolErrors.None) throw new Exception("native NetTool placement rejected: " + errors);
                    Preserved();
                    if (!apply && (Fingerprint(true).Count != originalNodes.Count || Fingerprint(false).Count != originalSegments.Count))
                        throw new Exception("native dry run unexpectedly allocated graph entries; discard editor");
                    lastPlacement = Host.Obj("prefab", prefab, "start", XYZ(a.m_position), "end", XYZ(b.m_position),
                        "dry_run", !apply, "first_node", first, "last_node", last, "segment", segment, "native_errors", errors.ToString());
                    checkedPlan = plan; state = apply ? "authored" : "checked";
                    if (apply && (first == 0 || last == 0 || segment == 0)) throw new Exception("native authoring returned missing IDs; discard editor");
                }
                catch (Exception e) { error = e.Message; state = "failed_discard_editor"; }
                finally { busy = false; }
            });
            return Host.Obj("state", state, "busy", true);
        }

        static Dictionary<string, object> Export(Dictionary<string, object> q)
        {
            Editor();
            if (busy || state != "authored") throw new Exception("requires successfully authored native path");
            Preserved();
            var net = Singleton<NetManager>.instance;
            ushort first = Convert.ToUInt16(lastPlacement["first_node"]), last = Convert.ToUInt16(lastPlacement["last_node"]);
            var visited = new HashSet<ushort>(); var pending = new Queue<ushort>(); pending.Enqueue(first);
            int outside = 0;
            while (pending.Count != 0)
            {
                ushort id = pending.Dequeue(); if (!visited.Add(id)) continue;
                var n = net.m_nodes.m_buffer[id];
                if (!Live(n) || !Plane(n.Info) || originalNodes.ContainsKey(id)) throw new Exception("air chain touches an original/non-plane node");
                if ((n.m_flags & NetNode.Flags.Outside) != 0)
                {
                    if (n.m_building == 0) throw new Exception("native outside building not ready");
                    outside++;
                }
                for (int j = 0; j < 8; j++)
                {
                    ushort segment = n.GetSegment(j); if (segment == 0) continue;
                    var s = net.m_segments.m_buffer[segment];
                    if (!Live(s) || !Plane(s.Info) || originalSegments.ContainsKey(segment)) throw new Exception("air chain touches original/non-plane segment");
                    pending.Enqueue(s.m_startNode == id ? s.m_endNode : s.m_startNode);
                }
            }
            if (!visited.Contains(last) || outside != 2 || visited.Count != Fingerprint(true).Count - originalNodes.Count)
                throw new Exception("native air route is not a single connected chain with two outside endpoints");
            var air = (Dictionary<string, object>)Counts()["air"];
            if (Convert.ToInt32(air["incoming"]) < 1 || Convert.ToInt32(air["outgoing"]) < 1)
                throw new Exception("native incoming/outgoing plane buildings not ready; do not fake their flags");
            string name = Json.Str(q, "name", ""), mapName = Json.Str(q, "map_name", "");
            if (!Regex.IsMatch(name, "^air-template-[A-Za-z0-9_-]{1,64}$") || mapName.Trim().Length == 0)
                throw new Exception("use a new air-template-... filename and explicit map_name");
            string path = Path.Combine(DataLocation.mapLocation, name + ".crp");
            if (File.Exists(path) || SaveMapPanel.isSaving) throw new Exception("refusing overwrite or concurrent save");
            UIView.library.Show("SaveMapPanel");
            var root = UIView.library.Get("SaveMapPanel");
            if (root == null || !root.isVisible) throw new Exception("native SaveMapPanel unavailable");
            var panels = root.GetComponentsInChildren<SaveMapPanel>(true);
            if (panels.Length != 1) throw new Exception("expected exactly one native SaveMapPanel");
            root.Find<UITextField>("SaveName").text = name;
            root.Find<UITextField>("MapName").text = mapName;
            root.Find<UICheckBox>("Publish").isChecked = false;
            exportPath = path; panels[0].OnSave(); state = "export_requested";
            return Host.Obj("path", path, "saving", SaveMapPanel.isSaving, "published", false);
        }
    }
}
