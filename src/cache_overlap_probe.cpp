// Directed independent-ID cache hit while a different-page sense is pending.
#include "hbf_eventlab/runtime/simulation_runner.hpp"
#include "hbf_eventlab/policies/round_robin_interleaver.hpp"
#include <iostream>
using namespace hbf_eventlab;
int main(){try{for(bool v3:{false,true}){
 Geometry g{1,1,1,4,2,1};StaticDeviceDescription desc(g,{256,8,false,true},{256,Tick{100000000},g.block_group_dlus()});EventQueue e;ExecutionConfiguration cfg;cfg.media_timing.sense=Tick{2720000};cfg.ucie.accounting=v3?LinkAccounting::PayloadV3:LinkAccounting::ServiceV2;cfg.ucie.speed_grade=UcieSpeedGrade::Grade2;cfg.read_dispatch.wait=Tick{0};
 DeviceDriver d(desc,cfg,e);RoundRobinInterleaver map(GlobalByteAddress{0},1,g.channel_bytes(),4096);HostConfiguration hc;hc.writes=WriteCommandMode::Burst4096;HostDriver h(d,e,map,hc);bool measuring=false;std::uint64_t start=0; h.set_completion_handler([&](const GlobalCompletion&c){if(!measuring)return;if(c.result.state!=LogicalResult::Success)throw std::logic_error("read failed");std::cout<<"{\"kind\":\"complete\",\"id\":"<<c.result.id.value<<",\"ps\":"<<c.at.value-start<<"}\n";});h.start_incremental();h.submit({GlobalRequest{GlobalRequestId{1},Op::Write,GlobalByteAddress{0},12288,7}});e.run();
 for(unsigned p=0;p<2;++p){GlobalRequest r{GlobalRequestId{2+p},Op::Read,GlobalByteAddress{p*4096},256,0};r.expected_content=7;r.not_before=e.now();h.submit(r);e.run();}
 if(!h.workload_success())throw std::logic_error("warmup failed");
 start=e.now().value;measuring=true;std::cout<<"{\"kind\":\"case\",\"v3\":"<<v3<<"}\n";
 d.set_trace([&](const DeviceTrace&t){if(std::string(t.action)=="sense-issue"||std::string(t.action)=="sense-finish")std::cout<<"{\"kind\":\"sense\",\"action\":\""<<t.action<<"\",\"page\":"<<t.target->page<<",\"ps\":"<<t.at.value-start<<"}\n";});

 for(unsigned p:{2u,0u,1u}){GlobalRequest r{GlobalRequestId{100+p},Op::Read,GlobalByteAddress{p*4096},256,0};r.expected_content=7;r.not_before=e.now();h.submit(r);}e.run();
 if(!h.workload_success()||!h.activity().drained()||!d.activity().drained())throw std::logic_error("incomplete");
 }}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
