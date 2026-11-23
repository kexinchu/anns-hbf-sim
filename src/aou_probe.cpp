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

#include "aou_link.hpp"
#include <iomanip>
int main(int argc,char**argv){bool gpu=false;try{
 if(argc>1&&std::string(argv[1])=="decode"){
  std::string hex;while(std::cin>>hex){try{aou::Bytes bytes;if(hex.size()%2)throw std::invalid_argument("hex length");for(std::size_t i=0;i<hex.size();i+=2)bytes.push_back(std::stoul(hex.substr(i,2),nullptr,16));auto m=aou::decode(bytes);std::cout<<m.kind<<' '<<m.rp<<' '<<m.id<<' '<<m.user<<' '<<m.sync<<' '<<m.count<<' '<<m.status<<' '<<m.address<<'\n';}catch(const std::exception&){std::cout<<"rejected\n";}}return 0;
 }
 if(argc>1&&std::string(argv[1])=="codec"){
  unsigned kind,rp,id,user,sync,count,status;std::uint64_t address;
  while(std::cin>>kind>>rp>>id>>user>>sync>>count>>status>>address){try{aou::Message m;m.kind=kind;m.rp=rp;m.id=id;m.user=user;m.sync=sync;m.count=count;m.status=status;m.address=address;for(unsigned i=0;i<64;i++)m.data[i]=i;
   auto b=aou::encode(m);auto r=aou::decode(b);for(auto v:b)std::cout<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(v);std::cout<<std::dec<<"\n";
  }catch(const std::invalid_argument&){std::cout<<"rejected\n";}}return 0;
 }
 unsigned type=argc>1?std::stoul(argv[1]):2;std::string mutation=argc>2?argv[2]:"";
 Geometry g{2,2,1,4,4,1};StaticDeviceDescription desc(g,{256,8,false,true},{256,Tick{10000000},g.block_group_dlus()});EventQueue events;ExecutionConfiguration cfg;cfg.core_bytes_per_ns=16;
 DeviceDriver d(desc,cfg,events);RoundRobinInterleaver mapping(GlobalByteAddress{0},2,g.channel_bytes(),64);HostDriver host(d,events,mapping);host.start_incremental();
 host.submit({GlobalRequest{GlobalRequestId{1},Op::Write,GlobalByteAddress{0},4096,7},GlobalRequest{GlobalRequestId{2},Op::Write,GlobalByteAddress{4096},4096,7}});events.run();
 aou::Link negative;negative.activate_ack(false);need(negative.state==aou::Link::Error,"invalid activation ack");negative.teardown();negative.activate_request(true);negative.activate_request(false);negative.activate_ack(true);need(negative.state!=aou::Link::Enabled,"one-sided ack");negative.activate_ack(false);
 aou::Message no_credit;no_credit.kind=2;need(!negative.send(no_credit,[](const auto&){}),"sent without credits");negative.grant(9);need(negative.credits==8,"credits failed to saturate");need(negative.send(no_credit,[](const auto&){}),"credited send");need(!negative.deactivate(),"deactivated outstanding request");bool early=false;try{negative.release_ids();}catch(const std::logic_error&){early=true;}need(early,"premature ID release");
 aou::Link link;auto boot=[&]{link.activate_request(true);link.activate_request(false);link.activate_ack(true);need(link.state==aou::Link::Activate,"early enable");link.activate_ack(false);link.grant(8);};boot();
 race_init();gpu=true;unsigned completions=0;std::uint64_t value=0,command=1000;
 auto consume=[&](const aou::Message&m){++completions;value=0;for(unsigned i=0;i<8;i++)value=(value<<8)|m.data[i];};
 auto pump=[&]{while(!link.tx.empty()){auto wire=std::move(link.tx.front());link.tx.pop_front();auto m=aou::decode(wire);
  auto h=d.try_submit({HostCommand{CommandId{++command},Op::Read,{0,LocalByteAddress{m.address}},64,std::uint16_t(m.id)},{}},[&,id=m.id](const DeliveredResponse&r){if(r.reset_invalidated)return;auto data=std::get<ReadResponse>(r.response).data;need(data.has_value(),"missing data");aou::Message out;out.kind=4;out.id=id;out.sync=255;for(unsigned i=0;i<8;i++)out.data[i]=data->value>>(56-8*i);link.rx.push_back(aou::encode(out));});need(h.disposition==HandoffDisposition::Taken,"driver backpressure");events.run();}
 };
 aou::Message req;req.kind=2;req.id=42;req.sync=255;need(link.send(req,consume),"first send");pump();auto old=link.rx.front();
 // Old bytes exist in the owned receive FIFO at reset; no hidden envelope.
 link.fail();d.reset_csr_write(0,0x14,0x48424600|type);need(!link.receive(old),"ERROR received");need(!link.send(req,consume),"ERROR sent");link.teardown();need(link.rx.empty()&&link.tx.empty(),"FIFO flush");
 events.run();events.advance_idle_to(Tick{events.now().value+1001});need(d.reset_recover(0),"device recovery");d.reset_csr_write(0,0x0c,1);link.release_ids();boot();
 // SYNC wraps to 0; it does not identify requests or cause rejection.
 aou::Message sync;sync.kind=0;sync.sync=0;sync.count=0;need(link.receive(aou::encode(sync)),"SYNC observation");
 req.address=64;req.sync=0;need(link.send(req,consume),"ID reuse after closure");pump();auto fresh=link.rx.front();link.rx.pop_front();need(link.receive(fresh),"new response");need(!link.receive(fresh),"duplicate response");need(!link.send(req,consume),"unsafe immediate ID reuse");
 need(link.deactivate(),"orderly deactivation");link.disabled_ack();link.release_ids();boot();need(link.send(req,consume),"new activation reuse");
 // Deliberately violate reliable lower-layer isolation: an old identical-ID byte
 // packet cannot be distinguished by AoU. Preserve this counterexample, not a pass claim.
 bool ambiguous=link.receive(old);need(ambiguous,"expected indistinguishability witness");
 link.fail();link.teardown();
 // GPU consumes the known fresh response, not the counterexample's stale payload.
 auto decoded=aou::decode(fresh);value=0;for(unsigned i=0;i<8;i++)value=(value<<8)|decoded.data[i];race_fill(0,int(value%97)+20);race_start(0,false);long long score[32];race_result(0,score);
 if(mutation=="bad_score")++score[0];if(mutation=="pretend_sync_epoch")ambiguous=false;
 std::cout<<"{\"type\":"<<type<<",\"callbacks\":"<<completions<<",\"ambiguous_old_bytes\":"<<(ambiguous?"true":"false")<<",\"performance_ready\":false,\"drained\":"<<(d.activity().drained()?"true":"false")<<",\"scores\":[";for(int i=0;i<32;i++)std::cout<<(i?",":"")<<score[i];std::cout<<"]}\n";race_close();gpu=false;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';if(gpu)race_close();return 1;}}
