#pragma once
#include "versioned_pages.hpp"
#include "hbf_eventlab/runtime/simulation_session.hpp"
#include <stdexcept>
// Host metadata only: tokens/epochs are NOT extra OCP wire fields. EventLab owns
// command IDs, fragmentation, response matching, credits and host recovery.
class EventLabPageWriteback {
public:
 struct Ack {int page;std::uint64_t token,epoch;bool success;};
 explicit EventLabPageWriteback(VersionedPages& p):pages(p){}
 hbf_eventlab::GlobalRequest prepare(std::uint64_t id,int page,std::uint64_t content,bool copied){
  if(!copied)throw std::invalid_argument("D2H event incomplete");
  if(used.count(id))throw std::invalid_argument("request ID reuse");
  auto result=pages.writeback(page);if(result!="writing")throw std::invalid_argument(result);
  auto w=pages.writebacks.at(page);pending.emplace(id,Ack{page,w.token,w.epoch,false});used.insert(id);
  return {hbf_eventlab::GlobalRequestId{id},hbf_eventlab::Op::Write,hbf_eventlab::GlobalByteAddress{std::uint64_t(page)*4096},4096,content};
 }
 void submit(hbf_eventlab::SimulationSession& session,std::uint64_t id,int page,std::uint64_t content,bool copied){
  if(session.configuration().values().device.geometry.host_channels!=1)throw std::invalid_argument("page bridge requires single host channel");
  auto req=prepare(id,page,content,copied);req.not_before=hbf_eventlab::Tick{session.now().value+1};
  try{session.submit(req);}catch(...){auto a=pending.at(id);a.success=false;pending.erase(id);deliver(a);throw;}
 }
 Ack completion(const hbf_eventlab::GlobalCompletion& c){auto it=pending.find(c.result.id.value);
  if(it==pending.end())throw std::invalid_argument("unknown or duplicate completion");
  if(c.result.state==hbf_eventlab::LogicalResult::Pending)throw std::invalid_argument("nonterminal completion");
  auto ack=it->second;ack.success=c.result.state==hbf_eventlab::LogicalResult::Success;pending.erase(it);return ack;
 }
 std::string deliver(const Ack& a){return pages.written(a.page,a.token,a.epoch,true,a.success);}
private:
 VersionedPages& pages;std::map<std::uint64_t,Ack> pending;std::set<std::uint64_t> used;
};
