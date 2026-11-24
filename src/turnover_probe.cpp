// Frozen component experiment, not an ANNS benchmark or hardware calibration.
#include "hbf_eventlab/runtime/simulation_runner.hpp"
#include "hbf_eventlab/policies/round_robin_interleaver.hpp"
#include "hbf_eventlab/policies/reference_address_layout.hpp"
#include <iostream>
#include <functional>
#include <map>
#include <fstream>
#include <cstdlib>
using namespace hbf_eventlab;
int main(int argc,char**argv){try{
 if(argc!=5)throw std::invalid_argument("usage: turnover bytes qd initialized_pages service-v2|payload-v3 < byte-addresses");
 const unsigned bytes=std::stoul(argv[1]),qd=std::stoul(argv[2]),init_pages=std::stoul(argv[3]);const std::string mode=argv[4];
 if((bytes!=256&&bytes!=4096)||!qd||qd>1024||init_pages<1||init_pages>65536||(mode!="service-v2"&&mode!="payload-v3"))throw std::invalid_argument("outside turnover protocol");
 std::vector<unsigned> pages;unsigned p;while(std::cin>>p){if(p>=std::uint64_t(init_pages)*4096||p%bytes)throw std::invalid_argument("invalid address");pages.push_back(p);}
 if(pages.empty())throw std::invalid_argument("empty trace");
 const unsigned mocs=4096;const bool byte_addresses=true,hot=false,dependent=qd==1;
 Geometry g{16,4,16,256,512,0}; // block decomposition is an explicit assumption
 StaticDeviceDescription desc(g,{mocs,8,false,true},{mocs,Tick{100000000},g.block_group_dlus()});
 EventQueue events;ExecutionConfiguration cfg;cfg.media_timing.sense=Tick{2720000};cfg.ucie.accounting=mode=="payload-v3"?LinkAccounting::PayloadV3:LinkAccounting::ServiceV2;cfg.ucie.speed_grade=UcieSpeedGrade::Grade2;cfg.read_dispatch.wait=Tick{0};
 RuntimeProfile profile; DeviceDriver d(desc,cfg,events); if(std::getenv("PROFILE"))d.set_runtime_profile(profile);RoundRobinInterleaver mapping(GlobalByteAddress{0},16,g.channel_bytes(),4096);ReferenceAddressLayout layout(g);
 for(unsigned i=0;i<1024;i++){auto a=mapping.map(GlobalByteAddress{std::uint64_t(i)*4096});auto b=layout.logical_view(a);if(a.channel!=i%16||b.block.bank!=(i/16)%16||b.block.die!=(i/256)%4||b.page!=0)throw std::logic_error("independent mapping check failed");}
 if(g.channel_bytes()*16!=(std::uint64_t{512}<<30))throw std::logic_error("capacity");
 HostConfiguration hc;hc.max_logical_fragments=2097152;hc.writes=WriteCommandMode::Burst4096;HostDriver h(d,events,mapping,hc);if(std::getenv("PROFILE"))h.set_runtime_profile(profile);bool measuring=false;unsigned next=0,done=0,active=0,peak=0;std::uint64_t senses=0,start=0,last=0;
 std::map<std::uint64_t,std::uint64_t> submitted;
 std::function<void()> issue=[&]{auto i=next++;GlobalRequest r{GlobalRequestId{10000+i},Op::Read,GlobalByteAddress{std::uint64_t(pages[i])*(byte_addresses?1:4096)},bytes,0};r.not_before=events.now();r.expected_content=7;submitted[r.id.value]=events.now().value;h.submit(r);++active;peak=std::max(peak,active);};
 h.set_completion_handler([&](const GlobalCompletion& c){if(!measuring)return;if(c.result.state!=LogicalResult::Success)throw std::logic_error("read failed");--active;++done;last=c.at.value;std::cout<<"{\"kind\":\"request\",\"id\":"<<c.result.id.value<<",\"submit_ps\":"<<submitted.at(c.result.id.value)-start<<",\"complete_ps\":"<<c.at.value-start<<"}\n";if(next<pages.size())issue();});
 std::cerr<<"initialization-start\n";h.start_incremental();h.submit({GlobalRequest{GlobalRequestId{1},Op::Write,GlobalByteAddress{0},init_pages*4096,7}});events.run();
 if(!h.workload_success())throw std::logic_error("initialization failed");std::cerr<<"initialization-complete\n";
 if(hot){for(unsigned i=0;i<1024;i++){GlobalRequest r{GlobalRequestId{2000+i},Op::Read,GlobalByteAddress{std::uint64_t(i)*4096},4096,0};r.not_before=events.now();r.expected_content=7;h.submit(r);events.run();}if(!h.workload_success())throw std::logic_error("warmup failed");}
 std::uint64_t digest=14695981039346656037ull,trace_count=0; auto mix=[&](std::uint64_t v){for(int i=0;i<8;++i){digest^=(v>>(i*8))&255;digest*=1099511628211ull;}}; unsigned busy=0,peak_busy=0; d.set_trace([&](const DeviceTrace&t){++trace_count;for(const char* p=t.action;*p;++p){digest^=static_cast<unsigned char>(*p);digest*=1099511628211ull;}mix(t.at.value);mix(t.channel);mix(t.identity);mix(t.target.has_value());if(t.target){mix(t.target->channel);mix(t.target->die);mix(t.target->bank);mix(t.target->block);mix(t.target->page);mix(t.target->byte_offset);}if(std::string(t.action)=="sense-issue"||std::string(t.action)=="sense-finish"){
 std::cout<<"{\"kind\":\"sense\",\"action\":\""<<t.action<<"\",\"id\":"<<t.identity<<",\"ps\":"<<t.at.value-start<<",\"bank\":"<<(t.target->channel*64+t.target->die*16+t.target->bank)<<",\"page\":"<<(t.target->block*256+t.target->page)<<"}\n";
 }if(std::string(t.action)=="sense-issue"){++senses;++busy;peak_busy=std::max(peak_busy,busy);}if(std::string(t.action)=="sense-finish"){if(!busy)throw std::logic_error("unbalanced sense");--busy;}});
 start=events.now().value;measuring=true;for(unsigned i=0;i<std::min<std::size_t>(qd,pages.size());i++)issue();events.run();
 std::cerr<<"peak_busy_banks="<<peak_busy<<" remaining="<<busy<<" mocs="<<mocs<<"\n";
 if(const char* path=std::getenv("PROFILE")){std::ofstream f(path);profile.write_json(f);}
 std::cerr<<"trace_count="<<trace_count<<" trace_digest="<<digest<<"\n";
 if(busy||done!=pages.size()||active||!h.activity().drained()||!d.activity().drained())throw std::logic_error("incomplete or leaked");
 std::cout<<"{\"kind\":\"summary\",\"bytes\":"<<bytes<<",\"qd\":"<<qd<<",\"hot\":"<<hot<<",\"dependent\":"<<dependent<<",\"peak\":"<<peak<<",\"requests\":"<<done<<",\"senses\":"<<senses<<",\"elapsed_ps\":"<<last-start<<",\"useful_bytes\":"<<std::uint64_t(done)*bytes<<"}\n";
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
