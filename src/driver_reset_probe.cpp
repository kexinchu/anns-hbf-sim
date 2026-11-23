#include "hbf_eventlab/runtime/simulation_runner.hpp"
#include "hbf_eventlab/policies/round_robin_interleaver.hpp"
#include <algorithm>
#include <array>
#include <iostream>
#ifdef ANNS_CUDA
#include "../gpu/race_backend.h"
#else
namespace {int values[4];bool held[4]{};}
void race_init(){} void race_fill(int f,int v){values[f]=v;}void race_start(int f,bool h){held[f]=h;}
bool race_ready(int f){return !held[f];}void race_open(int f){held[f]=false;}
void race_result(int f,long long* a){for(int k=0;k<32;k++){a[k]=0;for(int j=0;j<32;j++){long long d=values[f]+(k*32+j)%17-3;a[k]+=d*d;}}}
void race_copy(int f,int* a){for(int i=0;i<1024;i++)a[i]=values[f]+i%17;}void race_close(){}
#endif
using namespace hbf_eventlab;
void need(bool b,const char* msg){if(!b)throw std::runtime_error(msg);}
template<class F> void reject(F f){bool yes=false;try{f();}catch(const std::invalid_argument&){yes=true;}need(yes,"negative escaped");}

int main(int argc,char**argv){try{
 std::string phase=argc>1?argv[1]:"program-issue",kind=argc>2?argv[2]:"warm",mutation=argc>3?argv[3]:"";
 Geometry geometry{2,2,1,4,4,1};StaticDeviceDescription description(geometry,{256,8,false,true},{256,Tick{10000000},geometry.block_group_dlus()});
 EventQueue events;events.set_limits({1000000,100000,100000});ExecutionConfiguration config;
 config.core_bytes_per_ns=16;config.core_propagation=Tick{100};
 DeviceDriver device(description,config,events);RoundRobinInterleaver mapping(GlobalByteAddress{0},2,geometry.channel_bytes(),64);
 HostDriver host(device,events,mapping);std::map<std::uint64_t,bool> results;bool armed=false,fired=false;unsigned match=0;race_init();
 auto activity=[&](const char* tag){auto a=device.activity();auto h=host.statistics();std::cout<<"{\"event\":\""<<tag<<"\",\"resources\":["<<a.unsettled_transfers<<','<<a.ingress<<','<<a.in_flight_requests<<','<<a.outstanding<<','<<a.pending_dlus<<','<<a.bank_operations<<','<<a.waiting_erases<<','<<a.window_reads<<','<<a.queued_reads<<','<<a.egress<<','<<a.in_flight_responses<<','<<a.feedback_events<<','<<a.protected_cache_slots<<','<<a.filling_cache_slots<<','<<a.scheduled_driver_events<<','<<a.queued_wakeups<<"],\"handed\":"<<h.handed<<",\"accepted\":"<<h.accepted<<",\"responses\":"<<h.responses<<",\"errors\":"<<h.attempt_errors<<"}\n";};
 host.set_completion_handler([&](const GlobalCompletion& c){results[c.result.id.value]=c.result.state==LogicalResult::Success;if(!results[c.result.id.value])std::cerr<<c.result.id.value<<":"<<c.result.reason<<"\n";std::cout<<"{\"completion\":"<<c.result.id.value<<",\"success\":"<<(results[c.result.id.value]?"true":"false")<<"}\n";});
 device.set_trace([&](const DeviceTrace&t){if(!armed||fired||t.channel!=0||phase!=t.action)return;
  if(phase=="accepted"&&++match<2)return;
  fired=true;activity("at_reset");
  if(kind=="warm")device.reset_csr_write(0,0x14,0x48424602);
  else device.reset_fault(0,kind=="power",kind=="die"?0:-1);
  need(!device.reset_recover(0),"premature recovery");
 });
 reject([&]{device.reset_fault(2);});
 reject([&]{device.reset_fault(0,false,2);});
 reject([&]{device.reset_csr_write(0,0x10,1);});
 reject([&]{device.reset_csr_write(0,0x14,0x48424603);});
 reject([&]{device.reset_csr_write(0,0x14,0x48424604);});
 device.reset_csr_write(0,0x14,0x12345602);
 need(device.reset_csr_read(0,0x10)==1,"bad key changed readiness");
 host.start_incremental();
 auto write=[&](unsigned first,unsigned count,unsigned baseid,unsigned content){std::vector<GlobalRequest> r;
  for(unsigned p=first;p<first+count;p++){GlobalRequest x{GlobalRequestId{baseid+p-first},Op::Write,GlobalByteAddress{p*4096ull},4096,content};x.not_before=Tick{events.now().value+1};r.push_back(x);}host.submit(r);};
 auto read=[&](std::uint64_t address,unsigned id,unsigned content){GlobalRequest x{GlobalRequestId{id},Op::Read,GlobalByteAddress{address},64};x.expected_content=content;x.not_before=Tick{events.now().value+1};host.submit(x);};
 const bool reading=phase=="sense-issue"||phase=="window-release"||phase=="cache-hit";
 if(reading){write(0,4,1,7);events.run();if(phase=="cache-hit"){read(0,9,7);events.run();}}
 armed=true;
 if(reading){read(0,100,7);if(kind=="die"){read(8192,150,7);read(64,151,7);}}else write(0,2,100,7);
 events.run();need(fired,"stage not reached");activity("drained");need(device.activity().drained(),"resource leak");
 for(unsigned ch=0;ch<2;ch++)need(!device.ingress(ch).bytes()&&!device.egress(ch).bytes(),"payload reservation leak");
 if(kind=="power"){bool rejected=false;try{device.reset_csr_read(0,0x10);}catch(const std::invalid_argument&){rejected=true;}need(rejected,"powered-off CSR");}
 else need(device.reset_csr_read(0,0x10)==0,"early RDY");
 events.advance_idle_to(Tick{events.now().value+1001});need(device.reset_recover(0),"recovery blocked");device.reset_csr_write(0,0x0c,1);events.run();
 if(reading&&kind=="die")need(results[150]&&results[151],"physical isolation");
 const bool unknown=device.uncertain({0,LocalByteAddress{0}});
 std::cout<<"{\"unknown\":"<<(unknown?"true":"false")<<",\"ready\":"<<device.reset_csr_read(0,0x10)<<"}\n";
 read(0,200,7);events.run();
 if(mutation=="publish_unknown"&&unknown)results[200]=true;
 need(results.count(200)&&(!unknown||!results[200]),"unknown publication");
 host.acknowledge_reset_loss();
 // Ordered rewrite uses the same Host, actual splitter, erase and program paths.
 write(0,2,300,11);events.run();need(results[300]&&results[301],"rewrite failed");
 need(!device.uncertain({0,LocalByteAddress{0}}),"rewrite retained uncertainty");read(0,400,11);events.run();need(results[400],"rewritten read failed");
 auto physical=device.physical_address({0,LocalByteAddress{0}});auto data=device.media().read(physical);need(data,"missing physical media");int value=int(data->at(0).value%97)+20;
 race_fill(0,value);race_start(0,false);long long scores[32];race_result(0,scores);
 if(mutation=="bad_score")++scores[0];
 std::cout<<"{\"scores\":[";for(int i=0;i<32;i++)std::cout<<(i?",":"")<<scores[i];std::cout<<"],\"physical\":["<<physical.channel<<','<<physical.die<<','<<physical.bank<<','<<physical.block<<','<<physical.page<<"]}\n";
 activity("final");need(device.activity().drained()&&host.activity().drained(),"final leak");
 auto stats=host.statistics();need(stats.handed==stats.accepted&&stats.accepted==stats.responses,"response conservation");race_close();
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';race_close();return 1;}}
