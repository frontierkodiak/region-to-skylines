using System;
using System.Collections.Generic;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using Harmony;
using Harmony.ILCopying;
using Cs1Harness;
public static class Proof
{
    public static int Copies, Finally;
    [MethodImpl(MethodImplOptions.NoInlining)]
    public static int Arithmetic(int value)
    { try { if(value<0)return -value; return value*7+3; } finally { Finally++; } }
    public static void Copy() {Copies++;}
    public static IEnumerable<CodeInstruction> Observe(IEnumerable<CodeInstruction> input)
    {
        foreach(var original in input)
        {
            if(original.opcode==OpCodes.Ret)
            {
                var call=new CodeInstruction(OpCodes.Call,typeof(Proof).GetMethod("Copy"));
                call.labels.AddRange(original.labels);original.labels.Clear();
                call.blocks.AddRange(original.blocks);original.blocks.Clear();
                yield return call;
            }
            yield return original;
        }
    }
    public static int Main(string[] args)
    {
        int checkedMethods=0;
        foreach(var callback in typeof(TraceRecorder).GetMethods(BindingFlags.Static|BindingFlags.Public|BindingFlags.NonPublic))
        {
            if(callback.GetMethodBody()==null)continue;
            var scratch=DynamicTools.CreateDynamicMethod(callback,"_stores");
            foreach(var instruction in MethodBodyReader.GetInstructions(scratch.GetILGenerator(),callback))
            {
                var field=instruction.operand as FieldInfo;
                if(field!=null && (instruction.opcode==OpCodes.Stfld || instruction.opcode==OpCodes.Stsfld) &&
                    (field.DeclaringType==typeof(WaterSimulation) || field.DeclaringType==typeof(WaterSource) ||
                     field.DeclaringType==typeof(WaterSimulation.Cell) || field.DeclaringType==typeof(TerrainManager) ||
                     field.DeclaringType==typeof(SimulationManager)))return 8;
            }
            checkedMethods++;
        }
        Console.WriteLine("callback_native_field_stores=0 methods="+checkedMethods);
        var method=typeof(WaterSimulation).GetMethod("SimulateWater",BindingFlags.Instance|BindingFlags.NonPublic);
        var dm=DynamicTools.CreateDynamicMethod(method,"_proof");
        var copier=new MethodCopier(method,dm.GetILGenerator());
        copier.AddTranspiler(typeof(TraceIL).GetMethod("Transpile"));
        copier.Finalize(new List<Label>(),new List<ExceptionBlock>());
        foreach(var pair in TraceIL.Proof)Console.WriteLine(pair.Key+"="+pair.Value);
        if(!(bool)TraceIL.Proof["inverse_exact"])return 2;
        var arithmetic=typeof(Proof).GetMethod("Arithmetic");
        int original=Arithmetic(10), originalNegative=Arithmetic(-4);
        var harmony=HarmonyInstance.Create("cpu.readonly.proof");
        harmony.Patch(arithmetic,transpiler:new HarmonyMethod(typeof(Proof).GetMethod("Observe")));
        int observed=Arithmetic(10), observedNegative=Arithmetic(-4);
        Console.WriteLine("arithmetic="+observed+","+observedNegative+" copies="+Copies+" finally="+Finally);
        if(observed!=original || observedNegative!=originalNegative || Copies!=2 || Finally!=4)return 3;
        harmony.UnpatchAll("cpu.readonly.proof");
        if(Arithmetic(10)!=original || Copies!=2 || Finally!=5)return 4;
        Console.WriteLine("cpu_patch_and_removal=pass");
        return 0;
    }
}
