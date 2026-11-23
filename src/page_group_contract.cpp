#include "eventlab_page_group.hpp"
#include <iostream>
using namespace hbf_eventlab;
void need(bool b){if(!b)throw std::runtime_error("group contract failed");}
template<class F>void rejects(F f){bool yes=false;try{f();}catch(const std::invalid_argument&){yes=true;}need(yes);}
int main(){try{
 SimulationConfiguration cfg;cfg.device.geometry.host_channels=2;cfg.host.max_resident_fragments=512;
 SimulationSession session(resolve_configuration(cfg));VersionedPages p;EventLabPageGroup group(p);
 for(int i=0;i<2;i++){need(p.begin(i,i)=="accepted"&&p.publish(i,true)=="ready");need(p.dirty(i)=="dirty");}
 rejects([&]{group.submit(session,10,0,1,{true});});need(p.next_write==0&&p.writebacks.empty());
 rejects([&]{group.submit(session,10,0,1,{true,false});});need(p.next_write==0);
 group.submit(session,10,0,1,{true,true});
 // Unit-level terminal injection, separate from actual device recovery tests.
 GlobalCompletion c{};c.result.id=GlobalRequestId{10};c.result.state=LogicalResult::Pending;rejects([&]{group.completion(c);});
 c.result.state=LogicalResult::Failed;need(!group.completion(c));rejects([&]{group.completion(c);});
 c.result.id=GlobalRequestId{999};rejects([&]{group.completion(c);});
 c.result.id=GlobalRequestId{11};c.result.state=LogicalResult::Success;auto ack=group.completion(c);need(ack.has_value());
 auto partial=*ack;partial.pop_back();need(group.deliver(partial)=="stale_ack");
 auto forged=*ack;for(auto&a:forged)a.success=true;need(group.deliver(forged)=="stale_ack");
 need(p.frames[0].state=="writeback"&&p.frames[1].state=="writeback");
 need(group.deliver(*ack)=="failed");for(auto&f:p.frames)need(f.dirty&&f.state=="ready");
 need(group.deliver(*ack)=="stale_ack");
 rejects([&]{group.submit(session,10,0,2,{true,true});});need(p.writebacks.empty());
 std::cout<<"PASS partial/forged/duplicate completion, terminal failure retains group, atomic preflight\n";
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
