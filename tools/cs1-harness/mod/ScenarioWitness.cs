using System;
using System.Collections;
using System.Collections.Generic;
using ColossalFramework;
using UnityEngine;

namespace Cs1Harness
{
    public static partial class ScenarioOps
    {
        static void RegisterWitness()
        {
            Host.Register("capability_witness", Needs.City,
                "execute one pre-recorded start witness in a fresh paused city; no search or fallback; poll job", Witness);
            Host.Register("capability_water", Needs.City,
                "read exact-point native water quality/velocity, not a sustained-service verdict: {points:[[x,z]]}", WitnessWater);
        }

        static Vector3 WitnessPoint(object input)
        {
            var p = input as List<object>;
            if (p == null || p.Count != 3) throw new Exception("witness point needs [x,y,z]");
            var v = new Vector3(Convert.ToSingle(p[0]), Convert.ToSingle(p[1]), Convert.ToSingle(p[2]));
            if (float.IsNaN(v.x) || float.IsNaN(v.y) || float.IsNaN(v.z)
                || float.IsInfinity(v.x) || float.IsInfinity(v.y) || float.IsInfinity(v.z)
                || Mathf.Abs(v.x) > 8640 || Mathf.Abs(v.z) > 8640 || v.y < 0 || v.y > 1024)
                throw new Exception("witness point is nonfinite or outside the map");
            return v;
        }

        static Dictionary<string, object> Witness(Dictionary<string, object> q)
        {
            var w = q["witness"] as Dictionary<string, object>;
            string hash = Json.Str(q, "witness_sha256", "");
            if (w == null || Json.Num(w, "schema", 0) != 1 || hash.Length != 64)
                throw new Exception("schema1 witness and SHA256 binding required");
            foreach (char c in hash) if (!Uri.IsHexDigit(c)) throw new Exception("invalid witness digest");
            var points = w["points"] as Dictionary<string, object>;
            var bindings = w["bindings"] as Dictionary<string, object>;
            var steps = w["steps"] as List<object>;
            if (points == null || points.Count > 64 || bindings == null || bindings.Count != 2
                || steps == null || steps.Count == 0 || steps.Count > 64)
                throw new Exception("bounded points, two hookups and ordered steps required");
            foreach (var point in points) WitnessPoint(point.Value);
            foreach (var input in steps)
            {
                var step = input as Dictionary<string, object>;
                if (step == null || !points.ContainsKey(Json.Str(step,"from",""))
                    || !points.ContainsKey(Json.Str(step,"to","")) || Json.Str(step,"prefab","") != "Basic Road")
                    throw new Exception("step must reference declared points and Basic Road");
                double elevation = Json.Num(step,"end_elevation",0);
                if (double.IsNaN(elevation) || double.IsInfinity(elevation) || elevation < 0 || elevation > 64)
                    throw new Exception("invalid declared end elevation");
            }
            var centerXZ = w["center_xz"] as List<object>;
            float half = (float)Json.Num(w,"footprint_half_m",0);
            if (centerXZ == null || centerXZ.Count != 2 || float.IsNaN(half) || float.IsInfinity(half) || half < 144 || half > 256)
                throw new Exception("declared bounded footprint required");
            WitnessPoint(new List<object>{centerXZ[0],0,centerXZ[1]});
            var sm = Singleton<SimulationManager>.instance;
            string instance = sm.m_metaData.m_gameInstanceIdentifier;
            if (city == instance && state != "idle") throw new Exception("fixture already attempted; use fresh New Game");
            if (!sm.SimulationPaused || Singleton<DistrictManager>.instance.m_districts.m_buffer[0].m_populationData.m_finalCount != 0)
                throw new Exception("witness needs a paused empty New Game");
            city = instance;
            state = "witness";
            return Host.Obj("job",Jobs.Start("capability_witness",j => WitnessJob(j,w,hash)).Id);
        }

        static IEnumerator WitnessJob(Job job, Dictionary<string,object> w, string hash)
        {
            job.Result["witness_sha256"] = hash;
            job.Result["mode"] = "exact_recorded_plan_no_search";
            job.Result["observed_native_placement"] = null;
            job.Result["observed_start"] = null;
            job.Result["observed_surface_service"] = null;
            job.Result["limitations"] = new object[] {
                "Placement is not an outside car path or first-hour service verdict",
                "No adaptive site, order, route, bridge, or groundwater fallback",
                "Native tool terrain snapping is recorded at actual node poses"
            };
            var records = new List<object>();
            job.Result["steps"] = records;
            job.Note("validate bindings and execute exact recorded plan");
            bool complete = false;
            Singleton<SimulationManager>.instance.AddAction(() =>
            {
                try { ExecuteWitness(job,w,records); }
                catch (PlacementRejected e)
                {
                    job.Result["observed_native_placement"] = false;
                    job.Result["failure_kind"] = "native_tool_rejection";
                    job.Result["error"] = e.Message;
                    job.Result["tool_errors"] = e.Errors.ToString();
                    job.Result["colliding_segments"] = e.SegmentHits;
                    job.Result["colliding_buildings"] = e.BuildingHits;
                }
                catch (Exception e)
                {
                    // A setup/binding error is unscored, never a map negative.
                    job.Result["failure_kind"] = "setup_or_binding";
                    job.Result["error"] = e.ToString();
                }
                finally { complete = true; }
            });
            yield return Jobs.Until(() => complete,60,"exact witness simulation action");
        }

        static void ExecuteWitness(Job job, Dictionary<string,object> w, List<object> records)
        {
            var net = Singleton<NetManager>.instance;
            var tm = Singleton<TerrainManager>.instance;
            int tx,tz;
            Singleton<GameAreaManager>.instance.GetStartTile(out tx,out tz);
            if (tx+tz*5 != (int)Json.Num(w,"start_tile",-1)) throw new Exception("start tile binding mismatch");
            var points = (Dictionary<string,object>)w["points"];
            var bindings = (Dictionary<string,object>)w["bindings"];
            var ids = new Dictionary<string,ushort>();
            var resolved = new Dictionary<string,object>();
            job.Result["bindings"] = resolved;
            foreach (var input in bindings)
            {
                var binding = input.Value as Dictionary<string,object>;
                if (binding == null || !points.ContainsKey(input.Key)) throw new Exception("missing hookup binding");
                var expected = WitnessPoint(points[input.Key]);
                if ((expected-WitnessPoint(binding["position"])).sqrMagnitude > .0001f)
                    throw new Exception("binding and declared point disagree");
                ushort match=0;
                int count=0;
                for (int i=1;i<net.m_nodes.m_buffer.Length;i++)
                {
                    var n=net.m_nodes.m_buffer[i];
                    if ((n.m_flags & (NetNode.Flags.Created|NetNode.Flags.Deleted|NetNode.Flags.Outside)) != NetNode.Flags.Created
                        || n.Info == null || !(n.Info.m_netAI is RoadBaseAI) || n.CountSegments() != 1
                        || (n.m_position-expected).sqrMagnitude > 4) continue;
                    match=(ushort)i; count++;
                }
                if (count != 1) throw new Exception("hookup must match exactly one native road end within2m: "+input.Key+" matches="+count);
                if (ids.ContainsValue(match)) throw new Exception("two bindings resolved to one node");
                ids[input.Key]=match;
                resolved[input.Key]=Host.Obj("node",match,"position",XYZ(net.m_nodes.m_buffer[match].m_position),
                    "prefab",net.m_nodes.m_buffer[match].Info.name,"flags",net.m_nodes.m_buffer[match].m_flags.ToString());
            }
            var c=(List<object>)w["center_xz"];
            float cx=Convert.ToSingle(c[0]),cz=Convert.ToSingle(c[1]);
            float half=(float)Json.Num(w,"footprint_half_m",0);
            float low=float.MaxValue,high=float.MinValue,maxDepth=0;
            bool inside=true;
            for (float z=-half;z<=half;z+=16)
                for (float x=-half;x<=half;x+=16)
                {
                    var p=Ground(cx+x,cz+z);
                    inside &= Inside(p,16);
                    low=Mathf.Min(low,p.y); high=Mathf.Max(high,p.y);
                    float floor,surface; Vector3 velocity,normal;
                    if (tm.SampleWaterData(new Vector2(p.x,p.z),out floor,out surface,out velocity,out normal))
                        maxDepth=Mathf.Max(maxDepth,surface-p.y);
                }
            job.Result["site"] = Host.Obj("inside_start",inside,"native_relief_m",high-low,
                "max_sampled_depth_m",maxDepth,"spacing_m",16);
            if (!inside || maxDepth>.1f || high-low>8)
            {
                job.Result["observed_native_placement"]=false;
                job.Result["failure_kind"]="native_footprint_rejection";
                return;
            }
            var road=Net("Basic Road");
            roads.Clear();
            int index=0;
            foreach (Dictionary<string,object> step in (List<object>)w["steps"])
            {
                string from=Json.Str(step,"from",""),to=Json.Str(step,"to","");
                ushort a=ids.ContainsKey(from)?ids[from]:(ushort)0,b=ids.ContainsKey(to)?ids[to]:(ushort)0;
                var record=Host.Obj("index",index++,"from_key",from,"to_key",to,"from_node",a,"to_node",b,"status","attempting");
                records.Add(record);
                var endpoints=new List<ushort>();
                Link(road,WitnessPoint(points[from]),WitnessPoint(points[to]),a,b,true,
                    (float)Json.Num(step,"end_elevation",0),endpoints:endpoints);
                if (endpoints.Count!=2) throw new Exception("native link did not return two endpoints");
                ids[from]=endpoints[0]; ids[to]=endpoints[1];
                record["status"]="accepted";
                record["from_node"]=endpoints[0]; record["to_node"]=endpoints[1];
                record["from_position"]=XYZ(net.m_nodes.m_buffer[endpoints[0]].m_position);
                record["to_position"]=XYZ(net.m_nodes.m_buffer[endpoints[1]].m_position);
                record["segment"]=roads[roads.Count-1];
            }
            job.Result["observed_native_placement"]=true;
            job.Result["created_segments"]=roads.ToArray();
            job.Result["nodes"]=ids;
            // Reuse the existing, non-adaptive native car-path observer. It
            // probes this exact grid against all authored native edge roads.
            state="done";
        }

        static Dictionary<string,object> WitnessWater(Dictionary<string,object> q)
        {
            var points=q["points"] as List<object>;
            if (points==null || points.Count>256) throw new Exception("at most256 exact points required");
            var tm=Singleton<TerrainManager>.instance;
            var water=tm.WaterSimulation;
            var result=new List<object>();
            var cells=water.BeginRead();
            try
            {
                foreach (var input in points)
                {
                    var p=WitnessPoint(input);
                    int x=Mathf.RoundToInt((p.x+8640)/16),z=Mathf.RoundToInt((p.z+8640)/16);
                    var cell=cells[z*1081+x];
                    result.Add(Host.Obj("point",XYZ(p),"cell",new object[]{x,z},
                        "depth_m",cell.m_height/64f,"pollution_native",cell.m_pollution,
                        "velocity_native",new object[]{cell.m_velocityX,cell.m_velocityZ}));
                }
            }
            finally { water.EndRead(); }
            return Host.Obj("frame",Singleton<SimulationManager>.instance.m_currentFrameIndex,
                "samples",result,"rate_units","native, SI conversion not established",
                "observed_surface_service",null);
        }
    }
}
