#include "eventlab_page_writeback.hpp"
#include <iostream>
using namespace hbf_eventlab;
void require(bool b,int line){if(!b)throw std::runtime_error("writeback contract failed at "+std::to_string(line));}
#define need(x) require((x),__LINE__)
template<class F> void rejects(F f){bool caught=false;try{f();}catch(const std::invalid_argument&){caught=true;}need(caught);}
int main(){try{
 SimulationConfiguration config;config.device.geometry.host_channels=1;config.host.max_resident_fragments=512;
 SimulationSession session(resolve_configuration(config));VersionedPages p;EventLabPageWriteback b(p);
 std::vector<EventLabPageWriteback::Ack> ack;GlobalCompletion last{};
 session.set_completion_handler([&](const GlobalCompletion& c){last=c;ack.push_back(b.completion(c));});
 SimulationConfiguration multi;multi.device.geometry.host_channels=2;SimulationSession unsupported(resolve_configuration(multi));
 rejects([&]{b.submit(unsupported,99,0,1,true);});need(p.writebacks.empty());
 need(p.begin(1,0)=="accepted"&&p.publish(1,true)=="ready"&&p.dirty(0)=="dirty");
 rejects([&]{b.submit(session,10,0,1,false);});need(p.writebacks.empty()&&p.frames[0].dirty);
 b.submit(session,10,0,1,true);session.advance_until_yield();need(ack.size()==1&&b.deliver(ack.back())=="committed");
 need(p.dirty(0)=="dirty");
 // EventLab rejects duplicate fragments in one content version after prepare.
 rejects([&]{b.submit(session,11,0,1,true);});
 need(p.writebacks.empty()&&p.frames[0].dirty&&p.frames[0].state=="ready");
 need(b.deliver(ack.front())=="stale_ack");
 b.submit(session,12,0,2,true);
 rejects([&]{auto c=last;c.result.id=GlobalRequestId{999};b.completion(c);});
 rejects([&]{auto c=last;c.result.id=GlobalRequestId{12};c.result.state=LogicalResult::Pending;b.completion(c);});
 session.advance_until_yield();need(ack.size()==2);
 rejects([&]{b.completion(last);});need(b.deliver(ack.back())=="committed");need(b.deliver(ack.back())=="stale_ack");
 need(p.dirty(0)=="dirty");p.next_write=std::numeric_limits<std::uint64_t>::max();need(p.writeback(0)=="exhausted"&&p.frames[0].state=="ready");
 std::cout<<"PASS registration rollback, incomplete/unknown/duplicate completion, counter exhaustion\n";
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
