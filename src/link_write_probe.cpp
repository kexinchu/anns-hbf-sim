#include "hbf_eventlab/runtime/simulation_runner.hpp"
#include "hbf_eventlab/policies/round_robin_interleaver.hpp"
#include <iostream>
using namespace hbf_eventlab;
int main(){try{
 for(unsigned grade=1;grade<=3;++grade)for(unsigned control:{16u,32u})for(bool payload:{false,true}){
 Geometry g{2,1,2,4,2,1};StaticDeviceDescription desc(g,{256,8,false,true},{256,Tick{100000000},g.block_group_dlus()});EventQueue e;ExecutionConfiguration cfg;
 cfg.ucie.accounting=payload?LinkAccounting::PayloadV3:LinkAccounting::ServiceV2;cfg.ucie.speed_grade=UcieSpeedGrade(grade);cfg.ucie.overhead.request_control_bytes=control;cfg.ucie.overhead.response_control_bytes=control;
 DeviceDriver d(desc,cfg,e);RoundRobinInterleaver map(GlobalByteAddress{0},2,g.channel_bytes(),4096);HostConfiguration hc;hc.writes=WriteCommandMode::Burst4096;HostDriver h(d,e,map,hc);
 std::cout<<"{\"kind\":\"case\",\"grade\":"<<grade<<",\"control\":"<<control<<",\"payload\":"<<payload<<"}\n";
 d.set_trace([&](const DeviceTrace&t){std::cout<<"{\"kind\":\"event\",\"action\":\""<<t.action<<"\",\"id\":"<<t.identity<<",\"channel\":"<<t.channel<<",\"ps\":"<<t.at.value<<"}\n";});
 h.start_incremental();h.submit({GlobalRequest{GlobalRequestId{1},Op::Write,GlobalByteAddress{0},16384,7}});e.run();
 if(!h.workload_success()||!h.activity().drained()||!d.activity().drained())throw std::logic_error("write incomplete");
 }
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
