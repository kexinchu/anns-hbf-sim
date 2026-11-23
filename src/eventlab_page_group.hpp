#pragma once
#include "eventlab_page_writeback.hpp"
#include <optional>
#include <vector>
// Whole interleave groups only. A missing neighbor is not implicit zero padding.
class EventLabPageGroup {
public:
 struct Piece {std::uint64_t global;unsigned channel;std::uint64_t local;};
 using Ack=std::vector<EventLabPageWriteback::Ack>;
 explicit EventLabPageGroup(VersionedPages& p):pages(p){}
 static std::vector<Piece> plan(unsigned channels,std::uint64_t stripe,int first,unsigned count,std::uint64_t base=0){
  if(!channels||channels>4||count!=channels||first<0||first%channels||first+count>8||!stripe||stripe>4096||4096%stripe||stripe%64||base%64)
   throw std::invalid_argument("incomplete or unsupported interleave group");
  if(base>std::numeric_limits<std::uint64_t>::max()-std::uint64_t(first+count)*4096)throw std::invalid_argument("address overflow");
  std::vector<Piece> out;
  for(std::uint64_t offset=std::uint64_t(first)*4096;offset<std::uint64_t(first+count)*4096;offset+=64){
   auto s=offset/stripe;out.push_back({base+offset,unsigned(s%channels),(s/channels)*stripe+offset%stripe});
  }return out;
 }
 void submit(hbf_eventlab::SimulationSession& session,std::uint64_t id,int first,std::uint64_t content,const std::vector<bool>& copied){
  const auto& cfg=session.configuration().values();unsigned n=cfg.device.geometry.host_channels;
  plan(n,cfg.address.interleave_bytes,first,copied.size(),cfg.address.global_base.value);
  if(id>std::numeric_limits<std::uint64_t>::max()-n)throw std::invalid_argument("ID overflow");
  for(unsigned i=0;i<n;i++)if(!copied[i]||used.count(id+i))throw std::invalid_argument("incomplete D2H or reused ID");
  // Stage owner transitions; rejected registration cannot strand dirty frames.
  VersionedPages staged=pages;Group g;std::vector<hbf_eventlab::GlobalRequest> requests;
  for(unsigned i=0;i<n;i++){
   int p=first+i;if(staged.writeback(p)!="writing")throw std::invalid_argument("group page not dirty-ready");
   auto w=staged.writebacks.at(p);g.acks.push_back({p,w.token,w.epoch,true});
   hbf_eventlab::GlobalRequest r{hbf_eventlab::GlobalRequestId{id+i},hbf_eventlab::Op::Write,
    hbf_eventlab::GlobalByteAddress{cfg.address.global_base.value+std::uint64_t(p)*4096},4096,content};
   r.not_before=hbf_eventlab::Tick{session.now().value+1};requests.push_back(r);
  }
  session.submit(requests);pages=std::move(staged);groups.emplace(id,std::move(g));
  for(unsigned i=0;i<n;i++){used.insert(id+i);parents.emplace(id+i,id);}
 }
 std::optional<Ack> completion(const hbf_eventlab::GlobalCompletion& c){
  auto it=parents.find(c.result.id.value);if(it==parents.end())throw std::invalid_argument("unknown or duplicate parent");
  if(c.result.state==hbf_eventlab::LogicalResult::Pending)throw std::invalid_argument("nonterminal parent");
  auto group=it->second;auto&g=groups.at(group);parents.erase(it);++g.done;
  g.success &= c.result.state==hbf_eventlab::LogicalResult::Success;
  if(g.done!=g.acks.size())return std::nullopt;
  auto ack=g.acks;for(auto&a:ack)a.success=g.success;groups.erase(group);terminal.emplace(ack.front().token,ack);completed.emplace(group,ack.front().token);return ack;
 }
 // Cancellation revokes host commit permission; accepted wire work still drains.
 bool cancel(std::uint64_t id){
  auto it=groups.find(id);if(it!=groups.end()){it->second.success=false;return true;}
  auto t=completed.find(id);if(t==completed.end())return false;
  auto& a=terminal.at(t->second);
  bool live=false;for(auto&w:a)live |= pages.matches(w.page,w.token,w.epoch);
  if(!live)return false;
  for(auto&w:a)w.success=false;
  return true;
 }
 Ack terminal_ack(std::uint64_t id)const{return terminal.at(completed.at(id));}
 void reset_begin(int die){
  if(die<0||die>=2||resetting.count(die))throw std::invalid_argument("invalid reset scope");
  resetting.insert(die);pages.block(die,true);
  for(auto&[id,g]:groups)for(auto&a:g.acks)if(a.page/4==die){g.success=false;break;}
  for(auto&[token,ack]:terminal){bool affected=false;for(auto&a:ack)affected |= a.page/4==die;
   if(affected)for(auto&a:ack)a.success=false;
  }
 }
 std::string reset_finish(hbf_eventlab::SimulationSession& session,int die,bool ready){
  if(!resetting.count(die))return "invalid";
  // Outstanding parents must drain even after cancellation; no synthetic ACKs.
  for(auto&[id,g]:groups)for(auto&a:g.acks)if(a.page/4==die)return "draining";
  for(auto&[p,w]:pages.writebacks)if(p/4==die)return "draining";
  auto stats=session.host().statistics();
  if(stats.accepted!=stats.responses||session.next_event_time())return "draining";
  if(!ready)return "not_ready";
  pages.block(die,false);
  // Clean cached versions are invalidated, pinned consumers retain their frame.
  // Dirty backup remains authoritative until explicit ordered replay succeeds.
  for(int p=die*4;p<die*4+4;p++){bool dirty=false;for(auto&f:pages.frames)if(f.page==p&&f.dirty)dirty=true;
   if(!dirty)pages.refresh(p);
  }
  resetting.erase(die);return "resumed";
 }
 std::string deliver(const Ack& ack){
  if(ack.empty())return "stale_ack";
  auto record=terminal.find(ack.front().token);if(record==terminal.end()||record->second.size()!=ack.size())return "stale_ack";
  for(unsigned i=0;i<ack.size();i++){auto&a=ack[i];auto&b=record->second[i];if(a.page!=b.page||a.token!=b.token||a.epoch!=b.epoch||a.success!=b.success)return "stale_ack";}
  std::set<int> unique;for(auto&a:ack)if(!unique.insert(a.page).second||!pages.matches(a.page,a.token,a.epoch))return "stale_ack";
  for(auto&a:ack)pages.written(a.page,a.token,a.epoch,true,a.success);
  return ack.front().success?"committed":"failed";
 }
private:
 struct Group {Ack acks;unsigned done=0;bool success=true;};
 std::map<std::uint64_t,Ack> terminal;
 std::map<std::uint64_t,std::uint64_t> completed;std::set<int> resetting;
 VersionedPages& pages;std::map<std::uint64_t,Group> groups;std::map<std::uint64_t,std::uint64_t> parents;std::set<std::uint64_t> used;
};
