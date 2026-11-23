#include "eventlab_page_group.hpp"
#include <iostream>
using namespace hbf_eventlab;
int main(int argc,char**argv){try{
 unsigned c=std::stoul(argv[1]),stripe=std::stoul(argv[2]);int first=std::stoi(argv[3]);std::uint64_t base=argc>4?std::stoull(argv[4]):0;
 auto plan=EventLabPageGroup::plan(c,stripe,first,c,base);RoundRobinInterleaver map(GlobalByteAddress{base},c,1<<20,stripe);
 std::cout<<"{\"plan\":[";bool comma=false;for(auto&p:plan){auto actual=map.map(GlobalByteAddress{p.global});if(actual.channel!=p.channel||actual.local.value!=p.local)throw std::runtime_error("map disagreement");std::cout<<(comma?",":"")<<"["<<p.global<<","<<p.channel<<","<<p.local<<"]";comma=true;}std::cout<<"]}\n";
 SimulationConfiguration cfg;cfg.device.geometry.host_channels=c;cfg.address.interleave_bytes=stripe;cfg.address.global_base=GlobalByteAddress{base};cfg.host.max_resident_fragments=1024;
 SimulationSession session(resolve_configuration(cfg));VersionedPages pages(c);EventLabPageGroup group(pages);std::optional<EventLabPageGroup::Ack> ack;unsigned completed=0;
 session.set_completion_handler([&](const GlobalCompletion& r){++completed;auto a=group.completion(r);if(a)ack=*a;std::cout<<"{\"completed\":"<<completed<<",\"aggregate\":"<<(ack?"true":"false")<<"}\n";});
 for(unsigned i=0;i<c;i++){pages.begin(i,i);pages.publish(i,true);pages.dirty(i);}
 group.submit(session,10,0,1,std::vector<bool>(c,true));auto r=session.advance_until_yield();if(!r.run.workload_success||!ack||group.deliver(*ack)!="committed")throw std::runtime_error("group failed");
 auto st=session.host().statistics();std::cout<<"{\"accepted\":"<<st.accepted<<",\"responses\":"<<st.responses<<",\"duplicate\":\""<<group.deliver(*ack)<<"\"}\n";
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
