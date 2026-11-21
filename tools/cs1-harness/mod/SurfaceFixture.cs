using System;
using System.Collections;
using System.Collections.Generic;
using System.Threading;
using ColossalFramework;
using ColossalFramework.Math;
using UnityEngine;

namespace Cs1Harness
{
    public static partial class ScenarioOps
    {
        sealed class SurfaceTransfer
        {
            public int Ready;
            public Dictionary<string,object> Row;
        }

        static void RegisterSurfaceFixture()
        {
            Host.Register("capability_surface",Needs.City,
                "fixed surface-intake/outlet load fixture; controlled auxiliary power; one recorded shore snap each; poll job",SurfaceFixture);
        }

        static Dictionary<string,object> SurfaceFixture(Dictionary<string,object> q)
        {
            var w=q["witness"] as Dictionary<string,object>;
            string hash=Json.Str(q,"witness_sha256","");
            if (w==null || Json.Num(w,"schema",0)!=1 || hash.Length!=64)
                throw new Exception("schema1 surface witness and digest required");
            foreach(char c in hash) if(!Uri.IsHexDigit(c)) throw new Exception("invalid witness digest");
            var load=w["load"] as Dictionary<string,object>;
            var facilities=w["facilities"] as List<object>;
            if (load==null || facilities==null || facilities.Count!=2
                || Json.Num(load,"native_units_per_cycle",0)!=1000 || Json.Num(load,"cycle_frames",0)!=256
                || Json.Num(load,"settling_game_minutes",0)!=2 || Json.Num(load,"horizon_game_minutes",0)!=60
                || Json.Num(load,"auxiliary_power_rate",0)!=1000 || Json.Num(load,"max_pollution_native",-1)!=0)
                throw new Exception("unsupported fixed load contract");
            string[] names={"Water Intake","Water Outlet"};
            for(int i=0;i<2;i++)
            {
                var f=facilities[i] as Dictionary<string,object>;
                if(f==null || Json.Str(f,"prefab","")!=names[i]
                    || Json.Str(f,"placement","")!="one_native_shore_snap"
                    || Json.Num(f,"shore_snap_radius_m",0)!=50)
                    throw new Exception("unsupported exact surface facility contract");
                WitnessPoint(f["anchor"]);
            }
            WitnessPoint(w["consumer_point"]);
            var sm=Singleton<SimulationManager>.instance;
            string instance=sm.m_metaData.m_gameInstanceIdentifier;
            if(city==instance && state!="idle") throw new Exception("fixture already attempted; use fresh New Game");
            if(!sm.SimulationPaused || Singleton<DistrictManager>.instance.m_districts.m_buffer[0].m_populationData.m_finalCount!=0)
                throw new Exception("surface fixture needs paused empty New Game");
            city=instance;state="surface";
            return Host.Obj("job",Jobs.Start("capability_surface",j=>SurfaceJob(j,w,hash)).Id);
        }

        // Publish complete records across threads; only the main-thread iterator
        // changes Job.Result, so a simultaneous job RPC sees a stable snapshot.
        static IEnumerator SurfaceAction(Func<Dictionary<string,object>> action,SurfaceTransfer transfer)
        {
            Singleton<SimulationManager>.instance.AddAction(()=>
            {
                try { transfer.Row=action(); }
                catch(PlacementRejected e)
                {
                    transfer.Row=Host.Obj("kind",(e.Errors & ToolBase.ToolErrors.NotEnoughMoney)!=0 ? "fixture_resource_failure":"native_tool_rejection",
                        "error",e.Message,"tool_errors",e.Errors.ToString(),
                        "colliding_segments",e.SegmentHits,"colliding_buildings",e.BuildingHits);
                }
                catch(Exception e) { transfer.Row=Host.Obj("kind","fixture_setup_failure","error",e.ToString()); }
                finally { Interlocked.Exchange(ref transfer.Ready,1); }
            });
            yield return Jobs.Until(()=>Interlocked.CompareExchange(ref transfer.Ready,0,0)==1,60,"surface simulation action");
        }

        static IEnumerator SurfaceJob(Job job,Dictionary<string,object> w,string hash)
        {
            job.Result["witness_sha256"]=hash;
            job.Result["mode"]="fixed_surface_load_no_search";
            job.Result["observed_native_placement"]=null;
            job.Result["observed_surface_service"]=null;
            job.Result["observed_water_capability"]=null;
            job.Result["limits"]=new object[]{
                "One native shore snap at each declared anchor, then native checked placement; no alternate site",
                "1000 native water/sewage units per256simulationframes, 2min settling and60min load",
                "Auxiliary electricity held available through native supply API; not a power-generation or whole-game promise",
                "No SI-rate or population-equivalence conversion; no groundwater or water-source replacement"
            };
            var facilities=new List<ushort>();
            var setupRecords=new List<object>();
            ushort consumer=0;
            var setup=new SurfaceTransfer();
            yield return SurfaceAction(()=>SetupSurface(w,facilities,setupRecords,out consumer),setup);
            job.Result["setup"]=setup.Row;
            job.Result["placement_records"]=setupRecords.ToArray();
            string kind=Json.Str(setup.Row,"kind","");
            if(kind!="ready")
            {
                if(kind=="native_tool_rejection")
                {
                    job.Result["observed_native_placement"]=false;
                    job.Result["observed_water_capability"]=false;
                }
                else if(kind=="native_shore_snap_rejection")
                {
                    job.Result["observed_shore_snap"]=false;
                    job.Result["observed_water_capability"]=false;
                }
                yield break;
            }
            job.Result["observed_native_placement"]=true;
            var sm=Singleton<SimulationManager>.instance;
            double framesPerMinute=60.0/Time.fixedDeltaTime;
            if(double.IsNaN(framesPerMinute) || framesPerMinute<=0) throw new Exception("invalid native frame clock");
            job.Result["frames_per_game_minute"]=framesPerMinute;
            uint start=sm.m_currentFrameIndex;
            uint loadStart=start+(uint)(2*framesPerMinute),target=loadStart+(uint)(60*framesPerMinute);
            uint next=start;
            long fetched=0,sewage=0,requested=0;
            int cycles=0,shortWater=0,shortSewage=0,dirty=0,auxiliaryFailures=0;
            bool timingFailure=false;
            var samples=new List<object>();
            job.Result["samples"]=samples;
            sm.SelectedSimulationSpeed=3;sm.SimulationPaused=false;
            float deadline=Time.realtimeSinceStartup+3600;
            uint lastFrame=start;
            float lastProgress=Time.realtimeSinceStartup;
            while(sm.m_currentFrameIndex<target)
            {
                if(Time.realtimeSinceStartup>deadline) throw new Exception("surface fixture wall deadline reached");
                if(sm.m_currentFrameIndex!=lastFrame)
                { lastFrame=sm.m_currentFrameIndex;lastProgress=Time.realtimeSinceStartup; }
                else if(Time.realtimeSinceStartup-lastProgress>60) throw new Exception("surface fixture simulation stalled");
                if(sm.m_currentFrameIndex<next) { yield return null;continue; }
                bool loaded=sm.m_currentFrameIndex>=loadStart;
                uint due=next;
                var cycle=new SurfaceTransfer();
                yield return SurfaceAction(()=>SurfaceCycle(facilities,consumer,loaded,due),cycle);
                if(Json.Str(cycle.Row,"kind","")!="cycle")
                { job.Result["failure"]=cycle.Row;sm.SimulationPaused=true;yield break; }
                uint frame=Convert.ToUInt32(cycle.Row["frame"]);
                if(frame-due>=512) timingFailure=true;
                next=due+256;
                if(loaded)
                {
                    cycles++;requested+=1000;
                    int water=Convert.ToInt32(cycle.Row["fetched"]),dump=Convert.ToInt32(cycle.Row["sewage"]);
                    fetched+=water;sewage+=dump;
                    if(water<1000) shortWater++;
                    if(dump<1000) shortSewage++;
                    if(Convert.ToInt32(cycle.Row["pollution_native"])>0) dirty++;
                    if(!(bool)cycle.Row["auxiliary_valid"]) auxiliaryFailures++;
                    samples.Add(cycle.Row);
                }
                job.Result["elapsed_load_game_minutes"]=frame>=loadStart?(frame-loadStart)/framesPerMinute:0;
                job.Result["cycles"]=cycles;
            }
            sm.SimulationPaused=true;
            job.Result["requested_native_units"]=requested;
            job.Result["fetched_native_units"]=fetched;
            job.Result["sewage_accepted_native_units"]=sewage;
            job.Result["short_water_cycles"]=shortWater;
            job.Result["short_sewage_cycles"]=shortSewage;
            job.Result["polluted_delivery_cycles"]=dirty;
            job.Result["auxiliary_failure_cycles"]=auxiliaryFailures;
            job.Result["timing_failure"]=timingFailure;
            int expectedCycles=(int)((target-start-1)/256)-(int)Math.Ceiling((loadStart-start)/256.0)+1;
            job.Result["expected_load_cycles"]=expectedCycles;
            job.Result["observed_horizon_game_minutes"]=(sm.m_currentFrameIndex-loadStart)/framesPerMinute;
            bool qualified=cycles==expectedCycles && cycles>0 && !timingFailure && auxiliaryFailures==0;
            job.Result["fixture_qualified"]=qualified;
            if(qualified)
            {
                bool passed=shortWater==0 && shortSewage==0 && dirty==0;
                job.Result["observed_surface_service"]=passed;
                job.Result["observed_water_capability"]=passed;
            }
        }

        static Dictionary<string,object> SetupSurface(Dictionary<string,object> w,List<ushort> facilities,List<object> records,out ushort consumer)
        {
            consumer=0;
            int tx,tz;
            Singleton<GameAreaManager>.instance.GetStartTile(out tx,out tz);
            if(tx+tz*5!=(int)Json.Num(w,"start_tile",-1)) throw new Exception("surface start tile binding mismatch");
            buildings.Clear();
            var tm=Singleton<TerrainManager>.instance;
            foreach(Dictionary<string,object> f in (List<object>)w["facilities"])
            {
                var info=PrefabCollection<BuildingInfo>.FindLoaded(Json.Str(f,"prefab",""));
                var ai=info==null?null:info.m_buildingAI as WaterFacilityAI;
                if(ai==null || ai.m_useGroundWater) throw new Exception("surface-only native prefab required");
                var anchor=WitnessPoint(f["anchor"]);
                var groundedAnchor=Ground(anchor.x,anchor.z);
                Vector3 p,dir;float water;
                var record=Host.Obj("prefab",info.name,"anchor",XYZ(anchor),"placement_offset",info.m_placementOffset,
                    "grounded_anchor",XYZ(groundedAnchor),"status","shore_snap_attempting");
                records.Add(record);
                if(!tm.GetShorePos(groundedAnchor,50,out p,out dir,out water))
                    return Host.Obj("kind","native_shore_snap_rejection","prefab",info.name);
                record["shore_position"]=XYZ(p);record["shore_direction"]=XYZ(dir);record["water_height"]=water;
                if(VectorUtils.LengthXZ(p-anchor)>50.01f || dir.sqrMagnitude<.01f)
                    throw new Exception("native shore snap exceeded declared witness radius");
                p+=dir.normalized*info.m_placementOffset;
                if(!Inside(p,32)) throw new Exception("snapped facility outside declared fixture startup domain");
                float angle=Mathf.Atan2(dir.x,-dir.z);
                ushort id=Place(info,p,angle,water);
                facilities.Add(id);
                var b=Singleton<BuildingManager>.instance.m_buildings.m_buffer[id];
                record["status"]="native_placement_accepted";record["id"]=id;
                record["actual_position"]=XYZ(b.m_position);record["actual_angle_radians"]=b.m_angle;
                record["native_pipe_node"]=b.m_netNode;
                if(b.m_netNode==0) throw new Exception("native facility lacks pipe node");
            }
            var bm=Singleton<BuildingManager>.instance;
            var net=Singleton<NetManager>.instance;
            ushort intake=bm.m_buildings.m_buffer[facilities[0]].m_netNode,outlet=bm.m_buildings.m_buffer[facilities[1]].m_netNode;
            var point=WitnessPoint(w["consumer_point"]);
            if(!Inside(point,32)) throw new Exception("consumer point outside start tile");
            var pipe=Net("Water Pipe");
            consumer=Link(pipe,Vector3.zero,point,intake);
            Link(pipe,Vector3.zero,Vector3.zero,consumer,outlet);
            return Host.Obj("kind","ready","consumer_node",consumer,"consumer_position",XYZ(net.m_nodes.m_buffer[consumer].m_position),
                "money_after",Singleton<EconomyManager>.instance.InternalCashAmount);
        }

        static Dictionary<string,object> SurfaceFacility(ushort id,out bool auxiliaryValid)
        {
            var b=Singleton<BuildingManager>.instance.m_buildings.m_buffer[id];
            bool powered;
            Singleton<ElectricityManager>.instance.CheckElectricity(b.m_position,out powered);
            bool completed=(b.m_flags & (Building.Flags.Created|Building.Flags.Deleted|Building.Flags.Completed))
                ==(Building.Flags.Created|Building.Flags.Completed);
            auxiliaryValid=completed && powered && b.m_netNode!=0;
            var ai=(WaterFacilityAI)b.Info.m_buildingAI;
            object source=null;
            var water=Singleton<TerrainManager>.instance.WaterSimulation;
            if(b.m_waterSource!=0)
            {
                var s=water.LockWaterSource(b.m_waterSource);
                try { source=Host.Obj("id",b.m_waterSource,"type",s.m_type,"input_rate_native",s.m_inputRate,
                    "output_rate_native",s.m_outputRate,"flow_native",s.m_flow,"pollution_native",s.m_pollution,"buffer_native",s.m_water); }
                finally { water.UnlockWaterSource(b.m_waterSource,s); }
            }
            return Host.Obj("id",id,"position",XYZ(b.m_position),"flags",b.m_flags.ToString(),"problems",b.m_problems.ToString(),
                "completed",completed,"electricity_grid_powered",powered,"electricity_buffer",b.m_electricityBuffer,
                "water_buffer_native",b.m_waterBuffer,"sewage_buffer_native",b.m_sewageBuffer,
                "water_pollution_native",b.m_waterPollution,"water_rate_native",ai.GetWaterRate(id,ref b),"source",source);
        }

        static Dictionary<string,object> SurfaceCycle(List<ushort> facilities,ushort consumer,bool loaded,uint due)
        {
            var bm=Singleton<BuildingManager>.instance;
            var injected=new List<object>();
            foreach(ushort id in facilities)
                injected.Add(Singleton<ElectricityManager>.instance.TryDumpElectricity(bm.m_buildings.m_buffer[id].m_position,1000,1000));
            byte pollution=0;int fetched=0,dumped=0;
            if(loaded)
            {
                var consumerPosition=Singleton<NetManager>.instance.m_nodes.m_buffer[consumer].m_position;
                fetched=Singleton<WaterManager>.instance.TryFetchWater(consumerPosition,1000,1000,ref pollution);
                dumped=Singleton<WaterManager>.instance.TryDumpSewage(consumer,1000,1000);
            }
            bool intakeValid,outletValid;
            var intake=SurfaceFacility(facilities[0],out intakeValid);
            var outlet=SurfaceFacility(facilities[1],out outletValid);
            return Host.Obj("kind","cycle","due_frame",due,"frame",Singleton<SimulationManager>.instance.m_currentFrameIndex,
                "loaded",loaded,"fetched",fetched,"sewage",dumped,"pollution_native",pollution,
                "auxiliary_power_injected_native",injected,"auxiliary_valid",intakeValid && outletValid
                    && Singleton<EconomyManager>.instance.InternalCashAmount>=0,
                "intake",intake,"outlet",outlet);
        }
    }
}
