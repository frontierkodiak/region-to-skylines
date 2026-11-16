using System;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;

// Exercises the real framework accessor, not a water-solver implementation.
public static class ProfilerProbe
{
    [DllImport("__Internal")]
    static extern void ProbeEnable();

    static long Access(FastList<WaterSource> values)
    {
        long sum = 0;
        for (int i = 0; i < values.m_size; i++)
        {
            WaterSource value = values[i];
            sum += value.m_water;
            value.m_water++;
            values[i] = value;
        }
        return sum;
    }

    public static int Main(string[] args)
    {
        if (args.Length > 0 && args[0] == "metadata")
        {
            MethodInfo method = typeof(WaterSimulation).GetMethod("SimulateWater", BindingFlags.Instance | BindingFlags.NonPublic);
            byte[] il = method.GetMethodBody().GetILAsByteArray();
            using (var hash = new SHA256Managed())
                Console.WriteLine("solver_il_sha256=" + BitConverter.ToString(hash.ComputeHash(il)).Replace("-", "").ToLowerInvariant());
            Console.WriteLine("solver_il_bytes=" + il.Length);
            return 0;
        }
        var values = new FastList<WaterSource>();
        for (int i = 0; i < 290; i++)
            values.Add(new WaterSource { m_water = (uint)i });
        long first = Access(values);
        if (args.Length > 0 && args[0] == "late")
            ProbeEnable();
        long second = Access(values);
        long sum = first + second;
        Console.WriteLine("checksum=" + sum);
        return sum == 84100 ? 0 : 2;
    }
}
