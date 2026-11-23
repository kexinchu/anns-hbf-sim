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

int main(int argc,char**argv){bool cuda=false;try{
 unsigned type=argc>1?std::stoul(argv[1]):2;unsigned order=argc>2?std::stoul(argv[2]):0;
 std::string mutation=argc>3?argv[3]:"";bool writing=argc>4&&std::string(argv[4])=="write";
 Geometry g{2,2,1,4,4,1};StaticDeviceDescription desc(g,{256,8,false,true},{256,Tick{10000000},g.block_group_dlus()});
 EventQueue events;ExecutionConfiguration config;config.core_bytes_per_ns=16;config.core_propagation=Tick{100};
 DeviceDriver d(desc,config,events);RoundRobinInterleaver mapping(GlobalByteAddress{0},2,g.channel_bytes(),64);HostDriver host(d,events,mapping);
 host.start_incremental();std::vector<GlobalRequest> seed;
 for(unsigned i=0;i<2;i++)seed.push_back({GlobalRequestId{i+1},Op::Write,GlobalByteAddress{i*4096ull},4096,7});
 host.submit(seed);events.run();need(d.activity().drained(),"seed leak");
 race_init();cuda=true;d.hold_external_responses(true);
 LocalTransaction range_test{HostCommand{CommandId{42},Op::Read,{0,LocalByteAddress{0}},64,42},{}};
 reject([&]{d.try_submit_external(0,0,range_test,[](const auto&){});});
 range_test.command.id=CommandId{16384};reject([&]{d.try_submit_external(0,1,range_test,[](const auto&){});});
 std::uint64_t generation=0,last_generation=0;
 unsigned old_calls=0,new_calls=0,other_calls=0;std::uint64_t value=0;bool old_success=false;
 auto submit=[&](unsigned command,unsigned ch,unsigned addr,DeviceDriver::Receiver receiver){
  const bool write=writing&&ch==0;std::vector<DataToken> bytes;
  if(write)for(unsigned i=0;i<64;i++)bytes.push_back(DataToken{101+addr/64+i});
  auto result=d.try_submit_external(d.reset_domains(ch)[0],++generation,{HostCommand{CommandId{command},write?Op::Write:Op::Read,{ch,LocalByteAddress{write?0:addr}},write?4096u:64u,42},bytes},std::move(receiver));
  need(result.has_value(),"fresh request epoch rejected");const auto& h=*result;
  need(h.disposition==HandoffDisposition::Taken,"submission failed");last_generation=generation;return h.attempt->value;
 };
 auto oldid=submit(42,0,0,[&](const DeliveredResponse& r){++old_calls;old_success=!r.reset_invalidated;});events.run();
 auto packets=d.take_external_packets();need(packets.size()==1,"old packet missing");auto old=packets[0];
 bool dup=false;try{submit(42,0,0,[](const auto&){});}catch(const std::logic_error&){dup=true;}need(dup,"live ID reused");
 d.reset_csr_write(0,0x14,0x48424600|type);
 auto domains=d.reset_domains(0);
 std::cout<<"{\"type\":"<<type<<",\"domains\":["<<domains[0]<<','<<domains[1]<<','<<domains[2]<<','<<domains[3]<<"],\"en\":"<<d.reset_csr_read(0,0x0c)<<",\"ready\":"<<d.reset_csr_read(0,0x10)<<"}\n";
 auto blocked=d.try_submit({HostCommand{CommandId{44},Op::Read,{0,LocalByteAddress{64}},64,42},{}},[](const auto&){});
 need(blocked.disposition==HandoffDisposition::NotTaken,"reset admission");
 need(!d.receive_external(old),"packet while reset");
 bool recovered=false;std::size_t banks=0;
 d.set_trace([&](const DeviceTrace&t){if(t.channel==1&&std::string(t.action)=="sense-issue")
  events.schedule_at(Tick{events.now().value+1001},EventPhase::Arrival,[&]{banks=d.activity().bank_operations;recovered=d.reset_recover(0);});
 });
 submit(42,1,0,[&](const DeliveredResponse& r){need(!r.reset_invalidated,"other channel reset");++other_calls;});
 while(!recovered)need(events.run_next(),"recovery stalled");
 need(banks>0,"recovery avoided active other channel");
 if(type==2)d.reset_csr_write(0,0x0c,1);
 events.run();
 std::cout<<"{\"recovered\":true,\"other_banks\":"<<banks<<",\"old_external_packets\":1}\n";
 auto replay=d.take_external_packets();
 for(auto& p:replay){auto ch=std::visit([](auto& r){return r.channel;},p.delivery.response);
  if(ch==0){need(type==0,"unexpected replay");need(!d.receive_external(old),"stale replay accepted");need(d.receive_external(p),"fresh replay rejected");need(!d.receive_external(p),"duplicate replay");}
  else need(d.receive_external(p),"other response rejected");
 }
 need(old_calls==1&&other_calls==1,"reset callback conservation");
 auto newid=submit(42,0,64,[&](const DeliveredResponse& r){++new_calls;need(!r.reset_invalidated,"new request invalidated");value=writing?d.media().read(d.physical_address({0,LocalByteAddress{0}}))->at(0).value:std::get<ReadResponse>(r.response).data->value;});auto new_generation=last_generation;events.run();
 auto current=d.take_external_packets();need(current.size()==1,"new packet missing");auto fresh=current[0];need(oldid!=newid,"attempt reused");
 LocalTransaction stale_request{HostCommand{CommandId{42},writing?Op::Write:Op::Read,{0,LocalByteAddress{0}},writing?4096u:64u,42},{}};
 if(writing)stale_request.data.assign(64,DataToken{999});
 const auto before=d.statistics().handoffs;
 auto stale_handoff=d.try_submit_external(old.epoch,1,stale_request,[](const auto&){throw std::logic_error("stale request callback");});
 bool stale_request_accepted=stale_handoff.has_value();
 need(d.statistics().handoffs==before,"stale request acquired resources");
 auto forged=old;forged.delivery.attempt=fresh.delivery.attempt;
 auto wrong=fresh;std::visit([](auto&r){r.command=CommandId{43};},wrong.delivery.response);need(!d.receive_external(wrong),"wrong command accepted");
 wrong=fresh;std::visit([](auto&r){r.channel=1;},wrong.delivery.response);need(!d.receive_external(wrong),"wrong channel accepted");
 bool stale=false;
 if(order==0){stale=d.receive_external(old);need(!d.receive_external(forged),"old epoch aliased new attempt");}
 else if(order==1){need(!d.receive_external(forged),"old epoch aliased new attempt");stale=d.receive_external(old);}
 need(new_calls==0,"old response completed new request");
 need(d.receive_external(fresh),"new packet rejected");
 if(order==2)stale=d.receive_external(old);
 need(!d.receive_external(fresh),"duplicate accepted");need(!d.receive_external(old),"late old accepted");
 // Same connection, same command ID, different attempt: generation must still isolate.
 submit(42,0,128,[&](const DeliveredResponse&r){++new_calls;need(!r.reset_invalidated,"reuse failed");});events.run();
 need(!d.try_submit_external(fresh.epoch,new_generation,stale_request,[](const auto&){}).has_value(),"same-epoch stale request accepted");
 auto reuse=d.take_external_packets();need(reuse.size()==1,"reuse packet");need(!d.receive_external(fresh),"same-epoch stale accepted");need(d.receive_external(reuse[0]),"same-epoch new rejected");
 need(!d.try_submit_external(old.epoch,1,stale_request,[](const auto&){}).has_value(),"late request after new completion");
 if(mutation=="accept_old_request")stale_request_accepted=true;
 if(mutation=="accept_stale")stale=true;
 if(mutation=="alias_callback")++new_calls;
 race_fill(0,int(value%97)+20);race_start(0,false);long long scores[32];race_result(0,scores);if(mutation=="bad_score")++scores[0];
 events.run();
 std::cout<<"{\"old_success\":"<<(old_success?"true":"false")<<",\"old_calls\":"<<old_calls<<",\"new_calls\":"<<new_calls<<",\"other_calls\":"<<other_calls<<",\"stale_accepted\":"<<(stale?"true":"false")<<",\"stale_request_accepted\":"<<(stale_request_accepted?"true":"false")<<",\"drained\":"<<(d.activity().drained()?"true":"false")<<",\"external_pending\":"<<d.external_pending()<<",\"scores\":[";
 for(int i=0;i<32;i++)std::cout<<(i?",":"")<<scores[i];std::cout<<"]}\n";
 race_close();cuda=false;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';if(cuda)race_close();return 1;}}
