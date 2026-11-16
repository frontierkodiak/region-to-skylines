// Synthetic callback fixture, not a native simulation or qualification.
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Runtime.Serialization;
using Cs1Harness;
public static class TraceFixture
{
    static void Set(WaterSimulation water,string name,object value)
    {var field=typeof(WaterSimulation).GetField(name,BindingFlags.Instance|BindingFlags.NonPublic);field.SetValue(water,field.FieldType.IsInstanceOfType(value)?value:Convert.ChangeType(value,field.FieldType));}
    public static int Main(string[] args)
    {
        var request=(Dictionary<string,object>)Json.Parse("{\"sources\":[1],\"cells\":[[16,0]],\"max_steps\":1,\"binding\":{\"synthetic\":true},\"controls\":[{\"type\":1,\"target\":6400,\"input\":[0,0,0],\"output\":[0,0,0],\"input_rate\":100,\"output_rate\":0}]}");
        var bad=(Dictionary<string,object>)Json.Parse(Json.Write(request));bad["cells"]=Json.Parse("[[1,0]]");
        try {TraceRecorder.Arm(bad);return 2;}catch(Exception error){Console.WriteLine("unaligned_cell_rejected="+error.Message);}
        TraceRecorder.Arm(request);
        var water=(WaterSimulation)FormatterServices.GetUninitializedObject(typeof(WaterSimulation));
        var sources=new FastList<WaterSource>();
        var source=new WaterSource();source.m_type=1;source.m_target=6400;source.m_inputRate=100;sources.Add(source);
        typeof(WaterSimulation).GetField("m_waterSources").SetValue(water,sources);
        var floor=new ushort[1081*1081];for(int i=0;i<floor.Length;i++)floor[i]=6400;
        var buffers=new[]{new WaterSimulation.Cell[floor.Length],new WaterSimulation.Cell[floor.Length]};
        Set(water,"m_heightBuffer",floor);Set(water,"m_waterBuffers",buffers);
        Set(water,"m_waterFrameIndex",0u);Set(water,"m_waterFrameIndex2",0u);Set(water,"m_simulationFrameIndex",0u);Set(water,"m_stepIndex",7u);
        TraceRecorder.Begin(water);TraceRecorder.SourceBefore(water,0);TraceRecorder.AfterInput(water,0,source,0,0);
        TraceRecorder.SourceAfter(water,0,source);TraceRecorder.BeforePublish(water);TraceRecorder.Leave(water);TraceRecorder.Stop();
        var result=TraceRecorder.Export(Environment.GetEnvironmentVariable("CS1_TRACE_FIXTURE_OUTPUT"),true);
        Console.WriteLine(Json.Write(result));
        for(int i=0;i<floor.Length;i++)if(floor[i]!=6400 || buffers[0][i].m_height!=0 || buffers[1][i].m_height!=0)return 3;
        if(sources.m_size!=1 || sources[0].m_inputRate!=100 || sources[0].m_water!=0)return 4;
        Console.WriteLine("synthetic_callback_fixture_native_arrays_unchanged=True");
        return (bool)result["complete"] && Convert.ToInt32(result["nodes"])==9 ? 0 : 5;
    }
}
