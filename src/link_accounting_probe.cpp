// Service-equivalent accounting diagnostics; NOT a wire/flit implementation.
#include "hbf_eventlab/runtime/simulation_runner.hpp"
#include "hbf_eventlab/policies/round_robin_interleaver.hpp"
#include <iostream>
using namespace hbf_eventlab;
int main(){try{
 for(unsigned grade=1;grade<=3;++grade)for(unsigned control:{16u,32u})for(unsigned fixed:{0u,100u}){
 Geometry g{2,1,2,4,2,1};StaticDeviceDescription desc(g,{256,8,false,true},{256,Tick{100000000},g.block_group_dlus()});EventQueue e;ExecutionConfiguration cfg;cfg.ucie.speed_grade=UcieSpeedGrade(grade);cfg.ucie.overhead.response_control_bytes=control;cfg.ucie.overhead.request_fixed_latency=Tick{fixed};cfg.ucie.overhead.response_fixed_latency=Tick{fixed};cfg.read_dispatch.wait=Tick{0};
 DeviceDriver d(desc,cfg,e);RoundRobinInterleaver map(GlobalByteAddress{0},2,g.channel_bytes(),4096);HostConfiguration hc;hc.writes=WriteCommandMode::Burst4096;HostDriver h(d,e,map,hc);h.start_incremental();h.submit({GlobalRequest{GlobalRequestId{1},Op::Write,GlobalByteAddress{0},8192,7}});e.run();
 GlobalRequest warm{GlobalRequestId{2},Op::Read,GlobalByteAddress{0},8192,0};warm.not_before=e.now();warm.expected_content=7;h.submit(warm);e.run();if(!h.workload_success())throw std::runtime_error("warmup failed");
 auto start=e.now().value;std::cout<<"{\"kind\":\"case\",\"grade\":"<<grade<<",\"response_control\":"<<control<<",\"fixed_ps\":"<<fixed<<"}\n";
 d.set_trace([&](const DeviceTrace&t){std::cout<<"{\"kind\":\"event\",\"action\":\""<<t.action<<"\",\"id\":"<<t.identity<<",\"channel\":"<<t.channel<<",\"ps\":"<<t.at.value-start<<"}\n";});
 GlobalRequest read{GlobalRequestId{3},Op::Read,GlobalByteAddress{0},8192,0};read.not_before=e.now();read.expected_content=7;h.submit(read);e.run();if(!h.workload_success()||!d.activity().drained()||!h.activity().drained())throw std::runtime_error("read failed or leaked");std::cout<<"{\"kind\":\"done\",\"elapsed_ps\":"<<e.now().value-start<<"}\n";
 }
}catch(const std::exception&ex){std::cerr<<ex.what()<<'\n';return 1;}}
