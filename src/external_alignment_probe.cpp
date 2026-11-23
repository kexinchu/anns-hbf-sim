// Parameter propagation and architectural microtraces, NOT calibrated performance.
#include "hbf_eventlab/runtime/simulation_runner.hpp"
#include "hbf_eventlab/policies/round_robin_interleaver.hpp"
#include <iostream>
#include <vector>
using namespace hbf_eventlab;
int main(){try{
 for(unsigned grade=1;grade<=3;grade++){const auto&p=ucie_speed_profile(UcieSpeedGrade(grade));std::cout<<"{\"kind\":\"profile\",\"grade\":"<<grade<<",\"GBps_per_module\":"<<p.effective_gbytes_per_second<<",\"max_modules\":"<<p.max_modules<<",\"cube_GBps\":"<<p.effective_gbytes_per_second*p.max_modules<<"}\n";}
 for(unsigned profile=0;profile<3;profile++)for(unsigned mode=0;mode<4;mode++){
  Geometry g{1,1,2,4,2,1};StaticDeviceDescription desc(g,{256,8,false,true},{256,Tick{100000000},g.block_group_dlus()});EventQueue events;ExecutionConfiguration cfg;
  if(profile)cfg.media_timing.sense=Tick{profile==1?2720000u:4000000u};
  cfg.ucie.speed_grade=UcieSpeedGrade::Grade2;cfg.read_dispatch.wait=Tick{0};
  DeviceDriver d(desc,cfg,events);RoundRobinInterleaver map(GlobalByteAddress{0},1,g.channel_bytes(),4096);HostDriver h(d,events,map);h.start_incremental();
  h.submit({GlobalRequest{GlobalRequestId{1},Op::Write,GlobalByteAddress{0},16384,7}});events.run();
  std::vector<std::uint64_t> starts,ends;
  d.set_trace([&](const DeviceTrace&t){if(std::string(t.action)=="sense-issue")starts.push_back(t.at.value);if(std::string(t.action)=="sense-finish")ends.push_back(t.at.value);});
  auto begin=events.now().value;std::vector<GlobalRequest> input{{GlobalRequestId{2},Op::Read,GlobalByteAddress{0},256,0}};
  if(mode)input.push_back({GlobalRequestId{3},Op::Read,GlobalByteAddress{mode==1?256u:mode==2?4096u:8192u},256,0});
  for(auto&r:input){r.not_before=events.now();r.expected_content=7;}
  h.submit(input);events.run();
  if(h.statistics().logical_failed||h.results().size()!=1+input.size()||!h.activity().drained())throw std::runtime_error("logical completion failed");
  for(const auto&[id,result]:h.results())if(result.state!=LogicalResult::Success)throw std::runtime_error("parent completion failed");
  std::cout<<"{\"kind\":\"microtrace\",\"profile\":"<<profile<<",\"mode\":"<<mode<<",\"sense_parameter_ps\":"<<cfg.media_timing.sense.value<<",\"useful_bytes\":"<<256*input.size()<<",\"senses\":"<<starts.size()<<",\"elapsed_ps\":"<<events.now().value-begin<<",\"drained\":"<<(d.activity().drained()?"true":"false")<<",\"starts_ps\":[";
  for(unsigned i=0;i<starts.size();i++)std::cout<<(i?",":"")<<starts[i]-begin;
  std::cout<<"],\"finishes_ps\":[";for(unsigned i=0;i<ends.size();i++)std::cout<<(i?",":"")<<ends[i]-begin;std::cout<<"]}\n";
 }
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
