#if TRACE_OBSERVER
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Reflection;
using System.Reflection.Emit;
using System.Security.Cryptography;
using System.Text;
using Harmony;
using Harmony.ILCopying;

namespace Cs1Harness
{
    // Hash-bound observation only. No original instruction is deleted or changed.
    public static class TraceIL
    {
        public const string Engine = "c7f0e723dfe867d10aef73f14268bcf9f5ea4bab1c5ce4987897ed27f46511a1";
        public const string Body = "eef2d18b29f0ff396b792dd45ec06c26c5181652985975a7cd93b9e46bb432bc";
        public static Dictionary<string, object> Proof;

        public static string Hash(byte[] bytes)
        {
            using (var hash = new SHA256Managed())
                return BitConverter.ToString(hash.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
        }

        static CodeInstruction Copy(CodeInstruction source)
        {
            var copy = new CodeInstruction(source.opcode, source.operand);
            copy.labels.AddRange(source.labels);
            copy.blocks.AddRange(source.blocks);
            return copy;
        }

        static string Canonical(List<CodeInstruction> codes)
        {
            var labels = new Dictionary<Label, int>();
            for (int i = 0; i < codes.Count; i++) foreach (var l in codes[i].labels) labels[l] = i;
            var text = new StringBuilder();
            foreach (var code in codes)
            {
                foreach (var block in code.blocks)
                    text.Append("EH:").Append(block.blockType).Append(':').Append(block.catchType).Append(';');
                text.Append(code.opcode.Value).Append(':');
                object value = code.operand;
                if (value is Label) text.Append("L").Append(labels[(Label)value]);
                else if (value is Label[]) foreach (var l in (Label[])value) text.Append("L").Append(labels[l]).Append(',');
                else if (value is LocalBuilder)
                {
                    var local = (LocalBuilder)value;
                    text.Append("V").Append(local.LocalIndex).Append(':').Append(local.LocalType.FullName);
                }
                else if (value is MemberInfo)
                {
                    var member = (MemberInfo)value;
                    text.Append(member.Module.ModuleVersionId).Append(':').Append(member.MetadataToken).Append(':').Append(member.DeclaringType);
                }
                else if (value is float) text.Append(BitConverter.ToString(BitConverter.GetBytes((float)value)));
                else if (value is double) text.Append(BitConverter.ToString(BitConverter.GetBytes((double)value)));
                else if (value != null) text.Append(Convert.ToString(value, CultureInfo.InvariantCulture));
                text.Append('\n');
            }
            return Hash(Encoding.UTF8.GetBytes(text.ToString()));
        }

        static List<CodeInstruction> Call(string name, params int[] locals)
        {
            var result = new List<CodeInstruction> { new CodeInstruction(OpCodes.Ldarg_0) };
            foreach (int local in locals) result.Add(new CodeInstruction(OpCodes.Ldloc, (short)local));
            result.Add(new CodeInstruction(OpCodes.Call, typeof(TraceRecorder).GetMethod(name)));
            return result;
        }

        static int Local(CodeInstruction code)
        {
            var local = code.operand as LocalBuilder;
            return local == null ? -1 : local.LocalIndex;
        }

        public static IEnumerable<CodeInstruction> Transpile(IEnumerable<CodeInstruction> instructions, MethodBase original)
        {
            if (Hash(original.GetMethodBody().GetILAsByteArray()) != Body) throw new Exception("unsupported solver IL");
            var input = new List<CodeInstruction>();
            foreach (var code in instructions) input.Add(Copy(code));
            if (input.Count != 3432) throw new Exception("unexpected solver instruction count");
            var vars = original.GetMethodBody().LocalVariables;
            if (vars[145].LocalType != typeof(int) || vars[146].LocalType != typeof(WaterSource) ||
                vars[148].LocalType != typeof(int) || vars[154].LocalType != typeof(int)) throw new Exception("solver local binding drift");
            var getter = input[2580].operand as MethodInfo;
            if (getter == null || getter.Name != "get_Item" || getter.DeclaringType != typeof(FastList<WaterSource>) || Local(input[2579]) != 145 ||
                input[2951].operand as FieldInfo != typeof(WaterSource).GetField("m_type") || Local(input[2950]) != 146)
                throw new Exception("solver source boundary drift");
            int increment = -1;
            for (int i = 2950; i < input.Count - 3; i++)
                if (Local(input[i]) == 145 && input[i + 1].opcode == OpCodes.Ldc_I4_1 && input[i + 2].opcode == OpCodes.Add && Local(input[i + 3]) == 145)
                { if (increment != -1) throw new Exception("ambiguous source increment"); increment = i; }
            if (increment < 0 || ((MethodInfo)input[3429].operand).Name != "SetCurrentWaterFrame") throw new Exception("source final boundary drift");
            var add = new Dictionary<int, List<CodeInstruction>>();
            add[0] = Call("Begin");
            add[2577] = Call("SourceBefore", 145);
            add[2950] = Call("AfterInput", 145, 146, 154, 148);
            add[increment] = Call("SourceAfter", 145, 146);
            add[3429] = Call("BeforePublish");
            for (int i = 0; i < input.Count; i++) if (input[i].opcode == OpCodes.Ret) add[i] = Call("Leave");
            var inserted = new HashSet<CodeInstruction>();
            var output = new List<CodeInstruction>();
            for (int i = 0; i < input.Count; i++)
            {
                var code = Copy(input[i]);
                List<CodeInstruction> extra;
                if (add.TryGetValue(i, out extra))
                {
                    extra[0].labels.AddRange(code.labels); code.labels.Clear();
                    extra[0].blocks.AddRange(code.blocks); code.blocks.Clear();
                    foreach (var e in extra) { inserted.Add(e); output.Add(e); }
                }
                output.Add(code);
            }
            var stripped = new List<CodeInstruction>();
            var pendingLabels = new List<Label>(); var pendingBlocks = new List<ExceptionBlock>();
            foreach (var code in output)
            {
                if (inserted.Contains(code)) { pendingLabels.AddRange(code.labels); pendingBlocks.AddRange(code.blocks); continue; }
                var copy = Copy(code);
                copy.labels.InsertRange(0, pendingLabels); pendingLabels.Clear();
                copy.blocks.InsertRange(0, pendingBlocks); pendingBlocks.Clear();
                stripped.Add(copy);
            }
            string before = Canonical(input), after = Canonical(stripped);
            if (before != after || stripped.Count != input.Count || pendingLabels.Count != 0 || pendingBlocks.Count != 0)
                throw new Exception("observer inverse-IL/CFG verification failed");
            Proof = new Dictionary<string, object> {
                {"original_il_sha256", Body}, {"original_instructions", input.Count}, {"added_instructions", inserted.Count},
                {"canonical_original", before}, {"canonical_stripped", after}, {"inverse_exact", true},
                {"source_increment_index", increment}, {"injection_sites", new List<int>(add.Keys).ToArray()}
            };
            return output;
        }
    }
}
#endif
