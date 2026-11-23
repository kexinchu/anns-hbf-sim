#pragma once
#include <vector>
#include <stdexcept>
#include <map>
#include <set>
#include <string>
#include <cstdint>
#include <limits>
// Generation-checked finite frame owner. GPU event readiness is supplied only by
// the CUDA adapter. No timing estimate may authorize publication/reclamation.
class VersionedPages {
public:
 struct Frame {int page=-1;unsigned generation=0;std::string state="free";unsigned pins=0;bool dirty=false;};
 struct Fill {int frame;unsigned generation;};
 struct Write {std::uint64_t token,epoch;int frame;unsigned generation;};
 std::map<int,Write> writebacks;std::map<int,std::uint64_t> epochs;std::uint64_t next_write=0;
 bool matches(int page,std::uint64_t token,std::uint64_t epoch)const{auto i=writebacks.find(page);return i!=writebacks.end()&&i->second.token==token&&i->second.epoch==epoch;}
 struct Lease {int frame;unsigned generation;};
 explicit VersionedPages(unsigned n=2):frames(n){if(!n||n>8)throw std::invalid_argument("frame capacity");}
 std::vector<Frame> frames;std::map<int,unsigned> versions;
 std::map<int,Fill> fills;std::map<int,Lease> leases;std::set<int> blocked;
 unsigned version(int page){auto [i,_]=versions.emplace(page,1);return i->second;}
 int resident(int page)const{for(int i=0;i<int(frames.size());++i)if(frames[i].page==page&&(frames[i].state=="ready"||frames[i].state=="writeback"))return i;return -1;}
 std::string begin(int ticket,int page){
  if(ticket<0||page<0||page>=8||fills.count(ticket))return "invalid";
  if(blocked.count(page/4))return "blocked";
  unsigned g=version(page);
  for(auto&f:frames)if(f.page==page&&f.generation==g&&f.state!="free")return "busy";
  for(int i=0;i<int(frames.size());++i)if(frames[i].state=="free"){
   frames[i]={page,g,"filling",0,false};fills.emplace(ticket,Fill{i,g});return "accepted";}
  return "full";
 }
 std::string publish(int ticket,bool event_ready){auto it=fills.find(ticket);if(it==fills.end())return "invalid";
  if(!event_ready)return "pending";auto&f=frames[it->second.frame];
  bool stale=f.generation!=version(f.page);fills.erase(it);
  if(stale){f=Frame{};return "stale";}
  f.state="ready";return "ready";
 }
 std::string refresh(int page){if(page<0||page>=8)return "invalid";if(blocked.count(page/4))return "blocked";
  for(auto&f:frames)if(f.page==page&&(f.state=="writeback"||f.dirty))return "busy";
  ++versions.try_emplace(page,1).first->second;
  for(auto&f:frames)if(f.page==page&&f.state!="free"){
   if(f.state=="filling"||f.state=="retired_fill")f.state="retired_fill";
   else if(f.pins)f.state="retired";else f=Frame{};
  }return "refreshed";
 }
 std::string acquire(int lease,int page){if(lease<0||page<0||page>=8||leases.count(lease))return "invalid";
  if(blocked.count(page/4))return "blocked";
  for(int i=0;i<int(frames.size());++i){auto&f=frames[i];if(f.page==page&&f.generation==version(page)&&f.state=="ready"){
    ++f.pins;leases.emplace(lease,Lease{i,f.generation});return "acquired";}}
  return "unavailable";
 }
 std::string release(int lease,bool event_ready){auto it=leases.find(lease);if(it==leases.end())return "invalid";
  if(!event_ready)return "pending";auto&f=frames[it->second.frame];--f.pins;leases.erase(it);
  if(!f.pins&&f.state=="retired")f=Frame{};return "released";
 }
 std::string dirty(int page){for(auto&f:frames)if(f.page==page&&f.state=="ready"){
   if(blocked.count(page/4))return "blocked";if(f.pins)return "busy";f.dirty=true;return "dirty";}return "unavailable";}
 std::string evict(int page){for(auto&f:frames)if(f.page==page&&f.state=="ready"){
   if(f.pins||f.dirty)return "busy";f=Frame{};return "evicted";}return "unavailable";}
 std::string writeback(int page){for(auto&f:frames)if(f.page==page&&f.state=="ready"){
   if(blocked.count(page/4))return "blocked";if(f.pins)return "busy";if(!f.dirty)return "clean";if(next_write==std::numeric_limits<std::uint64_t>::max()||epochs[page]==std::numeric_limits<std::uint64_t>::max())return "exhausted";f.state="writeback";writebacks[page]={++next_write,++epochs[page],int(&f-frames.data()),f.generation};return "writing";}return "unavailable";}
 std::string written(int page,std::uint64_t token,std::uint64_t epoch,bool ready,bool success){
  if(!matches(page,token,epoch))return "stale_ack";
  auto w=writebacks.at(page);auto&f=frames[w.frame];
  if(f.page!=page||f.generation!=w.generation||f.state!="writeback")return "stale_ack";
  if(!ready)return "pending";writebacks.erase(page);f.state="ready";if(success)f.dirty=false;
  return success?"committed":"failed";
 }
 std::string block(int die,bool value){if(die<0||die>=2)return "invalid";if(value)blocked.insert(die);else blocked.erase(die);return value?"blocked":"resumed";}
};
