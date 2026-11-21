using System;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using UnityEngine;

namespace Cs1Harness
{
    // Work that spans many frames (an import, a save, a load) runs as a job: an iterator the
    // host steps once per frame, so ops stay quick and the CLI polls `job`. One job at a time.
    public sealed class Job
    {
        public int Id;
        public string Kind;
        public string State = "running"; // running, done, failed
        public string Step = "";
        public string Error;
        public float Started = Time.realtimeSinceStartup;
        public float Ended;
        public readonly List<object> Log = new List<object>();
        public readonly Dictionary<string, object> Result = new Dictionary<string, object>();
        internal IEnumerator Body;
        internal Stack<IEnumerator> Stack = new Stack<IEnumerator>();

        public void Note(string step)
        {
            Step = step;
            Log.Add(Host.Obj("t", Math.Round(Time.realtimeSinceStartup - Started, 2), "step", step));
            Debug.Log("[Cs1Harness] job " + Id + " " + Kind + ": " + step);
        }
    }

    public static class Jobs
    {
        static Job current;
        static int nextId = 1;

        public static Job Start(string kind, Func<Job, IEnumerator> body)
        {
            if (current != null && current.State == "running")
                throw new Exception("job " + current.Id + " (" + current.Kind + ") is still running; poll `job`");
            var job = new Job { Id = nextId++, Kind = kind };
            job.Body = body(job);
            job.Stack.Push(job.Body);
            current = job;
            return job;
        }

        public static Dictionary<string, object> Status()
        {
            if (current == null)
                return Host.Obj("job", null);
            var j = current;
            return Host.Obj(
                "job", j.Id,
                "kind", j.Kind,
                "state", j.State,
                "step", j.Step,
                "error", j.Error,
                "seconds", Math.Round((j.State == "running" ? Time.realtimeSinceStartup : j.Ended) - j.Started, 2),
                "log", j.Log,
                "result", j.Result
            );
        }

        // Steps nested iterators (yield return another IEnumerator runs it to completion first).
        public static void Tick()
        {
            var j = current;
            if (j == null || j.State != "running")
                return;
            try
            {
                while (j.Stack.Count > 0)
                {
                    var top = j.Stack.Peek();
                    if (!top.MoveNext())
                    {
                        j.Stack.Pop();
                        continue;
                    }
                    var inner = top.Current as IEnumerator;
                    if (inner != null)
                    {
                        j.Stack.Push(inner);
                        continue;
                    }
                    return; // yielded null: next frame
                }
                j.State = "done";
                j.Ended = Time.realtimeSinceStartup;
                j.Note("done");
            }
            catch (Exception e)
            {
                j.State = "failed";
                j.Error = e.GetType().Name + ": " + e.Message;
                j.Ended = Time.realtimeSinceStartup;
                j.Log.Add(Host.Obj("t", Math.Round(j.Ended - j.Started, 2), "error", j.Error, "at", e.StackTrace));
                Debug.LogError("[Cs1Harness] job " + j.Id + " failed: " + e);
            }
        }

        // Wait until cond() holds, a frame at a time; fail after `seconds` of real time.
        public static IEnumerator Until(Func<bool> cond, float seconds, string what)
        {
            float deadline = Time.realtimeSinceStartup + seconds;
            while (!cond())
            {
                if (Time.realtimeSinceStartup > deadline)
                    throw new TimeoutException("timed out after " + seconds + " s waiting for " + what);
                yield return null;
            }
        }

        public static IEnumerator Frames(int n)
        {
            for (int i = 0; i < n; i++)
                yield return null;
        }
    }

    // Private members of game classes, by name. Every use names what it reads, so a game
    // update that renames one fails with the member's name rather than a null reference.
    public static class Reflect
    {
        const BindingFlags All = BindingFlags.Instance | BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;

        static FieldInfo Field(Type t, string name)
        {
            for (var x = t; x != null; x = x.BaseType)
            {
                var f = x.GetField(name, All);
                if (f != null)
                    return f;
            }
            throw new MissingFieldException(t.Name, name);
        }

        public static T Get<T>(object o, string field)
        {
            return (T)Field(o.GetType(), field).GetValue(o);
        }

        public static T GetStatic<T>(Type t, string field)
        {
            return (T)Field(t, field).GetValue(null);
        }

        public static void Set(object o, string field, object value)
        {
            Field(o.GetType(), field).SetValue(o, value);
        }

        public static object Call(object o, string method, params object[] args)
        {
            var types = new Type[args.Length];
            for (int i = 0; i < args.Length; i++)
                types[i] = args[i].GetType();
            return Invoke(o.GetType(), o, method, types, args);
        }

        public static object CallStatic(Type t, string method, params object[] args)
        {
            var types = new Type[args.Length];
            for (int i = 0; i < args.Length; i++)
                types[i] = args[i].GetType();
            return Invoke(t, null, method, types, args);
        }

        static object Invoke(Type t, object o, string method, Type[] types, object[] args)
        {
            for (var x = t; x != null; x = x.BaseType)
            {
                var m = x.GetMethod(method, All, null, types, null);
                if (m != null)
                    return m.Invoke(o, args);
            }
            throw new MissingMethodException(t.Name, method);
        }
    }
}
