// Frozen component experiment, not an ANNS benchmark or hardware calibration.
#include "hbf_eventlab/runtime/simulation_runner.hpp"
#include "hbf_eventlab/policies/round_robin_interleaver.hpp"
#include "hbf_eventlab/policies/reference_address_layout.hpp"
#include <iostream>
#include <functional>
#include <map>
using namespace hbf_eventlab;
int main(int argc,char**argv){try{
 if(argc!=5)throw std::invalid_argument("usage: probe bytes qd hot dependent < page_ids");
 const unsigned bytes=std::stoul(argv[1]),qd=std::stoul(argv[2]);const bool hot=std::stoul(argv[3]),dependent=std::stoul(argv[4]);
 if((bytes!=256&&bytes!=4096)||!qd||qd>1024)throw std::invalid_argument("outside frozen grid");
 std::vector<unsigned> pages;unsigned p;while(std::cin>>p){if(p>=1024)throw std::invalid_argument("page outside footprint");pages.push_back(p);}
 if(pages.size()!=1024)throw std::invalid_argument("expected 1024 requests");
 Geometry g{16,4,16,256,512,0}; // block decomposition is an explicit assumption
 StaticDeviceDescription desc(g,{256,8,false,true},{256,Tick{100000000},g.block_group_dlus()});
 EventQueue events;ExecutionConfiguration cfg;cfg.media_timing.sense=Tick{2720000};cfg.ucie.speed_grade=UcieSpeedGrade::Grade2;cfg.read_dispatch.wait=Tick{0};
 DeviceDriver d(desc,cfg,events);RoundRobinInterleaver mapping(GlobalByteAddress{0},16,g.channel_bytes(),4096);ReferenceAddressLayout layout(g);
 for(unsigned i=0;i<1024;i++){auto a=mapping.map(GlobalByteAddress{std::uint64_t(i)*4096});auto b=layout.logical_view(a);if(a.channel!=i%16||b.block.bank!=(i/16)%16||b.block.die!=(i/256)%4||b.page!=0)throw std::logic_error("independent mapping check failed");}
 if(g.channel_bytes()*16!=(std::uint64_t{512}<<30))throw std::logic_error("capacity");
 HostConfiguration hc;hc.writes=WriteCommandMode::Burst4096;HostDriver h(d,events,mapping,hc);bool measuring=false;unsigned next=0,done=0,active=0,peak=0;std::uint64_t senses=0,start=0,last=0;
 std::map<std::uint64_t,std::uint64_t> submitted;
 std::function<void()> issue=[&]{auto i=next++;GlobalRequest r{GlobalRequestId{10000+i},Op::Read,GlobalByteAddress{std::uint64_t(pages[i])*4096},bytes,0};r.not_before=events.now();r.expected_content=7;submitted[r.id.value]=events.now().value;h.submit(r);++active;peak=std::max(peak,active);};
 h.set_completion_handler([&](const GlobalCompletion& c){if(!measuring)return;if(c.result.state!=LogicalResult::Success)throw std::logic_error("read failed");--active;++done;last=c.at.value;std::cout<<"{\"kind\":\"request\",\"id\":"<<c.result.id.value<<",\"submit_ps\":"<<submitted.at(c.result.id.value)-start<<",\"complete_ps\":"<<c.at.value-start<<"}\n";if(next<pages.size())issue();});
 std::cerr<<"initialization-start\n";h.start_incremental();h.submit({GlobalRequest{GlobalRequestId{1},Op::Write,GlobalByteAddress{0},1024*4096,7}});events.run();
 if(!h.workload_success())throw std::logic_error("initialization failed");std::cerr<<"initialization-complete\n";
 if(hot){for(unsigned i=0;i<1024;i++){GlobalRequest r{GlobalRequestId{2000+i},Op::Read,GlobalByteAddress{std::uint64_t(i)*4096},4096,0};r.not_before=events.now();r.expected_content=7;h.submit(r);events.run();}if(!h.workload_success())throw std::logic_error("warmup failed");}
 d.set_trace([&](const DeviceTrace&t){if(std::string(t.action)=="sense-issue")++senses;});
 start=events.now().value;measuring=true;for(unsigned i=0;i<(dependent?1:qd);i++)issue();events.run();
 if(done!=pages.size()||active||!h.activity().drained()||!d.activity().drained())throw std::logic_error("incomplete or leaked");
 std::cout<<"{\"kind\":\"summary\",\"bytes\":"<<bytes<<",\"qd\":"<<qd<<",\"hot\":"<<hot<<",\"dependent\":"<<dependent<<",\"peak\":"<<peak<<",\"requests\":"<<done<<",\"senses\":"<<senses<<",\"elapsed_ps\":"<<last-start<<",\"useful_bytes\":"<<std::uint64_t(done)*bytes<<"}\n";
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
