// A process-local CPU feasibility probe of the installed Mono profiler ABI.
// No game is launched, no method is replaced, and no game file is written.
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef void (*method_callback)(void *, void *);
static void *runtime;
static void (*install)(void *, void (*)(void *));
static void (*install_callbacks)(method_callback, method_callback);
static void (*set_events)(int);
static const char *(*method_name)(void *);
static void *(*method_class)(void *);
static const char *(*class_name)(void *);
static int state;
static unsigned count, dropped;
static struct event { const char *klass, *method; int entering; } events[8192];

static void *symbol(const char *name)
{
    void *value = dlsym(runtime, name);
    if (!value) { fprintf(stderr, "missing symbol %s\n", name); exit(3); }
    return value;
}

static void observe(void *profiler, void *method, int entering)
{
    (void)profiler;
    const char *klass = class_name(method_class(method));
    if (strcmp(klass, "ProfilerProbe") && strcmp(klass, "FastList`1")) return;
    if (count >= sizeof(events) / sizeof(events[0])) { dropped++; return; }
    events[count++] = (struct event){klass, method_name(method), entering};
}

static void enter(void *profiler, void *method) { observe(profiler, method, 1); }
static void leave(void *profiler, void *method) { observe(profiler, method, 0); }
static void shutdown_profiler(void *profiler) { (void)profiler; }

void ProbeEnable(void)
{
    if (state) return;
    install(&state, shutdown_profiler);
    install_callbacks(enter, leave);
    // MONO_PROFILE_ENTER_LEAVE from the upstream mono-2-6 profiler header.
    set_events(1 << 12);
    state = 1;
}

int main(int argc, char **argv)
{
    if (argc != 5) { fprintf(stderr, "usage: embed LIBMONO MANAGED EXE MODE\n"); return 2; }
    if (strcmp(argv[4], "off") && strcmp(argv[4], "early") && strcmp(argv[4], "late") &&
        strcmp(argv[4], "early-noinline") && strcmp(argv[4], "metadata")) return 2;
    runtime = dlopen(argv[1], RTLD_NOW | RTLD_GLOBAL);
    if (!runtime) { fprintf(stderr, "%s\n", dlerror()); return 3; }
    install = symbol("mono_profiler_install");
    install_callbacks = symbol("mono_profiler_install_enter_leave");
    set_events = symbol("mono_profiler_set_events");
    method_name = symbol("mono_method_get_name");
    method_class = symbol("mono_method_get_class");
    class_name = symbol("mono_class_get_name");
    void (*assemblies_path)(const char *) = symbol("mono_set_assemblies_path");
    void *(*init)(const char *, const char *) = symbol("mono_jit_init_version");
    void *(*open_assembly)(void *, const char *) = symbol("mono_domain_assembly_open");
    int (*execute)(void *, void *, int, char **) = symbol("mono_jit_exec");
    void (*cleanup)(void *) = symbol("mono_jit_cleanup");
    assemblies_path(argv[2]);
    if (!strcmp(argv[4], "early-noinline")) {
        unsigned (*optimizations)(const char *) = symbol("mono_parse_default_optimizations");
        void (*defaults)(int, unsigned) = symbol("mono_set_defaults");
        defaults(0, optimizations("-inline"));
    }
    if (!strcmp(argv[4], "early") || !strcmp(argv[4], "early-noinline")) ProbeEnable();
    void *domain = init("intake-observer-feasibility", "v2.0.50727");
    if (!domain) return 4;
    void *assembly = open_assembly(domain, argv[3]);
    if (!assembly) return 5;
    char *managed_argv[] = {argv[3], argv[4], NULL};
    int result = execute(domain, assembly, 2, managed_argv);
    printf("events=%u dropped=%u mode=%s result=%d\n", count, dropped, argv[4], result);
    for (unsigned i = 0; i < count; i++)
        printf("%c %s %s\n", events[i].entering ? '+' : '-', events[i].klass, events[i].method);
    cleanup(domain);
    return result;
}
