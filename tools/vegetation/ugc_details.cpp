// Read-only Steamworks UGC queries through the already-running Steam client.
// No SteamAPI_Init, game launch, login, subscription or publishing calls.
#include <dlfcn.h>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#pragma pack(push, 4)
struct Details {
    uint64_t id; int32_t result, type; uint32_t creator_app, consumer_app;
    char title[129], description[8000]; uint64_t owner;
    uint32_t created, updated, added; int32_t visibility;
    bool banned, accepted, tags_truncated; char tags[1025];
    uint64_t file, preview; char filename[260]; int32_t bytes, preview_bytes;
    char url[256]; uint32_t votes_up, votes_down; float score; uint32_t children;
    uint64_t total_bytes;
};
struct Completed {
    uint64_t handle; int32_t result; uint32_t returned, total; bool cached;
    char cursor[256];
};
#pragma pack(pop)
static_assert(offsetof(Details, children) == 9760);
static_assert(sizeof(Completed) == 280);

std::string quote(const char* value, size_t cap) {
    std::string out = "\"";
    for (size_t i=0; i<cap && value[i]; i++) {
        unsigned char c = value[i];
        if (c=='"' || c=='\\') {out+='\\'; out+=c;}
        else if(c=='\n') out+="\\n";
        else if(c=='\r') out+="\\r";
        else if(c=='\t') out+="\\t";
        else if(c>=32) out+=c;
    }
    return out+"\"";
}
template<typename T> T fn(void* lib, const char* name) {
    auto p=dlsym(lib,name); if(!p) throw std::runtime_error(name);
    return reinterpret_cast<T>(p);
}
int main(int argc,char** argv) {
    try {
        if(argc<4) throw std::runtime_error("usage: ugc_details steamclient.so libsteam_api.so id...");
        auto clientlib=dlopen(argv[1],RTLD_NOW|RTLD_GLOBAL);
        auto api=dlopen(argv[2],RTLD_NOW|RTLD_GLOBAL);
        if(!clientlib || !api) throw std::runtime_error(dlerror());
        auto factory=fn<void*(*)(const char*,int*)>(clientlib,"CreateInterface");
        void* client=factory("SteamClient023",nullptr);
        if(!client) throw std::runtime_error("SteamClient023 unavailable");
        int pipe=fn<int(*)(void*)>(api,"SteamAPI_ISteamClient_CreateSteamPipe")(client);
        int user=fn<int(*)(void*,int)>(api,"SteamAPI_ISteamClient_ConnectToGlobalUser")(client,pipe);
        if(!pipe || !user) throw std::runtime_error("Existing Steam global user unavailable");
        void* ugc=fn<void*(*)(void*,int,int,const char*)>(api,"SteamAPI_ISteamClient_GetISteamUGC")(client,user,pipe,"STEAMUGC_INTERFACE_VERSION021");
        void* utils=fn<void*(*)(void*,int,const char*)>(api,"SteamAPI_ISteamClient_GetISteamUtils")(client,pipe,"SteamUtils010");
        if(!ugc || !utils) throw std::runtime_error("Expected UGC/Utils version unavailable");
        if(std::string(argv[3])=="entitlement" || std::string(argv[3])=="dlc") {
            void* apps=fn<void*(*)(void*,int,int,const char*)>(api,"SteamAPI_ISteamClient_GetISteamApps")(client,user,pipe,"STEAMAPPS_INTERFACE_VERSION008");
            if(!apps) throw std::runtime_error("SteamApps008 unavailable");
            bool owns=fn<bool(*)(void*,uint32_t)>(api,"SteamAPI_ISteamApps_BIsSubscribedApp")(apps,255710);
            std::cout<<"{\"app\":255710,\"owned\":"<<(owns?"true":"false");
            if(std::string(argv[3])=="dlc") {
                int count=fn<int(*)(void*)>(api,"SteamAPI_ISteamApps_GetDLCCount")(apps);
                std::cout<<",\"build_id\":"<<fn<int(*)(void*)>(api,"SteamAPI_ISteamApps_GetAppBuildId")(apps)<<",\"dlc\":[";
                for(int i=0;i<count;i++) {
                    uint32_t id=0; bool available=false; char name[512]{};
                    if(!fn<bool(*)(void*,int,uint32_t*,bool*,char*,int)>(api,"SteamAPI_ISteamApps_BGetDLCDataByIndex")(apps,i,&id,&available,name,sizeof(name))) throw std::runtime_error("DLC index unavailable");
                    bool licensed=fn<bool(*)(void*,uint32_t)>(api,"SteamAPI_ISteamApps_BIsSubscribedApp")(apps,id);
                    bool installed=fn<bool(*)(void*,uint32_t)>(api,"SteamAPI_ISteamApps_BIsDlcInstalled")(apps,id);
                    if(i)std::cout<<',';
                    std::cout<<"{\"app\":"<<id<<",\"title\":"<<quote(name,sizeof(name))<<",\"available\":"<<(available?"true":"false")<<",\"licensed\":"<<(licensed?"true":"false")<<",\"installed\":"<<(installed?"true":"false")<<'}';
                }
                std::cout<<']';
            }
            std::cout<<'}'<<std::endl;
            fn<void(*)(void*,int,int)>(api,"SteamAPI_ISteamClient_ReleaseUser")(client,pipe,user);
            fn<bool(*)(void*,int)>(api,"SteamAPI_ISteamClient_BReleaseSteamPipe")(client,pipe);
            return 0;
        }
        std::vector<uint64_t> ids;
        bool search=std::string(argv[3]).rfind("search:",0)==0;
        bool tagged=std::string(argv[3]).rfind("tag:",0)==0;
        bool subscriptions=std::string(argv[3])=="subscriptions";
        uint64_t query;
        if(subscriptions) {
            void* account=fn<void*(*)(void*,int,int,const char*)>(api,"SteamAPI_ISteamClient_GetISteamUser")(client,user,pipe,"SteamUser023");
            if(!account) throw std::runtime_error("SteamUser023 unavailable");
            uint64_t steamid=fn<uint64_t(*)(void*)>(api,"SteamAPI_ISteamUser_GetSteamID")(account);
            query=fn<uint64_t(*)(void*,uint32_t,int,int,int,uint32_t,uint32_t,uint32_t)>(api,"SteamAPI_ISteamUGC_CreateQueryUserUGCRequest")(ugc,uint32_t(steamid),6,-1,4,0,255710,argc>4?std::stoul(argv[4]):1);
        } else if(tagged) {
            query=fn<uint64_t(*)(void*,int,int,uint32_t,uint32_t,uint32_t)>(api,"SteamAPI_ISteamUGC_CreateQueryAllUGCRequestPage")(ugc,12,2,0,255710,argc>4?std::stoul(argv[4]):1);
            if(!fn<bool(*)(void*,uint64_t,const char*)>(api,"SteamAPI_ISteamUGC_AddRequiredTag")(ugc,query,argv[3]+4)) throw std::runtime_error("AddRequiredTag failed");
        } else if(search) {
            query=fn<uint64_t(*)(void*,int,int,uint32_t,uint32_t,uint32_t)>(api,"SteamAPI_ISteamUGC_CreateQueryAllUGCRequestPage")(ugc,11,2,0,255710,1);
            if(!fn<bool(*)(void*,uint64_t,const char*)>(api,"SteamAPI_ISteamUGC_SetSearchText")(ugc,query,argv[3]+7)) throw std::runtime_error("SetSearchText failed");
        } else {
            for(int i=3;i<argc;i++) ids.push_back(std::stoull(argv[i]));
            query=fn<uint64_t(*)(void*,uint64_t*,uint32_t)>(api,"SteamAPI_ISteamUGC_CreateQueryUGCDetailsRequest")(ugc,ids.data(),ids.size());
        }
        if(query==UINT64_MAX) throw std::runtime_error("Invalid UGC query");
        if(!fn<bool(*)(void*,uint64_t,bool)>(api,"SteamAPI_ISteamUGC_SetReturnChildren")(ugc,query,true)) throw std::runtime_error("SetReturnChildren failed");
        fn<bool(*)(void*,uint64_t,bool)>(api,"SteamAPI_ISteamUGC_SetReturnLongDescription")(ugc,query,true);
        fn<bool(*)(void*,uint64_t,uint32_t)>(api,"SteamAPI_ISteamUGC_SetAllowCachedResponse")(ugc,query,0);
        auto call=fn<uint64_t(*)(void*,uint64_t)>(api,"SteamAPI_ISteamUGC_SendQueryUGCRequest")(ugc,query);
        auto completed=fn<bool(*)(void*,uint64_t,bool*)>(api,"SteamAPI_ISteamUtils_IsAPICallCompleted");
        bool failed=false; auto end=std::chrono::steady_clock::now()+std::chrono::seconds(90);
        while(!completed(utils,call,&failed)) {
            if(std::chrono::steady_clock::now()>end) throw std::runtime_error("UGC query timeout");
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
        Completed result{};
        if(failed || !fn<bool(*)(void*,uint64_t,void*,int,int,bool*)>(api,"SteamAPI_ISteamUtils_GetAPICallResult")(utils,call,&result,sizeof(result),3401,&failed) || failed || result.result!=1)
            throw std::runtime_error("UGC callback result="+std::to_string(result.result));
        if(result.handle!=query || (!search && !tagged && !subscriptions && result.returned!=ids.size())) throw std::runtime_error("UGC count/handle mismatch");
        std::cerr<<"query total="<<result.total<<" returned="<<result.returned<<" cached="<<result.cached<<std::endl;
        auto details=fn<bool(*)(void*,uint64_t,uint32_t,void*)>(api,"SteamAPI_ISteamUGC_GetQueryUGCResult");
        auto children=fn<bool(*)(void*,uint64_t,uint32_t,uint64_t*,uint32_t)>(api,"SteamAPI_ISteamUGC_GetQueryUGCChildren");
        for(uint32_t i=0;i<result.returned;i++) {
            alignas(8) char buffer[65536]{};
            if(!details(ugc,query,i,buffer)) throw std::runtime_error("GetQueryUGCResult failed");
            auto& d=*reinterpret_cast<Details*>(buffer);
            if((!search && !tagged && !subscriptions && d.id!=ids[i]) || d.children>10000 || (d.result==1 && (d.updated<1167609600 || d.votes_up>100000000 || !std::isfinite(d.score) || d.score<0 || d.score>1))) throw std::runtime_error("Unexpected metadata layout");
            if(subscriptions) {std::cout<<"{\"subscribed_id\":\""<<d.id<<"\"}"<<std::endl;continue;}
            std::vector<uint64_t> child(d.children);
            if(d.result==1 && d.children && !children(ugc,query,i,child.data(),d.children)) throw std::runtime_error("GetQueryUGCChildren failed");
            uint64_t subscribers=0,favourites=0;
            auto statistic=fn<bool(*)(void*,uint64_t,uint32_t,int,uint64_t*)>(api,"SteamAPI_ISteamUGC_GetQueryUGCStatistic");
            bool has_subscribers=statistic(ugc,query,i,0,&subscribers), has_favourites=statistic(ugc,query,i,1,&favourites);
            std::cout<<"{\"file_bytes\":"<<d.bytes<<",\"created\":"<<d.created<<",\"id\":\""<<d.id<<"\",\"result\":"<<d.result<<",\"consumer_app\":"<<d.consumer_app<<",\"visibility\":"<<d.visibility<<",\"banned\":"<<(d.banned?"true":"false")<<",\"owner\":\""<<d.owner<<"\",\"title\":"<<quote(d.title,129)<<",\"tags\":"<<quote(d.tags,1025)<<",\"updated\":"<<d.updated<<",\"subscribers\":"<<(has_subscribers?std::to_string(subscribers):"null")<<",\"favourites\":"<<(has_favourites?std::to_string(favourites):"null")<<",\"description\":"<<quote(d.description,8000)<<",\"votes_up\":"<<d.votes_up<<",\"votes_down\":"<<d.votes_down<<",\"score\":"<<d.score<<",\"children\":[";
            for(size_t j=0;j<child.size();j++) {if(j)std::cout<<",";std::cout<<"\""<<child[j]<<"\"";}
            std::cout<<"]}"<<std::endl;

        }
        fn<bool(*)(void*,uint64_t)>(api,"SteamAPI_ISteamUGC_ReleaseQueryUGCRequest")(ugc,query);
        fn<void(*)(void*,int,int)>(api,"SteamAPI_ISteamClient_ReleaseUser")(client,pipe,user);
        fn<bool(*)(void*,int)>(api,"SteamAPI_ISteamClient_BReleaseSteamPipe")(client,pipe);
    } catch(const std::exception& e) {std::cerr<<e.what()<<std::endl;return 1;}
}
