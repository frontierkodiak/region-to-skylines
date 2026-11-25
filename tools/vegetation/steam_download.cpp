// Authorized downloads through the existing client; no subscribe or publish API.
#include <dlfcn.h>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <set>
#include <stdexcept>
#include <thread>

template <typename T> T symbol(void* library, const char* name) {
    auto value = dlsym(library, name);
    if (!value) throw std::runtime_error(name);
    return reinterpret_cast<T>(value);
}
struct Callback { int user, callback; unsigned char* data; int bytes; };
#pragma pack(push, 4)
struct DownloadResult { uint32_t app; uint64_t id; int result; };
#pragma pack(pop)

int main(int argc, char** argv) {
    void (*shutdown)() = nullptr;
    try {
        if (argc < 4) throw std::runtime_error("usage: steam_download steamclient.so libsteam_api.so id...");
        setenv("SteamAppId", "255710", 1);
        setenv("SteamGameId", "255710", 1);
        if (!dlopen(argv[1], RTLD_NOW | RTLD_GLOBAL)) throw std::runtime_error(dlerror());
        auto api = dlopen(argv[2], RTLD_NOW | RTLD_GLOBAL);
        if (!api) throw std::runtime_error(dlerror());
        if (!symbol<bool (*)()>(api, "SteamAPI_InitSafe")()) throw std::runtime_error("Existing client initialization failed");
        shutdown = symbol<void (*)()>(api, "SteamAPI_Shutdown");
        auto ugc = symbol<void* (*)()>(api, "SteamAPI_SteamUGC_v021")();
        auto pipe = symbol<int (*)()>(api, "SteamAPI_GetHSteamPipe")();
        symbol<void (*)()>(api, "SteamAPI_ManualDispatch_Init")();
        auto frame = symbol<void (*)(int)>(api, "SteamAPI_ManualDispatch_RunFrame");
        auto next = symbol<bool (*)(int, Callback*)>(api, "SteamAPI_ManualDispatch_GetNextCallback");
        auto release = symbol<void (*)(int)>(api, "SteamAPI_ManualDispatch_FreeLastCallback");
        auto download = symbol<bool (*)(void*, uint64_t, bool)>(api, "SteamAPI_ISteamUGC_DownloadItem");
        auto overall_end = std::chrono::steady_clock::now() + std::chrono::minutes(30);
        for (int start = 3; start < argc; start += 16) {
            std::set<uint64_t> pending;
            for (int i = start; i < argc && i < start + 16; ++i) {
                uint64_t id = std::stoull(argv[i]);
                bool queued = download(ugc, id, false);
                if (queued) pending.insert(id);
                std::cout << "{\"id\":\"" << id << "\",\"queued\":" << (queued ? "true" : "false") << "}" << std::endl;
            }
            while (!pending.empty() && std::chrono::steady_clock::now() < overall_end) {
                frame(pipe);
                Callback callback{};
                while (next(pipe, &callback)) {
                    if (callback.callback == 3406 && callback.bytes == sizeof(DownloadResult)) {
                        DownloadResult result{};
                        std::memcpy(&result, callback.data, sizeof(result));
                        if (result.app == 255710 && pending.erase(result.id)) {
                            std::cout << "{\"id\":\"" << result.id << "\",\"result\":" << result.result << "}" << std::endl;
                        }
                    }
                    release(pipe);
                }
                std::this_thread::sleep_for(std::chrono::milliseconds(100));
            }
            if (!pending.empty()) throw std::runtime_error("Download callback timeout");
        }
        shutdown();
        return 0;
    } catch (const std::exception& error) {
        if (shutdown) shutdown();
        std::cerr << error.what() << std::endl;
        return 1;
    }
}
