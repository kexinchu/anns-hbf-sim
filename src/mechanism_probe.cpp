// Public Host -> Device -> media/cache/core/link path. No private-state injection.
#include "hbf_eventlab/runtime/simulation_runner.hpp"
#include "hbf_eventlab/policies/round_robin_interleaver.hpp"
#include <iostream>
#include <vector>
using namespace hbf_eventlab;
int main(int argc,char**argv){try{
 if(argc!=3&&argc!=4)throw std::runtime_error("sense_ps core_bytes_per_ns required");
 if(argc==4&&std::string(argv[3])!="fifo"&&std::string(argv[3])!="lru")throw std::invalid_argument("cache policy must be fifo or lru");
 Geometry g{1,1,2,4,2,1};StaticDeviceDescription desc(g,{256,8,false,true},{256,Tick{100000000},g.block_group_dlus()});
 EventQueue events;ExecutionConfiguration cfg;cfg.media_timing.sense=Tick{std::stoull(argv[1])};cfg.core_bytes_per_ns=std::stoull(argv[2]);cfg.cache_hit_recency=argc==4&&std::string(argv[3])=="lru";cfg.read_dispatch.wait=Tick{0};
 std::vector<std::array<std::uint64_t,5>> transfers;
 cfg.core_observer=[&](ChannelId c,std::uint32_t k,Tick a,Tick b,Tick e){transfers.push_back({c,k,a.value,b.value,e.value});};
 DeviceDriver d(desc,cfg,events);RoundRobinInterleaver map(GlobalByteAddress{},1,g.channel_bytes(),4096);HostDriver h(d,events,map);h.start_incremental();
 h.submit({GlobalRequest{GlobalRequestId{1},Op::Write,GlobalByteAddress{},24576,7}});events.run();
 // Capture actual reservations and media events; Python supplies the reference.
 std::vector<DeviceTrace> trace;
 d.set_trace([&](const DeviceTrace&t){if(std::string(t.action)=="sense-issue"||std::string(t.action)=="sense-finish"||std::string(t.action)=="sense-media-finish")trace.push_back(t);});
 unsigned n,phase=0;std::uint64_t id=2;
 while(std::cin>>n){if(!n||n>16)throw std::runtime_error("bad phase size");
  std::vector<GlobalRequest> input;std::vector<unsigned> pages;const auto begin=events.now().value;trace.clear();transfers.clear();auto senses=d.statistics().senses;
  for(unsigned i=0,p;i<n;i++){if(!(std::cin>>p)||p>=6)throw std::runtime_error("bad page");pages.push_back(p);GlobalRequest r{GlobalRequestId{id++},Op::Read,GlobalByteAddress{p*4096ull},256,0};r.expected_content=7;r.not_before=events.now();input.push_back(r);}
  h.submit(input);events.run();
  if(!h.workload_success()||!h.activity().drained()||!d.activity().drained())throw std::runtime_error("data/result/resource failure");
  std::cout<<"{\"phase\":"<<phase++<<",\"elapsed_ps\":"<<events.now().value-begin<<",\"senses\":"<<d.statistics().senses-senses<<",\"events\":[";
  bool first=true;for(auto&t:trace){if(!first)std::cout<<',';first=false;std::cout<<"[\""<<t.action<<"\","<<t.at.value-begin<<','<<t.identity<<','<<t.target->bank<<']';}std::cout<<"],\"core\":[";first=true;for(auto x:transfers){if(!first)std::cout<<',';first=false;std::cout<<'['<<x[0]<<','<<x[1]<<','<<x[2]-begin<<','<<x[3]-begin<<','<<x[4]-begin<<']';}std::cout<<"]}\n";
 }
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
