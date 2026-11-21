#if TRACE_OBSERVER
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using ColossalFramework;
using Harmony;

namespace Cs1Harness
{
    public static class TraceOps
    {
        public const string Owner = "polli.pl912.disposable.atomic.trace";
        public const string HarmonyHash = "e271d22a7c32bfca105d0e471c04eee14eec6142d37a30cd73cb7d32c7d1dd0f";
        static HarmonyInstance harmony;
        static MethodInfo original;

        public static void Register()
        {
            Host.Register("trace_arm", Needs.MainMenu, "disposable pinned observer: {sources,cells,controls,binding,dependency_path}", Arm);
            Host.Register("trace_arm_loaded", Needs.City, "arm an observer on a paused disposable city with the same explicit bindings", ArmLoaded);
            Host.Register("trace_finish", Needs.City, "stop and export completed updates with a published checkpoint; then end disposable Session: {dir}", Finish);
        }

        static Dictionary<string, object> Arm(Dictionary<string, object> request)
        {
            if (harmony != null) throw new Exception("one atomic trace per disposable process");
            if (Environment.MachineName != "blade" || Environment.GetEnvironmentVariable("DISPLAY") != ":57")
                throw new Exception("trace is authorized only on blade's private :57");
            string enginePath = "/peach-pool/peach/Games/SteamLibrary/steamapps/common/Cities_Skylines/Cities_Data/Managed/Assembly-CSharp.dll";
            string dependencyPath = Json.Str(request, "dependency_path", "");
            if (!Path.IsPathRooted(dependencyPath) ||
                TraceIL.Hash(File.ReadAllBytes(enginePath)) != TraceIL.Engine ||
                TraceIL.Hash(File.ReadAllBytes(dependencyPath)) != HarmonyHash ||
                typeof(WaterSimulation).Assembly.ManifestModule.ModuleVersionId.ToString() != "dfdbd2a3-d411-405b-b161-0caa98a9bdb2" ||
                typeof(HarmonyInstance).Assembly.ManifestModule.ModuleVersionId.ToString() != "1b235470-4299-4e96-b8b6-361dbe3791d9")
                throw new Exception("trace engine/dependency hash mismatch");
            original = typeof(WaterSimulation).GetMethod("SimulateWater", BindingFlags.Instance | BindingFlags.NonPublic);
            if (TraceIL.Hash(original.GetMethodBody().GetILAsByteArray()) != TraceIL.Body) throw new Exception("trace IL mismatch");
            harmony = HarmonyInstance.Create(Owner);
            var prior = harmony.GetPatchInfo(original);
            if (prior != null && prior.Owners.Count > 0) throw new Exception("solver already has patches");
            TraceRecorder.Arm(request);
            harmony.Patch(original, transpiler: new HarmonyMethod(typeof(TraceIL).GetMethod("Transpile")));
            if (TraceIL.Proof == null) throw new Exception("inverse IL proof missing");
            return Host.Obj("armed", true, "engine", TraceIL.Engine, "harmony", HarmonyHash, "proof", TraceIL.Proof,
                "configuration", TraceRecorder.Configuration, "native_trace_yet", false,
                "loaded_engine_mvid", typeof(WaterSimulation).Assembly.ManifestModule.ModuleVersionId.ToString(),
                "loaded_dependency_mvid", typeof(HarmonyInstance).Assembly.ManifestModule.ModuleVersionId.ToString());
        }

        static Dictionary<string, object> ArmLoaded(Dictionary<string, object> request)
        {
            if (!Singleton<SimulationManager>.instance.SimulationPaused) throw new Exception("pause before arming a loaded city");
            return Arm(request);
        }

        static Dictionary<string, object> Finish(Dictionary<string, object> request)
        {
            if (harmony == null) throw new Exception("trace was not armed");
            if (!Singleton<SimulationManager>.instance.SimulationPaused) throw new Exception("pause before finishing observer");
            TraceRecorder.Stop();
            // A paused solver may be waiting inside its current update. Do not
            // repatch its executing code or read its mutable tail. The owning
            // Session ends this disposable process and removes the installed mod.
            string directory = Json.Str(request, "dir", "");
            if (!Path.IsPathRooted(directory)) throw new Exception("trace output needs absolute directory");
            return TraceRecorder.Export(directory, false);
        }
    }
}
#endif
